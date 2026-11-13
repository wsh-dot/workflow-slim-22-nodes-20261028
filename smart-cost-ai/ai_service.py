"""结构判断、CBS 两轮匹配及工程量节点转换；模型调用不访问业务数据库。"""
from __future__ import annotations

import copy
import http.client
import json
import re
import time
from collections import Counter
from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import uuid4

from jsonschema import Draft202012Validator, ValidationError

from config import Config, Trace
from chunking import packet_for_chunk, plan_chunks
from classification import (validate_classification_evidence, compile_confirmed_rules,
                            confirmed_classification, apply_confirmed_classifications,
                            validate_confirmed_rule_citations)
from quantity import ancestors, basis, count, number, resolve_scope_total, text_of, total_from_source, valid_basis_ref, validate_quantities

PHYSICAL = {"item", "assembly", "component"}
SECTIONS = {"section", "group", "summary"}
OMITTED = {"project", "attribute", "note"}
ROW_FIELDS = ("serial_no", "equipment_tag", "description", "nominal_size", "unit", "quantity",
              "unit_weight", "total_weight", "remark", "orderno")
HEADER_FIELDS = ("table_type", "specialty_name", "project_section")
STRING_ASSEMBLIES = {"单联悬垂绝缘子串", "双联悬垂绝缘子串", "单联耐张绝缘子串", "双联耐张绝缘子串"}


class ModelError(RuntimeError):
    """供应商失败、拒答、截断或响应协议异常，不能消耗结构纠正预算。"""


class ModelOutputTruncated(ModelError):
    """供应商明确以length结束；正文只供追踪，不能用于构建工程量。"""


class AnalysisError(ValueError):
    """模型完整结果未通过结构或业务校验。"""

    def __init__(self, message="", *, public_message=None):
        self.public_message = public_message
        super().__init__(message)


class StructureErrors(AnalysisError):
    """在一次纠正预算内提供本轮已发现的全部格式和行级结构错误。"""

    def __init__(self, errors):
        self.errors = errors
        super().__init__("；".join(error["message"] for error in errors))


def call_model(system: str, user: dict, schema: dict, config: Config, trace: Trace, stage: str) -> str:
    """发送一次非流式请求；仅提取业务正文和真实元数据，不重试或切换模型。"""
    model = config.model
    trace.execution_check()
    trace = trace.scoped(model_call_id=str(uuid4()), packet_id=user.get('prepared_input', {}).get('packet_id'),
                         context_id=user.get('context_id'))
    options = copy.deepcopy(model.get("request_options", {}))
    # 两家扩展能力分别构建，防止百炼字段泄入移动云请求。
    allowed = {"temperature", "top_p", "stream"}
    if model["provider"] == "aliyun_bailian":
        allowed |= {"response_format", "enable_thinking"}
    if set(options) - allowed:
        raise ModelError("供应商参数不在已确认范围")
    options["stream"] = False
    if model["provider"] == "aliyun_bailian":
        options.update(response_format={"type": "json_object"}, enable_thinking=False)
    actual_system = system + "\n\n输出 JSON Schema（在本地校验）：\n" + json.dumps(schema, ensure_ascii=False)
    request = {"model": model["model"], "messages": [{"role": "system", "content": actual_system},
               {"role": "user", "content": json.dumps(user, ensure_ascii=False, default=str, allow_nan=False)}],
               "max_tokens": model["max_output_tokens"], **options}
    trace.write("model_request", stage=stage, provider=model["provider"], model=model["model"],
                api_style=model["api_style"], base_url=model["base_url"], timeout_seconds=model["timeout_seconds"],
                request=request, schema=schema)
    url = urlsplit(model["base_url"].rstrip("/"))
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ModelError('模型目标必须为无凭据和查询参数的HTTPS地址')
    path = url.path if url.path.endswith("/chat/completions") else url.path + "/chat/completions"
    start = time.monotonic()
    connection = None
    try:
        connection = http.client.HTTPSConnection(url.hostname, url.port, timeout=model['timeout_seconds'])
        connection.connect()
        trace.write('model_connection', stage=stage, reused=False, connect_seconds=time.monotonic() - start,
                    connection_policy='single_request')
        # http.client 不跟随重定向，认证头只发送给已配置的 HTTPS 主机。
        connection.request("POST", path, json.dumps(request, ensure_ascii=False, allow_nan=False).encode("utf-8"),
                           {"Authorization": "Bearer " + model["api_key"], "Content-Type": "application/json"})
        response = connection.getresponse()
        payload = response.read()
        request_id = response.getheader("x-request-id") or response.getheader("request-id")
        if not 200 <= response.status < 300:
            trace.write("model_http_error", stage=stage, http_status=response.status, request_id=request_id,
                        elapsed_seconds=time.monotonic() - start)
            raise ModelError(f"模型 HTTP 状态 {response.status}")
        try:
            envelope = json.loads(payload)
        except (ValueError, UnicodeError) as exc:
            raise ModelError("模型 HTTP 响应不是合法 JSON") from exc
        if not isinstance(envelope, dict) or envelope.get("error"):
            raise ModelError("模型响应包含错误或不符合协议")
        choices = envelope.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ModelError("模型响应缺少 choices[0]")
        choice = choices[0]
        message = choice.get("message")
        if not isinstance(message, dict):
            raise ModelError("模型响应缺少 message")
        content = message.get("content")
        trace.write("model_response", stage=stage, provider=model["provider"], model=model["model"],
                    content=content, finish_reason=choice.get("finish_reason"),
                    response_model=envelope.get('model'),
                    request_id=request_id or envelope.get("request_id"), response_id=envelope.get("id"), usage=envelope.get("usage"),
                    elapsed_seconds=time.monotonic() - start)
        if not message.get("refusal") and choice.get("finish_reason") == "length":
            raise ModelOutputTruncated("模型输出达到长度上限，结果不完整")
        if message.get("refusal") or choice.get("finish_reason") != "stop":
            raise ModelError("模型拒答、截断或未正常结束")
        if not isinstance(content, str) or not content.strip():
            raise ModelError("模型正文为空或不是文本")
        return content
    except ModelError as exc:
        trace.write("model_failed", stage=stage, error=str(exc), elapsed_seconds=time.monotonic() - start)
        raise
    except (OSError, http.client.HTTPException) as exc:
        trace.write("model_transport_error", stage=stage, error_type=type(exc).__name__,
                    elapsed_seconds=time.monotonic() - start)
        raise ModelError("模型连接或读取失败：" + type(exc).__name__) from exc
    finally:
        if connection is not None:
            connection.close()


def analyze_material_file(header: dict, raw_rows: list, cbs_nodes: list, config: Config, trace: Trace) -> dict:
    """完整保留输入行；一次结构纠正后，以相同原文完成 CBS 两轮判断。"""
    if not raw_rows:
        raise AnalysisError("原始行为空")
    order = [row.get("orderno") for row in raw_rows]
    if None in order or order != sorted(order) or len(set(order)) != len(order):
        raise AnalysisError("原始行顺序无法确定")
    packet_id = str(uuid4())
    prepared = {"packet_id": packet_id, "header": {k: header.get(k) for k in HEADER_FIELDS},
                "rows": [{"r": i, **{k: row.get(k) for k in ROW_FIELDS}} for i, row in enumerate(raw_rows, 1)],
                "classification_rules": copy.deepcopy(config.classification_rules), "confirmed_decisions": []}
    raw = {i: row for i, row in enumerate(raw_rows, 1)}
    policies = compile_confirmed_rules(config.classification_rules)
    prepared['confirmed_decisions'] = [decision for r in raw
        if (raw[r].get('unit') or raw[r].get('quantity'))
        and (decision := confirmed_classification(r, raw, policies)) is not None]
    rule_ids = {rule["rule_id"] for rule in config.classification_rules}
    schemas = {name: json.loads((config.prompt_dir / (name + '.schema.json')).read_text(encoding='utf-8'))
               for name in ("model-output", "cbs-leaf-output", "cbs-parent-output")}
    system = (config.prompt_dir / 'structure.txt').read_text(encoding='utf-8')
    trace.write("analysis_input", prepared_input=prepared, cbs_nodes=cbs_nodes,
                row_map=[{"r": r, "raw_id": row["id"], "orderno": row["orderno"]} for r, row in raw.items()])

    def validate_structure(proposal, targets=None, *, partial=False):
        """Schema 外检查全行覆盖、真实引用、无环、分类与计量依赖。"""
        schema_errors = list(Draft202012Validator(schemas["model-output"]).iter_errors(proposal))
        errors = []
        for error in schema_errors:
            detail = {"code": "INVALID_SCHEMA", "path": error.json_path, "message": error.message}
            path = list(error.absolute_path)
            if len(path) >= 2 and path[0] == "rows" and isinstance(path[1], int):
                candidate = proposal["rows"][path[1]]
                if isinstance(candidate, dict) and type(candidate.get("r")) is int:
                    detail["r"] = candidate["r"]
            if error.validator == "const" and len(path) == 3 and path[0] == "rows" and path[2] == "quantity_basis":
                row = proposal["rows"][path[1]]
                detail.update(code="NONPHYSICAL_QUANTITY", r=row.get("r"), actual=error.instance, expected="not_applicable",
                              message=f"r={row.get('r')} role={row.get('role')} 的quantity_basis必须从{error.instance!r}改为'not_applicable'；原始总数仍在raw行保留，只改reason文字不算修复")
            errors.append(detail)
        # 额外字段和常量冲突不改变已通过类型/必填校验的形状，可同时报告其他行级结构错误。
        # 其他Schema错误可能破坏输入形状，不能盲目访问缺失或错误类型的字段。
        def unsafe_schema_error(error):
            path = list(error.absolute_path)
            # node_type的非法字符串仍可安全读取；合并时与跨段证据错误一并纠正，最终不放宽enum。
            safe_node_type_enum = (error.validator == 'enum' and type(error.instance) is str
                and len(path) == 3 and path[0] == 'rows' and type(path[1]) is int and path[2] == 'node_type')
            return error.validator not in {'additionalProperties', 'const'} and not safe_node_type_enum
        # 条件契约限制的是合法状态组合，并不改变基础字段形状。例如pending的
        # parent虽违反null约束，整数值仍可安全用于关系校验。只用基础Schema
        # 判断能否继续读取字段，避免状态错误提前耗掉唯一纠正机会。
        shape_schema = copy.deepcopy(schemas["model-output"])
        shape_schema["properties"]["rows"]["items"].pop("allOf", None)
        shape_errors = Draft202012Validator(shape_schema).iter_errors(proposal)
        if any(unsafe_schema_error(error) for error in shape_errors):
            raise StructureErrors(errors)
        expected = list(raw) if targets is None else targets
        # JSON Schema 的 integer 允许2.0，行号在Python中必须可安全用于离散索引。
        for index, row in enumerate(proposal["rows"]):
            refs = [(key, row[key]) for key in ("r", "parent", "qty_from", "unit_from", "quantity_parent", "quantity_basis_ref")]
            refs += [("inherit", value) for value in row["inherit"]]
            refs += [("classification.source_rows", value) for value in row["classification"]["source_rows"]]
            for key, value in refs:
                if value is not None and type(value) is not int:
                    errors.append({"code": "INVALID_ROW_ID", "r": expected[index] if index < len(expected) else None,
                                   "path": f"$.rows[{index}].{key}", "message": f"第{index + 1}个输出的{key}必须为整数行号，不能写成{value!r}"})
        if any(e["code"] == "INVALID_ROW_ID" for e in errors):
            raise StructureErrors(errors)
        actual = [row["r"] for row in proposal["rows"]]
        if proposal["packet_id"] != packet_id or actual != expected:
            errors.append({"code": "INVALID_COVERAGE", "path": "$", "expected_rows": expected, "actual_rows": actual,
                           "missing_rows": sorted(set(expected) - set(actual)), "unexpected_rows": sorted(set(actual) - set(expected)),
                           "duplicate_rows": [r for r, n in Counter(actual).items() if n > 1],
                           "message": f"必须按顺序输出全部目标行{expected}，包括属性和说明；当前实际行{actual}。packet_id须原样返回{packet_id}"})
            raise StructureErrors(errors)
        rows = {row["r"]: row for row in proposal["rows"]}
        if partial:
            # 字段形状安全的额外键/常量错误延后到完整合并时，和跨段语义错误
            # 一次汇总纠正；不能先耗掉唯一预算，再报告本可同时发现的父关系错误。
            return rows

        invalid_identity_rows = set()

        def validate_row(r, row):
            def report(message, field=None, **detail):
                path = f"$.rows[{r - 1}]" + (f".{field}" if field else "")
                errors.append({"code": "INVALID_STRUCTURE", "r": r, "path": path,
                               "message": f"r={r} {message}", **detail})

            # 同行约束独立收集；无效引用只阻止依赖它的检查，不掩盖分类等问题。
            for field in ("parent", "qty_from", "unit_from", "quantity_parent", "quantity_basis_ref"):
                if row[field] is not None and row[field] not in rows:
                    report(f"{field} 引用不存在", field)
            ancestry, current, ancestry_valid = [], row["parent"], True
            while current is not None:
                if current not in rows:
                    if current != row["parent"]:
                        report("祖先引用不存在", "parent")
                    ancestry_valid = False
                    break
                if current == r or current in ancestry:
                    report("父关系成环", "parent")
                    ancestry_valid = False
                    break
                ancestry.append(current)
                current = rows[current]["parent"]
            parent = rows.get(row["parent"])
            if parent and parent["role"] in {"attribute", "note", "pending"}:
                report("不能以属性、说明或未知结构为父节点", "parent")
            if ancestry_valid and row["role"] == "project" and any(rows[a]["role"] in PHYSICAL for a in ancestry):
                report("单项工程范围不能隶属于具体实物；请修正范围层级，不能把另一工程挂到上一设备内部", "parent")
            if row["role"] == "attribute" and (parent is None or parent["role"] not in PHYSICAL):
                if parent and parent["role"] == "summary":
                    report(f"是不独立计量汇总母行r={row['parent']}的公共参数，必须把本行role从attribute改为note，parent仍保留{row['parent']}；不能仅改parent到相邻说明行或某个子设备，也不能把汇总母行改回assembly。参数内容继续作为该汇总范围的公共说明保留。",
                           "role", code="SUMMARY_ANNOTATION_ROLE", expected_fields={"role": "note", "parent": row["parent"]})
                else:
                    report("属性必须属于具体实物", "parent")
            if row["role"] == "pending" and (row["parent"] is not None or not row["reason"]):
                report("pending 应保留为根并说明疑点；分类依据不足应保留已确定的实物角色，不能据此改为pending", "parent")
            if ancestry_valid:
                inherited = [a for a in reversed(ancestry) if a in row["inherit"]]
                if inherited != row["inherit"] or any(rows[a]["role"] not in {"group", "summary"} for a in inherited):
                    report("inherit 只能按顺序引用group/summary共同身份祖先；共同物名分组不应误报为section，工程范围不能用于名称继承", "inherit")
                    invalid_identity_rows.add(r)
            else:
                invalid_identity_rows.add(r)
            for field in ("qty_from", "unit_from"):
                source = row[field]
                related = {r, *ancestry}
                if source is None or source not in rows:
                    continue
                if ancestry_valid and source not in related and not (
                        rows[source]["role"] in {"attribute", "note"} and rows[source]["parent"] in related):
                    report(f"{field} 跨无关行取值", field)
                if rows[source]["role"] == "project":
                    report("工程范围不能提供实物数量或单位", field)
            c = row["classification"]
            if not set(c["rule_ids"]) <= rule_ids or not set(c["source_rows"]) <= raw.keys():
                report("企业规则或分类原行引用不存在", "classification")
            if row["role"] in PHYSICAL:
                if c["status"] == "resolved":
                    if row["node_type"] is None or not c["rule_ids"] or not c["source_rows"] or not c["reason"]:
                        report("明确分类缺少规则、原文或类型", "classification")
                elif c["status"] != "review" or row["node_type"] is not None or not c["reason"]:
                    report(f"未确定的实物分类应保留未知和原因：classification.status须为'review'、node_type须改为JSON null、classification.reason须非空；当前status={c['status']!r}、node_type={row['node_type']!r}，不能保留猜测类型", "classification")
            elif row["node_type"] is not None or c["status"] != "not_applicable" or c["rule_ids"] or c["source_rows"]:
                report("非实物或结构待确认行不应输出设备材料分类：保持该role时node_type=null、classification.status=not_applicable、rule_ids/source_rows为空；若原文已能确定实物身份，应保留实物角色并只将分类设为review，不得为通过校验隐藏明细和原始数量", "classification")
            if row["role"] in OMITTED | SECTIONS and row["quantity_basis"] != "not_applicable":
                report("非实物参考行不能独立计量", "quantity_basis")
        for r, row in rows.items():
            validate_row(r, row)
            # 只校验模型对本母行的明确结论与角色是否一致，不从空数量、名称或子项数推断汇总。
            if row["role"] in PHYSICAL and any(child["parent"] == r and child["role"] in PHYSICAL for child in rows.values()):
                conclusion = re.split(r"[；;。\n]", row["reason"] or "", maxsplit=1)[0].strip()
                summary = re.match(r"^(?:(?:本行|该行|母行|本项|该项|母项)(?:仅为|只是|属于|是)|仅为|只是)?汇总(?:母行|行|参考|标题|总项)?(?=[，,：:\s]|不)", conclusion)
                if summary and re.search(r"不(?:独立|单独)(?:计量|计价|出表)", conclusion):
                    errors.append({"code": "SUMMARY_ROLE_CONFLICT", "r": r, "path": f"$.rows[{r - 1}].role",
                                   "message": f"r={r} reason已确认本母行为不独立计量的汇总，却仍输出{row['role']}实物角色；请依据原文将role改为summary、quantity_basis改为not_applicable、node_type改为null、classification改为not_applicable，并保留下级各自工程量及公共说明。若确为独立成套对象，应说明其真实对象依据，不能只改措辞掩盖汇总。"})
        errors.extend(validate_quantities(raw, rows))
        errors.extend(validate_classification_evidence(rows, raw))
        # 规则适用性依赖合法的共同身份链；已报错的链不能用于拼物名或索引raw。
        # 完整文件仍因上述错误拒绝，修复关系后会重新校验全部规则引用。
        errors.extend(validate_confirmed_rule_citations(
            {r: row for r, row in rows.items() if r not in invalid_identity_rows}, raw, policies))
        if errors:
            raise StructureErrors(errors)
        return rows

    try:
        chunks = plan_chunks(prepared, config)
    except ValueError as exc:
        raise AnalysisError("分段配置无效：" + str(exc)) from exc
    chunked = len(chunks) > 1
    trace.write("structure_chunk_plan", chunks=chunks, chunk_count=len(chunks), output_budget=config.model["max_output_tokens"])
    outputs, responses, repaired = {}, {}, set()
    split_depth = {tuple(targets): 0 for targets in chunks}

    def errors_for(exc):
        return getattr(exc, "errors", [{"code": "INVALID_STRUCTURE", "path": getattr(exc, "json_path", "$"), "message": str(exc)}])

    def fail(errors):
        quantity_error = next((e for e in errors if e["code"] in {"NONPHYSICAL_QUANTITY", "SUMMARY_ROLE_CONFLICT"}), None)
        public = "模型结构结果纠正后仍未通过校验，请重试未完成料表。"
        if quantity_error:
            r = quantity_error.get("r")
            row_hint = f"第{r}行" if type(r) is int and r > 0 else ""
            public = f"{row_hint}汇总/分组被标为独立计量，模型纠正后仍未修正。请重试未完成料表。"
        raise AnalysisError("结构纠正后仍不合法：" + "；".join(e["message"] for e in errors), public_message=public)

    def request_chunk(index, errors=None):
        nonlocal chunked
        targets = chunks[index]
        key = tuple(targets)
        known = [outputs[r] for r in sorted(outputs)]
        packet = packet_for_chunk(prepared, targets, known) if chunked else prepared
        repair = errors is not None
        if repair:
            if key in repaired:
                fail(errors)
            repaired.add(key)
        stage = "structure_repair" if repair else "structure_initial"
        if chunked:
            stage += f"_{index + 1:03d}"
        contract = {"packet_id": packet_id, "row_count": len(targets), "row_ids": targets,
                    "context_policy": "prepared_input.rows中的其他行及structure_context仅供只读引用，不得输出这些行"}
        user = {"task": "STRUCTURE_REPAIR" if repair else "STRUCTURE_INITIAL",
                "output_contract": contract, "prepared_input": packet}
        if repair:
            try:
                previous = json.loads(responses[key])
            except ValueError:
                previous = None
            user["repair"] = {"original_response": responses[key], "parsed_proposal": previous, "errors": errors}
        user["response_requirements"] = (f"本次只返回{len(targets)}行，rows的r必须依次恰为"
            + json.dumps(targets) + "。其余原行仅作上下文，不得输出；目标行中的工程、属性和说明仍须输出。")
        request_schema = schemas["model-output"]
        if chunked:
            request_schema = copy.deepcopy(request_schema)
            array = request_schema["properties"]["rows"]
            row_schema = array.pop("items")
            request_schema["$defs"] = {"row": row_schema}
            array.update(minItems=len(targets), maxItems=len(targets), items=False,
                         prefixItems=[{"allOf": [{"$ref": "#/$defs/row"}, {"properties": {"r": {"const": r}}}]} for r in targets])
        scoped_system = system + "\n\n本次输出边界（程序指定）：\n" + user["response_requirements"]
        try:
            response = call_model(scoped_system, user, request_schema, config, trace, stage)
        except ModelOutputTruncated as exc:
            # 不截取/拼接不完整JSON。仅初始请求允许最多两级二分，单行或纠正请求不继续重试。
            depth = split_depth[key]
            if repair or len(targets) <= 1 or depth >= 2:
                raise AnalysisError("分段输出缩小后仍截断", public_message=
                    f"第{targets[0]}～{targets[-1]}行的模型输出仍被截断，本文件未保存，请重试未完成料表。") from exc
            middle = len(targets) // 2
            halves = [targets[:middle], targets[middle:]]
            chunks[index:index + 1] = halves
            split_depth.update({tuple(part): depth + 1 for part in halves})
            chunked = True
            trace.write("structure_chunk_split", output_rows=targets, retry_chunks=halves,
                        split_depth=depth + 1, reason="length")
            return False
        responses[key] = response
        try:
            result = json.loads(response)
            validated = validate_structure(result, targets, partial=chunked)
        except (ValueError, ValidationError) as exc:
            current_errors = errors_for(exc)
            trace.write("structure_invalid", chunk=index + 1, attempt=int(repair), errors=current_errors, original_response=response)
            if repair:
                fail(current_errors)
            request_chunk(index, current_errors)
            return True
        outputs.update(validated)
        trace.write("structure_chunk_validated", chunk=index + 1, output_rows=targets, attempt=int(repair))
        return True

    index = 0
    while index < len(chunks):
        if request_chunk(index):
            index += 1
    # 跨段父关系、身份、计量及分类证据只能在全部决策齐全后统一校验。
    # 错误只纠正所属段；每段最多一次，且任何错误都禁止进入落库阶段。
    while True:
        proposal = {"packet_id": packet_id, "rows": [outputs[r] for r in sorted(outputs)]}
        try:
            rows = validate_structure(proposal)
            break
        except (ValueError, ValidationError) as exc:
            errors = errors_for(exc)
            trace.write("structure_merge_invalid", errors=errors)
            affected = {i for i, targets in enumerate(chunks) if any(e.get("r") in targets for e in errors)}
            if not affected:
                fail(errors)
            # 先纠正最早的受影响段，再重新校验，避免根因修复后仍用旧错误
            # 无谓重写其他段，浪费它们唯一的纠正预算。
            request_chunk(min(affected), errors)
    try:
        confirmed = apply_confirmed_classifications(rows, raw, policies)
    except ValueError as exc:
        raise AnalysisError(str(exc)) from exc
    if confirmed:
        rows = validate_structure(proposal)
        trace.write('confirmed_classification_applied', decisions=confirmed)
    trace.write("structure_validated", proposal=proposal, chunk_count=len(chunks), repaired_chunks=sorted(repaired))

    from cbs_matching import match_scopes
    matching = match_scopes(header, prepared["header"], raw, rows, cbs_nodes, config, trace, schemas, call_model, AnalysisError)
    return {"raw_rows": raw_rows, "structure": proposal, **matching}


def _merge_string_components(raw, rows, by_r, mapping, config, trace):
    """仅执行已确认的整串出表口径；原始结构、分类和计量结果不改写。"""
    annotations = {}
    for r, row in rows.items():
        if row["role"] in {"attribute", "note"}:
            annotations.setdefault(row["parent"], []).append(r)

    def separate(r, scope=False):
        owners = [r, *ancestors(rows, r)] if scope else [r]
        sources = [k for owner in owners for k in [owner, *annotations.get(owner, [])]]
        if scope:
            sources.extend(annotations.get(None, []))
        text = " ".join(text_of(raw[k]) for k in sources)
        if re.search(r"是否|待定|不确定|并非|不是|未必|不能不|不得不", text):
            return True
        # 否定声明不得因包含“另计”而误判；其余不明确声明保守保留。
        terms = r"另(?:行)?(?:采购|购买|购置|计价|计量|计费|购|计)|(?:单独|独立)(?:采购|购买|购置|计价|计量|计费)"
        text = re.sub(r"(?:不|无需|无须|不得|禁止)\s*(?:" + terms + r")", "", text)
        return bool(re.search(terms, text))

    visible_types = set(config.business["item_types"][key] for key in ("MATERIAL", "EQUIPMENT"))
    parents_in_use = {item["parent_id"] for item in by_r.values()}
    merged = {}
    for r, row in rows.items():
        parent, ref = row["parent"], row["quantity_basis_ref"]
        if row["role"] != "component" or parent not in by_r or r not in by_r:
            continue
        owner, item = by_r[parent], by_r[r]
        name = "".join(str(raw[parent].get("description") or "").split())
        if (rows[parent]["role"] != "assembly" or name not in STRING_ASSEMBLIES
                or owner["unit"] != "串" or owner["quantity"] is None
                or owner["type"] not in visible_types or item["type"] not in visible_types
                or item["quantity"] is None or not raw[r].get("unit")
                or row["qty_from"] not in {None, r} or row["unit_from"] not in {None, r}
                or item["project_cbs_id"] != owner["project_cbs_id"]
                or item["id"] in parents_in_use or separate(parent, scope=True) or separate(r)):
            continue
        if (row["quantity_basis"] != "per_parent" or row["quantity_parent"] != parent
                or ref not in raw or basis(raw[ref]) != (1, "串")
                or not re.match(r"^\s*每\s*(?:1|一)?\s*串\s*(?:[:：]|包括|包含|用量)", text_of(raw[ref]))
                or not valid_basis_ref(raw, rows, r, parent, ref)):
            continue
        merged[r] = parent

    for parent in dict.fromkeys(merged.values()):
        sources = sorted(k for r, owner in merged.items() if owner == parent for k in [r, *annotations.get(r, [])])
        details = ["；".join(str(raw[r][key]) for key in ROW_FIELDS
                            if key != "orderno" and raw[r].get(key) is not None) for r in sources]
        owner = by_r[parent]
        owner["remark"] = "；".join(filter(None, [owner["remark"], "每串组成：" + "；".join(details)]))
    merged_sources = {k: owner for r, owner in merged.items() for k in [r, *annotations.get(r, [])]}
    for entry in mapping:
        r = entry["r"]
        if r in merged_sources:
            entry.update(item_id=None, merged_into=by_r[merged_sources[r]]["id"], reason="已确认绝缘子串组成并入母项备注")
            trace.write("assembly_component_merged" if r in merged else "assembly_annotation_merged", r=r, raw_id=raw[r]["id"],
                        parent_r=merged_sources[r], item_id=entry["merged_into"], quantity_basis_ref=rows[r]["quantity_basis_ref"])
    return {by_r[r]["id"] for r in merged}


@dataclass
class FileBuildResult:
    """同一次构建的最终实物与全行映射；组成件合并后统一交给快照组装。"""
    items: list
    row_map: list


def build_file_result(file: dict, analysis: dict, task: dict, config: Config, trace: Trace) -> FileBuildResult:
    """内部树参与完整计量，最终仅保存实物/待确认项，跨过结构项保留实物父子关系。"""
    raw = {i: row for i, row in enumerate(analysis["raw_rows"], 1)}
    decisions = analysis["structure"]["rows"]
    rows = {row["r"]: row for row in decisions}
    if list(rows) != list(raw) or len(rows) != len(decisions):
        raise AnalysisError("构建前原行覆盖不完整")
    policies = compile_confirmed_rules(config.classification_rules)
    if validate_confirmed_rule_citations(rows, raw, policies):
        raise AnalysisError('已确认分类规则引用超出适用对象，拒绝保存')
    for r, row in rows.items():
        if row['role'] not in PHYSICAL:
            continue
        expected = confirmed_classification(r, raw, policies, row['inherit'])
        if expected is not None and (row['node_type'] != expected['node_type']
                or row['classification']['status'] != 'resolved'
                or not set(expected['rule_ids']) <= set(row['classification']['rule_ids'])):
            raise AnalysisError(f'第{r}行已确认分类未落实，拒绝保存为错误类型或待确认')
    ids = {r: str(uuid4()) for r, row in rows.items() if row["role"] in PHYSICAL | {"pending"}}
    if "cbs_by_row" in analysis and not set(ids) <= set(analysis["cbs_by_row"]):
        raise AnalysisError("逐行CBS判断缺少保留的实物/待确认记录")
    records, by_r, mapping, counts = [], {}, [], Counter()
    # 拓扑顺序用于父量计算和 INSERT；sort_no 另按原表同级顺序赋值。
    remaining, ordered = set(rows), []
    while remaining:
        ready = [r for r in rows if r in remaining and (rows[r]["parent"] is None or rows[r]["parent"] in ordered)]
        if not ready:
            raise AnalysisError("构建时发现非法父引用或环")
        # 每次取原表最早的就绪行，避免跳过结构分组后根明细被层级批次打乱。
        ordered.append(ready[0])
        remaining.remove(ready[0])
    sibling_order = {}
    for r, row in rows.items():
        if r not in ids:
            continue
        parent = row["parent"]
        if parent is not None and parent not in rows:
            raise AnalysisError("构建时父引用不存在")
        if row["role"] == "pending":
            parent = None
        else:
            visited = set()
            while parent is not None and parent not in ids:
                if parent in visited or parent not in rows or rows[parent]["role"] in {"attribute", "note"}:
                    raise AnalysisError("保留节点的父行非法或成环")
                visited.add(parent)
                parent = rows[parent]["parent"]
        counts[parent] += 1
        sibling_order[r] = (parent, counts[parent])

    for r in ordered:
        row, source = rows[r], raw[r]
        if r not in ids:
            mapping.append({"r": r, "raw_id": source["id"], "item_id": None, "original_parent": row["parent"],
                            "reason": "结构项仅供名称/计量/CBS上下文，不落库" if row["role"] in SECTIONS | {"project"} else "属性或说明并入备注"})
            continue
        remark = [str(source[k]) for k in ("remark",) if source.get(k)]
        for field in ("equipment_tag", "nominal_size", "unit_weight", "total_weight"):
            if source.get(field) is not None and str(source[field]).strip():
                remark.append(field + "=" + str(source[field]))
        name = str(source.get("description") or "")
        specification = None
        prefixes = []
        for ancestor in row["inherit"]:
            common = str(raw[ancestor].get("description") or "").strip()
            if common and common not in name and not any(common in prefix for prefix in prefixes):
                prefixes = [prefix for prefix in prefixes if prefix not in common]
                prefixes.append(common)
        if prefixes:
            if re.fullmatch(r"[A-Za-z0-9×*+./²³μΩ°%()（）_\-\s]+", name.strip()) and re.search(r"\d", name):
                specification = name
            name = " ".join([*prefixes, name])
        q_source = row["qty_from"] if row["qty_from"] is not None else r
        u_source = row["unit_from"] if row["unit_from"] is not None else r
        quantity = None
        raw_quantity = raw[q_source].get("quantity")
        quantity_reason = "非实物参考行不独立计量"
        divisor = None
        multiplier_total = None
        quantity_count_source = None
        derived_unit = None
        if row["role"] in PHYSICAL:
            value = number(raw_quantity)
            if row["quantity_basis"] == "total":
                value, derived_unit, quantity_count_source = total_from_source(raw, rows, r)
                quantity, quantity_reason = value, "原范围总量" if value is not None else "原量缺失或无法解析"
                if value is not None and q_source != r:
                    quantity_reason = f"原文第{q_source}行明确总数={value}{derived_unit or ''}"
            elif row["quantity_basis"] in {"per_parent", "per_scope"}:
                ref = raw[row["quantity_basis_ref"]]
                denominator = basis(ref)
                divisor = denominator[0] if denominator else None
                total = None
                if row["quantity_basis"] == "per_scope":
                    total, quantity_count_source = resolve_scope_total(raw, rows, r)
                else:
                    parent_item = by_r.get(row["quantity_parent"])
                    total = parent_item["quantity"] if parent_item else None
                    quantity_count_source = row["quantity_parent"]
                    # 工作量范围台数和父设备采购数量是不同概念。父项采购总量
                    # 未确定时，仍可使用直属说明明确的共N台计算组件，不回填父量。
                    ref_decision = rows[row["quantity_basis_ref"]]
                    if total is None and denominator and ref_decision["role"] == "note" and ref_decision["parent"] == row["quantity_parent"]:
                        explicit = count(ref, denominator[1])
                        if explicit:
                            total = explicit[0]
                            quantity_count_source = row["quantity_basis_ref"]
                if value is not None and total is not None and divisor is not None and divisor > 0:
                    quantity = value * total / divisor
                    multiplier_total = total
                    quantity_reason = f"原量{value}×{'范围' if row['quantity_basis'] == 'per_scope' else '父实物'}总量{total}/{divisor}（依据第{row['quantity_basis_ref']}行）"
                    if row["quantity_basis"] == "per_scope" and quantity_count_source != row["quantity_basis_ref"]:
                        quantity_reason += f"；范围总量来源第{quantity_count_source}行"
                else:
                    quantity_reason = "单件口径、限定基数、原量或父实物总量不明确"
            else:
                quantity_reason = "数量口径未知或不适用"
        if quantity is None or row["quantity_basis"] in {"per_parent", "per_scope"} or q_source != r:
            remark.append(f"原量={raw_quantity!s}；{quantity_reason}")
        if row["reason"]:
            remark.append(row["reason"])
        node_type = None
        if row["role"] in PHYSICAL:
            node_type = config.business["item_types"].get(row["node_type"])
            if node_type is None:
                remark.append("类型待确认：" + str(row["classification"]["reason"] or "企业规则依据不足"))
        parent_r, sort_no = sibling_order[r]
        cbs_decision = analysis.get("cbs_by_row", {}).get(r)
        target = cbs_decision["project_cbs_id"] if cbs_decision is not None else analysis["project_cbs_id"]
        if cbs_decision:
            if cbs_decision["cbs_path"]:
                remark.append("CBS：" + cbs_decision["cbs_path"])
            elif cbs_decision["scope_title"]:
                remark.append("CBS未命中；工程范围：" + cbs_decision["scope_title"])
        record = {"id": ids[r], "file_id": file["id"], "project_cbs_id": target,
                  "parent_id": ids[parent_r] if parent_r is not None else None, "sort_no": sort_no,
                  "type": node_type, "code": None, "name": name, "specification": specification,
                  "unit": raw[u_source].get("unit") or (derived_unit if u_source in {r, q_source} else None),
                  "quantity": quantity, "remark": "；".join(dict.fromkeys(remark)) or None,
                  "cbs_match_status": config.business["cbs_matched" if target else "cbs_unmatched"],
                  "cbs_match_method": config.business["cbs_method"],
                  **{k: task.get(k) for k in ("create_user_id", "create_org_id", "create_date")}}
        records.append(record)
        by_r[r] = record
        mapping.append({"r": r, "raw_id": source["id"], "item_id": ids[r], "original_parent": row["parent"],
                        "parent_id": record["parent_id"], "qty_from": q_source, "unit_from": u_source,
                        "quantity_parent": row["quantity_parent"], "quantity_basis_ref": row["quantity_basis_ref"],
                        "quantity_count_source": quantity_count_source,
                        "divisor": divisor, "quantity_reason": quantity_reason, "quantity": quantity,
                        "raw_quantity": raw_quantity, "raw_unit": raw[u_source].get("unit"),
                        "quantity_basis": row["quantity_basis"], "multiplier_total": multiplier_total})
    global_notes = []
    for r, row in rows.items():
        if row["role"] not in {"attribute", "note"}:
            continue
        text = "；".join(str(raw[r][k]) for k in ROW_FIELDS if k != "orderno" and raw[r].get(k) is not None)
        if row["parent"] in by_r:
            owner = by_r[row["parent"]]
            owner["remark"] = "；".join(filter(None, [owner["remark"], text]))
            trace.write("annotation_attached", r=r, raw_id=raw[r]["id"], item_id=owner["id"], text=text)
        elif row["parent"] is not None and rows[row["parent"]]["role"] in SECTIONS:
            # 被过滤分部的说明携带范围来源，不把它改成每条实物自身属性。
            from quantity import ancestors
            owner_r = row["parent"]
            label = "范围说明（" + str(raw[owner_r].get("description") or owner_r) + "）：" + text
            for child_r, child in by_r.items():
                if owner_r in ancestors(rows, child_r):
                    child["remark"] = "；".join(filter(None, [child["remark"], label]))
                    trace.write("scope_annotation_attached", r=r, source_scope=owner_r, item_id=child["id"], text=text)
        elif row["parent"] is None and row["role"] == "note":
            global_notes.append("全表说明：" + text)
        else:
            trace.write("annotation_context_only", r=r, raw_id=raw[r]["id"], text=text)
    for record in records:
        if record["parent_id"] is None and global_notes:
            record["remark"] = "；".join(filter(None, [record["remark"], *global_notes]))
    merged_ids = _merge_string_components(raw, rows, by_r, mapping, config, trace)
    records = [record for record in records if record["id"] not in merged_ids]
    trace.write("items_built", records=records, row_map=mapping, audit_source="sc_ai_python_task",
                project_cbs_id=analysis["project_cbs_id"], cbs_reason=analysis["cbs_reason"])
    return FileBuildResult(records, mapping)


def build_item_records(file: dict, analysis: dict, task: dict, config: Config, trace: Trace) -> list:
    """保留既有转换调用接口；正式Runner使用包含全行映射的build_file_result。"""
    return build_file_result(file, analysis, task, config, trace).items
