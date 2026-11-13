"""Validate the scoped second-round confirmations and follow-up materials."""
from verify import PackageError, evaluate_condition, reads

PV = {f"A06-R{n:03d}" for n in range(72, 78)} | {"A07-R012"}
WIND = {f"A06-R{n:03d}" for n in range(78, 82)}
FILM = {"A06-R010", "A06-R014", "A06-R069"}
NEW_CLOSED = PV | WIND | FILM
OIL_LIB = "DE1000022001"
PV_LIB = "DE06000003"
WIND_LIB = "DE07000022"


def _fail(message):
    raise PackageError("round2 " + message)


def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _libraries(rule):
    return [entry["code"] for entry in rule["library_scope"].get("libraries", [])]


def _check_bound(rule, code, main, target=None):
    effect = rule["effect"]
    if _libraries(rule) != [code] or effect.get("release_blocked_by"):
        _fail("bound library or released status mismatch: " + rule["rule_id"])
    mains = effect.get("main_catalog_references", [])
    if {i["code"] for i in mains} != {main} or any(i["library_code"] != code for i in mains):
        _fail("main catalog binding mismatch: " + rule["rule_id"])
    main_ids = {i["id"] for i in mains}
    if not any(n.get("field") == "selection.main_quota_id" and n.get("op") == "IN" and set(n.get("value", [])) == main_ids for n in _walk(rule["conditions"])):
        _fail("main catalog condition missing: " + rule["rule_id"])
    if target is not None:
        targets = effect.get("catalog_references", [])
        if {i["code"] for i in targets} != {target} or any(i["library_code"] != code for i in targets):
            _fail("target catalog binding mismatch: " + rule["rule_id"])


def _check_film(rule, catalog):
    rid = rule["rule_id"]
    effect = rule["effect"]
    if _libraries(rule) != [OIL_LIB] or effect.get("release_blocked_by"):
        _fail("film library or release mismatch: " + rid)
    refs = effect.get("catalog_references", [])
    expected = {f"3-220{n}" for n in range(2, 8)}
    if {r["code"] for r in refs} != expected or any(r["library_code"] != OIL_LIB or r["unit"] != "10张" for r in refs):
        _fail("film references or units mismatch: " + rid)
    recorded = {(x["code"], x["id"]) for x in catalog if x.get("library_code") == OIL_LIB and x.get("code") in expected}
    if {(x["code"], x["id"]) for x in refs} != recorded:
        _fail("film catalog identity mismatch: " + rid)
    guards = effect.get("execution_guards", [])
    required_true = {"inspection.radiographic.plan_evidence_verified", "inspection.radiographic.target_and_quantity_same_scope_verified", "evidence.target_identity_unit_and_chapter_verified", "evidence.same_work_not_already_charged"}
    if not all(any(g.get("op") == "EQ" and g.get("field") == f and g.get("value") is True for g in guards) for f in required_true):
        _fail("film evidence guard missing: " + rid)
    quantity = "inspection.radiographic.verified_physical_quantity"
    if not any(g.get("op") == "RANGE" and g.get("field") == quantity and g.get("unit") == "张" and g.get("min") == "0" and g.get("include_min") is False for g in guards):
        _fail("film positive quantity guard missing: " + rid)
    formula = effect.get("formula", {})
    expected_formula = {"op": "DIV", "args": [{"op": "READ", "field": quantity, "unit": "张"}, {"op": "CONST", "value": "10", "unit": "张"}]}
    if formula != expected_formula or effect.get("output_unit") != "10张":
        _fail("film quantity conversion changed: " + rid)
    policy = effect.get("inspection_policy", {})
    for key, value in {"automatic_film_selection": False, "target_selection": "EXPLICIT_VERIFIED_DESIGN_TARGET_ONLY", "overlapping_thickness_bands": "DO_NOT_INFER_LOWER_BOUND_OR_AUTO_SELECT", "mixed_specifications": "PARTITION_VERIFIED_QUANTITIES_BY_TARGET_NEVER_REUSE_TOTAL"}.items():
        if policy.get(key) != value: _fail("film policy missing: " + key)
    fields = {"selection.target_quota_id", "inspection.radiographic.film_spec_mm", "inspection.radiographic.wall_thickness_mm"}
    choices = [g for g in guards if g.get("op") == "OR" and fields <= reads(g)]
    if len(choices) != 1 or len(choices[0].get("args", [])) != 6:
        _fail("film explicit target/spec/thickness guard missing: " + rid)
    guard = choices[0]
    ids = {x["code"]: x["id"] for x in refs}
    def outcome(code, spec, thickness):
        return evaluate_condition(guard, {"selection.target_quota_id": ids[code], "inspection.radiographic.film_spec_mm": spec, "inspection.radiographic.wall_thickness_mm": thickness})
    samples = [("3-2202", "80x150", "8", "TRUE"), ("3-2203", "80x150", "8", "TRUE"),
               ("3-2204", "80x300", "8", "TRUE"), ("3-2205", "80x300", "8", "TRUE"),
               ("3-2206", "80x300", "21", "TRUE"), ("3-2207", "80x300", "22", "TRUE"),
               ("3-2203", "80x150", "15", "TRUE"), ("3-2205", "80x300", "15", "TRUE"),
               ("3-2202", "80x300", "8", "FALSE"), ("3-2204", "80x150", "8", "FALSE"),
               ("3-2202", "80x150", "9", "FALSE"), ("3-2204", "80x300", "9", "FALSE"),
               ("3-2203", "80x150", "16", "FALSE"), ("3-2205", "80x300", "16", "FALSE"),
               ("3-2206", "80x300", "22", "FALSE"), ("3-2207", "80x300", "20", "FALSE"),
               ("3-2207", "80x300", "21", "FALSE")]
    if any(outcome(code, spec, thickness) != want for code, spec, thickness, want in samples):
        _fail("film candidate/spec/thickness mismatch or overlap lost: " + rid)
    if evaluate_condition(guard, {"inspection.radiographic.wall_thickness_mm": "8"}) != "UNKNOWN":
        _fail("film inferred without explicit target and specification: " + rid)
    if evaluate_condition(guard, {"selection.target_quota_id": "unknown-target", "inspection.radiographic.film_spec_mm": "80x150", "inspection.radiographic.wall_thickness_mm": "8"}) != "FALSE":
        _fail("film unknown target accepted: " + rid)


def validate_round2_confirmations(source_map, package):
    c = source_map["confirmed_changes"]
    if c.get("schema_version") != "0903-confirmed-changes-v2" or c.get("release_version") != package.get("release_version") or c.get("runtime_activation") is not False or c.get("excluded_phase") != "0904":
        _fail("confirmation identity mismatch")
    decisions = {d["id"]: d for d in c["decisions"]}
    scope = {"D01": {f"A06-R{n:03d}" for n in (64,65,66,67,68,69,70,72,73)}, "D09": {"A06-R070"}, "D12": {"A09-R006","A09-R087","A09-R091"}, "D03_2": {"A06-R072","A06-R073"}, "D02": PV, "D03_1": WIND, "D04": FILM, "D05": {"A05-R021"}, "D06": {"A06-R087"}, "D08": {f"A06-R{n:03d}" for n in range(96, 100)}}
    if len(decisions) != len(c["decisions"]) or set(decisions) != set(scope) or any(set(decisions[k]["rule_ids"]) != ids for k, ids in scope.items()):
        _fail("confirmation scope mismatch")
    if decisions["D02"].get("library_code") != PV_LIB or decisions["D03_1"].get("library_code") != WIND_LIB or decisions["D04"].get("library_code") != OIL_LIB:
        _fail("confirmation library mismatch")
    if set(c["expected_newly_closed_rule_ids"]) != NEW_CLOSED or len(c["expected_newly_closed_rule_ids"]) != len(NEW_CLOSED) or c.get("remaining_technical_count") != 18:
        _fail("closed scope mismatch")
    rules = {r["rule_id"]: r for r in package["approved_rules"]}
    pending = {r["rule_id"]: r for r in package["pending_rules"] if r["pending_kind"] == "TECHNICAL_EVIDENCE"}
    if len(pending) != 18 or NEW_CLOSED & set(pending): _fail("pending scope mismatch")
    title = c["catalog_evidence"]["oil_title_directory"]
    explanation = title.get("description", "")
    if title.get("library_code") != OIL_LIB or "××以上" not in explanation or "不包括" not in explanation or "本身" not in explanation:
        _fail("oil general explanation for strict above-boundary missing")
    catalog = c["catalog_evidence"]["round2_items"]
    for n in (72, 73):
        rid = f"A06-R{n:03d}"
        pv = rules[rid + "-POLICY"]
        _check_bound(pv, PV_LIB, "4-3176", "4-3141" if n == 72 else "4-3143")
        if _libraries(rules[rid + "-OIL2022"]) != [OIL_LIB] or rules[rid + "-OIL2022"]["effect"].get("release_blocked_by"):
            _fail("oil branch altered: " + rid)
        wind = rules[rid + "-WIND_WITHDRAWN"]
        if _libraries(wind) != [WIND_LIB] or wind["effect"].get("type") != "exclude_association": _fail("wind withdrawal lost: " + rid)
    for n in range(74, 78):
        r = rules[f"A06-R{n:03d}-POLICY"]
        _check_bound(r, PV_LIB, "G-b1", f"G-b{n - 37}")
        split = r["effect"].get("capacity_split", {})
        if ("pv.subarray_capacity_mwp" not in r["dependencies"] or "group.design_subarray_id" not in r["dependencies"]
                or split.get("emit_only_target") != f"G-b{n - 37}" or split.get("partition") != "ONE_DESIGN_SUBARRAY_AT_A_TIME"
                or split.get("algorithm") != "REPEAT_MAX_THEN_CEILING_REMAINDER"):
            _fail("PV subarray input or split lost")
    for suffix in ("-POLICY", "-TOTAL"):
        r = rules["A07-R012" + suffix]
        _check_bound(r, PV_LIB, "G-b2", "G-b2")
        expected = "pv_support.design_mass_per_unit_t" if suffix == "-POLICY" else "pv_support.design_total_mass_t"
        if expected not in r["dependencies"] or r["effect"].get("parameter_defaults") is not None:
            _fail("PV support design weight or no-default contract lost")
    for rid in WIND:
        r = rules[rid + "-POLICY"]
        _check_bound(r, WIND_LIB, "F-b4")
        if "wind.turbine_count" not in r["dependencies"] or (rid == "A06-R079" and "wind.transport_km_per_turbine" not in r["dependencies"]):
            _fail("wind actual count or distance missing: " + rid)
        guards = r["effect"].get("execution_guards", [])
        if not any(g.get("op") == "EQ" and g.get("field") == "evidence.main_quota_applicability_verified" and g.get("value") is True for g in guards):
            _fail("wind F-b4 project applicability guard missing: " + rid)
        heights = [g for g in guards if g.get("op") == "RANGE" and g.get("field") == "wind.hub_height_m"]
        if len(heights) != 1 or heights[0].get("unit") != "m" or heights[0].get("min") != "120" or heights[0].get("max") != "130":
            _fail("wind F-b4 height scope missing: " + rid)
        for height, expected in (("119", "FALSE"), ("125", "TRUE"), ("131", "FALSE")):
            if evaluate_condition(heights[0], {"wind.hub_height_m": height}) != expected:
                _fail("wind F-b4 height mismatch: " + rid)
        if evaluate_condition(heights[0], {}) != "UNKNOWN": _fail("wind missing height not unknown: " + rid)
    for rid in FILM: _check_film(rules[rid + "-POLICY"], catalog)
    for rid in scope["D05"] | scope["D06"] | scope["D08"]:
        if rid not in pending: _fail("retained electrical pending rule closed: " + rid)
        affected = [r for r in rules.values() if r["source_record_id"] == rid]
        if not affected or any(rid not in r["effect"].get("release_blocked_by", []) for r in affected):
            _fail("retained electrical blocker missing: " + rid)
    for rid in NEW_CLOSED:
        affected = [r for r in rules.values() if r["source_record_id"] == rid]
        key = "D02" if rid in PV else "D03_1" if rid in WIND else "D04"
        if not any(key in r["effect"].get("confirmation_refs", []) and "confirmed-changes:" + key in r["review_evidence"] for r in affected):
            _fail("scoped confirmation provenance missing: " + rid)


def validate_round2_materials(request, rules, review):
    if request.get("schema_version") != "0903-materials-request-v3" or request.get("release_version") != rules.get("release_version"):
        _fail("materials version mismatch")
    pending = {r["rule_id"]: r for r in rules["pending_rules"] if r["pending_kind"] == "TECHNICAL_EVIDENCE"}
    groups = request["groups"]
    if len(groups) != 12 or {g["id"] for g in groups} != {f"D{n:02d}" for n in range(1, 13)}:
        _fail("materials group identity mismatch")
    if len(pending) != 18 or {i for g in groups for i in g["pending_rule_ids"]} != set(pending):
        _fail("materials pending coverage mismatch")
    baseline = set(request["baseline_rule_ids"])
    if len(baseline) != 32 or set(pending) - baseline or baseline - set(pending) != NEW_CLOSED or request["newly_closed_rule_ids"] != sorted(NEW_CLOSED):
        _fail("materials closure scope mismatch")
    for g in groups:
        rows = g["pending_rule_ids"]
        if len(rows) != len(set(rows)) or not set(rows) <= set(g["rule_ids"]): _fail("materials group dependency mismatch")
        if any(not g.get(k) for k in ("known", "request", "accepted", "already_answered", "completion", "answer")):
            _fail("materials request detail missing")
        if not rows and (g["status"] != "CLOSED" or g["request"] != "无需补充或重复确认。"):
            _fail("answered materials group reopened")
        if rows and g["status"] != "OPEN": _fail("pending group closed")
    index = request["rule_index"]
    if len(index) != 18 or {r["rule_id"] for r in index} != set(pending): _fail("materials index mismatch")
    reviewed = {r["source_record_id"]: r for r in review["records"]}
    for item in index:
        rid = item["rule_id"]; entry = reviewed[rid]
        if item["groups"] != [g["id"] for g in groups if rid in g["pending_rule_ids"]]: _fail("materials index dependency mismatch")
        if item["candidate_checks"] != entry["catalog_checks"] or item["source_refs"] != entry["source_refs"] or item["generated_rule_ids"] != entry["generated_rule_ids"]:
            _fail("materials source evidence mismatch")
        if item["missing_evidence"] != entry["missing_evidence"] or item["pending_scope"] != pending[rid]["conservative_scope"]:
            _fail("materials missing evidence or scope mismatch")
    expected = {"baseline_unique_rules": 32, "unique_rules": 18, "groups": 12, "active_groups": 6, "group_rule_links": 21, "newly_closed": 14, "deferred_0904": 5}
    if request["summary"] != expected or sum(len(g["pending_rule_ids"]) for g in groups) != 21 or sum(bool(g["pending_rule_ids"]) for g in groups) != 6:
        _fail("materials summary mismatch")
    evidence = request["existing_evidence"]
    if evidence["database_read_only"] is not True or evidence["newly_closed_rule_ids"] or any(any(c.values()) for c in evidence["catalog_comparison"].values()):
        _fail("historical catalog evidence altered")
