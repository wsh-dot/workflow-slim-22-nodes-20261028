"""按真实单项工程范围隔离CBS证据；每个范围复用专业与直接父工程两轮匹配。"""
from __future__ import annotations

import copy
import json
import unicodedata
from collections import Counter
from uuid import uuid4
from jsonschema import Draft202012Validator, ValidationError
from quantity import ancestors

PHYSICAL = {"item", "assembly", "component"}
PERSISTED = PHYSICAL | {"pending"}


def _possible_evidence_errors(output, context, candidates):
    """核对可能归属的原文引文；工程关系的语义由一次定向复核负责。"""
    sources = {"header.project_section": context["header"].get("project_section")}
    sources.update({f"internalSections[{i}].title": s["title"] for i, s in enumerate(context["internalSections"])})
    sources.update({"match_context." + key: value for key, value in list(sources.items())})
    profession_only = {str(context["header"].get(key) or "").strip() for key in ("specialty_name", "table_type")}
    normalize = lambda text: "".join(unicodedata.normalize("NFKC", text).split())
    by_parent = {c["parent_id"]: c for c in candidates}
    errors = []
    for evaluation in output["evaluations"]:
        if evaluation["judgment"] != "possible":
            continue
        support = evaluation.get("possible_support", [])
        candidate = by_parent[evaluation["parent_id"]]
        terms = [candidate["parent_name"], *candidate["parent_path"][1:-1]]
        valid = bool(support)
        for evidence in support:
            source = sources.get(evidence["ref"])
            quote = evidence["quote"].strip()
            term = normalize(evidence.get("candidate_term", ""))
            valid = valid and (isinstance(source, str) and bool(quote) and quote in source
                              and quote not in profession_only and evidence["ref"] in evaluation["evidence_refs"]
                              and bool(evidence["missing_information"].strip()) and len(term) >= 2
                              and term not in {normalize(s) for s in profession_only}
                              and term in normalize(quote) and any(term in normalize(name) for name in terms))
        if not valid:
            errors.append({"parent_id": evaluation["parent_id"], "code": "POSSIBLE_WITHOUT_IDENTITY_EVIDENCE",
                           "candidate_terms": terms,
                           "message": "可能匹配须引用当前范围真实的工程身份证据，candidate_term须同时出现在候选工程名及引文中，并说明尚缺什么；未明确排除、专业相同不构成正面依据"})
    return errors


def _parent_decision_errors(output, context, candidates):
    """核对事实来源、候选关系和整体结论；引文真实不等于语义必然正确。"""
    sources = {"match_context.header.project_section": context["header"].get("project_section")}
    sources.update({f"match_context.internalSections[{i}].title": s["title"]
                    for i, s in enumerate(context["internalSections"])})
    sources.update({key.removeprefix("match_context."): value for key, value in list(sources.items())})
    errors, facts = [], {}

    def reject(code, message, **details):
        errors.append({"code": code, "message": message, **details})

    for fact in output["scope_facts"]:
        source, quote = sources.get(fact["ref"]), fact["quote"]
        if fact["fact_id"] in facts:
            reject("DUPLICATE_SCOPE_FACT", "范围事实标识重复")
        facts[fact["fact_id"]] = fact
        if not isinstance(source, str) or not quote.strip() or quote not in source:
            reject("INVALID_SCOPE_FACT", "范围事实须逐字引用当前范围的工程原文", fact_id=fact["fact_id"])
    allowed_relations = {"match": {"identity"}, "possible": {"unresolved"},
                         "no_match": {"location_only", "different_identity"}}
    for evaluation in output["evaluations"]:
        refs = evaluation["fact_ids"]
        if not set(refs) <= facts.keys():
            reject("UNKNOWN_SCOPE_FACT", "候选引用不存在的范围事实", parent_id=evaluation["parent_id"])
            continue
        cited = [facts[key] for key in refs]
        if evaluation["relation"] not in allowed_relations[evaluation["judgment"]]:
            reject("RELATION_JUDGMENT_CONFLICT", "候选关系与匹配判断不一致", parent_id=evaluation["parent_id"])
        if not {f["ref"].removeprefix("match_context.") for f in cited} <= {
                ref.removeprefix("match_context.") for ref in evaluation["evidence_refs"]}:
            reject("FACT_REFERENCE_MISMATCH", "候选证据字段未覆盖引用事实", parent_id=evaluation["parent_id"])
        roles = {f["role"] for f in cited}
        if evaluation["judgment"] == "match" and "engineering_identity" not in roles:
            reject("MATCH_WITHOUT_IDENTITY_FACT", "明确匹配必须引用工程身份事实，位置或专业不能单独证明归属",
                   parent_id=evaluation["parent_id"])
        if evaluation["relation"] == "location_only" and "location" not in roles:
            reject("LOCATION_WITHOUT_FACT", "仅位置关系必须引用位置事实", parent_id=evaluation["parent_id"])
        if evaluation["relation"] == "different_identity" and "engineering_identity" not in roles:
            reject("EXCLUSION_WITHOUT_IDENTITY", "排除其他工程须引用当前范围明确的工程身份", parent_id=evaluation["parent_id"])

    decision = output["scope_decision"]
    candidate_ids = {candidate["parent_id"] for candidate in candidates}
    matches = {e["parent_id"] for e in output["evaluations"] if e["judgment"] == "match"}
    possible = {e["parent_id"] for e in output["evaluations"] if e["judgment"] == "possible"}
    contenders = set(decision["contender_parent_ids"])
    if contenders != matches | possible or not contenders <= candidate_ids:
        reject("CONTENDER_COVERAGE_MISMATCH", "整体结论必须完整保留明确或可能匹配的候选，不能隐藏竞争工程")
    if decision["status"] == "matched":
        if (output["context_status"] != "sufficient" or len(matches) != 1 or possible
                or decision["selected_parent_id"] not in matches):
            reject("INVALID_UNIQUE_DECISION", "整体唯一结论与证据状态或逐候选判断不一致")
    elif decision["selected_parent_id"] is not None:
        reject("UNRESOLVED_WITH_SELECTION", "未确定的整体结论不能指定目标工程")
    if decision["status"] == "ambiguous" and len(contenders) < 2:
        reject("AMBIGUITY_WITHOUT_CONTENDERS", "真实候选歧义须保留至少两个竞争工程")
    if decision["status"] == "no_candidate" and contenders:
        reject("NO_CANDIDATE_WITH_CONTENDERS", "无合适候选不能同时保留匹配候选")
    return errors


def partition_scopes(raw, rows):
    """仅用已校验的真实结构划分范围；成套内部的技术章节不拆CBS归属。"""
    groups = {}
    for r, row in rows.items():
        if row["role"] not in PERSISTED:
            continue
        chain = ancestors(rows, r)
        physical = [a for a in chain if rows[a]["role"] in PHYSICAL]
        anchor = physical[-1] if physical else r
        if physical and any(rows[a]["role"] == "project" for a in chain[:chain.index(anchor)]):
            raise ValueError("成套设备内部出现另一个工程范围，不能继承父设备的CBS")
        scope_chain = ancestors(rows, anchor)
        owner = next((a for a in scope_chain if rows[a]["role"] in {"project", "section"}), None)
        groups.setdefault(owner, []).append(r)
    return groups


def match_scopes(header, prepared_header, raw, rows, cbs_nodes, config, trace, schemas, call_model, error_cls):
    """每个范围分别两轮判断；逐行返回结果，不用某个命中范围填补另一范围。"""
    groups = partition_scopes(raw, rows)
    multiple = len(groups) > 1
    results, by_row = [], {}
    cbs = {node["id"]: node for node in cbs_nodes}
    if len(cbs) != len(cbs_nodes):
        raise error_cls("项目 CBS ID 重复")
    def match_scope(unit):
        index, (scope, members) = unit
        scope_trace = trace.scoped(scope_id=index, scope_root=scope)
        chain = list(reversed(ancestors(rows, scope))) + [scope] if scope is not None else []
        sections = [{"r": r, "title": raw[r].get("description")} for r in chain if rows[r]["role"] in {"project", "section"}]
        context = {"header": copy.deepcopy(prepared_header), "internalSections": sections,
                   "scope_source": "internal_sections" if sections else "header"}
        if multiple and scope is None:
            # 无归属明细不能仅凭整份文件封面名称套用某一个已识别单项工程。
            outcome = {"project_cbs_id": None, "cbs_reason": "料表存在多个工程范围，本行所属范围未确定", "match_context": context}
        else:
            outcome = _match_unit(header, context, copy.deepcopy(cbs_nodes), config, scope_trace, schemas, call_model, error_cls,
                                  f"_{index:03d}" if multiple else "")
        target = outcome["project_cbs_id"]
        path = None
        if target:
            node = cbs[target]
            path = " / ".join([cbs[node["parent_id"]]["name"], node["name"]])
        unit = {"scope_root": scope, "source_rows": list(members), "scope_title": raw[scope].get("description") if scope else None,
                **outcome, "cbs_path": path}
        return unit

    results = [match_scope(unit) for unit in enumerate(groups.items(), 1)]
    for unit in results:
        for r in unit['source_rows']:
            by_row[r] = {k: unit[k] for k in ("scope_root", "scope_title", "project_cbs_id", "cbs_reason", "cbs_path")}
    targets = {result["project_cbs_id"] for result in results}
    shared = next(iter(targets)) if len(targets) == 1 else None
    trace.write("cbs_scope_decisions", matching_units=results, cbs_by_row=by_row)
    return {"project_cbs_id": shared, "cbs_reason": results[0]["cbs_reason"] if len(results) == 1 else f"按{len(results)}个工程范围分别判断",
            "match_context": results[0]["match_context"] if len(results) == 1 else {"header": copy.deepcopy(prepared_header), "internalSections": []},
            "matching_units": results, "cbs_by_row": by_row}


def _match_unit(header, context, cbs_nodes, config, trace, schemas, call_model, error_cls, stage_suffix=""):
    context_id = str(uuid4())
    evidence_ref_paths = ["match_context.header." + key for key, value in context["header"].items()
                          if isinstance(value, str) and value.strip()]
    evidence_ref_paths += [f"match_context.internalSections[{i}].title" for i, section in enumerate(context["internalSections"]) if section["title"]]
    cbs = {node["id"]: node for node in cbs_nodes}
    if len(cbs) != len(cbs_nodes):
        raise error_cls("项目 CBS ID 重复")
    parents = {node.get("parent_id") for node in cbs_nodes}
    candidates = [{"leaf_id": node["id"], "leaf_name": node.get("name")} for node in cbs_nodes
                  if node.get("category_name") == "单位工程" and node["id"] not in parents]
    target, reason, leaf, parent = None, "没有单位工程候选", None, None

    def validate_cbs(response_text, candidates, schema_name):
        """验证全候选覆盖与真实原文字段；同名判断冲突留给未挂接分支。"""
        try:
            output = json.loads(response_text)
            Draft202012Validator(schemas[schema_name]).validate(output)
        except (ValueError, ValidationError) as exc:
            raise error_cls("CBS 输出结构非法：" + str(exc)) from exc
        ids = [candidate["leaf_id"] for candidate in candidates]
        evaluations = output["evaluations"]
        if output["context_id"] != context_id or Counter(e["leaf_id"] for e in evaluations) != Counter(ids):
            raise error_cls("CBS context_id 或候选覆盖不符")
        valid_refs = {"header." + k for k, v in context["header"].items() if isinstance(v, str) and v.strip()}
        valid_refs |= {f"internalSections[{i}].title" for i, section in enumerate(context["internalSections"]) if section["title"]}
        valid_refs |= {"match_context." + path for path in list(valid_refs)}
        by_id = {c["leaf_id"]: c for c in candidates}
        for evaluation in evaluations:
            if not set(evaluation["evidence_refs"]) <= valid_refs:
                raise error_cls("CBS evidence_refs 引用不存在或没有原文的字段")
            if evaluation["judgment"] == "match" and not evaluation["evidence_refs"]:
                raise error_cls("CBS match 缺少原文证据")
            if schema_name == "cbs-parent-output" and evaluation["parent_id"] != by_id[evaluation["leaf_id"]]["parent_id"]:
                raise error_cls("CBS 父轮改写了真实父节点")
        return output

    if candidates:
        profession_groups = {}
        for candidate in candidates:
            name = candidate["leaf_name"]
            if not isinstance(name, str) or not name.strip():
                raise error_cls("CBS单位工程候选缺少有效名称")
            name = name.strip()
            group = profession_groups.setdefault(name, {"leaf_id": candidate["leaf_id"], "leaf_name": name,
                                                         "member_leaf_ids": []})
            group["member_leaf_ids"].append(candidate["leaf_id"])
        requested_professions = [{key: group[key] for key in ("leaf_id", "leaf_name")}
                                 for group in profession_groups.values()]
        trace.write("cbs_leaf_group_plan", stage="cbs_leaf" + stage_suffix, match_context=context,
                    candidate_count=len(candidates), group_count=len(requested_professions),
                    groups=list(profession_groups.values()))
        leaf_input = {"file_id": header.get("file_id"), "context_id": context_id,
                      "match_context": copy.deepcopy(context), "evidence_ref_paths": evidence_ref_paths,
                      "candidates": requested_professions}
        leaf_response = call_model((config.prompt_dir / 'cbs-leaf.txt').read_text(encoding='utf-8'), leaf_input,
                                   schemas["cbs-leaf-output"], config, trace, "cbs_leaf" + stage_suffix)
        leaf = validate_cbs(leaf_response, requested_professions, "cbs-leaf-output")
        evaluations_by_representative = {e["leaf_id"]: e for e in leaf["evaluations"]}
        leaf["evaluations"] = [
            {**copy.deepcopy(evaluations_by_representative[profession_groups[c["leaf_name"].strip()]["leaf_id"]]),
             "leaf_id": c["leaf_id"]} for c in candidates]
        leaf = validate_cbs(json.dumps(leaf, ensure_ascii=False), candidates, "cbs-leaf-output")
        judgments = {e["leaf_id"]: e["judgment"] for e in leaf["evaluations"]}
        name_judgments = {}
        for candidate in candidates:
            name_judgments.setdefault((candidate["leaf_name"] or "").strip(), set()).add(judgments[candidate["leaf_id"]])
        kept = [c for c in candidates if judgments[c["leaf_id"]] in {"match", "possible"}]
        if any(len(j) != 1 for j in name_judgments.values()):
            reason = "首轮同名单位工程判断冲突"
        elif leaf["context_status"] == "conflicting":
            reason = "首轮原文工程范围冲突"
        elif not kept:
            reason = "首轮没有保留候选"
        elif any(not cbs[c["leaf_id"]].get("parent_id") or cbs[c["leaf_id"]]["parent_id"] not in cbs
                 or not cbs[cbs[c["leaf_id"]]["parent_id"]].get("name") for c in kept):
            reason = "保留候选缺少直接父节点资料"
        else:
            def parent_path(parent_id):
                path, seen = [], set()
                while parent_id is not None:
                    if parent_id in seen or parent_id not in cbs:
                        raise error_cls("CBS父链循环或缺少祖先节点")
                    seen.add(parent_id)
                    node = cbs[parent_id]
                    path.append(node.get("name") or "")
                    parent_id = node.get("parent_id")
                return list(reversed(path))

            parent_candidates = [{**c, "parent_id": cbs[c["leaf_id"]]["parent_id"],
                                  "parent_name": cbs[cbs[c["leaf_id"]]["parent_id"]]["name"],
                                  "parent_path": parent_path(cbs[c["leaf_id"]]["parent_id"]),
                                  "leaf_judgment": judgments[c["leaf_id"]]} for c in kept]
            # Parent identity is shared by its professions. Evaluate it once,
            # without letting a sibling's uncertain profession change the scope.
            unique_parents = {}
            for candidate in parent_candidates:
                unique_parents.setdefault(candidate["parent_id"], {key: candidate[key] for key in
                    ("leaf_id", "parent_id", "parent_name", "parent_path")})
            requested_parents = list(unique_parents.values())
            parent_input = {"file_id": header.get("file_id"), "context_id": context_id,
                            "match_context": copy.deepcopy(context), "evidence_ref_paths": evidence_ref_paths, "candidates": requested_parents}
            fact_refs = [ref for ref in evidence_ref_paths if ref == "match_context.header.project_section"
                         or ref.startswith("match_context.internalSections[")]
            parent_input["scope_fact_ref_paths"] = fact_refs
            parent_input["output_contract"] = {
                "context_id": context_id,
                "required_fields": list(schemas["cbs-parent-output"]["required"]),
                "required_evaluation_fields": list(schemas["cbs-parent-output"]["properties"]["evaluations"]["items"]["required"]),
                "fact_reference_fields": {"scope_facts[].fact_id": "字符串，定义一个事实标识",
                                          "evaluations[].fact_ids": "字符串数组，引用已定义的事实标识；字段名必须是复数fact_ids"},
                "instruction": "必须原样返回本次context_id及全部必需字段；每条evaluations都必须包含fact_ids数组，不能写成fact_id。"
                               "scope_facts.ref只允许scope_fact_ref_paths中的字段，不能引用专业字段。"}
            parent_schema = copy.deepcopy(schemas["cbs-parent-output"])
            if fact_refs:
                parent_schema["properties"]["scope_facts"]["items"]["properties"]["ref"]["enum"] = fact_refs
            parent_response = call_model((config.prompt_dir / 'cbs-parent.txt').read_text(encoding='utf-8'), parent_input,
                                         parent_schema, config, trace, "cbs_parent" + stage_suffix)
            parent = validate_cbs(parent_response, requested_parents, "cbs-parent-output")
            if any(e["judgment"] == "possible" for e in parent["evaluations"]):
                errors = (_possible_evidence_errors(parent, context, requested_parents)
                          + _parent_decision_errors(parent, context, requested_parents))
                # 即使引文确实存在，也须复核它是否支持候选工程身份，不能只验证字段路径。
                review_input = {**parent_input, "review": {"previous_output": copy.deepcopy(parent), "errors": errors,
                    "instruction": "逐一复核可能匹配的正面工程依据。没有明确排除不是支持证据，专业相同不是工程相同。"
                                   "按当前范围及标题优先级重新输出全部候选；有真实歧义继续possible，缺失身份承认insufficient，不能为唯一命中猜选。"}}
                trace.write("cbs_parent_review_requested", match_context=context, previous_output=parent, errors=errors)
                review_response = call_model((config.prompt_dir / 'cbs-parent.txt').read_text(encoding='utf-8'), review_input,
                                             parent_schema, config, trace, "cbs_parent_review" + stage_suffix)
                try:
                    parent = validate_cbs(review_response, requested_parents, "cbs-parent-output")
                    errors = (_possible_evidence_errors(parent, context, requested_parents)
                              + _parent_decision_errors(parent, context, requested_parents))
                except error_cls:
                    errors = [{"code": "INVALID_PARENT_REVIEW", "message": "CBS父轮复核未通过候选与原文引用校验"}]
                    parent = None
                if errors:
                    reason = "父轮可能匹配缺少有效工程证据，复核后仍未确定" if parent else "父轮复核结果未通过校验"
                    trace.write("cbs_parent_review_unresolved", match_context=context, errors=errors, parent_output=parent)
                    trace.write("cbs_decision", match_context=context, candidates=candidates, leaf_output=leaf,
                                parent_output=parent, project_cbs_id=None, reason=reason)
                    return {"project_cbs_id": None, "cbs_reason": reason, "match_context": context}
            decision_errors = _parent_decision_errors(parent, context, requested_parents)
            trace.write("cbs_parent_decision_checked", match_context=context, errors=decision_errors,
                        scope_facts=parent["scope_facts"], scope_decision=parent["scope_decision"])
            if decision_errors:
                reason = "父轮范围事实、候选关系与整体结论不一致，保留未挂接"
                trace.write("cbs_decision", match_context=context, candidates=candidates, leaf_output=leaf,
                            parent_output=parent, project_cbs_id=None, reason=reason)
                return {"project_cbs_id": None, "cbs_reason": reason, "match_context": context}
            evaluations_by_parent = {e["parent_id"]: e for e in parent["evaluations"]}
            parent["evaluations"] = [{**evaluations_by_parent[c["parent_id"]], "leaf_id": c["leaf_id"]}
                                     for c in parent_candidates]
            parent_judgments = {e["leaf_id"]: e["judgment"] for e in parent["evaluations"]}
            groups = {}
            for candidate in parent_candidates:
                for key in (("id", candidate["parent_id"]),
                            ("path", tuple(name.strip() for name in candidate["parent_path"]))):
                    groups.setdefault(key, set()).add(parent_judgments[candidate["leaf_id"]])
            matches = [e for e in parent["evaluations"] if e["judgment"] == "match"]
            definite = [e for e in matches if judgments[e["leaf_id"]] == "match"]
            if any(len(j) != 1 for j in groups.values()):
                reason = "父轮相同父节点或同名父范围判断冲突"
            elif leaf["context_status"] != "sufficient" or parent["context_status"] != "sufficient":
                reason = "两轮证据不足或存在冲突"
            elif parent["scope_decision"]["status"] != "matched":
                reason = "父轮整体归属未确定：" + parent["scope_decision"]["status"]
            elif len({e["parent_id"] for e in matches}) != 1 or any(e["judgment"] == "possible" for e in parent["evaluations"]):
                reason = "父轮未能唯一明确匹配"
            elif not definite:
                reason = "父轮唯一候选在首轮未明确匹配"
            elif len(definite) != 1:
                reason = "同一父范围下多个单位工程明确匹配"
            else:
                target, reason = definite[0]["leaf_id"], "两轮证据充分且唯一匹配单位工程"
    trace.write("cbs_decision", match_context=context, candidates=candidates, leaf_output=leaf,
                parent_output=parent, project_cbs_id=target, reason=reason)
    return {"project_cbs_id": target, "cbs_reason": reason, "match_context": context}
