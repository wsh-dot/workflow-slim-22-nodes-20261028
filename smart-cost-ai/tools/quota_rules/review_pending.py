"""Build a traceable, exhaustive review of the first release's 95 technical rows."""
from collections import Counter
from copy import deepcopy
import json

from authoring import value, selector_codes
from verify import file_digest


def answer_ids(row):
    family, n = row["sheet"], row["row"]
    if family == "A-05": return ["A05-02"]
    if family == "A-07": return ["A07源表第12行设计重量要求"]
    if family == "A-09":
        ids = ["A09-01", "A09-02"]
        if n in (11, 18, 19, 20, 23, 24, 25, 68): ids += ["A09-04（标红忽略，非范围更正）"]
        if n in (19, 20, 24, 25): ids += ["A05-01整线第八/九章分流"]
        if n in (62, 63): ids += ["A09-07"]
        return ids
    if family == "A-11":
        ids = ["A11等同仅用于表达检索的已确认政策"]
        if n <= 32: ids += ["A11-03"]
        if n in (33, 63): ids += ["A11-06"]
        if n in (34, 35, 36): ids += ["A11-05"]
        if n >= 55: ids += ["A11-07（忽略问题，不等于技术属性补齐）"]
        return ids
    if 9 <= n <= 16 or n in (68, 69): return ["A06-04及追加确认（删13—16编号排除，保留工艺约束）"]
    if n in (65, 67): return ["A06-07", "A06-08扣除同沟已计量"]
    if n == 66 or 88 <= n <= 95: return ["A06-14（YS7-163明确排除）"]
    if n == 70: return ["A06-07每1m算例为1.26m³"]
    if n in (72, 73): return ["A06-03最新计算口径及三种型号/规格门槛"]
    if 74 <= n <= 77: return ["A06-10及9MWp=4+4+1追加答复"]
    if 78 <= n <= 81: return ["A06-11"]
    if n in (82, 83): return ["A06-12"]
    if 96 <= n <= 99: return ["A06-15"]
    return ["本行源表明确数量/工作要求"]


def catalog_checks(row, catalog):
    family, n = row["sheet"], row["row"]
    if family == "A-11" or family == "A-09": return []
    if family == "A-05": libraries = ["DE07000019"]
    elif family == "A-07" or 74 <= n <= 77: libraries = ["DE06000003"]
    elif 78 <= n <= 81: libraries = ["DE07000022"]
    elif n in (82, 83): return [{"status": "EXPLICIT_SUPPLEMENT_NO_CATALOG_ID_REQUIRED"}]
    elif n >= 87: libraries = ["DE07000019"]
    elif n in (72, 73): libraries = ["DE1000022001", "DE06000003", "DE07000022"]
    else: libraries = ["DE1000022001"]
    selectors = [("main", value(row, "main_code")), ("target", value(row, "related_code") or value(row, "target_code"))]
    checks = []
    for lib in libraries:
        for role, expression in selectors:
            if not expression or expression.startswith("补"): continue
            try:
                found = selector_codes(expression, lib, catalog)
                checks.append({"library_code": lib, "role": role, "selector": expression, "status": "FOUND_IN_FROZEN_SNAPSHOT_ONLY",
                               "count": len(found), "samples": found if len(found) <= 2 else [found[0], found[-1]]})
            except ValueError as exc:
                checks.append({"library_code": lib, "role": role, "selector": expression, "status": "NOT_RESOLVED_IN_SNAPSHOT", "diagnostic": str(exc)})
        if family == "A-07":
            found = [{k: i[k] for k in ("id", "code", "name", "unit")} for i in catalog["items"] if i["library_code"] == lib and "固定支架" in i["name"]]
            checks.append({"library_code": lib, "name_query": "固定支架", "status": "NAME_CANDIDATES_NOT_IDENTITY_PROOF", "count": len(found), "samples": found[:3]})
        if family == "A-06" and n in range(87, 96):
            code = "GD2-13" if n == 87 else "GJ14-2"
            found = [{k: i[k] for k in ("id", "code", "name", "unit")} for i in catalog["items"] if i["library_code"] == lib and i["code"] == code]
            checks.append({"library_code": lib, "source_code": value(row, "main_code"), "source_unit": value(row, "main_unit"),
                           "status": "NAME_CANDIDATES_NOT_IDENTITY_PROOF", "count": len(found), "samples": found})
        if family == "A-05":
            found = [{k: i[k] for k in ("id", "code", "name", "unit")} for i in catalog["items"] if i["library_code"] == lib and "35" in i["name"] and "电缆" in i["name"]]
            checks.append({"library_code": lib, "name_query": "35 AND 电缆", "status": "FROZEN_SNAPSHOT_NAME_SEARCH_ONLY", "count": len(found), "samples": found})
    return checks


def make_review(previous, package, source_map, catalog):
    old = json.loads((previous / "rules.json").read_text(encoding="utf-8"))
    old_pending = [r for r in old["pending_rules"] if r["pending_kind"] == "TECHNICAL_EVIDENCE"]
    if len(old_pending) != 95: raise ValueError("review baseline must contain exactly 95 technical rows")
    records = {r["rule_id"]: r for r in source_map["records"]}
    disposition = {d["source_record_id"]: d for d in source_map["dispositions"]}
    approved = {r["rule_id"]: r for r in package["approved_rules"]}
    pending = {r["rule_id"]: r for r in package["pending_rules"]}
    reviews = []
    for prior in old_pending:
        rid = prior["rule_id"]; row = records[rid]; d = disposition[rid]
        generated = [approved[x] for x in d["rule_ids"]]
        remaining = rid in pending
        issues = pending[rid]["reason"].split("；") if remaining else []
        state = "PARTIALLY_COMPILED_BLOCKED" if remaining and generated else "STILL_BLOCKED" if remaining else "CLOSED_FOR_DECLARED_USAGE"
        specs = {k: v["value"] for k, v in row["context"].items()}
        reviews.append({"source_record_id": rid, "family": prior["family"], "source_refs": row["source_refs"],
                        "original_reason": prior["reason"], "source_values": specs,
                        "recorded_answer_ids": answer_ids(row) + ["用户2026-11-12 " + d["id"] for d in catalog.get("confirmed_changes", {}).get("decisions", []) if rid in d["rule_ids"]], "recorded_interpretation": row["confirmed_interpretation"],
                        "catalog_checks": catalog_checks(row, catalog),
                        "review_state": state, "result": d["reason"], "generated_rule_ids": d["rule_ids"],
                        "generated_actions": [{"rule_id": r["rule_id"], "type": r["effect"]["type"], "strength": r["strength"],
                            "release_blocked": bool(r["effect"].get("release_blocked_by"))} for r in generated],
                        "missing_evidence": issues,
                        "pending_scope": deepcopy(pending[rid]["conservative_scope"]) if remaining else None,
                        "project_input_fields": sorted({k for r in generated for k in r["dependencies"]}),
                        "input_note": "项目输入由具体项目/定额数据提供，未知时待补，不是再次征询通用业务意图。",
                        "closure_test": "新版本须附真实来源/身份映射并解除相应release_blocked_by；当前版本不可手工置true绕过。" if remaining else
                                        "仅限已编译用途；A11检索提示不得升级为标准属性、等价物料或价格结论。"})
    return {"schema_version": "0903-pending-review-v1", "release_version": package["release_version"],
            "previous_release": {"version": old["release_version"], "manifest_sha256": file_digest(previous / "manifest.json"),
                                 "rules_sha256": file_digest(previous / "rules.json")},
            "authority": {"source": "source-update-20261110.json中的A05/A06/A07/A09/A11",
                          "answers": "专家答复表及待答复问题清单中的最新追加答复优先；历史未答栏不重新生效",
                          "catalog": "quota-source-db-20261110.json冻结快照；不是正式原书全量核验",
                          "online_calls": 0},
            "summary": {"reviewed": len(reviews), "states": dict(Counter(r["review_state"] for r in reviews)),
                        "by_family": {f: dict(Counter(r["review_state"] for r in reviews if r["family"] == f)) for f in ("A05", "A06", "A07", "A09", "A11")},
                        "remaining_technical": sum(r["review_state"] != "CLOSED_FOR_DECLARED_USAGE" for r in reviews),
                        "deferred_0904": len([r for r in package["pending_rules"] if r["pending_kind"] == "PHASE_DEFERRED"]),
                        "normalized_rules_total": len(approved),
                        "blocked_policy_rules": sum(bool(r["effect"].get("release_blocked_by")) for r in approved.values())},
            "findings": ["首版95条不是95项未答业务问题：包含限定用途未编码、项目输入和真实证据缺口。",
                         "已答的条件/公式先结构化；只因项目数值尚未提供不阻止生成参数化规则。",
                         "A11按原约定生成单向检索提示，标准或型号属性未核部分仍禁止作为硬事实。",
                         "库名、原文或源范围仍缺依据的策略保持发行级阻断；部分生成不计作技术闭合。",
                         "0904五条来源保持后续；原业务代码、数据库、Dify和模型未变动。"], "records": reviews}


def markdown_review(review):
    def clean(text): return str(text).replace("|", "\\|").replace("\r", "").replace("\n", "<br>")
    s = review["summary"]
    lines = ["# 95条技术待核逐项复核", "", f"版本：`{review['release_version']}`；对照：`{review['previous_release']['version']}`。",
             "", "本表逐条记录原待核原因、已有依据、本次结果和缺失证据。‘已闭合’仅指允许用途的规则定义，仍需项目输入和正常运行校验；‘部分生成’保留发行级阻断，不能据此输出正式套项。", "",
             f"复核{s['reviewed']}条：按声明用途闭合{s['states'].get('CLOSED_FOR_DECLARED_USAGE',0)}条；部分生成但仍阻断{s['states'].get('PARTIALLY_COMPILED_BLOCKED',0)}条；仍未生成{s['states'].get('STILL_BLOCKED',0)}条。0904另有{s['deferred_0904']}条保持后续。", "",
             "| 类别 | 已闭合 | 部分生成仍阻断 | 未生成 |", "|---|---:|---:|---:|"]
    for family, count in s["by_family"].items():
        lines.append(f"| {family} | {count.get('CLOSED_FOR_DECLARED_USAGE',0)} | {count.get('PARTIALLY_COMPILED_BLOCKED',0)} | {count.get('STILL_BLOCKED',0)} |")
    lines += ["", "已有答复不重复提问。正式版本映射、章说明或空白源行的对象说明属于待补资料；设计重量、实际长度、检测量等属于每个项目的输入。未调用网络或业务数据库重新补库，目录核验范围是本地冻结快照。", ""]
    labels = {"CLOSED_FOR_DECLARED_USAGE": "已闭合（限定用途）", "PARTIALLY_COMPILED_BLOCKED": "部分生成，仍阻断", "STILL_BLOCKED": "未生成，保留待核"}
    for family in s["by_family"]:
        lines += [f"## {family}", "", "| 编号及源内容 | 首版为何待核 | 已有依据与本次处理 | 仍缺的依据 | 生成规则 |", "|---|---|---|---|---|"]
        for r in review["records"]:
            if r["family"] != family: continue
            source = "; ".join(f"{k}={v}" for k, v in sorted(r["source_values"].items()))
            result = f"{labels[r['review_state']]}。依据：{'；'.join(r['recorded_answer_ids'])}。{r['result']}"
            missing = "；".join(r["missing_evidence"]) or "本次允许用途无编译阻断。项目字段及检索属性限制见规则；不代表标准条文已全面核验。"
            lines.append("| " + " | ".join(clean(x) for x in [r["source_record_id"] + "<br>" + source, r["original_reason"], result, missing, "、".join(r["generated_rule_ids"]) or "—"]) + " |")
        lines.append("")
    lines += ["## 对照与验收", "", "`pending-review.json`保留95条完整源字段、来源单元格、答复编号、生成规则ID、缺失证据及逐规则输入字段。`test-cases.json`和`validation-report.json`记录固定验收；输出能力由规则的作用类型、条件、发行阻断和输入约束共同决定。", "",
              "取得新证据后建立新版本：补真实条目/版本映射或原文条款→重编译受影响分支→通过正反例与来源校验→在新版本解除阻断。不得编辑旧版文件，不得由模型或一个项目布尔值绕过阻断。", ""]
    return "\n".join(lines)
