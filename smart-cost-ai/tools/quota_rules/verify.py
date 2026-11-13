"""Read-only offline verifier for a quota resource release; no service imports."""
from collections import Counter
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
from pathlib import Path


class PackageError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value): return hashlib.sha256(canonical(value)).hexdigest()
def file_digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def strict_json(text):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result: raise PackageError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs, parse_constant=lambda s: (_ for _ in ()).throw(PackageError(s)))


def reads(node):
    result = set()
    if isinstance(node, dict):
        if "field" in node: result.add(node["field"])
        for value in node.values(): result.update(reads(value))
    elif isinstance(node, list):
        for value in node: result.update(reads(value))
    return result


def number(value):
    if not isinstance(value, str): raise PackageError("decimal must be a string")
    try: result = Decimal(value)
    except InvalidOperation as exc: raise PackageError("invalid decimal") from exc
    if not result.is_finite(): raise PackageError("non-finite decimal")
    return result


def condition_shape(node, fields, units):
    if not isinstance(node, dict): raise PackageError("condition must be an object")
    op = node.get("op")
    if op in ("AND", "OR"):
        if set(node) != {"op", "args"} or not node["args"]: raise PackageError("empty/invalid boolean group")
        for child in node["args"]: condition_shape(child, fields, units)
    elif op == "NOT":
        if set(node) != {"op", "arg"}: raise PackageError("invalid NOT")
        condition_shape(node["arg"], fields, units)
    elif op in ("EQ", "IN", "HAS_ANY"):
        if set(node) != {"op", "field", "value"}: raise PackageError("invalid comparison")
        if node["field"] not in fields: raise PackageError("unknown condition field")
        spec = fields[node["field"]]
        vals = node["value"] if op in ("IN", "HAS_ANY") else [node["value"]]
        if not isinstance(vals, list) or not vals: raise PackageError("invalid IN")
        for v in vals:
            if spec["type"] == "boolean" and type(v) is not bool: raise PackageError("invalid boolean")
            if spec["type"] == "string" and not isinstance(v, str): raise PackageError("invalid string")
            if op == "HAS_ANY" and (spec["type"] != "string_set" or not isinstance(v, str)): raise PackageError("invalid kind set")
    elif op == "RANGE":
        if set(node) != {"op", "field", "unit", "min", "max", "include_min", "include_max"}: raise PackageError("invalid range")
        if node["field"] not in fields or fields[node["field"]]["unit"] != node["unit"]: raise PackageError("range field/unit mismatch")
        if node["unit"] not in units: raise PackageError("unknown range unit")
        low, high = [number(node[k]) if node[k] is not None else None for k in ("min", "max")]
        if low is None and high is None: raise PackageError("unbounded range")
        if low is not None and high is not None and low > high: raise PackageError("reversed range")
        if type(node["include_min"]) is not bool or type(node["include_max"]) is not bool: raise PackageError("invalid endpoint")
    else: raise PackageError(f"unsupported condition op: {op}")


def dimension(node, fields, units):
    op = node.get("op")
    if op in ("CONST", "READ"):
        keys = {"op", "unit", "value" if op == "CONST" else "field"}
        if set(node) != keys or node["unit"] not in units: raise PackageError("invalid expression leaf")
        if op == "CONST": number(node["value"])
        elif node["field"] not in fields or fields[node["field"]]["unit"] != node["unit"]: raise PackageError("expression field/unit mismatch")
        return units[node["unit"]]["dimension"]
    if op not in ("ADD", "SUB", "MUL", "DIV") or set(node) != {"op", "args"}: raise PackageError(f"unsupported formula op: {op}")
    args = node["args"]
    if len(args) < 2 or op in ("DIV", "SUB") and len(args) != 2: raise PackageError("invalid arity")
    dims = [dimension(arg, fields, units) for arg in args]
    if op in ("ADD", "SUB"):
        if any(d != dims[0] for d in dims): raise PackageError("incompatible addition dimensions")
        return dims[0]
    out = Counter(dims[0])
    for d in dims[1:]:
        for k, v in d.items(): out[k] += v * (-1 if op == "DIV" else 1)
    if op == "DIV" and args[1]["op"] == "CONST" and number(args[1]["value"]) == 0: raise PackageError("constant zero divisor")
    return {k: v for k, v in out.items() if v}


def formulas(node):
    if isinstance(node, dict):
        if "op" in node and node["op"] not in ("CONST", "READ", "ADD", "SUB", "MUL", "DIV", "EQ", "IN", "HAS_ANY", "RANGE", "AND", "OR", "NOT"):
            raise PackageError("unsupported embedded op: " + str(node["op"]))
        if node.get("op") in ("CONST", "READ", "ADD", "SUB", "MUL", "DIV"):
            yield node
        else:
            for v in node.values(): yield from formulas(v)
    elif isinstance(node, list):
        for v in node: yield from formulas(v)


def fact_value(facts, key):
    raw = facts.get(key)
    if isinstance(raw, dict):
        if raw.get("state") == "CONFLICT": return "__CONFLICT__"
        if raw.get("state") != "KNOWN": return None
        return raw.get("value")
    return raw


def evaluate_condition(node, facts):
    op = node["op"]
    if op in ("AND", "OR"):
        results = [evaluate_condition(child, facts) for child in node["args"]]
        if "CONFLICT" in results: return "CONFLICT"
        if op == "AND": return "FALSE" if "FALSE" in results else "UNKNOWN" if "UNKNOWN" in results else "TRUE"
        return "TRUE" if "TRUE" in results else "UNKNOWN" if "UNKNOWN" in results else "FALSE"
    if op == "NOT":
        return {"TRUE": "FALSE", "FALSE": "TRUE", "UNKNOWN": "UNKNOWN", "CONFLICT": "CONFLICT"}[evaluate_condition(node["arg"], facts)]
    raw = fact_value(facts, node["field"])
    if raw == "__CONFLICT__": return "CONFLICT"
    if raw is None: return "UNKNOWN"
    if op == "EQ": return "TRUE" if type(raw) is type(node["value"]) and raw == node["value"] else "FALSE"
    if op == "IN": return "TRUE" if raw in node["value"] else "FALSE"
    if op == "HAS_ANY":
        if not isinstance(raw, list) or any(not isinstance(v, str) for v in raw): raise PackageError("invalid kind set fact")
        return "TRUE" if set(raw) & set(node["value"]) else "FALSE"
    if op == "RANGE":
        val = number(raw)
        if node["min"] is not None:
            lo = number(node["min"])
            if val < lo or val == lo and not node["include_min"]: return "FALSE"
        if node["max"] is not None:
            hi = number(node["max"])
            if val > hi or val == hi and not node["include_max"]: return "FALSE"
        return "TRUE"
    raise PackageError("invalid condition")


def evaluate_formula(node, facts):
    op = node["op"]
    if op == "CONST": return number(node["value"])
    if op == "READ":
        value = fact_value(facts, node["field"])
        if value is None: raise PackageError("NEEDS_INPUT:" + node["field"])
        if value == "__CONFLICT__": raise PackageError("CONFLICT:" + node["field"])
        return number(value)
    values = [evaluate_formula(a, facts) for a in node["args"]]
    with localcontext() as ctx:
        ctx.prec = 36
        if op == "ADD": return sum(values, Decimal(0))
        if op == "SUB": return values[0] - values[1]
        if op == "MUL":
            out = Decimal(1)
            for v in values: out *= v
            return out
        if op == "DIV":
            if values[1] == 0: raise PackageError("DIVISION_BY_ZERO")
            return values[0] / values[1]
    raise PackageError("invalid formula")


def nested(value, path):
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def policy_status(rule, facts):
    """Offline acceptance helper only; never writes a business result."""
    if rule["effect"].get("release_blocked_by"): return "BLOCKED_EVIDENCE"
    state = evaluate_condition(rule["conditions"], facts)
    if state != "TRUE": return {"FALSE": "NOT_APPLICABLE", "UNKNOWN": "NEEDS_INPUT", "CONFLICT": "CONFLICT"}[state]
    inspection = rule['effect'].get('inspection_policy', {})
    if inspection.get('target_selection') == 'EXPLICIT_VERIFIED_DESIGN_TARGET_ONLY':
        quantity = fact_value(facts, 'inspection.radiographic.verified_physical_quantity')
        if quantity == '__CONFLICT__': return 'CONFLICT'
        if quantity is not None:
            try: quantity = number(quantity)
            except PackageError: return 'INVALID_INPUT'
            if quantity < 0: return 'INVALID_INPUT'
            if quantity == 0: return 'NO_ASSOCIATION'
    for guard in rule["effect"].get("execution_guards", []):
        state = evaluate_condition(guard, facts)
        if state != "TRUE": return "CONFLICT" if state == "CONFLICT" else "NEEDS_INPUT"
    return "CONDITIONS_AND_GUARDS_PASS_INPUTS_STILL_REQUIRED"


def pv_plan(spec, facts):
    """Simulate the published finite splitting policy, even if binding is blocked."""
    expected_tiers = [{"upper_mwp": str(i), "target_source_code": "G-b" + str(i + 36)} for i in range(1, 5)]
    if spec["algorithm"] != "REPEAT_MAX_THEN_CEILING_REMAINDER" or spec["tiers"] != expected_tiers or spec["max_mwp"] != "4":
        raise PackageError("invalid PV split policy")
    value = fact_value(facts, spec["capacity_input"]["field"])
    if value is None: raise PackageError("NEEDS_INPUT")
    if value == "__CONFLICT__": raise PackageError("CONFLICT")
    capacity = number(value)
    if capacity <= 0: raise PackageError("INVALID_CAPACITY")
    whole, remainder = divmod(capacity, number("4"))
    counts = {tier["target_source_code"]: 0 for tier in expected_tiers}
    counts["G-b40"] = int(whole)
    if remainder:
        for tier in expected_tiers:
            if remainder <= number(tier["upper_mwp"]):
                counts[tier["target_source_code"]] += 1
                break
    return {key: val for key, val in counts.items() if val}


def run_cases(package, cases):
    rules = {r["rule_id"]: r for r in package["approved_rules"]}
    pending = {r["rule_id"]: r for r in package["pending_rules"]}
    results = []
    for case in cases:
        try:
            kind = case["kind"]
            if kind == "CONDITION": actual = evaluate_condition(rules[case["rule_id"]]["conditions"], case["facts"])
            elif kind == "FORMULA":
                try:
                    actual = format(evaluate_formula(nested(rules[case["rule_id"]], case.get("path", "effect.formula")), case["facts"]), "f")
                    if "expected_decimal" in case: actual = number(actual) == number(case["expected_decimal"])
                except PackageError as exc: actual = str(exc).split(":", 1)[0]
            elif kind == "PROPERTY": actual = nested(rules[case["rule_id"]], case["path"])
            elif kind == "PENDING": actual = pending[case["rule_id"]]["pending_kind"]
            elif kind == "POLICY_STATUS": actual = policy_status(rules[case["rule_id"]], case["facts"])
            elif kind == "PV_PLAN":
                try: actual = pv_plan(rules[case["rule_id"]]["effect"]["capacity_split"], case["facts"])
                except PackageError as exc: actual = str(exc).split(":", 1)[0]
            else: raise PackageError("unknown test kind")
            expected = True if "expected_decimal" in case else case["expected"]
            results.append({"id": case["id"], "passed": actual == expected, "actual": actual, "expected": expected})
        except (KeyError, PackageError) as exc:
            results.append({"id": case["id"], "passed": False, "error": str(exc)})
    return results


ACTIONS = {"normalize_feature", "expand_query", "restrict_candidate", "prefer_candidate", "exclude_candidate",
           "convert_quantity", "associate_item", "exclude_association", "borrow_item_on_missing", "check_coverage", "select_pricing_method"}
EFFECT_KEYS = set("""allocation already_total_area_policy amount_policy approximate basis basis_default basis_evidence_required
capacity_policy catalog_references check_corrosion_work_coverage choose_target_by_verified_power_bracket cost_kind
counted_volume_default covered_components covered_equipment creates_design_fact dimensions_default display_name
duplicate_charge emit_only_positive excluded_fittings exclusive_group execution_guards formula group
includes_commissioning_no_extra_item interface_name_alone_is_insufficient inverse_mapping keep_original_route
main_catalog_references mass_conversion match_mode material_by_geology material_equivalence missing_inputs
no_default_fallback note_in_estimate_required on_missing_amount on_missing_input on_missing_target original_chapter
other_geology output_unit pair_key parameter_defaults physical_quantity_unchanged policy preserve_physical_item
preserve_source quantity quantity_kind rate_default rounding select_actual_item source_expression stage_policy stage_field
target_chapter target_expression target_feature target_kind target_label target_mapping_required
technical_conditions_still_required transitive_mapping type uncovered_voltage_gap unique_by unit
verify_actual_work_coverage waive_only_chapter_entry within_allowed_scope_only work work_coverage_check""".split())
EFFECT_KEYS.add("source_database_name_preserved")
EFFECT_KEYS.update("source_binding release_blocked_by review_notes inspection_policy capacity_split amount_formula amount_unit candidate_policy parameter_policy length_fraction".split())
EFFECT_KEYS.add("catalog_evidence_refs")
EFFECT_KEYS.update({"confirmation_refs", "fallback_contract", "target_directory_scope"})


def validate_materials_request(request, rules, review):
    if request.get("schema_version") == "0903-materials-request-v3":
        from verify_round2 import validate_round2_materials
        return validate_round2_materials(request, rules, review)
    if request.get("schema_version") == "0903-materials-request-v2":
        return validate_materials_followup(request, rules, review)
    pending = {r["rule_id"] for r in rules["pending_rules"] if r["pending_kind"] == "TECHNICAL_EVIDENCE"}
    groups = request["groups"]
    if len(groups) != 12 or len({g["id"] for g in groups}) != 12: raise PackageError("materials group identity mismatch")
    union = {i for g in groups for i in g["rule_ids"]}
    if union != pending or len(pending) != 41: raise PackageError("materials 41-rule coverage mismatch")
    index = request["rule_index"]
    if {r["rule_id"] for r in index} != pending or len(index) != 41: raise PackageError("materials index mismatch")
    reviewed = {r["source_record_id"]: r for r in review["records"]}
    for r in index:
        if r["groups"] != [g["id"] for g in groups if r["rule_id"] in g["rule_ids"]]: raise PackageError("materials dependency loss")
        source = reviewed[r["rule_id"]]
        if r["candidate_checks"] != source["catalog_checks"] or r["source_refs"] != source["source_refs"]: raise PackageError("materials candidate evidence mismatch")
        if r["generated_rule_ids"] != source["generated_rule_ids"]: raise PackageError("materials output mismatch")
    for g in groups:
        if len(g["rule_ids"]) != len(set(g["rule_ids"])): raise PackageError("duplicate row within materials group")
        if any(not g.get(k) for k in ("known", "request", "accepted", "already_answered", "completion")): raise PackageError("materials missing request detail")
    if request["summary"] != {"unique_rules": 41, "groups": 12, "group_rule_links": sum(len(g["rule_ids"]) for g in groups), "newly_closed": 0, "deferred_0904": 5}:
        raise PackageError("materials summary mismatch")
    evidence = request["existing_evidence"]
    if evidence["database_read_only"] is not True or evidence["newly_closed_rule_ids"]: raise PackageError("invalid evidence claim")
    if any(any(c.values()) for c in evidence["catalog_comparison"].values()): raise PackageError("catalog comparison requires review")
    if request["release_version"] != rules["release_version"]: raise PackageError("materials release mismatch")


def validate_materials_followup(request, rules, review):
    pending = {r["rule_id"]: r for r in rules["pending_rules"] if r["pending_kind"] == "TECHNICAL_EVIDENCE"}
    groups = request["groups"]
    if len(groups) != 12 or {g["id"] for g in groups} != {f"D{n:02d}" for n in range(1,13)}:
        raise PackageError("materials group identity mismatch")
    if {rid for g in groups for rid in g["pending_rule_ids"]} != set(pending) or len(pending) != 32:
        raise PackageError("materials 32-rule coverage mismatch")
    baseline = set(request["baseline_rule_ids"])
    closed = sorted(baseline - set(pending))
    if len(baseline) != 41 or set(pending)-baseline or closed != request["newly_closed_rule_ids"] or closed != sorted(request["confirmed_changes"]["expected_newly_closed_rule_ids"]):
        raise PackageError("materials closure scope mismatch")
    for g in groups:
        if len(g["pending_rule_ids"]) != len(set(g["pending_rule_ids"])) or not set(g["pending_rule_ids"]).issubset(g["rule_ids"]):
            raise PackageError("materials invalid group links")
        if any(not g.get(k) for k in ("known", "request", "accepted", "already_answered", "completion", "answer")):
            raise PackageError("materials missing request detail")
        if g["id"] in ("D01", "D09", "D12") and (g["status"] != "CLOSED" or g["pending_rule_ids"] or g["request"] != "无需补充或重复确认。"):
            raise PackageError("answered group reopened")
        if g["id"] == "D03" and g["pending_rule_ids"] != [f"A06-R{n:03d}" for n in range(78,82)]:
            raise PackageError("withdrawn wind branch requested again")
    index = request["rule_index"]
    reviewed = {r["source_record_id"]: r for r in review["records"]}
    if len(index) != 32 or {r["rule_id"] for r in index} != set(pending): raise PackageError("materials index mismatch")
    for r in index:
        rid = r["rule_id"]; entry = reviewed[rid]
        if r["groups"] != [g["id"] for g in groups if rid in g["pending_rule_ids"]]: raise PackageError("materials dependency loss")
        if r["candidate_checks"] != entry["catalog_checks"] or r["source_refs"] != entry["source_refs"]: raise PackageError("materials candidate evidence mismatch")
        if r["missing_evidence"] != entry["missing_evidence"] or r["pending_scope"] != pending[rid]["conservative_scope"]: raise PackageError("materials pending branch mismatch")
        if r["generated_rule_ids"] != entry["generated_rule_ids"]: raise PackageError("materials output mismatch")
    expected = {"baseline_unique_rules": 41, "unique_rules": 32, "groups": 12, "active_groups": 9, "group_rule_links": 35, "newly_closed": 9, "deferred_0904": 5}
    if request["summary"] != expected or sum(len(g["pending_rule_ids"]) for g in groups) != 35: raise PackageError("materials summary mismatch")
    ev = request["existing_evidence"]
    if ev["database_read_only"] is not True or ev["newly_closed_rule_ids"] or any(any(c.values()) for c in ev["catalog_comparison"].values()):
        raise PackageError("historical catalog evidence altered")
    if request["release_version"] != rules["release_version"]: raise PackageError("materials release mismatch")


def validate_confirmed_changes(source_map, package):
    c = source_map["confirmed_changes"]
    round2 = c.get('schema_version') == '0903-confirmed-changes-v2'
    if c["runtime_activation"] is not False or c["excluded_phase"] != "0904" or c["release_version"] != package["release_version"]:
        raise PackageError("confirmation release mismatch")
    scope = {"D01": {f"A06-R{n:03d}" for n in (64,65,66,67,68,69,70,72,73)},
             "D09": {"A06-R070"}, "D12": {"A09-R006","A09-R087","A09-R091"}, "D03_2": {"A06-R072","A06-R073"}}
    if round2:
        from authoring_round2 import PV_ROWS, WIND_ROWS, FILM_ROWS
        scope.update(D02=PV_ROWS, D03_1=WIND_ROWS, D04=FILM_ROWS, D05={'A05-R021'}, D06={'A06-R087'}, D08={f'A06-R{n:03d}' for n in range(96,100)})
    decisions = {d["id"]: d for d in c["decisions"]}
    if set(decisions) != set(scope) or any(set(decisions[k]["rule_ids"]) != v for k,v in scope.items()):
        raise PackageError("confirmation scope expanded")
    if decisions["D01"]["library_code"] != "DE1000022001" or decisions["D03_2"]["library_code"] != "DE07000022":
        raise PackageError("confirmation library changed")
    if decisions["D12"]["affected_primary_rule_ids"] != ["A09-R005", "A09-R090"]: raise PackageError("primary scope expanded")
    scope["D12"] |= {"A09-R005", "A09-R090"}
    rules = {r["rule_id"]:r for r in package["approved_rules"]}
    pending = {r["rule_id"]:r for r in package["pending_rules"]}
    def libraries(rule): return [l["code"] for l in rule["library_scope"]["libraries"]]
    def conjuncts(node):
        return [leaf for arg in node["args"] for leaf in conjuncts(arg)] if node.get("op")=="AND" else [node]
    def require_eq(rule, name, value):
        if not any(n.get("op")=="EQ" and n.get("field")==name and n.get("value")==value for n in conjuncts(rule["conditions"])):
            raise PackageError("confirmation required condition missing: " + name)
    for rule in rules.values():
        for key in rule["effect"].get("confirmation_refs", []):
            if key not in scope or rule["source_record_id"] not in scope[key] or "confirmed-changes:"+key not in rule["review_evidence"]:
                raise PackageError("confirmation reference outside scope")
    for n in (64,65,66,67,68,69):
        rule = rules[f"A06-R{n:03d}-POLICY"]
        if libraries(rule)!=["DE1000022001"] or not rule["effect"].get("main_catalog_references") or "D01" not in rule["effect"].get("confirmation_refs", []):
            raise PackageError("confirmed oil identity missing")
        if bool(rule["effect"].get("release_blocked_by")) != (n==69 and not round2): raise PackageError("oil gap incorrectly closed")
    row70 = rules["A06-R070-POLICY"]
    if row70["effect"]["type"] != "exclude_association" or list(formulas(row70["effect"])) or row70["effect"].get("release_blocked_by"):
        raise PackageError("withdrawn row70 must not calculate")
    require_eq(row70, "binding.source_rule_id", "A06-R070")
    for n in (72,73):
        rid=f"A06-R{n:03d}"; oil=rules[rid+"-OIL2022"]; pv=rules[rid+"-POLICY"]; wind=rules[rid+"-WIND_WITHDRAWN"]
        if libraries(oil)!=["DE1000022001"] or oil["effect"].get("release_blocked_by") or oil["effect"]["type"]!="associate_item": raise PackageError("oil branch lost")
        if libraries(pv)!=["DE06000003"] or (bool(pv["effect"].get("release_blocked_by")) if round2 else pv["effect"].get("release_blocked_by")!=[rid]): raise PackageError("PV branch blocker lost or incorrect closure")
        if libraries(wind)!=["DE07000022"] or wind["effect"]["type"]!="exclude_association" or list(formulas(wind["effect"])): raise PackageError("wind branch not withdrawn")
        require_eq(wind,"binding.source_rule_id",rid)
        if not round2 and (pending[rid]["conservative_scope"].get("library_codes") != ["DE06000003"] or pending[rid]["conservative_scope"].get("blocked_rule_ids") != [rid+"-POLICY"]):
            raise PackageError("pending scope blocks resolved branch")
        if not round2 and pending[rid]["conservative_scope"].get("library_ids") != [l["id"] for l in pv["library_scope"]["libraries"]]:
            raise PackageError("pending branch library identity mismatch")
    for rid in ("A09-R005","A09-R006","A09-R087","A09-R090","A09-R091"):
        rule=rules[rid]; primary=rid in ("A09-R005","A09-R090")
        require_eq(rule,"coverage.standard_scope_matches_current_work",True)
        require_eq(rule,"coverage.standard_module_available_for_work",primary)
        contract=rule["effect"].get("fallback_contract",{})
        if contract.get("assessment_unit")!="SAME_OBJECT_AND_SAME_WORK_SCOPE_NOT_WHOLE_OBJECT" or contract.get("unknown")!="NEEDS_INPUT_NO_FALLBACK": raise PackageError("fallback coverage contract missing")
        if not primary and libraries(rule)!=["DE1000022001"]: raise PackageError("fallback target library mismatch")
    require_eq(rules["A09-R087"],"coverage.corrosion_work_included",False)
    require_eq(rules["A09-R091"],"crossing.separate_drawing",True)
    require_eq(rules["A09-R091"],"coverage.crossing_work_included",False)
    scope9=rules["A09-R091"]["effect"].get("target_directory_scope",{})
    if scope9.get("root_id")!=c["catalog_evidence"]["crossing_directory"]["id"] or scope9.get("library_code")!="DE1000022001": raise PackageError("crossing chapter scope mismatch")
    dirs=c["catalog_evidence"]["crossing_directories"]
    if any(d["library_code"]!="DE1000022001" or not (d["bsid"]=="1.9.2" or d["bsid"].startswith("1.9.2.")) for d in dirs) or scope9.get("directory_ids")!=sorted(d["id"] for d in dirs):
        raise PackageError("crossing chapter directories expanded")
    guards=rules["A09-R091"]["effect"].get("execution_guards",[])
    if {"op":"IN","field":"selection.target_directory_id","value":scope9.get("directory_ids")} not in guards: raise PackageError("crossing chapter guard missing")
    if round2:
        from verify_round2 import validate_round2_confirmations
        validate_round2_confirmations(source_map, package)


def validate_review(review, rules, dispositions, confirmations=None):
    records = review["records"]
    if len(records) != 95 or len({r["source_record_id"] for r in records}) != 95:
        raise PackageError("95-row review coverage mismatch")
    approved = {r["rule_id"]: r for r in rules["approved_rules"]}
    pending = {r["rule_id"]: r for r in rules["pending_rules"] if r["pending_kind"] == "TECHNICAL_EVIDENCE"}
    if set(pending) != {r["source_record_id"] for r in records if r["review_state"] != "CLOSED_FOR_DECLARED_USAGE"}:
        raise PackageError("review and pending scope mismatch")
    for entry in records:
        rid = entry["source_record_id"]
        if entry["generated_rule_ids"] != dispositions[rid]["rule_ids"]: raise PackageError("review generated rule mismatch")
        if not entry["recorded_answer_ids"] or not entry["source_refs"]: raise PackageError("review evidence missing")
        remaining = rid in pending
        if remaining != bool(entry["missing_evidence"]): raise PackageError("review gap state mismatch")
        if remaining and pending[rid]["reason"] != "；".join(entry["missing_evidence"]): raise PackageError("pending reason differs from review")
        for rule_id in entry["generated_rule_ids"]:
            if approved[rule_id]["source_record_id"] != rid: raise PackageError("review source mismatch")
            confirmed_branch = confirmations and rid in ("A06-R072", "A06-R073") and rule_id in (rid+"-OIL2022", rid+"-WIND_WITHDRAWN")
            if remaining and not confirmed_branch and rid not in approved[rule_id]["effect"].get("release_blocked_by", []):
                raise PackageError("partial policy lost release blocker")
    s = review["summary"]
    states = dict(Counter(r["review_state"] for r in records))
    if s["reviewed"] != 95 or s["states"] != states or s["remaining_technical"] != len(pending):
        raise PackageError("review summary mismatch")
    by_family = {f: dict(Counter(r["review_state"] for r in records if r["family"] == f)) for f in ("A05", "A06", "A07", "A09", "A11")}
    if s["by_family"] != by_family or s["normalized_rules_total"] != len(approved): raise PackageError("review family count mismatch")
    if s["blocked_policy_rules"] != sum(bool(r["effect"].get("release_blocked_by")) for r in approved.values()):
        raise PackageError("blocked policy count mismatch")


def validate_data(rules, cards, source_map, dictionary, cases):
    fields, units = dictionary["fields"], dictionary["units"]
    approved = rules["approved_rules"]
    ids = [r["rule_id"] for r in approved] + [r["rule_id"] for r in rules["pending_rules"]]
    if len(ids) != len(set(ids)): raise PackageError("duplicate rule IDs")
    records = {r["rule_id"]: r for r in source_map["records"]}
    catalog_refs = {r["id"]: r for r in source_map["catalog_reference_evidence"]}
    if len(catalog_refs) != len(source_map["catalog_reference_evidence"]): raise PackageError("duplicate catalog identity")
    if len(records) != source_map["coverage"]["source_records"]: raise PackageError("source record loss")
    dispositions = {d["source_record_id"]: d for d in source_map["dispositions"]}
    if set(dispositions) != set(records): raise PackageError("incomplete source disposition")
    source_ids = {f["fragment_id"] for f in source_map["fragments"]}
    if len(source_ids) != source_map["coverage"]["field_fragments"]: raise PackageError("fragment loss/duplication")
    if any(not f["disposition"] for f in source_map["fragments"]): raise PackageError("unhandled fragment")
    snapshots = source_map["authorized_sheet_snapshots"]
    if set(snapshots) != {"A-05", "A-06", "A-07", "A-09", "A-11"}: raise PackageError("unauthorized sheet")
    expected_cells = {(sheet, cell) for sheet, data in snapshots.items() for cell in data["cells"]}
    actual_cells = set()
    for row in source_map["records"] + source_map["metadata"]:
        for cell, original in row.get("source_cells", row.get("cells", {})).items():
            if snapshots[row["sheet"]]["cells"].get(cell) != original: raise PackageError("source cell altered")
            actual_cells.add((row["sheet"], cell))
    if actual_cells != expected_cells: raise PackageError("raw cell coverage mismatch")
    for fragment in source_map["fragments"]:
        sheet, cell = fragment["source_ref"].split("!")
        if (sheet, cell) not in expected_cells: raise PackageError("fragment source does not exist")
    for d in dispositions.values():
        if any(i not in ids for i in d["rule_ids"]): raise PackageError("unresolved linked rule")
    if len(cards) != len(approved): raise PackageError("rule card coverage mismatch")
    card_map = {c["rule_id"]: c for c in cards}
    if len(card_map) != len(cards): raise PackageError("duplicate card")
    for rule in approved:
        if rule["family"] not in ("A05", "A06", "A07", "A09", "A11"): raise PackageError("unauthorized family")
        if rule["source_record_id"] not in records or not rule["source_refs"]: raise PackageError("missing source")
        if rule["review_status"] != "APPROVED" or not rule["review_evidence"] or rule["open_issue_ids"]: raise PackageError("invalid approval")
        if rule["effect"]["type"] not in ACTIONS: raise PackageError("unsupported action")
        if set(rule["effect"]) - EFFECT_KEYS: raise PackageError("unsupported effect parameter")
        effect = rule["effect"]
        blockers = effect.get("release_blocked_by", [])
        technical_pending = {r["rule_id"] for r in rules["pending_rules"] if r["pending_kind"] == "TECHNICAL_EVIDENCE"}
        if any(i not in technical_pending for i in blockers): raise PackageError("missing release blocker record")
        if "source_binding" in effect and not blockers and effect["type"] != "exclude_association":
            raise PackageError("unbound positive action must remain blocked")
        if "candidate_policy" in effect:
            p = effect["candidate_policy"]
            if (rule["strength"] != "RETRIEVAL_ONLY" or effect["type"] != "expand_query" or
                p.get("hard_constraints_source") != "ORIGINAL_VERIFIED_FACTS_ONLY" or
                p.get("replace_original_query") is not False or p.get("auto_accept_candidate") is not False or
                p.get("prohibit_fact_backfill") is not True or effect.get("creates_design_fact") is not False or
                effect.get("material_equivalence") is not False or effect.get("inverse_mapping") is not False or effect.get("transitive_mapping") is not False):
                raise PackageError("retrieval hint exceeded allowed use")
        if "capacity_split" in effect:
            if not blockers and not (source_map.get('confirmed_changes',{}).get('schema_version')=='0903-confirmed-changes-v2' and 'D02' in effect.get('confirmation_refs',[])):
                raise PackageError("PV binding not yet verified")
            pv_plan(effect["capacity_split"], {"pv.subarray_capacity_mwp": "9"})
        if "catalog_evidence_refs" in effect:
            supplement = source_map.get("materials_request", {}).get("existing_evidence")
            if not supplement: raise PackageError("missing catalog supplement")
            valid_refs = {"existing-evidence.json#sections." + k for k in supplement["sections"]}
            valid_refs.update("existing-evidence.json#findings." + f["id"] for f in supplement["findings"])
            if not set(effect["catalog_evidence_refs"]).issubset(valid_refs): raise PackageError("unresolved catalog supplement reference")
        if "PRICE_MATCH" in rule["usage"]: raise PackageError("0904 is deferred")
        condition_shape(rule["conditions"], fields, units)
        for guard in rule["effect"].get("execution_guards", []): condition_shape(guard, fields, units)
        for expression in formulas(rule["effect"]): dimension(expression, fields, units)
        deps = sorted(reads(rule["conditions"]) | reads(rule["effect"]))
        if rule["dependencies"] != deps: raise PackageError("dependency loss")
        if any(k not in fields for k in deps): raise PackageError("unregistered dependency")
        if rule["required_inputs"] != [{"field": k, **fields[k]} for k in deps]: raise PackageError("required input mismatch")
        if card_map[rule["rule_id"]]["rule"] != rule: raise PackageError("card differs from executable rule")
        for key in ("catalog_references", "main_catalog_references"):
            refs = rule["effect"].get(key, [])
            lib_codes = {l["code"] for l in rule["library_scope"]["libraries"]}
            if any(r["library_code"] not in lib_codes or not r["id"] or not r["unit"] for r in refs): raise PackageError("reference outside bound library")
            if any(catalog_refs.get(r["id"]) != r for r in refs): raise PackageError("catalog identity/evidence mismatch")
        if rule["library_scope"]["domain"] == "QUOTA" and not rule["library_scope"]["libraries"]: raise PackageError("unbound quota rule")
    for rule in rules["pending_rules"]:
        if rule["executable"] or not rule["reason"] or rule["source_record_id"] not in records: raise PackageError("invalid pending rule")
    expected_index = {f: sorted(r["rule_id"] for r in approved + rules["pending_rules"] if r["family"] == f) for f in ("A05", "A06", "A07", "A09", "A11")}
    if rules["scope_index"] != expected_index: raise PackageError("scope index omission")
    review = source_map.get("pending_review")
    if rules["package_schema_version"] == "0903-rule-package-v2":
        if not review: raise PackageError("pending review required")
        validate_review(review, rules, dispositions, source_map.get("confirmed_changes"))
    if "confirmed_changes" in source_map: validate_confirmed_changes(source_map, rules)
    if "materials_request" in source_map: validate_materials_request(source_map["materials_request"], rules, review)
    outcomes = run_cases(rules, cases["cases"])
    if not outcomes or any(not r["passed"] for r in outcomes): raise PackageError("acceptance failure: " + json.dumps([r for r in outcomes if not r["passed"]], ensure_ascii=False))
    report = {"scope": "OFFLINE_RESOURCE_CONTRACT_AND_FIXED_CASES", "source_records": len(records), "raw_cells": len(actual_cells),
            "field_fragments": len(source_ids), "catalog_references": len(catalog_refs), "approved_rules": len(approved), "pending_rules": len(rules["pending_rules"]),
            "case_count": len(outcomes), "passed": True, "cases": outcomes,
            "not_tested": ["production rule_runtime", "Dify updated libraries", "0903 business integration", "model selection", "UI", "0904"]}
    if review: report["pending_review_summary"] = review["summary"]
    if "materials_request" in source_map: report["materials_request_summary"] = source_map["materials_request"]["summary"]
    return report


def verify_directory(directory):
    directory = Path(directory).resolve()
    manifest = strict_json((directory / "manifest.json").read_text(encoding="utf-8"))
    expected_files = {"rules.json", "rule-cards.jsonl", "source-map.json", "unit-dictionary.json", "test-cases.json", "validation-report.json", "rule-package.schema.json"}
    if manifest["package_schema_version"] == "0903-rule-package-v2": expected_files.update({"pending-review.json", "pending-review.md"})
    if manifest.get("materials_request_schema") in ("0903-materials-request-v1", "0903-materials-request-v2", "0903-materials-request-v3"): expected_files.update({"materials-request.json", "materials-request.md", "existing-evidence.json"})
    if manifest.get("confirmation_schema") in ("0903-confirmed-changes-v1", "0903-confirmed-changes-v2"): expected_files.add("confirmed-changes.json")
    if set(manifest["files"]) != expected_files: raise PackageError("manifest file coverage mismatch")
    if {p.name for p in directory.iterdir()} != expected_files | {"manifest.json"}: raise PackageError("unexpected release contents")
    for name, expected in manifest["files"].items():
        path = (directory / name).resolve()
        if path.parent != directory or path.name != name: raise PackageError("invalid artifact path")
        if file_digest(path) != expected: raise PackageError("hash mismatch: " + name)
    values = {name: strict_json((directory / name).read_text(encoding="utf-8")) for name in
              ("rules.json", "source-map.json", "unit-dictionary.json", "test-cases.json", "validation-report.json")}
    cards = [strict_json(line) for line in (directory / "rule-cards.jsonl").read_text(encoding="utf-8").splitlines()]
    if manifest.get("materials_request_schema") in ("0903-materials-request-v1", "0903-materials-request-v2", "0903-materials-request-v3"):
        if manifest["materials_request_schema"] == "0903-materials-request-v3":
            from materials_round2 import markdown_round2 as markdown_request
        elif manifest["materials_request_schema"] == "0903-materials-request-v2":
            from materials_followup import markdown_followup as markdown_request
        else:
            from materials_request import markdown_request
        request = strict_json((directory / "materials-request.json").read_text(encoding="utf-8"))
        if request != values["source-map.json"].get("materials_request"): raise PackageError("materials artifact mismatch")
        if (directory / "materials-request.md").read_text(encoding="utf-8") != markdown_request(request): raise PackageError("materials markdown mismatch")
        if strict_json((directory / "existing-evidence.json").read_text(encoding="utf-8")) != request["existing_evidence"]: raise PackageError("materials evidence mismatch")
        if manifest["materials_request_summary"] != request["summary"]: raise PackageError("manifest materials mismatch")
    if manifest.get("confirmation_schema") in ("0903-confirmed-changes-v1", "0903-confirmed-changes-v2"):
        confirmations = strict_json((directory / "confirmed-changes.json").read_text(encoding="utf-8"))
        if confirmations != values["source-map.json"].get("confirmed_changes") or confirmations != request.get("confirmed_changes"):
            raise PackageError("confirmation artifact mismatch")
    if manifest["package_schema_version"] == "0903-rule-package-v2":
        from review_pending import markdown_review
        review = strict_json((directory / "pending-review.json").read_text(encoding="utf-8"))
        if review != values["source-map.json"]["pending_review"]: raise PackageError("review artifact mismatch")
        if (directory / "pending-review.md").read_text(encoding="utf-8") != markdown_review(review): raise PackageError("review markdown mismatch")
        if manifest["pending_review_summary"] != review["summary"]: raise PackageError("manifest review summary mismatch")
        if manifest["previous_release"] != review["previous_release"]: raise PackageError("previous release identity mismatch")
        if manifest["blocked_policy_rule_ids"] != [r["rule_id"] for r in values["rules.json"]["approved_rules"] if r["effect"].get("release_blocked_by")]:
            raise PackageError("manifest blocked scope mismatch")
    import jsonschema
    schema = strict_json((directory / "rule-package.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(values["rules.json"], schema)
    report = validate_data(values["rules.json"], cards, values["source-map.json"], values["unit-dictionary.json"], values["test-cases.json"])
    package = values["rules.json"]
    if package["release_version"] != manifest["release_version"]: raise PackageError("release identity mismatch")
    if manifest["runtime_activation"] is not False: raise PackageError("runtime activation outside offline scope")
    if manifest["approved_scope"]["rule_ids"] != [r["rule_id"] for r in package["approved_rules"]]: raise PackageError("approved manifest scope mismatch")
    if manifest["pending_scope"]["rule_ids"] != [r["rule_id"] for r in package["pending_rules"]]: raise PackageError("pending manifest scope mismatch")
    if report != values["validation-report.json"]: raise PackageError("verification report mismatch")
    semantic = digest({k: manifest["files"][k] for k in sorted(manifest["files"]) if k != "validation-report.json"})
    if semantic != manifest["semantic_hash"]: raise PackageError("semantic hash mismatch")
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    report = verify_directory(args.directory)
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, ensure_ascii=False, indent=2))
