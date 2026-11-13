"""分类证据校验及可信配置中的已确认分类；不推断未确认条款的语义。"""
from __future__ import annotations

import re
import copy
import unicodedata

PHYSICAL = {"item", "assembly", "component"}
IDENTITY_GROUPS = {"group", "summary"}
ANNOTATIONS = {"attribute", "note"}
TEXT_FIELDS = ("description", "nominal_size", "equipment_tag", "remark")


def compile_confirmed_rules(rules: list) -> list:
    """仅从服务端规则配置读取确定分类，料表或模型不能新增这类规则。"""
    compiled = []
    for rule in rules:
        policy = rule.get('confirmed_classification')
        if policy is None:
            continue
        if (not isinstance(policy, dict) or set(policy) != {'node_type', 'identity_patterns', 'exclude_patterns'}
                or policy.get('node_type') not in {'EQUIPMENT', 'MATERIAL'}):
            raise ValueError(f"已确认分类规则格式错误：{rule['rule_id']}")
        groups = []
        for key in ('identity_patterns', 'exclude_patterns'):
            values = policy[key]
            if (not isinstance(values, list) or (key == 'identity_patterns' and not values)
                    or any(not isinstance(v, str) or not v.strip() for v in values)):
                raise ValueError(f"已确认分类匹配条件错误：{rule['rule_id']}")
            try:
                groups.append([re.compile(v, re.IGNORECASE) for v in values])
            except re.error as exc:
                raise ValueError(f"已确认分类正则错误：{rule['rule_id']}") from exc
        compiled.append({'rule_id': rule['rule_id'], 'node_type': policy['node_type'],
                         'includes': groups[0], 'excludes': groups[1]})
    return compiled


def confirmed_classification(r: int, raw: dict, policies: list, inherit=()) -> dict | None:
    """匹配完整物名，不用父设备类型或关键词包含关系替代对象身份。"""
    description = str(raw[r].get('description') or '').strip()
    identities = [(description, [r])]
    prefixes = []
    for source in inherit:
        name = str(raw[source].get('description') or '').strip()
        if name and name not in description and not any(name in p for p in prefixes):
            prefixes = [p for p in prefixes if p not in name]
            prefixes.append(name)
    if prefixes:
        identities.append((' '.join([*prefixes, description]), [*inherit, r]))
    matches = []
    for policy in policies:
        for identity, sources in identities:
            normalized = re.sub(r'\s+', '', unicodedata.normalize('NFKC', identity))
            identity_details = ' '.join(str(raw[s].get(k) or '') for s in sources
                                        for k in ('nominal_size', 'equipment_tag'))
            exclusions = normalized + re.sub(r'\s+', '', unicodedata.normalize('NFKC', identity_details))
            if (any(p.fullmatch(normalized) for p in policy['includes'])
                    and not any(p.search(exclusions) for p in policy['excludes'])):
                matches.append((policy, sources, identity))
                break
    if not matches:
        return None
    if len({policy['node_type'] for policy, _, _ in matches}) != 1:
        raise ValueError(f"第{r}行命中相互冲突的已确认分类规则")
    return {'r': r, 'node_type': matches[0][0]['node_type'],
            'applicable_roles': sorted(PHYSICAL),
            'rule_ids': [p['rule_id'] for p, _, _ in matches],
            'source_rows': sorted({s for _, sources, _ in matches for s in sources}),
            'reason': '已确认企业分类：' + ','.join(p['rule_id'] for p, _, _ in matches),
            'identity': matches[0][2]}


def apply_confirmed_classifications(rows: dict, raw: dict, policies: list) -> list:
    """仅在结构已验证后确定实物分类；保留模型原响应，返回可追溯的变化。"""
    changes = []
    for r, row in rows.items():
        if row['role'] not in PHYSICAL:
            continue
        expected = confirmed_classification(r, raw, policies, row['inherit'])
        if expected is None:
            continue
        before = {'node_type': row['node_type'], 'classification': copy.deepcopy(row['classification'])}
        row['node_type'] = expected['node_type']
        row['classification'] = {'status': 'resolved', 'rule_ids': expected['rule_ids'],
                                 'source_rows': expected['source_rows'], 'reason': expected['reason']}
        changes.append({'r': r, 'identity': expected['identity'], 'before': before,
                        'after': {'node_type': row['node_type'], 'classification': copy.deepcopy(row['classification'])}})
    return changes


def validate_confirmed_rule_citations(rows: dict, raw: dict, policies: list) -> list:
    """不能以不适用的已确认规则证明同类结论；排除说明不等于肯定分类。"""
    errors = []
    for r, row in rows.items():
        if row['role'] not in PHYSICAL or row['classification']['status'] != 'resolved':
            continue
        cited = {p['rule_id'] for p in policies if p['rule_id'] in row['classification']['rule_ids']
                 and p['node_type'] == row['node_type']}
        if not cited:
            continue
        expected = confirmed_classification(r, raw, policies, row['inherit'])
        applicable = set(expected['rule_ids']) if expected else set()
        if cited - applicable:
            errors.append({'code': 'CONFIRMED_RULE_NOT_APPLICABLE', 'r': r,
                           'path': f'$.rows[{r - 1}].classification.rule_ids',
                           'message': f'第{r}行不是已确认规则适用的完整对象，不能据此确定类别',
                           'rule_ids': sorted(cited - applicable)})
    return errors


def _text(row: dict) -> str:
    return " ".join(str(row[field]).strip() for field in TEXT_FIELDS
                    if row.get(field) is not None and str(row[field]).strip())


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def _names_object(annotation: dict, identity_rows: list[dict]) -> bool:
    """祖先说明须原文点名目标；不以同一父项或文字相邻代替归属证据。"""
    text = _compact(_text(annotation))
    for identity in identity_rows:
        for field in ("description", "equipment_tag"):
            label = _compact(str(identity.get(field) or ""))
            if len(label) < 2 or not re.search(r"[A-Za-z\u3400-\u9fff]", label):
                continue
            # 位号/规格前缀不是同一对象，例如 TAG-01 与 TAG-010、M16 与 M160。
            left = r"(?<![a-z0-9_-])" if re.match(r"[a-z0-9_-]", label) else ""
            right = r"(?![a-z0-9_-])" if re.search(r"[a-z0-9_-]$", label) else ""
            if re.search(left + re.escape(label) + right, text):
                return True
    return False


def _collective_supply(annotation: dict) -> bool:
    """接受明确覆盖全部组成件的供货条件；存在排除/限定时仍须具体指向。"""
    text = _compact(_text(annotation))
    if re.search(r"不含|不包括|除|仅|不随|不属于|非配套", text):
        return False
    return bool(re.search(r"本(?:设备|装置|成套)[^。；;]*?(?:全部|所有)(?:组成件|配件|部件)[^。；;]*?(?:随主体|随设备|配套供货)", text))


def validate_classification_evidence(rows: dict[int, dict], raw: dict[int, dict]) -> list[dict]:
    """返回可合并到 StructureErrors 的错误，不修改输入或推断 node_type。

    调用方先验证 Schema、全行覆盖、parent/继承关系及分类状态。这里进一步限制
    source_rows：本行、合法 inherit 共同身份、所属实物祖先以及相关属性/说明。
    实物祖先仅补充条件，resolved 仍须引用本对象的身份或直属属性/说明，不能
    仅因父项是设备就把不同物名的组成件归设备。

    祖先的属性/说明只在原文明确包含目标名称或位号时接受；无法明确归属的
    整体供货说明应由模型保留 review 或改用真正指向目标的原行。此规则保守，
    不判断条款是否适用，也不能证明已引用文字实际支持 MATERIAL/EQUIPMENT。
    """
    errors = []
    for r, decision in rows.items():
        if decision["role"] not in PHYSICAL:
            continue
        sources = set(decision["classification"]["source_rows"])
        ancestors, seen = [], {r}
        current = decision.get("parent")
        while current is not None and current in rows and current not in seen:
            ancestors.append(current)
            seen.add(current)
            current = rows[current].get("parent")
        inherited = {source for source in decision["inherit"]
                     if source in ancestors and rows[source]["role"] in IDENTITY_GROUPS}
        identity = {r, *inherited}
        owners = {source for source in ancestors if rows[source]["role"] in PHYSICAL}
        # 只检查实际引用，避免大成套表的每个子项反复扫描父项全部属性行。
        local = identity | {source for source in sources if source in rows
                            and rows[source]["role"] in ANNOTATIONS
                            and rows[source].get("parent") in identity}
        allowed = local | owners
        # 祖先说明必须点名当前明细，只有共同物名可能仍指向另一规格。
        identity_rows = [raw[r]] if r in raw else []
        allowed.update(source for source in sources if source in rows and source in raw
                       and rows[source]["role"] in ANNOTATIONS
                       and rows[source].get("parent") in owners
                       and (_names_object(raw[source], identity_rows) or _collective_supply(raw[source])))

        def error(code, message, **details):
            errors.append({"code": code, "r": r, "path": f"$.rows[{r - 1}].classification.source_rows",
                           "message": f"r={r} {message}", **details})

        unrelated = sorted(sources - allowed)
        if unrelated:
            error("UNRELATED_CLASSIFICATION_EVIDENCE", "分类证据跨无关行或未明确归属本对象的祖先说明",
                  source_rows=unrelated)
        empty = sorted(source for source in sources if source in raw and not _text(raw[source]))
        if empty:
            error("EMPTY_CLASSIFICATION_EVIDENCE", "分类证据原行缺少物名、规格、位号或备注原文",
                  source_rows=empty)
        if decision["classification"]["status"] == "resolved" and not sources & local:
            error("MISSING_OBJECT_CLASSIFICATION_EVIDENCE", "明确分类缺少本对象身份或直属属性说明，不能仅依父设备分类")
    return errors
