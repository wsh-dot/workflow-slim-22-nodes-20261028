"""Offline, source-specific normalization. Never imported by the business runner.

This is an explicit transcription of the five authorized sheets and the recorded
user corrections, not a natural-language compiler. Published JSON is the runtime
contract. Unknown book identities and missing source evidence remain pending.
"""
from copy import deepcopy
import re

FIELDS = {}


def field(name, kind="string", unit=None):
    spec = {"type": kind, "unit": unit, "unknown_policy": "NEEDS_INPUT",
            "source_required": True}
    if name in FIELDS and FIELDS[name] != spec:
        raise ValueError(f"conflicting field definition: {name}")
    FIELDS[name] = spec
    return name


def eq(name, value):
    if name == "object.kind":
        return {"op": "HAS_ANY", "field": field("object.kinds", "string_set"), "value": [value]}
    return {"op": "EQ", "field": field(name, "boolean" if isinstance(value, bool) else "string"), "value": value}


def inside(name, values):
    if name == "object.kind":
        return {"op": "HAS_ANY", "field": field("object.kinds", "string_set"), "value": values}
    return {"op": "IN", "field": field(name), "value": values}


def bounds(name, unit, low=None, high=None, include_low=True, include_high=True):
    return {"op": "RANGE", "field": field(name, "decimal", unit), "unit": unit,
            "min": None if low is None else str(low), "max": None if high is None else str(high),
            "include_min": include_low, "include_max": include_high}


def AND(*args): return {"op": "AND", "args": list(args)}
def OR(*args): return {"op": "OR", "args": list(args)}
def NOT(arg): return {"op": "NOT", "arg": arg}
def C(value, unit="1"): return {"op": "CONST", "value": str(value), "unit": unit}
def V(name, unit="1"): return {"op": "READ", "field": field(name, "decimal", unit), "unit": unit}
def X(op, *args): return {"op": op, "args": list(args)}
def mul(*args): return X("MUL", *args)
def div(a, b): return X("DIV", a, b)
def add(*args): return X("ADD", *args)
def sub(a, b): return X("SUB", a, b)


def value(row, key):
    return str(row.get("context", {}).get(key, {}).get("value", "")).strip()


def chapter_nine():
    distance = bounds("pipeline.route_length_km", "km", 25)
    return OR(
        bounds("pipeline.outer_diameter_mm", "mm", 457, include_low=False),
        AND(inside("pipeline.service", ["oil", "gas"]), eq("pipeline.outside_source_region", True), distance),
        AND(eq("pipeline.service", "water"), eq("pipeline.steel", True),
            eq("pipeline.source_to_first_reservoir", True), distance),
        AND(eq("pipeline.service", "manufactured_gas"), eq("pipeline.plant_to_first_distribution", True), distance),
        AND(eq("pipeline.service", "slurry"), eq("pipeline.outside_processing_plant", True), distance),
        eq("pipeline.obstacle_crossing", True))


def selector_codes(text, library, catalog):
    """Expand only records actually present in the frozen catalog. No generated IDs."""
    records = [i for i in catalog["items"] if i["library_code"] == library]
    selected = {}
    for raw in text.upper().replace("～", "~").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        if re.fullmatch(r"\d+-", raw):
            hits = [i for i in records if i["code"].upper().startswith(raw)]
        else:
            match = re.fullmatch(r"([A-Z]*\d+-\d+|[A-Z]-[A-Z]\d+)(?:\s*~\s*([A-Z]*\d+-\d+|\d+))?", raw)
            if not match:
                raise ValueError(f"UNRESOLVED_CODE_EXPRESSION: {text}")
            start, end = match.groups()
            if end:
                prefix, start_num = start.rsplit("-", 1)
                if "-" in end:
                    end_prefix, end = end.rsplit("-", 1)
                    if end_prefix != prefix: raise ValueError("CROSS_PREFIX_RANGE")
                if int(end) < int(start_num): raise ValueError("REVERSED_CODE_RANGE")
                hits = [i for i in records if re.fullmatch(re.escape(prefix) + r"-\d+", i["code"].upper())
                        and int(start_num) <= int(i["code"].rsplit("-", 1)[1]) <= int(end)]
                actual = {i["code"].upper() for i in hits}
                if start not in actual or prefix + "-" + end not in actual:
                    raise ValueError(f"MISSING_RANGE_ENDPOINT: {text}")
            else:
                hits = [i for i in records if i["code"].upper() == start]
        if not hits: raise ValueError(f"NO_CATALOG_REFERENCE: {library}/{text}")
        for item in hits:
            if not item.get("unit"): raise ValueError(f"MISSING_CATALOG_UNIT: {item['code']}")
            selected[item["id"]] = {k: item[k] for k in ("id", "library_code", "directory_id", "code", "name", "unit")}
    return sorted(selected.values(), key=lambda i: (i["code"], i["id"]))


def library_for(row):
    text = value(row, "library") or value(row, "library_and_profession")
    if "石油建设安装工程概算指标" in text: return "DE1000022001"
    if "电力建设工程概算定额" in text: return "DE07000019"
    # Similar book titles are candidates, not an approved edition mapping.
    raise ValueError("BOOK_IDENTITY_MAPPING_UNVERIFIED")


def make(row, suffix, condition, effect, *, usage=None, scope="ITEM", strength="HARD", evidence=None):
    return {"rule_id": row["rule_id"] + suffix, "revision": "1", "family": row["sheet"].replace("-", ""),
            "source_record_id": row["rule_id"], "source_refs": row["source_refs"],
            "usage": usage or ["QUOTA_MATCH"], "evaluation_scope": scope,
            "object_scope": {"mode": "CONSERVATIVE", "aliases": [value(row, "subject")] if value(row, "subject") else [],
                             "unknown_object_policy": "RETAIN_AS_POSSIBLE"},
            "context": deepcopy(row.get("context", {})),
            "library_scope": {"domain": "NONE", "mode": "ANY", "libraries": [],
                              "basis": "Rule never authorizes a library outside the task AllowedScope."},
            "conditions": condition, "effect": effect, "strength": strength,
            "relation_direction": "FORWARD", "information_loss": {"present": False, "attributes": []},
            "review_status": "APPROVED", "review_evidence": evidence or ["current-plan", "latest-confirmations"],
            "source_interpretation": row["confirmed_interpretation"], "open_issue_ids": [],
            "activation": "OFFLINE_ONLY_NOT_CONNECTED", "priority": None}


def bound(rule, library, catalog):
    lib = next(x for x in catalog["libraries"] if x["code"] == library)
    rule["library_scope"] = {"domain": "QUOTA", "mode": "ALLOWLIST", "libraries": [
        {"id": lib["id"], "code": lib["code"], "name": lib["name"],
         "version_kind": "FROZEN_CATALOG_SNAPSHOT", "version": catalog["snapshot_sha256"]}],
        "basis": "Database identity from the recorded read-only snapshot; not a Dify release ID."}
    rule["conditions"] = AND(eq("binding.library_id", lib["id"]), rule["conditions"])
    return rule


def a05(row, catalog):
    n = row["row"]
    if n in (18, 19, 20): return [], "EXPLANATORY_EXAMPLE", "示例保留，不编译为电缆固定编号映射。"
    if n == 21: return [], "PENDING", "35kV电力2018目标编号及章说明待专家提供；旧YD8-46不得使用。"
    lib = library_for(row)
    if n in (10, 11):
        base = AND(eq("object.kind", "pipeline"), eq("context.location", "offsite"),
                   inside("context.profession", ["天然气", "石油", "给排水"]))
        condition = AND(base, chapter_nine() if n == 11 else NOT(chapter_nine()))
        rules = [bound(make(row, "", condition, {"type": "restrict_candidate", "catalog_references":
            selector_codes("9-" if n == 11 else "8-", lib, catalog), "technical_conditions_still_required": True}), lib, catalog)]
        if n == 10:
            rules.append(bound(make(row, "-BORROW", AND(base, eq("selection.original_chapter", "8"),
                eq("evidence.original_chapter_missing_proven", True)), {"type": "borrow_item_on_missing",
                "original_chapter": "8", "target_chapter": "9", "keep_original_route": True,
                "waive_only_chapter_entry": True, "technical_conditions_still_required": True,
                "catalog_references": selector_codes("9-", lib, catalog)}), lib, catalog))
        return rules, "COMPILED", ""
    specs = {
        3: ("diesel_fire_pump", ["消防"], None),
        4: ("steel_valve", ["天然气", "石油", "热工", "燃气", "注水", "给排水（产建）"], None),
        5: ("steel_valve", ["暖通", "消防", "给排水（矿建）"], None),
        6: ("pipeline", ["天然气", "石油", "热工", "注水", "给排水（产建）"], "station"),
        7: ("pipeline", ["暖通"], "station"), 8: ("pipeline", ["消防", "给排水（矿建）"], "station"),
        9: ("pipeline", ["燃气"], "station"),
        12: ("nondestructive_testing", ["天然气", "石油", "注水", "热工", "燃气"], "station"),
        13: ("nondestructive_testing", ["天然气", "石油", "注水"], "offsite"),
        14: ("cable", ["电气"], None), 15: ("cable", ["阴极保护"], None),
        16: ("optical_cable", ["通信"], "station"), 17: ("optical_cable", ["通信"], "offsite")}
    kind, professions, location = specs[n]
    clauses = [eq("object.kind", kind), inside("context.profession", professions)]
    if location: clauses.append(eq("context.location", location))
    effect = {"type": "restrict_candidate", "catalog_references": selector_codes(value(row, "target_code"), lib, catalog),
              "technical_conditions_still_required": True}
    if n == 3: effect["covered_components"] = ["消防泵", "柴油机", "油箱", "排气管", "消声器", "自冷却系统", "控制系统"]
    return [bound(make(row, "", AND(*clauses), effect), lib, catalog)], "COMPILED", ""


def group_spec(category, extra=()):
    keys = ["file_id", "logical_table_id", "single_project_id", "library_id", "library_version", category, *extra]
    return {"keys": keys, "key_fields": [{"field": field("group." + k), "purpose": "GROUP_KEY"} for k in keys],
            "membership": "ALL_MEMBERS_INCLUDING_PENDING", "anchor": "LAST_ELIGIBLE_SOURCE_ORDER",
            "incomplete_members": "PENDING_GROUP", "deduplicate": "SAME_WORK_SCOPE_AND_TARGET"}


def a06(row, catalog, *, defer_binding=False):
    n = row["row"]
    if n == 70:
        return [], "PENDING", "1m应为1.26m³的修正已确认；源行缺主项/范围，不能跨未合并空白继承。"
    if 74 <= n <= 83:
        return [], "PENDING", "业务公式及范围已确认；光伏/风电指南与现库的版次映射尚未核实。"
    if 84 <= n <= 86:
        kind = {84: "environmental_protection", 85: "water_soil_conservation", 86: "occupational_health_safety"}[n]
        effect = {"type": "associate_item", "target_kind": "PROJECT_SUPPLEMENT", "cost_kind": kind,
                  "display_name": value(row, "related_name"), "quantity": C(1, "项"),
                  "unit": "项", "unique_by": ["project_id", "batch_id", "cost_kind", "generation"],
                  "amount_policy": {"feasibility": mul(V(f"fees.{kind}.basis", "CNY"), V(f"fees.{kind}.rate")),
                                    "preliminary_design": V(f"fees.{kind}.report_amount", "CNY")},
                  "stage_field": {"field": field("project.stage")},
                  "basis_evidence_required": True, "rate_default": None, "basis_default": None,
                  "on_missing_amount": "KEEP_QUANTITY_ONE_AMOUNT_NULL_NEEDS_INPUT", "allocation": "NONE"}
        return [make(row, "", eq("project.kind", "wind_farm"), effect, usage=["COST_COVERAGE"], scope="PROJECT")], "COMPILED", ""
    lib = None if defer_binding else library_for(row)
    main_refs = [] if defer_binding else selector_codes(value(row, "main_code"), lib, catalog)
    related = "4-3052~3063" if n == 4 else value(row, "related_code")
    effect = {"type": "associate_item", "pair_key": row["rule_id"], "main_catalog_references": main_refs,
              "work_coverage_check": "REQUIRED_BEFORE_ADD", "missing_inputs": "NEEDS_INPUT",
              "technical_conditions_still_required": True}
    condition = [eq("binding.source_rule_id", row["rule_id"])] if defer_binding else [inside("selection.main_quota_id", [x["id"] for x in main_refs])]
    formula = None
    if related == "补": effect.update(target_kind="SUPPLEMENT", display_name=value(row, "related_name"))
    elif not defer_binding: effect["catalog_references"] = selector_codes(related, lib, catalog)
    scope = "ITEM"
    if row["status"] == "EXCLUDED_BY_USER":
        effect["type"] = "exclude_association"
        rule = make(row, "", AND(*condition), effect)
        return [rule if defer_binding else bound(rule, lib, catalog)], "COMPILED_EXCLUSION", ""
    if n in (3, 4, 5):
        condition += [eq("object.kind", "pump"), eq("motor.explosion_proof", n == 5)]
        condition.append(bounds("motor.power_kw", "kW", 0 if n == 3 else 3, 3 if n == 3 else (3000 if n == 4 else 200), n == 5))
        formula = V("motor.actual_count", "台")
        effect["choose_target_by_verified_power_bracket"] = True
        if n == 3: effect["includes_commissioning_no_extra_item"] = True
    elif n in (6, 7, 8):
        condition.append(eq("object.kind", "air_cooler"))
        formula = V({6: "air_cooler.frame_mass", 7: "air_cooler.fan_count", 8: "air_cooler.louver_count"}[n], {6: "t", 7: "台", 8: "个"}[n])
    elif 9 <= n <= 16 or n in (68, 69):
        return [], "PENDING", "需指定库检测/热处理单位含量及施工说明；射线胶片规格章说明尚缺，保留已确认衬里排除与13—16行编号修正。"
    elif 17 <= n <= 36 or n == 66:
        actuator = {"5-2009": "electric", "5-2008": "pneumatic", "5-2010": "hydraulic_linkage"}[related]
        if related == "5-2010":
            actuator = "gas_hydraulic" if "气液" in value(row, "subject") else "electro_hydraulic"
        condition += [eq("object.kind", "valve"), eq("valve.actuator_type", actuator),
                      eq("valve.connection", "welded" if 29 <= n <= 36 else "flanged")]
        if n == 66: condition.pop()  # source 66 does not specify connection form
        formula = V("valve.actual_actuator_count", "台")
    elif n in (37, 38, 39, 48, 50, 52, 54, 72, 73, 97, 98):
        kind = {48: "twisted_pair", 50: "optical_cable", 52: "buried_telephone", 54: "duct_telephone"}.get(n, "power_cable")
        condition += [inside("object.kind", ["signal_cable", "control_cable"]) if n == 39 else eq("object.kind", kind), eq("group.members_complete", True)]
        if n == 73: condition.append(bounds("group.distinct_model_or_spec_count", "1", 3))
        coefficient = "0.3" if n in (38, 73, 98) else "0.4"
        formula = mul(div(V("group.total_physical_length_m", "m"), C(100, "m")), C(coefficient))
        effect.update(group=group_spec("cable_category"), output_unit=value(row, "related_unit"), quantity_kind="QUOTA_QUANTITY")
        scope = "GROUP"
    elif n in (40, 41, 42, 43):
        condition += [inside("object.kind", ["gas_detector", "flame_detector"]), eq("group.members_complete", True), bounds("alarm.physical_points", "1", 1)]
        formula = C(1) if n in (40, 42) else sub(V("alarm.physical_points"), C(1))
        effect.update(group=group_spec("alarm_loop_id"), output_unit="套", emit_only_positive=True)
        effect["group"]["anchor"] = "VERIFIED_EQUIPMENT_TABLE_ANCHOR"
        scope = "GROUP"
    elif n in (44, 45, 46):
        condition += [eq("io.physical_points_verified", True), eq("io.virtual_bus_points_excluded", True)]
        formula = {44: V("io.pulse_points"), 45: div(add(V("io.digital_inputs"), V("io.digital_outputs")), C(8)),
                   46: add(V("io.analog_inputs"), V("io.analog_outputs"))}[n]
        effect.update(output_unit=value(row, "related_unit"), rounding="NONE", basis="PHYSICAL_POINTS_ONCE")
    elif n == 47:
        condition += [eq("fcs.same_segment_master_configuration", True), eq("fcs.high_speed_h2", True),
                      eq("fcs.segment_test_and_communication_diagnostics", True)]
        formula = V("fcs.independent_master_or_system_count", "套")
        effect["interface_name_alone_is_insufficient"] = True
    elif n in (56, 58, 62, 64):
        formula = div(V("pipe.physical_length_m", "m"), C(100, "m"))
        effect.update(output_unit="100m", quantity_kind="QUOTA_QUANTITY", check_corrosion_work_coverage=True)
    elif n in (57, 59, 63, 65, 67):
        condition += [eq("group.members_complete", True), eq("trench.already_counted_scope_verified", True)]
        formula = sub(mul(V("group.total_physical_length_m", "m"), V("trench.actual_width_m", "m"), V("trench.actual_depth_m", "m")),
                      V("trench.already_counted_volume_m3", "m3"))
        effect.update(group=group_spec("pipe_category", ("pipe_material", "pipe_diameter", "main_code_group", "trench_id")),
                      output_unit="m3", emit_only_positive=True, dimensions_default=None, counted_volume_default=None)
        scope = "GROUP"
    elif n in (60, 61):
        condition += [inside("context.geology", ["loess", "desert"])]
        formula = V("pipe.physical_length_m", "m")
        effect.update(output_unit="m", material_by_geology={"loess": "灰土", "desert": "砂"}, other_geology="NEEDS_INPUT")
    elif n == 87:
        formula = V("transformer.design_oil_mass_t", "t")
    elif n in (88, 89, 90, 92, 93, 94, 95):
        condition.append(eq("object.kind", "synchronous_condenser"))
        formula = V("condenser.actual_machine_count", "台")
    elif n == 96:
        formula = mul(V("group.total_physical_length_m", "m"), C("0.7", "m"), C(1, "m"), C("0.5"))
        condition.append(eq("group.members_complete", True))
        effect.update(group=group_spec("cable_category"), output_unit="m3", parameter_policy="CONFIRMED_TEMPORARY_DEFAULTS", length_fraction="0.5")
        scope = "GROUP"
    elif n == 99:
        condition += [eq("object.kind", "grounding_flat_steel"), eq("group.members_complete", True)]
        formula = mul(V("group.total_physical_length_m", "m"), V("grounding.trench_width_m", "m"), V("grounding.trench_depth_m", "m"))
        effect.update(group=group_spec("grounding_scope_id"), output_unit="m3", dimensions_default=None,
                      policy="SEPARATE_FROM_CABLE_EARTHWORK_PER_CONFIRMED_A06_15")
        scope = "GROUP"
    else:
        raise ValueError(f"UNHANDLED_A06_ROW: {n}")
    effect["formula"] = formula
    effect.setdefault("output_unit", value(row, "related_unit"))
    rule = make(row, "", AND(*condition), effect, usage=["QUOTA_MATCH", "QUANTITY_CONVERT"], scope=scope)
    result = [rule if defer_binding else bound(rule, lib, catalog)]
    if n == 47:
        h1 = deepcopy(effect)
        h1["pair_key"] = row["rule_id"] + "-H1"
        h1["catalog_references"] = selector_codes("5-4019", lib, catalog)
        h1["source_database_name_preserved"] = True
        h1_condition = AND(inside("selection.main_quota_id", [x["id"] for x in main_refs]),
                           eq("fcs.system_class", "FCS"), inside("fcs.protocol", ["FF-H1", "Profibus-PA"]),
                           eq("fcs.high_speed_h2", False))
        result.append(bound(make(row, "-H1", h1_condition, h1, usage=["QUOTA_MATCH", "QUANTITY_CONVERT"]), lib, catalog))
    return result, "COMPILED", ""


def a07(row, catalog):
    n = row["row"]
    if n <= 6: return [], "EXCLUDED", "用户确认的残留示例，不作单位换算规则。"
    if n == 12: return [], "PENDING", "设计重量取值原则已确认；光伏指南/实际指标库的目标绑定待核，不猜支架单重。"
    lib = library_for(row)
    refs = selector_codes(value(row, "target_code"), lib, catalog)
    condition = [inside("selection.main_quota_id", [i["id"] for i in refs])]
    effect = {"type": "convert_quantity", "catalog_references": refs, "quantity_kind": "QUOTA_QUANTITY", "physical_quantity_unchanged": True,
              "on_missing_input": "NEEDS_INPUT", "parameter_defaults": None, "output_unit": value(row, "target_unit")}
    scope = "ITEM"
    if n == 7:
        condition.append(eq("object.kind", "cable_tray"))
        effect["formula"] = div(mul(V("tray.section_count", "节"), V("tray.actual_section_length_m", "m")), C(10, "m"))
        effect["mass_conversion"] = "SEPARATE_EVIDENCE_REQUIRED_TABLE_4_7_NOT_EMBEDDED"
    elif n == 8:
        condition += [eq("object.kind", "cable_lug"), eq("lug.use", "grounding_jumper")]
        effect["formula"] = div(V("lug.count", "个"), C(20, "个"))
    elif n == 9:
        condition += [eq("optical_terminal.supply_scope", "complete_pair_two_ends")]
        effect["formula"] = V("optical_terminal.complete_pair_count", "对")
    elif n == 10:
        condition += [eq("screen.dimensions_include_frame", True), eq("screen.quantity_basis", "complete_screen_count")]
        effect["formula"] = mul(V("screen.outer_width_m", "m"), V("screen.outer_height_m", "m"), V("screen.complete_screen_count"))
        effect["already_total_area_policy"] = "USE_VERIFIED_TOTAL_OUTER_AREA_WITHOUT_MULTIPLYING_AGAIN"
    elif n == 11:
        condition += [eq("group.members_complete", True), eq("heat_shrink.eligible_butt_weld_fittings_verified", True)]
        effect["formula"] = add(V("heat_shrink.main_cut_length_km", "km"), mul(div(V("heat_shrink.eligible_fitting_count"), C(10)), C("0.23", "km")))
        effect["group"] = group_spec("pipe_diameter", ("corrosion_protection_grade",))
        effect["excluded_fittings"] = ["法兰", "阀门", "螺纹", "承插", "随设备成套供货管件"]
        scope = "GROUP"
    result = [bound(make(row, "", AND(*condition), effect, usage=["QUANTITY_CONVERT"], scope=scope), lib, catalog)]
    if n == 10:
        total_effect = deepcopy(effect)
        total_effect["formula"] = V("screen.total_outer_area_m2", "m2")
        total_condition = AND(inside("selection.main_quota_id", [i["id"] for i in refs]),
                              eq("screen.dimensions_include_frame", True), eq("screen.quantity_basis", "total_outer_area"))
        result.append(bound(make(row, "-TOTAL", total_condition, total_effect, usage=["QUANTITY_CONVERT"]), lib, catalog))
    return result, "COMPILED", ""


def a09(row, catalog):
    n = row["row"]
    if row["kind"] == "SECTION_OR_METADATA": return [], "METADATA", "标题/问题栏保留来源，不作为业务动作。"
    if n in (6, 87, 91): return [], "PENDING", "本行主对象为空且没有明确合并继承依据，保留原目标但不跨空行推断作用域。"
    if n in (11, 18, 19, 20, 23, 24, 25, 62, 63, 68):
        return [], "PENDING", "规则业务问题不重复询问；仍需将本行具体目录/作用域与源条件逐项核验，不能从忽略提问推定任意边界。"
    if n in (12, 13):
        return [], "LINKED_RULE", "采用A05-R010/A05-R010-BORROW/A05-R011的同一管线分流条件，源片段保留关联。"
    subject = value(row, "subject")
    condition = [eq("context.route_subject", subject)] if subject else []
    target = value(row, "target")
    effect = {"type": "select_pricing_method", "target_label": target, "within_allowed_scope_only": True,
              "target_mapping_required": True, "on_missing_target": "NEEDS_INPUT", "select_actual_item": False}
    scope = "ITEM"
    if n in (7, 16, 21, 50, 54, 73):
        condition += [eq("indicator.applicable_standard_module_exists", True), eq("indicator.module_identity_verified", True)]
        if n == 16: condition.append(eq("indicator.atlas_number_from_design", True))
        effect["policy"] = "PREFER_APPLICABLE_STANDARD_MODULE"
    elif n in (8, 51, 55, 69, 79):
        condition += [eq("object.kind", "storage_tank"), eq("indicator.capacity_exact_match", True), eq("indicator.module_identity_verified", True)]
        effect["capacity_policy"] = "EXACT_CORRESPONDENCE_NOT_RANGE_CLAMP"
    elif n in (9, 17, 22, 52, 53, 56, 70, 74, 80):
        condition += [eq("indicator.applicable_standard_module_exists", False)]
        if n == 9: condition.append(inside("object.kind", ["valve", "pipeline"]))
        if n == 52: condition.append(inside("object.kind", ["carbon_steel_pipe", "carbon_steel_valve"]))
        if n == 53: condition.append(inside("object.kind", ["cpvc_pipe", "cpvc_valve"]))
        if n == 80: condition.append(NOT(eq("object.kind", "storage_tank")))
    elif n in (28, 29):
        valve = eq("object.kind", "valve")
        condition.append(valve if n == 29 else NOT(valve))
        effect["exclusive_group"] = "gas_station_route"
    elif n in (32, 33):
        present = eq("transformer.low_voltage_distribution_box_listed", True)
        condition.append(present if n == 32 else NOT(present))
        effect["exclusive_group"] = "pole_transformer_route"
        if n == 32: effect.update(capacity_policy="LARGEST_ABOVE_VERIFIED_MAX", covered_equipment="柱上变电站低压配电箱")
    elif n in (34, 35):
        condition.append(bounds("electrical.voltage_kv", "kV", 0 if n == 34 else 110, 35 if n == 34 else None))
        effect["uncovered_voltage_gap"] = "NEEDS_INPUT"
    elif n in (36, 37, 38):
        condition.append(inside("electrical.voltage_label", {36: ["10kV"], 37: ["35kV", "110kV"], 38: ["10kV", "35kV", "110kV"]}[n]))
    elif n in (39, 40):
        condition = [eq("project.rooftop_pv", True)] if n == 40 else [eq("project.rooftop_pv", False), eq("project.production_distributed_pv", True), eq("project.special_pv_project", False)]
        effect.update(exclusive_group="project_pv_method", no_default_fallback=True)
        scope = "PROJECT"
    elif n == 43: condition.append(eq("context.location", "offsite"))
    elif n in (48, 49):
        condition += [eq("context.location", "offsite"), eq("indicator.applicable_standard_module_exists", n == 48)]
        effect["exclusive_group"] = "offsite_water_pipe_method"
    elif n == 86:
        condition += [inside("indicator.main_work", ["steel_structure", "module", "pipeline", "storage_tank", "well_site"]), eq("coverage.corrosion_work_included", True)]
        effect = {"type": "check_coverage", "work": "corrosion_protection", "duplicate_charge": "FORBIDDEN", "preserve_physical_item": True}
    elif n in (89, 90):
        condition = [eq("object.kind", "crossing"), eq("crossing.separate_drawing", True), eq("coverage.crossing_work_included", False), eq("coverage.supplement_basis_verified", True)]
        effect.update(target_label="标准化造价指标", policy="ONLY_UNCOVERED_WORK", note_in_estimate_required=True)
        if n == 89: return [], "LINKED_RULE", "单出图条件并入A09-R090，并保留已含工作防重条件。"
    else:
        # Explicit object -> method lines. Actual module content is still verified at runtime.
        if n not in (4, 5, 44, 47, 59, 66, 67, 76, 83, 94, 97): raise ValueError(f"UNHANDLED_A09_ROW: {n}")
        if n == 4: condition.append(inside("project.production_type", ["shale_oil", "conventional"]))
        effect["verify_actual_work_coverage"] = True
    rule = make(row, "", AND(*condition), effect, usage=["QUOTA_MATCH", "COST_COVERAGE"], scope=scope)
    rule["context"]["stage_policy"] = {"source": "latest-confirmations", "feasibility": "ESTIMATE_INDICATOR_FIRST",
        "preliminary_design": "OIL2022_FIRST", "new_energy_both_stages": "ESTIMATE_INDICATOR", "apply_object_specific_exceptions": True}
    return [rule], "COMPILED", ""


def a11(row, catalog):
    n = row["row"]
    if n in (5, 6, 7, 8, 17):
        return [], "DEFERRED_0904", "参数化计价数量/裸管重量规则保留完整来源与确认，不在本次0903启用。"
    if n in list(range(9, 33)) + [33, 34, 35, 36, 55, 56, 58, 59, 60, 61, 63, 64, 65, 66, 67, 68, 69]:
        return [], "PENDING", "仅表达检索用途已确认；对应标准版本/条款、型号语义或完整属性的技术证据未齐，不写入硬等价或默认补值。"
    source, target = value(row, "source_expression"), value(row, "candidate_expression")
    if n == 4:
        effect = {"type": "expand_query", "formula": mul(V("feature.pressure_mpa", "MPa"), C(10, "per_MPa")),
                  "target_feature": "PN", "approximate": True, "preserve_source": True, "creates_design_fact": False,
                  "material_equivalence": False, "inverse_mapping": False}
        rule = make(row, "", eq("feature.pressure_context_verified", True), effect, strength="RETRIEVAL_ONLY")
    else:
        kind = "material_designation" if 37 <= n <= 53 else {3: "rated_power", 54: "pressure_range", 57: "valve_model", 62: "fuse_model", 70: "check_valve_model"}[n]
        # Literal, scoped forward hints. No token substring replacement and no transitive aliases.
        condition = AND(eq("feature.kind", kind), eq("feature.source_expression", source))
        effect = {"type": "expand_query", "source_expression": source, "target_expression": target,
                  "match_mode": "EXACT_WHOLE_FIELD", "preserve_source": True, "creates_design_fact": False,
                  "material_equivalence": False, "inverse_mapping": False, "transitive_mapping": False}
        rule = make(row, "", condition, effect, strength="RETRIEVAL_ONLY")
        if 37 <= n <= 53: rule["information_loss"] = {"present": True, "attributes": ["grade_or_material_subtype"]}
    return [rule], "COMPILED", ""


def normalize(source_rows, catalog):
    FIELDS.clear()
    catalog["source_rows_by_id"] = {r["rule_id"]: r for r in source_rows}
    approved, pending, dispositions = [], [], []
    for row in source_rows:
        try:
            rules, state, reason = {"A-05": a05, "A-06": a06, "A-07": a07, "A-09": a09, "A-11": a11}[row["sheet"]](row, catalog)
        except ValueError as exc:
            # Only catalog-resolution limitations become pending. Programming errors stop the build.
            if not str(exc).startswith(("BOOK_IDENTITY_", "MISSING_RANGE_", "NO_CATALOG_", "MISSING_CATALOG_", "UNRESOLVED_CODE_")):
                raise
            rules, state, reason = [], "PENDING", str(exc)
        if state == "PENDING":
            # Revisit only the first release's unresolved branches using the same evidence.
            # This module is an offline authoring supplement, not a runtime interpreter.
            from authoring_revision import resolve
            rules, state, reason = resolve(row, catalog, reason)
        from authoring_confirmations import revise
        rules, state, reason = revise(row, catalog, rules, state, reason)
        from authoring_round2 import revise_round2
        rules, state, reason = revise_round2(row, catalog, rules, state, reason)
        for rule in rules:
            effect = rule["effect"]
            supplement = catalog.get("verified_supplement")
            if supplement:
                for finding in supplement["findings"]:
                    if row["rule_id"] in finding["rule_ids"] and rule["family"] != "A05":
                        effect.setdefault("catalog_evidence_refs", []).append("existing-evidence.json#findings." + finding["id"])
                        effect.setdefault("review_notes", []).append(finding["finding"] + finding["limit"])
                if effect.get("catalog_evidence_refs"): rule["revision"] = "3"
            if effect.get("technical_conditions_still_required"):
                guard = eq("evidence.target_identity_unit_and_chapter_verified", True)
                if guard not in effect.setdefault("execution_guards", []): effect["execution_guards"].append(guard)
            if effect.get("work_coverage_check"):
                effect.setdefault("execution_guards", []).append(eq("evidence.same_work_not_already_charged", True))
            if effect.get("target_mapping_required"):
                effect.setdefault("execution_guards", []).append(eq("evidence.method_target_in_allowed_scope_verified", True))
            if rule["family"] == "A09":
                effect["stage_policy"] = {
                    "stage_field": {"field": field("project.stage")},
                    "new_energy_field": {"field": field("project.new_energy", "boolean")},
                    "supported_stages": ["feasibility", "preliminary_design"],
                    "default_preference": {"feasibility": "ESTIMATE_INDICATOR", "preliminary_design": "OIL2022_INDICATOR"},
                    "new_energy_preference_both_stages": "ESTIMATE_INDICATOR",
                    "object_specific_target_requires_verified_applicability": True,
                    "missing_or_conflicting_stage": "NEEDS_INPUT"}
        approved.extend(rules)
        disposition = {"source_record_id": row["rule_id"], "state": state, "rule_ids": [r["rule_id"] for r in rules], "reason": reason}
        if state == "LINKED_RULE":
            disposition["rule_ids"] = ["A05-R010", "A05-R010-BORROW", "A05-R011"] if row["sheet"] == "A-09" and row["row"] in (12, 13) else ["A09-R090"]
        if state in ("PENDING", "PARTIAL_COMPILED", "DEFERRED_0904"):
            pending.append({"rule_id": row["rule_id"], "family": row["sheet"].replace("-", ""), "source_record_id": row["rule_id"],
                            "review_status": "NEEDS_CONFIRMATION", "pending_kind": "PHASE_DEFERRED" if state == "DEFERRED_0904" else "TECHNICAL_EVIDENCE",
                            "business_answer_status": "USE_LATEST_RECORDED_ANSWERS_DO_NOT_REASK", "reason": reason,
                            "source_refs": row["source_refs"], "source_interpretation": row["confirmed_interpretation"],
                            "context": deepcopy(row["context"]), "affects": ["0904"] if state == "DEFERRED_0904" else ["0903"],
                            "conservative_scope": {"family": row["sheet"].replace("-", ""), "subject": value(row, "subject") or value(row, "source_expression"),
                                                   "unknown_scope_policy": "RETAIN_AS_POSSIBLE_WITHIN_FAMILY"},
                            "on_possible_match": "RULE_PENDING_REQUIRE_EVIDENCE", "executable": False})
            if catalog.get("confirmed_changes") and row["sheet"] == "A-06" and row["row"] in (72, 73):
                pv = next(lib for lib in catalog["libraries"] if lib["code"] == "DE06000003")
                pending[-1]["conservative_scope"].update(library_codes=[pv["code"]], library_ids=[pv["id"]],
                    blocked_rule_ids=[row["rule_id"] + "-POLICY"],
                    scope_policy="ONLY_THIS_LIBRARY_BRANCH_UNKNOWN_LIBRARY_RETAINS_POSSIBLE")
        dispositions.append(disposition)
    return approved, pending, dispositions, deepcopy(FIELDS)
