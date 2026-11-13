"""0902持久上下文：复用已校验结果，不调用模型，不从日志或备注猜结构。"""
from __future__ import annotations

import copy
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from jsonschema import Draft202012Validator

SCHEMA_VERSION = "1.0"
INPUT_HEADER_FIELDS = ("id", "file_id", "table_type", "specialty_name", "project_section")
INPUT_ROW_FIELDS = ("id", "file_id", "orderno", "serial_no", "equipment_tag", "description",
                    "nominal_size", "unit", "quantity", "unit_weight", "total_weight", "remark")


def json_text(value):
    """Decimal按十进制文本保留精度；拒绝非有限数及未知对象，不隐式转float。"""
    def encode(item):
        if isinstance(item, Decimal) and item.is_finite():
            return str(item)
        raise ValueError("快照包含不能安全序列化的值")
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"), default=encode)


def json_value(value):
    """形成独立JSON值，防止后续构建或数据库适配修改原始解析结果。"""
    return json.loads(json_text(value))


def input_source(header, raw_rows):
    """只保存本文件可定位、可复核的输入字段；原始顺序不使用UUID或界面排序。"""
    return {"header": {k: header.get(k) for k in INPUT_HEADER_FIELDS},
            "raw_rows": [{k: row.get(k) for k in INPUT_ROW_FIELDS} for row in raw_rows]}


def fingerprint(value):
    """为冻结输入及结果生成内容指纹，不用指纹冒充数据库输入修订号。"""
    return hashlib.sha256(json_text(value).encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def snapshot_validator():
    """按本地受控格式合同校验，Schema不从模型或数据库正文加载。"""
    path = Path(__file__).with_name("schemas") / "file-analysis-snapshot.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _scope_context(file_id, raw, rows, r):
    """仅保存显式project祖先；逻辑表边界尚无可靠输入时如实记UNKNOWN。"""
    cursor, visited = r, set()
    while cursor is not None:
        if cursor in visited or cursor not in rows:
            raise ValueError("快照范围祖先引用非法")
        visited.add(cursor)
        if rows[cursor]["role"] == "project":
            source = raw[cursor]
            return {"logical_table_id": None, "logical_table_status": "UNKNOWN",
                    "subproject_instance_id": str(uuid5(NAMESPACE_URL, f"smart-cost:project:{file_id}:{source['id']}")),
                    "subproject_status": "KNOWN", "scope_title": source.get("description"),
                    "scope_source_raw_ids": [source["id"]]}
        cursor = rows[cursor]["parent"]
    return {"logical_table_id": None, "logical_table_status": "UNKNOWN",
            "subproject_instance_id": None, "subproject_status": "UNKNOWN",
            "scope_title": None, "scope_source_raw_ids": []}


def build_snapshot(file, input_context, analysis, built, task, config):
    """在成套合并完成后构建快照；工程量和映射使用同一次构建生成的ID。"""
    source = input_source(input_context["header"], input_context["raw_rows"])
    if input_source(input_context["header"], analysis["raw_rows"]) != source:
        raise ValueError("解析使用的原始行与冻结输入不一致")
    raw = dict(enumerate(analysis["raw_rows"], 1))
    rows = {row["r"]: row for row in analysis["structure"]["rows"]}
    if len(rows) != len(analysis["structure"]["rows"]) or set(rows) != set(raw):
        raise ValueError("快照结构没有完整覆盖输入")
    mapping = copy.deepcopy(built.row_map)
    for entry in mapping:
        entry["source_order"] = raw[entry["r"]]["orderno"]
        entry["role"] = rows[entry["r"]]["role"]
    items_by_id = {item["id"]: item for item in built.items}
    contexts, unresolved = {}, []
    for entry in mapping:
        r, item_id = entry["r"], entry["item_id"]
        if item_id is None:
            continue
        item = items_by_id[item_id]
        source_rows = [m["raw_id"] for m in mapping if m["item_id"] == item_id or m.get("merged_into") == item_id]
        refs = {r, *rows[r].get("inherit", [])}
        refs.update(rows[r][k] for k in ("parent", "qty_from", "unit_from", "quantity_parent", "quantity_basis_ref")
                    if rows[r].get(k) is not None)
        if entry.get("quantity_count_source") is not None:
            refs.add(entry["quantity_count_source"])
        contexts[item_id] = {
            "primary_raw_id": raw[r]["id"], "source_order": raw[r]["orderno"],
            "source_raw_ids": source_rows, "evidence_raw_ids": [raw[k]["id"] for k in sorted(refs)],
            "original_role": rows[r]["role"], "original_parent": rows[r]["parent"],
            "scope": _scope_context(file["id"], raw, rows, r),
            "measurement": {k: entry.get(k) for k in ("raw_quantity", "raw_unit", "quantity_basis", "qty_from",
                "unit_from", "quantity_parent", "quantity_basis_ref", "quantity_count_source", "divisor", "multiplier_total", "quantity_reason")},
            "calculated_quantity": item["quantity"], "physical_quantity": item["quantity"],
            "supply_scope": {"status": "UNKNOWN"},
        }
        missing = [field for field, value in (("quantity", item["quantity"]), ("classification", item["type"]),
                                              ("cbs", item["project_cbs_id"])) if value is None]
        if rows[r]["role"] == "pending" or missing:
            unresolved.append({"r": r, "file_item_id": item_id, "role": rows[r]["role"], "missing_fields": missing})
    snapshot = json_value({
        "schema_version": SCHEMA_VERSION,
        "provenance": {"file_id": file["id"], "project_id": task["project_id"], "batch_id": task["batch_id"],
                       "task_id": task["id"], "request_id": task.get("request_id"),
                       "input_revision": input_context["input_revision"], "input_fingerprint": fingerprint(source),
                       "classification_rules_fingerprint": fingerprint(config.classification_rules),
                       "model": {k: config.model.get(k) for k in ("provider", "model")}},
        "source": source, "structure": analysis["structure"], "row_map": mapping,
        "items": built.items, "item_contexts": contexts,
        "cbs": {k: v for k, v in analysis.items() if k not in {"raw_rows", "structure"}},
        "unresolved": unresolved,
        "scope_completeness": {"status": "UNKNOWN", "missing_fields": ["logical_table_boundaries"],
                               "reason": "当前0901没有完整逻辑表边界合同；保留标题、说明和祖先链，不按CBS或整文件猜范围"},
    })
    validate_snapshot(snapshot, file, task, built.items)
    return snapshot


def validate_snapshot(snapshot, file, task, items):
    """核验来源、全行覆盖及最终ID归属；UNKNOWN允许保存，悬空或跨文件引用拒绝。"""
    snapshot_validator().validate(snapshot)
    provenance = snapshot["provenance"]
    for key, expected in (("file_id", file["id"]), ("task_id", task["id"]),
                          ("project_id", task["project_id"]), ("batch_id", task["batch_id"]),
                          ("request_id", task.get("request_id"))):
        if provenance[key] != expected:
            raise ValueError("快照归属或请求身份不一致")
    if snapshot["items"] != json_value(items):
        raise ValueError("快照实物与本次构建结果不一致")
    source = snapshot["source"]
    if provenance["input_fingerprint"] != fingerprint(source):
        raise ValueError("快照输入指纹不一致")
    raw = dict(enumerate(source["raw_rows"], 1))
    raw_ids = {row["id"] for row in raw.values()}
    orders = [row["orderno"] for row in raw.values()]
    if not raw or len(raw_ids) != len(raw) or any(type(n) is not int for n in orders) or orders != sorted(set(orders)):
        raise ValueError("快照原行身份或顺序无效")
    if source["header"].get("file_id") not in {None, file["id"]} or any(
            row.get("file_id") not in {None, file["id"]} for row in raw.values()):
        raise ValueError("快照引用了其他文件的输入")
    rows = snapshot["structure"]["rows"]
    decisions = {row["r"]: row for row in rows}
    row_ids = [row["r"] for row in rows]
    mapping = snapshot["row_map"]
    if len(row_ids) != len(raw) or set(row_ids) != set(raw) or len(mapping) != len(raw) or {m["r"] for m in mapping} != set(raw):
        raise ValueError("快照遗漏或重复结构/来源行")
    item_ids = {item["id"] for item in items}
    emitted = [m["item_id"] for m in mapping if m["item_id"] is not None]
    if len(item_ids) != len(items) or len(emitted) != len(item_ids) or set(emitted) != item_ids:
        raise ValueError("快照来源映射未唯一覆盖最终实物")
    for entry in mapping:
        row = raw[entry["r"]]
        if (entry["raw_id"] != row["id"] or entry["source_order"] != row["orderno"]
                or entry["role"] != decisions[entry["r"]]["role"]):
            raise ValueError("快照原始顺序或源行映射不一致")
        if entry.get("merged_into") is not None and (entry["item_id"] is not None or entry["merged_into"] not in item_ids):
            raise ValueError("合并组件仍独立出表或目标已被删除")
    if set(snapshot["item_contexts"]) != item_ids:
        raise ValueError("快照实物上下文覆盖不完整")
    by_item = {entry["item_id"]: entry for entry in mapping if entry["item_id"] is not None}
    for item in items:
        context = snapshot["item_contexts"][item["id"]]
        primary = by_item[item["id"]]
        expected_sources = [m["raw_id"] for m in mapping if m["item_id"] == item["id"] or m.get("merged_into") == item["id"]]
        if (context["primary_raw_id"] != primary["raw_id"] or context["source_order"] != primary["source_order"]
                or context["source_raw_ids"] != expected_sources):
            raise ValueError("快照主来源或来源集合与最终实物映射不一致")
        if item["file_id"] != file["id"] or context["primary_raw_id"] not in raw_ids or not (
                set(context["source_raw_ids"]) | set(context["evidence_raw_ids"])) <= raw_ids:
            raise ValueError("快照实物引用了不存在的源行")
        if context["physical_quantity"] != json_value(item["quantity"]):
            raise ValueError("快照实物量与工程量结果不一致")


def finalize_snapshot(snapshot, persisted_items, result_revision):
    """以数据库实际持久化精度固定历史结果；不重新乘倍率或修改计算原值。"""
    final = copy.deepcopy(snapshot)
    expected = {item["id"]: item for item in final["items"]}
    actual = {item["id"]: item for item in json_value(persisted_items)}
    if set(expected) != set(actual):
        raise ValueError("已写入实物与快照ID集合不一致")
    for item_id, item in actual.items():
        for key, value in expected[item_id].items():
            if key == "quantity" and value is not None:
                if item[key] is None or Decimal(str(item[key])) != Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP):
                    raise ValueError("数据库实物量超出约定持久化精度")
            elif item[key] != value:
                raise ValueError("数据库实物值与本次构建结果不一致")
        final["item_contexts"][item_id]["physical_quantity"] = item["quantity"]
    final["items"] = [actual[item["id"]] for item in final["items"]]
    final["provenance"]["result_revision"] = result_revision
    final["provenance"]["items_fingerprint"] = fingerprint(sorted(final["items"], key=lambda x: x["id"]))
    return final
