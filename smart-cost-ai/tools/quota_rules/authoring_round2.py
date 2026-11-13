"""Apply the bounded second-round confirmations, offline only."""
from copy import deepcopy

from authoring import AND, OR, eq, inside, bounds, bound, selector_codes, value
from authoring_confirmations import replace_source_selector

PV_ROWS = {f'A06-R{n:03d}' for n in range(72, 78)} | {'A07-R012'}
WIND_ROWS = {f'A06-R{n:03d}' for n in range(78, 82)}
FILM_ROWS = {'A06-R010', 'A06-R014', 'A06-R069'}


def annotate(rule, key, message):
    rule['revision'] = '5'
    rule['review_evidence'] = list(dict.fromkeys(rule['review_evidence'] + ['confirmed-changes:' + key]))
    effect = rule['effect']
    effect['confirmation_refs'] = list(dict.fromkeys(effect.get('confirmation_refs', []) + [key]))
    effect.pop('release_blocked_by', None)
    effect.pop('source_binding', None)
    effect['review_notes'] = [message]
    return rule


def bind_refs(rule, catalog, library, main_code, target_code=None):
    main = selector_codes(main_code, library, catalog)
    rule['effect']['main_catalog_references'] = main
    if target_code:
        rule['effect']['catalog_references'] = selector_codes(target_code, library, catalog)
    rule['conditions'] = replace_source_selector(rule['conditions'], rule['source_record_id'], [i['id'] for i in main])
    # Some formerly blocked policies had only object guards, not a source selector.
    rule['conditions'] = AND(rule['conditions'], inside('selection.main_quota_id', [i['id'] for i in main]))
    return bound(rule, library, catalog)


def film_target_guard(references):
    """Validate an explicit target; overlapping upper bounds never auto-select one."""
    specs = {'3-2202': ('80x150', '8'), '3-2203': ('80x150', '15'),
             '3-2204': ('80x300', '8'), '3-2205': ('80x300', '15'),
             '3-2206': ('80x300', '21'), '3-2207': ('80x300', None)}
    choices = []
    for ref in references:
        film, upper = specs[ref['code']]
        thickness = bounds('inspection.radiographic.wall_thickness_mm', 'mm', 21 if upper is None else 0,
                           upper, include_low=False)
        choices.append(AND(eq('selection.target_quota_id', ref['id']),
                           eq('inspection.radiographic.film_spec_mm', film), thickness))
    return OR(*choices)


def revise_round2(row, catalog, rules, state, reason):
    if catalog.get('confirmed_changes', {}).get('schema_version') != '0903-confirmed-changes-v2':
        return rules, state, reason
    rid = row['rule_id']
    if rid in PV_ROWS:
        out = []
        for old in rules:
            if row['row'] in (72, 73) and old['rule_id'] != rid + '-POLICY':
                out.append(old)
                continue
            r = deepcopy(old)
            main = 'G-b2' if rid == 'A07-R012' else value(row, 'main_code')
            target = 'G-b2' if rid == 'A07-R012' else value(row, 'related_code')
            r = bind_refs(r, catalog, 'DE06000003', main, target)
            annotate(r, 'D02', 'D02仅限本行的光伏安装表项目映射；保留原刊名、源名称和真实库名，不建立全局别名。设计分组、实际重量及同工作防重不因确认而省略。')
            if row['row'] == 73 and row['sheet'] == 'A-06':
                r['effect']['review_notes'].append('源关联名称铺砂、盖砖与光伏4-3143库名铺砂、盖（每增一根）分别保留，须核实际工作内容，不能偷偷补改库名。')
            out.append(r)
        return out, 'COMPILED', 'D02限定库映射已确认，绑定真实主/关联子目；仅解除发行依据缺口，项目输入、允许库和防重校验仍必需。'
    if rid in WIND_ROWS:
        out = []
        for old in rules:
            r = bind_refs(deepcopy(old), catalog, 'DE07000022', 'F-b4')
            r['effect']['execution_guards'] = r['effect'].get('execution_guards', []) + [
                eq('evidence.main_quota_applicability_verified', True),
                bounds('wind.hub_height_m', 'm', 120, 130)]
            annotate(r, 'D03_1', 'D03①仅确认F-b4（120～130m）这4行对应安装估价表。保留原企业暂定参数、实际台数和实际运距；50km不默认，不恢复72/73风电分支，不推定全部35kV及以下适用。')
            out.append(r)
        return out, 'COMPILED', 'D03①按限定确认绑定F-b4；不推广高度、全库刊名或输电线路范围。'
    if rid in FILM_ROWS:
        out = []
        for old in rules:
            r = deepcopy(old)
            refs = r['effect']['catalog_references']
            annotate(r, 'D04', 'D04按用户选择，只读取设计/检测方案明确的规格、张数及经核实具体目标，不自动选片。原书自动选片条款未核；不采用DN100/8mm建议示例。')
            r['effect']['execution_guards'] = r['effect'].get('execution_guards', []) + [
                eq('inspection.radiographic.plan_evidence_verified', True),
                eq('inspection.radiographic.target_and_quantity_same_scope_verified', True),
                film_target_guard(refs),
                bounds('inspection.radiographic.verified_physical_quantity', '张', 0, include_low=False)]
            r['effect']['inspection_policy'].update(
                target_selection='EXPLICIT_VERIFIED_DESIGN_TARGET_ONLY', automatic_film_selection=False,
                thickness_boundary_source='confirmed-changes.json#catalog_evidence.oil_title_directory：总说明第七条，以上不含本数',
                quantity_scope='THIS_EXPLICIT_TARGET_AND_THIS_WORK_SCOPE_ONLY',
                mixed_specifications='PARTITION_VERIFIED_QUANTITIES_BY_TARGET_NEVER_REUSE_TOTAL',
                zero_quantity='NO_ASSOCIATION', negative_quantity='INVALID_INPUT_NO_ASSOCIATION',
                overlapping_thickness_bands='DO_NOT_INFER_LOWER_BOUND_OR_AUTO_SELECT')
            out.append(r)
        return out, 'COMPILED', 'D04改为有项目依据的明确选片分支；规格/壁厚/具体目标须一致且张数>0，数量按本目标张数÷10。缺项仍待补，衬里/编号排除及工作防重保留。'
    return rules, state, reason
