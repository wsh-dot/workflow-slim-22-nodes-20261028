"""Apply only the four scoped user confirmations to the offline v4 package."""
from copy import deepcopy

from authoring import AND, eq, inside, make, bound, selector_codes, value


OIL_ROWS = {64, 65, 66, 67, 68, 69, 70, 72, 73}
PRIMARY_ROWS = {5, 90}
FALLBACK_ROWS = {6: 5, 87: 86, 91: 90}
AVAILABLE = "coverage.standard_module_available_for_work"
SAME_SCOPE = "coverage.standard_scope_matches_current_work"


def decision(catalog, key):
    return next(d for d in catalog["confirmed_changes"]["decisions"] if d["id"] == key)


def note(rule, *keys):
    rule["revision"] = "4"
    rule["review_evidence"] = list(dict.fromkeys(rule["review_evidence"] + ["confirmed-changes:" + k for k in keys]))
    rule["effect"]["confirmation_refs"] = list(keys)
    return rule


def replace_source_selector(node, source_id, actual_ids):
    if isinstance(node, dict):
        if node.get("field") == "binding.source_rule_id" and node.get("value") == source_id:
            return inside("selection.main_quota_id", actual_ids)
        return {k: replace_source_selector(v, source_id, actual_ids) for k, v in node.items()}
    if isinstance(node, list): return [replace_source_selector(v, source_id, actual_ids) for v in node]
    return node


def bind_actual(rule, row, catalog, library, confirmed):
    rule = deepcopy(rule)
    effect = rule["effect"]
    main = selector_codes(value(row, "main_code"), library, catalog)
    effect["main_catalog_references"] = main
    target = value(row, "related_code")
    if target and not target.startswith("补"):
        effect["catalog_references"] = selector_codes(target, library, catalog)
    rule["conditions"] = replace_source_selector(rule["conditions"], row["rule_id"], [i["id"] for i in main])
    if confirmed:
        effect.pop("source_binding", None)
        effect.pop("release_blocked_by", None)
        effect["review_notes"] = [s for s in effect.get("review_notes", []) if s != "条件/公式已整理；关联证据未闭合，禁止输出正式套项或金额。"]
        effect["review_notes"].append("D01仅确认本源行对应DE1000022001；源书名原值保留，不建立全局刊名别名。")
    return bound(rule, library, catalog)


def fallback_contract(primary, role):
    return {"primary_source_record_id": primary, "role": role,
            "assessment_unit": "SAME_OBJECT_AND_SAME_WORK_SCOPE_NOT_WHOLE_OBJECT",
            "available_field": AVAILABLE, "same_scope_field": SAME_SCOPE,
            "true": "PRIMARY_COVERS_THIS_WORK", "false": "VERIFIED_NO_APPLICABLE_PRIMARY_COVERAGE_FOR_THIS_WORK",
            "unknown": "NEEDS_INPUT_NO_FALLBACK",
            "insufficient_evidence": ["RETRIEVAL_ZERO_HITS", "UNAUTHORIZED_LIBRARY", "RETRIEVAL_ERROR", "UNREVIEWED_CANDIDATE", "UNKNOWN_COVERAGE"],
            "partial_coverage": "ASSESS_COVERED_AND_UNCOVERED_WORK_SCOPES_SEPARATELY_NO_RECHARGE",
            "stage_precedence": "EXPLICIT_OBJECT_SPECIFIC_CHAIN_WITHIN_EXISTING_STAGE_AND_ALLOWED_SCOPE_CHECKS"}


def revise(row, catalog, rules, state, reason):
    if not catalog.get("confirmed_changes"): return rules, state, reason
    family, n = row["sheet"], row["row"]
    if family == "A-06" and n in OIL_ROWS:
        if row["rule_id"] not in decision(catalog, "D01")["rule_ids"]: raise ValueError("unconfirmed oil row")
        if n == 70:
            effect = {"type": "exclude_association", "pair_key": row["rule_id"], "target_kind": "SUPPLEMENT",
                      "display_name": value(row, "related_name"), "preserve_physical_item": True,
                      "policy": "WITHDRAW_THIS_ROW_TRENCH_ONLY_KEEP_PIPE_INSTALLATION_TRENCH",
                      "review_notes": ["D09取消本行土方关联；原10×0.7×1.8和1m修正算例仅保留来源历史，不作数量公式。",
                                       "防腐10m²不得当管长m；保留管道安装行既有土方规则，按实际范围核实并扣同沟已计量，不推定土方已经计取。"]}
            rule = make(row, "-POLICY", eq("binding.source_rule_id", row["rule_id"]), effect, usage=["QUOTA_MATCH", "COST_COVERAGE"])
            return [note(bound(rule, "DE1000022001", catalog), "D01", "D09")], "COMPILED_EXCLUSION", "D01库对应已确认；D09撤销本行土方关联，保留原文和旧算例追溯，面积不换算成管长。"
        if n in (72, 73):
            oil = bind_actual(rules[0], row, catalog, "DE1000022001", True)
            oil["rule_id"] = row["rule_id"] + "-OIL2022"
            note(oil, "D01")
            pv = bind_actual(rules[0], row, catalog, "DE06000003", False)
            pv["effect"]["review_notes"] = ["本分支仅为光伏DE06000003候选；D02指南身份对应仍缺，保留发行级阻断。"]
            note(pv, "D01", "D03_2")
            effect = {"type": "exclude_association", "pair_key": row["rule_id"], "select_actual_item": False,
                      "catalog_references": selector_codes(value(row, "related_code"), "DE07000022", catalog),
                      "policy": "WITHDRAW_ONLY_THIS_SOURCE_ROW_WIND_ASSOCIATION",
                      "review_notes": ["D03②仅取消本行风电分支；4-3176缺失，不影响石油/光伏分支或其他风电规则。"]}
            wind = bound(make(row, "-WIND_WITHDRAWN", AND(eq("binding.source_rule_id", row["rule_id"]),
                         eq("selection.main_quota_code", "4-3176")), effect), "DE07000022", catalog)
            note(wind, "D03_2")
            return [oil, pv, wind], "PARTIAL_COMPILED", "仅光伏分支仍缺光伏2022指南与DE06000003的正式版本映射；石油分支已由D01确认，风电分支按D03②撤销，不再索要风电4-3176。"
        result = [note(bind_actual(r, row, catalog, "DE1000022001", True), "D01") for r in rules]
        if n == 69:
            for r in result: r["effect"]["release_blocked_by"] = [row["rule_id"]]
            return result, "PARTIAL_COMPILED", "D01库映射已确认；仍缺D04射线探伤胶片规格选择条款，同壁厚不能确定胶片尺寸。"
        return result, "COMPILED", "D01仅限本行的库对应已确认并绑定真实主/关联子目；保留原数量条件、单位、适用及防重守卫。"
    if family == "A-09" and n in PRIMARY_ROWS:
        for r in rules:
            r["conditions"] = AND(r["conditions"], eq(SAME_SCOPE, True), eq(AVAILABLE, True))
            r["effect"]["fallback_contract"] = fallback_contract(row["rule_id"], "PRIMARY")
            r["effect"]["exclusive_group"] = "D12-" + row["rule_id"]
            note(r, "D12")
        return rules, state, "D12为本工作范围补首级覆盖已核实条件，与新增第二级路径互斥；其余原守卫保留。"
    if family == "A-09" and n in FALLBACK_ROWS:
        primary_id = f"A09-R{FALLBACK_ROWS[n]:03d}"
        primary = catalog["source_rows_by_id"][primary_id]
        clauses = [eq("context.route_subject", value(primary, "subject")), eq(SAME_SCOPE, True), eq(AVAILABLE, False)]
        if n == 6: clauses.append(eq("context.location", "offsite"))
        if n == 87: clauses.append(eq("coverage.corrosion_work_included", False))
        if n == 91:
            clauses += [eq("object.kind", "crossing"), eq("crossing.separate_drawing", True),
                        eq("coverage.crossing_work_included", False), eq("coverage.supplement_basis_verified", True)]
        effect = {"type": "select_pricing_method", "target_label": value(row, "target"),
                  "within_allowed_scope_only": True, "target_mapping_required": True, "select_actual_item": False,
                  "on_missing_target": "NEEDS_INPUT", "verify_actual_work_coverage": True,
                  "exclusive_group": "D12-" + primary_id,
                  "fallback_contract": fallback_contract(primary_id, "FALLBACK"),
                  "review_notes": ["仅D12确认的本行继承对象；空白原单元格不改写。不用检索0命中或覆盖未知触发回退。"]}
        if n == 6:
            effect["fallback_contract"]["routing_rule_ids"] = ["A05-R010", "A05-R010-BORROW", "A05-R011"]
        if n == 87:
            effect["policy"] = "ONLY_CORROSION_WORK_NOT_INCLUDED_BY_PRIMARY_OR_MAIN_PROFESSION"
            effect["fallback_contract"]["primary_role"] = "COVERAGE_CHECK_NOT_PRIMARY_METHOD_SELECTION"
        if n == 91:
            scope = catalog["confirmed_changes"]["catalog_evidence"]["crossing_directory"]
            descendants = [d["id"] for d in catalog["directories"] if d["library_code"] == "DE1000022001" and (d["bsid"] == scope["bsid"] or d["bsid"].startswith(scope["bsid"] + "."))]
            effect["target_label"] += " 第九章第二节 管道穿跨越工程"
            effect["target_directory_scope"] = {"library_code": "DE1000022001", "root_id": scope["id"], "directory_ids": sorted(descendants)}
            effect["execution_guards"] = [inside("selection.target_directory_id", sorted(descendants))]
            effect["note_in_estimate_required"] = True
        rule = bound(make(row, "", AND(*clauses), effect, usage=["QUOTA_MATCH", "COST_COVERAGE"]), "DE1000022001", catalog)
        return [note(rule, "D12")], "COMPILED", "D12明确本行是指定专业的第二级依据；仅在同一工作范围首级已核实未覆盖且防重/AllowedScope/适用守卫通过后选择路径，不自动生成子目。"
    return rules, state, reason
