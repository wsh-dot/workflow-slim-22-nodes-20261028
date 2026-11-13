"""Second offline review: separate known policies, project inputs and missing evidence.

No database, model or online business calls. A blocked policy is useful structured
work, but is not an executable target binding. Its blocker survives publication.
"""
from copy import deepcopy

from authoring import (AND, OR, NOT, C, V, add, sub, mul, div, eq, inside, bounds,
                       field, value, make, bound, selector_codes, group_spec, chapter_nine)


def binding_spec(row):
    return {"book_title": value(row, "library"), "main_code": value(row, "main_code"),
            "main_name": value(row, "main_name"), "main_unit": value(row, "main_unit"),
            "target_code": value(row, "related_code") or value(row, "target_code"),
            "target_name": value(row, "related_name") or value(row, "target_name"),
            "target_unit": value(row, "related_unit") or value(row, "target_unit"),
            "identity_status": "UNVERIFIED_SOURCE_SELECTOR_NOT_CATALOG_ID"}


def missing_evidence(row):
    """Exact remaining artifact, not a repeated request for an answered business policy."""
    f, n = row["sheet"], row["row"]
    if f == "A-05":
        return ["已核到现概算库第7章四.2：厂站内35kV及以上转电力预算2018第五册。仍缺本35kV、3×95mm²示例的真实目标编号/名称/单位、对应库与适用说明；实际敷设位置是项目输入。不得将厂站内分支泛用于站外或自动换库，旧YD8-46/20kV映射仍失效。"]
    if f == "A-06":
        gaps = []
        if n in (10, 14, 69):
            gaps.append("石油2022射线探伤章说明中胶片规格的选择条款及版本/条目。数据库3-2202与3-2204均有8mm以内档但胶片长度不同，壁厚不足以确定胶片；未取得该条款前不得自动选片。")
        if 64 <= n <= 70 or n in (72, 73):
            gaps.append("源表“石油建设安装工程概算定额(2022版)”与库DE1000022001“石油建设安装工程概算指标2022”的正式身份对应记录；已有同号条目是候选证据，不能单凭同号消除书名差异。")
        if n == 70:
            gaps.append("E70已明确“埋地管线防腐保温”，但C70/D70为空且无合并继承；还缺该主工作在指定库的作用域/主项对应记录，不能继承上一行7-4006～4013。")
        if n in (72, 73):
            gaps.append("还缺光伏2022指南↔DE06000003、陆上风电2023指南↔DE07000022的版本映射；风电候选快照未检得主项4-3176，须补正式条目或明确该库不适用的依据。")
        if 74 <= n <= 77:
            gaps.append("光伏2022指南↔DE06000003“石油工程光伏定额（2022试行）”的正式版本映射。G-b1及G-b37～40名称、单位已在快照查得，不再笼统称缺编号。")
        if 78 <= n <= 81:
            gaps.append("陆上风电2023指南↔DE07000022“中石油陆上风电场安装工程单位估价表（2023试行）”的正式版本映射。F-b4已查得；企业暂定计费参数已有答复，不再列为待答。")
        if 87 <= n <= 99 and n != 91:
            gaps.append(f"电力2018正式章节/编码体系对应资料：源主项{value(row, 'main_code')}、关联项{value(row, 'related_code')}的编码在DE07000019冻结快照均未检得；源表用YD/YJ/YS，现库为GD/GJ/GS等，不能机械换前缀或借用其他库。须有真实编号、单位及工作覆盖对应证据。")
            if 88 <= n <= 95:
                gaps.append("现库有GJ14-2“300Mvar调相机 定子液压提升法 空冷”、单位台；源YJ16-2为组。名称相同不足以证明工作内容及组/台口径相同，须核对正式章节后才能绑定。")
            if n == 87:
                gaps.append("现库有GD2-13“110kV三相三绕组变压器安装 容量120000kVA以内”、单位台；这是名称候选，不能替代源YD2-20或证明绝缘油过滤须独立关联。")
        return gaps
    if f == "A-07":
        return ["仍缺光伏2022指南↔DE06000003的正式版本映射。现库已查得G-b2“固定支架 安装”、单位t，作为源表无编号项的明确候选；取得版本及适用范围对应依据后才能绑定。设计重量是项目输入，已生成参数规则，不再作为编译缺口。"]
    if f == "A-09":
        if n in (6, 87, 91):
            return [f"A09!B{n}/D{n}为空且无合并锚点，只有C{n}指标名称；缺本行适用对象及条件的可追溯记录。不能向上填充或把通用优先原则擅自分配给空白行。"]
        if n == 11:
            return ["B11“油气集输-**管线”的**没有对象定义或映射依据；已保留Φ48～168范围，但不把**自动解释为任意油气管线。需能识别适用管线类型的来源记录。"]
        if n == 23:
            return ["B23“天然气-**管线”的对象定义缺失；D23同时写“Φ27～Φ273（含168）”，273与168的限定关系及与D24/D25“Φ273以上”交界不明确。A09-04被标红忽略不等于已更正这两段文字。"]
        if n in (24, 25):
            return ["B23合并锚点“天然气-**管线”的对象定义及Φ273边界归属仍缺可追溯依据；与D23区间可能重叠。已引用A05整线第八/九章分流，但不能替代这两项前置范围证据。"]
        if n == 68:
            return ["B68“注水-**管线”的**所指管线类型缺明确对象定义/映射记录；源表无进一步限定，不能擅自解释为全部注水管线。"]
    return []


def blocked(row, rules):
    reasons = missing_evidence(row)
    if not reasons:
        raise ValueError("blocked policy needs a concrete evidence gap: " + row["rule_id"])
    for rule in rules:
        if rule["rule_id"] == row["rule_id"]: rule["rule_id"] += "-POLICY"
        rule["revision"] = "2"
        rule["effect"]["release_blocked_by"] = [row["rule_id"]]
        rule["effect"].setdefault("review_notes", []).append("条件/公式已整理；关联证据未闭合，禁止输出正式套项或金额。")
    return rules, "PARTIAL_COMPILED" if rules else "PENDING", "；".join(reasons)


def inspection(row, catalog, defer_binding=False):
    n = row["row"]
    method = {9: "ultrasonic", 10: "radiographic", 11: "pre_post_heat", 12: "heat_treatment",
              13: "ultrasonic", 14: "radiographic", 15: "pre_post_heat", 16: "heat_treatment",
              68: "ultrasonic", 69: "radiographic"}[n]
    lib = "DE1000022001"
    source = binding_spec(row)
    if defer_binding:
        condition = [eq("binding.source_rule_id", row["rule_id"])]
        references = {}
    else:
        main = selector_codes(value(row, "main_code"), lib, catalog)
        condition = [inside("selection.main_quota_id", [x["id"] for x in main])]
        references = {"main_catalog_references": main, "catalog_references": selector_codes(value(row, "related_code"), lib, catalog)}
    condition += [eq("inspection." + method + ".required_by_specification", True),
                  eq("inspection." + method + ".quantity_basis_verified", True)]
    # The lining exclusion is present in rows 9-16, not invented for gas rows 68/69.
    if 9 <= n <= 16: condition.append(eq("pipeline.lined", False))
    if n <= 12:
        excluded = selector_codes("3-2061~2065", lib, catalog)
        condition.append(NOT(inside("selection.main_quota_id", [x["id"] for x in excluded])))
    unit = "张" if method == "radiographic" else "口"
    quantity = f"inspection.{method}.verified_physical_quantity"
    effect = {"type": "associate_item", "pair_key": row["rule_id"], **references,
              "formula": div(V(quantity, unit), C(10, unit)), "output_unit": value(row, "related_unit"),
              "quantity_kind": "QUOTA_QUANTITY", "technical_conditions_still_required": True,
              "work_coverage_check": "REQUIRED_BEFORE_ADD", "on_missing_input": "NEEDS_INPUT",
              "parameter_defaults": None,
              "inspection_policy": {"method": method, "automatic_all_methods": False,
                  "physical_quantity_basis": "VERIFIED_QUOTA_CONTENT_AND_DESIGN_SPECIFICATION_RATIO",
                  "basis_source_required": True, "ratio_default": None,
                  "raw_main_quantity_is_not_weld_or_film_count": True,
                  "reference_content_codes": "3-2101~2111" if n in (68, 69) else None,
                  "film_selection_from_wall_thickness_alone": False}}
    if defer_binding: effect["source_binding"] = source
    rule = make(row, "", AND(*condition), effect, usage=["QUOTA_MATCH", "QUANTITY_CONVERT"])
    if not defer_binding: rule = bound(rule, lib, catalog)
    if missing_evidence(row): return blocked(row, [rule])
    return [rule], "COMPILED", "已编译条件触发、衬里/编号排除和已核实物理工作量÷10；实际含量及比例由项目/指定子目提供，不设默认。"


def pv_capacity(row):
    effect = {"type": "associate_item", "source_binding": binding_spec(row), "pair_key": row["rule_id"],
              "capacity_split": {"algorithm": "REPEAT_MAX_THEN_CEILING_REMAINDER", "capacity_input": {"field": field("pv.subarray_capacity_mwp", "decimal", "MWp")},
                  "max_mwp": "4", "tiers": [{"upper_mwp": str(i), "target_source_code": "G-b" + str(36 + i)} for i in range(1, 5)],
                  "emit_only_target": value(row, "related_code"), "zero_remainder": "NO_ITEM",
                  "zero_or_negative_capacity": "REJECT", "partition": "ONE_DESIGN_SUBARRAY_AT_A_TIME"},
              "group": group_spec("design_subarray_id"), "output_unit": "子方阵", "quantity_kind": "TIER_OCCURRENCE_COUNT",
              "work_coverage_check": "REQUIRED_BEFORE_ADD", "on_missing_input": "NEEDS_INPUT"}
    rule = make(row, "", AND(eq("object.kind", "pv_module"), eq("pv.design_subarray_partition_verified", True),
                            eq("group.members_complete", True)), effect, scope="GROUP", usage=["QUOTA_MATCH", "QUANTITY_CONVERT"])
    return blocked(row, [rule])


def wind_charge(row):
    n = row["row"]
    foundation = n in (82, 83)
    count = V("wind.foundation_count" if foundation else "wind.turbine_count", "座" if foundation else "台")
    effect = {"type": "associate_item", "target_kind": "SUPPLEMENT", "display_name": value(row, "related_name"),
              "quantity": count, "output_unit": "座" if foundation else "台", "amount_unit": "CNY",
              "work_coverage_check": "REQUIRED_BEFORE_ADD", "on_missing_amount": "KEEP_QUANTITY_AMOUNT_NULL_NEEDS_INPUT"}
    if foundation:
        cost = "test_pile" if n == 82 else "pile_corrosion"
        effect.update(cost_kind=cost, amount_formula=mul(count, V(f"wind.{cost}.verified_amount_per_foundation", "CNY")),
                      parameter_defaults=None, policy="PROJECT_EVIDENCED_AMOUNT_PER_FOUNDATION",
                      review_notes=["8万元/1万元为原表暂估示例，均不设为默认。试桩与桩身防腐为两个并列项目。"])
        condition = AND(eq("project.kind", "wind_farm"), eq("object.kind", "wind_turbine_foundation"), eq("wind.foundation_scope_verified", True))
    else:
        cost = {78: "crane_assembly", 79: "crane_transport", 80: "crane_insurance", 81: "crane_loading"}[n]
        rate = {78: "50963", 79: "298", 80: "5969", 81: "18916"}[n]
        amount = mul(count, C(rate, "CNY"))
        if n == 79: amount = mul(count, V("wind.transport_km_per_turbine", "km"), C(rate, "CNY_per_km"))
        effect.update(cost_kind=cost, amount_formula=amount, source_binding=binding_spec(row),
                      parameter_policy="EXPERT_CONFIRMED_TEMPORARY_ENTERPRISE_PARAMETERS",
                      review_notes=["每台风机计取；50km只是估算示例，不默认填入。此为0903规则定义的补充费用，不启动0904价格匹配。"])
        condition = AND(eq("project.kind", "wind_farm"), eq("object.kind", "wind_turbine"), eq("binding.source_rule_id", row["rule_id"]))
    effect["unique_by"] = ["project_id", "batch_id", "cost_kind", "source_object_id", "generation"]
    rule = make(row, "", condition, effect, usage=["COST_COVERAGE"])
    return ([rule], "COMPILED", "补充项目及每座计取已确认；金额作为有依据的项目参数，不使用原表示例默认值。") if foundation else blocked(row, [rule])


def a09_revision(row):
    n = row["row"]
    if n in (6, 87, 91): return blocked(row, [])
    condition = [eq("context.route_subject", value(row, "subject"))]
    effect = {"type": "select_pricing_method", "target_label": value(row, "target"),
              "within_allowed_scope_only": True, "target_mapping_required": True,
              "on_missing_target": "NEEDS_INPUT", "select_actual_item": False}
    if n == 18:
        condition += [eq("object.kind", "pipeline"), eq("context.location", "offsite"),
                      inside("pipeline.service_role", ["methanol_injection", "medium_pressure_gas_gathering"]),
                      eq("indicator.module_identity_verified", True), eq("indicator.applicable_standard_module_exists", True)]
    elif n in (19, 20, 24, 25):
        condition += [eq("object.kind", "pipeline"), eq("context.location", "offsite"),
                      eq("indicator.applicable_standard_module_exists", False),
                      chapter_nine() if n in (20, 25) else NOT(chapter_nine())]
        if n in (19, 20): condition.append(eq("pipeline.service_role", "storage_high_pressure_injection_withdrawal"))
        else:
            # No invented >= versus > boundary: keep the source row's applicability unresolved.
            condition.append(eq("evidence.source_diameter_scope_verified", True))
        effect.update(exclusive_group="pipeline_chapter_8_or_9", review_notes=["复用A05-R010/R011整条管线分流；缺项借用仍为独立子目动作。"])
    elif n == 62:
        condition += [eq("object.kind", "storage_tank"), eq("indicator.capacity_exact_match", True),
                      eq("indicator.module_identity_verified", True), bounds("tank.capacity_m3", "m3", 20, 5000)]
        effect.update(policy="PREFER_APPLICABLE_STANDARD_MODULE", capacity_policy="EXACT_CORRESPONDENCE_NOT_RANGE_CLAMP")
    elif n == 63:
        condition += [eq("indicator.applicable_standard_module_exists", False)]
        effect["verify_actual_work_coverage"] = True
    else:
        condition += [eq("object.kind", "pipeline"), eq("evidence.source_object_scope_verified", True),
                      eq("indicator.module_identity_verified", True), eq("indicator.applicable_standard_module_exists", True)]
        if n == 11: condition.append(bounds("pipeline.outer_diameter_mm", "mm", 48, 168))
        if n == 23: condition.append(eq("evidence.source_diameter_scope_verified", True))
    rule = make(row, "", AND(*condition), effect, usage=["QUOTA_MATCH", "COST_COVERAGE"])
    if missing_evidence(row): return blocked(row, [rule])
    return [rule], "COMPILED", "按源表明确对象和专家A09-02/A09-07答复补齐；具体项目阶段、模块和覆盖仍由实际输入校验。"


def a11_revision(row):
    n = row["row"]
    source, target = value(row, "source_expression"), value(row, "candidate_expression")
    kind = ("pressure_class" if 9 <= n <= 15 else "pipe_outer_to_nominal" if n == 16 else
            "nominal_pipe_size" if 18 <= n <= 32 else "pump_attributes" if n == 33 else
            "pump_flow" if n == 34 else "pump_head" if n in (35, 36) else
            "flange_expression" if n in (55, 56) else "pipe_fitting_expression" if 58 <= n <= 61 else
            "distribution_box_expression" if 63 <= n <= 67 else "heat_exchanger_expression" if n == 68 else "valve_model")
    constraints = {"mode": "ADDITIONAL_QUERY_HINT_ONLY", "hard_constraints_source": "ORIGINAL_VERIFIED_FACTS_ONLY",
                   "replace_original_query": False, "auto_accept_candidate": False,
                   "unverified_attributes": [], "prohibit_fact_backfill": True,
                   "same_price_or_material_inference": False}
    if 9 <= n <= 15: constraints["unverified_attributes"] = ["B16.5版本/材料组/温度压力额定值，不把Class-PN提示当设计压力换算"]
    elif n == 16: constraints["unverified_attributes"] = ["外径系列及DN标准适用范围"]
    elif 18 <= n <= 32: constraints["unverified_attributes"] = ["GB/T 1047版本/公称尺寸系列，不把英寸换算为实际外径"]
    elif n in (55, 56): constraints["unverified_attributes"] = ["法兰型式、材质、标准和压力标记；原B56的PN2.5未经证实，不写为硬属性"]
    elif 58 <= n <= 61: constraints["unverified_attributes"] = ["CF415K/RE/RC的适用标准系列、偏心/同心等原有关键属性"]
    elif 64 <= n <= 67: constraints["unverified_attributes"] = ["型号/品牌/回路用途/防护等级；IP4X和IP40不得据提示认定技术等价"]
    elif n == 68: constraints["unverified_attributes"] = ["源侧温度工况、抗硫、材质及压力语境；候选省略属性须保留原约束"]
    elif n == 69: constraints["unverified_attributes"] = ["阀门标准版次、螺纹连接、密封和材质完整属性"]
    effect = {"type": "expand_query", "source_expression": source, "target_expression": target,
              "match_mode": "EXACT_WHOLE_FIELD", "preserve_source": True, "creates_design_fact": False,
              "material_equivalence": False, "inverse_mapping": False, "transitive_mapping": False,
              "candidate_policy": constraints}
    condition = AND(eq("feature.kind", kind), eq("feature.source_expression", source))
    rule = make(row, "", condition, effect, strength="RETRIEVAL_ONLY")
    if n == 33:
        effect["review_notes"] = ["仅解释当前原文Q/H/N为流量/扬程/电机功率；例中的70/400/160不作为其他设备的默认值。"]
    elif n == 63:
        effect["review_notes"] = ["A11-06已确认本例WBX(T)-400中的400为额定电流400A；不得推广到其他型号后缀。"]
    if n == 34:
        rule["conditions"] = AND(eq("feature.kind", kind), eq("pump.gallon_system", "US"))
        effect.update(formula=div(V("pump.flow_m3_per_h", "m3_per_h"), C("0.227", "m3_per_h_per_GPM")),
                      output_unit="GPM_US", target_feature="flow_GPM_US", approximate=True, match_mode="VERIFIED_TYPED_FEATURE")
    if n in (35, 36):
        pressure_unit, coefficient = ("psi", "0.703") if n == 35 else ("bar", "10.2")
        clear_water = AND(eq("pump.fluid", "clear_water"), bounds("pump.temperature_c", "degC", 4, 4),
                          bounds("pump.density_kg_m3", "kg_per_m3", 1000, 1000))
        rule["conditions"] = AND(eq("feature.kind", kind), clear_water)
        effect.update(formula=div(V("pump.head_m", "m"), C(coefficient, "m_per_" + pressure_unit)),
                      output_unit=pressure_unit, target_feature="pressure_" + pressure_unit, approximate=True,
                      match_mode="VERIFIED_TYPED_FEATURE")
        general = deepcopy(rule)
        general["rule_id"] += "-GENERAL"
        general["conditions"] = AND(eq("feature.kind", kind), NOT(clear_water),
                                    eq("pump.design_density_and_gravity_verified", True),
                                    eq("pump.pressure_unit_factor_verified", True))
        general["effect"]["formula"] = div(mul(V("pump.head_m", "m"), V("pump.density_kg_m3", "kg_per_m3"), V("pump.gravity_m_s2", "m_per_s2")),
                                             V("pump.pa_per_" + pressure_unit, "Pa_per_" + pressure_unit))
        general["effect"]["parameter_defaults"] = None
        general["effect"]["review_notes"] = ["按已答H=p/(ρg)变形；实际密度、重力和压力单位系数均须带依据，缺失不套清水常数。"]
        return [rule, general], "COMPILED", "已确认的近似系数及非清水公式已参数化，仅用于属性检索；不做0904计价。"
    if constraints["unverified_attributes"]:
        rule["information_loss"] = {"present": True, "attributes": constraints["unverified_attributes"]}
    return [rule], "COMPILED", "依据已确认的A11用途，按原文整字段增加单向检索提示；标准细节限制硬属性认定，不阻断此有限用途。"


def resolve(row, catalog, old_reason):
    family, n = row["sheet"], row["row"]
    if family == "A-11": return a11_revision(row)
    if family == "A-09": return a09_revision(row)
    if family == "A-05":
        evidence = catalog.get("verified_supplement")
        if not evidence: return blocked(row, [])
        effect = {"type": "select_pricing_method", "target_label": "电力建设工程预算定额（2018年版）第五册电缆输电线路工程相应子目",
                  "source_binding": {**binding_spec(row), "book_title": value(row, "library_and_profession")},
                  "within_allowed_scope_only": True, "target_mapping_required": True, "select_actual_item": False,
                  "on_missing_target": "NEEDS_INPUT", "policy": "VERIFIED_LOOKUP_DIRECTION_FOR_STATION_35KV_SAMPLE_ONLY",
                  "review_notes": ["本轮已读DE07000019第7章四.2；仅厂站内成立。目标子目未绑定，不自动切换到预算库，旧YD8-46是失效来源值。"],
                  "catalog_evidence_refs": ["existing-evidence.json#sections.electric_cable", "existing-evidence.json#findings.F01"]}
        condition = AND(eq("object.kind", "power_cable"), eq("context.location", "station"),
                        bounds("electrical.voltage_kv", "kV", 35, 35), eq("material.source_spec", value(row, "subject")))
        rule = bound(make(row, "", condition, effect), "DE07000019", catalog)
        return blocked(row, [rule])
    if family == "A-07":
        effect = {"type": "convert_quantity", "source_binding": binding_spec(row), "output_unit": "t",
                  "physical_quantity_unchanged": True, "parameter_defaults": None, "on_missing_input": "NEEDS_INPUT"}
        total = make(row, "-TOTAL", AND(eq("object.kind", "pv_support"), eq("pv_support.mass_basis", "design_total")),
                     {**effect, "formula": V("pv_support.design_total_mass_t", "t")}, usage=["QUANTITY_CONVERT"])
        per_unit = make(row, "", AND(eq("object.kind", "pv_support"), eq("pv_support.mass_basis", "design_per_unit")),
                        {**effect, "formula": mul(V("pv_support.count", "个"), V("pv_support.design_mass_per_unit_t", "t"))}, usage=["QUANTITY_CONVERT"])
        return blocked(row, [total, per_unit])
    if family == "A-06":
        if n in range(9, 17) or n in (68, 69): return inspection(row, catalog, n in (68, 69))
        if 74 <= n <= 77: return pv_capacity(row)
        if 78 <= n <= 83: return wind_charge(row)
        if n == 70:
            effect = {"type": "associate_item", "source_binding": binding_spec(row), "target_kind": "SUPPLEMENT",
                      "display_name": value(row, "related_name"), "output_unit": "m3", "dimensions_default": None,
                      "formula": mul(V("pipe.physical_length_m", "m"), V("trench.actual_width_m", "m"), V("trench.actual_depth_m", "m")),
                      "work_coverage_check": "REQUIRED_BEFORE_ADD", "review_notes": ["1m×0.7m×1.8m=1.26m³只为修正算例，尺寸不默认。不得继承上一行主项。"]}
            return blocked(row, [make(row, "", AND(eq("context.profession", "防腐"), eq("selection.main_work", "埋地管线防腐保温")), effect, usage=["QUOTA_MATCH", "QUANTITY_CONVERT"])])
        if n == 91:
            # Negative work exclusion does not create or require a catalog item.
            effect = {"type": "exclude_association", "source_binding": binding_spec(row),
                      "policy": "LITERAL_SOURCE_CODE_EXCLUSION_WITHIN_NAMED_BOOK_ONLY", "select_actual_item": False}
            condition = AND(eq("object.kind", "synchronous_condenser"), eq("selection.main_quota_code", "YJ16-2"))
            rule = bound(make(row, "", condition, effect), "DE07000019", catalog)
            return [rule], "COMPILED_EXCLUSION", "YS7-163已明确排除，编译为指定库及主项编码内的禁止关联规则；不生成或伪造该子目ID。其他调相机正向关联仍待绑定。"
        if n in (64, 65, 66, 67, 72, 73, 87, 88, 89, 90, 92, 93, 94, 95, 96, 97, 98, 99):
            from authoring import a06
            rules, _, _ = a06(row, catalog, defer_binding=True)
            for rule in rules: rule["effect"]["source_binding"] = binding_spec(row)
            return blocked(row, rules)
    raise ValueError("unreviewed pending record: " + row["rule_id"] + ": " + old_reason)
