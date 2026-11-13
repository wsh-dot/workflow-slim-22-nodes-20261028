"""只从原文读取计量限定和基数；不从型号、相邻数量或模型理由猜数。"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

PHYSICAL = {"item", "assembly", "component"}
SCOPES = PHYSICAL | {"section", "group", "summary"}
UNITS = r"台|套|面|组|件|串|个|具|只|根|支|回|基|处|架|座"
NUMERAL = r"\d+(?:,\d{3})*(?:\.\d+)?|[零〇一二两三四五六七八九十百千]+"


def number(value):
    if value is None or isinstance(value, bool):
        return None
    text = unicodedata.normalize("NFKC", str(value)).strip().replace("，", ",")
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+|\d{1,3}(?:,\d{3})+(?:\.\d+)?)", text):
        return None
    try:
        result = Decimal(text.replace(",", ""))
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


def _numeral(text):
    value = number(text)
    if value is not None:
        return value
    digits = dict(zip("零〇一二两三四五六七八九", (0, 0, 1, 2, 2, 3, 4, 5, 6, 7, 8, 9)))
    total, digit, last = 0, None, 10000
    for char in text:
        if char in digits:
            if digit is not None:
                return None
            digit = digits[char]
        elif char in "十百千":
            scale = {"十": 10, "百": 100, "千": 1000}[char]
            if scale >= last:
                return None
            total += (digit if digit is not None else 1) * scale
            digit, last = None, scale
        else:
            return None
    return Decimal(total + (digit or 0)) if total or digit is not None else None


def text_of(row):
    return " ".join(unicodedata.normalize("NFKC", str(row.get(k) or "")) for k in ("description", "remark"))


def _basis_candidates(row):
    text = text_of(row)
    found = {(Decimal(1) if not n else _numeral(n), unit)
             for n, unit in re.findall(r"每\s*(" + NUMERAL + r")?\s*(" + UNITS + r")", text)}
    # “单回终端塔”“单串绝缘子”是规格；只有工作量/设备等口径措辞才是单件限定。
    found |= {(Decimal(1), unit) for unit in re.findall(
        r"单\s*(" + UNITS + r")(?=设备|工作量|用量|配置|包括|包含|数量|[:：，,。；;\s]|$)", text)}
    return found


def basis(row):
    """返回唯一的(分母,单位)；多种限定冲突时不选择其中之一。"""
    found = _basis_candidates(row)
    return next(iter(found)) if len(found) == 1 and all(n is not None and n > 0 for n, _ in found) else None


def _counts(row):
    return [(_numeral(n), u) for n, u in re.findall(
        r"(?:共|合计|总计)\s*[:：为]?\s*(" + NUMERAL + r")\s*(" + UNITS + r")", text_of(row))]


def count(row, unit=None):
    """只认一个明确总数；多个对象即使数字相同也不能合成一个基数。"""
    found = _counts(row)
    if len(found) != 1:
        return None
    value, found_unit = found[0]
    if value is None or value < 0 or (unit and str(unit).strip() != found_unit):
        return None
    return value, found_unit


def ancestors(rows, r):
    result, current = [], rows[r]["parent"]
    while current is not None:
        if current not in rows or current == r or current in result:
            return []
        result.append(current)
        current = rows[current]["parent"]
    return result


def _shared_prefix(row):
    # “每串:U型螺丝”是后续并列组件的限定；“螺丝每串1个”只限定本行。
    return bool(re.match(r"^\s*每\s*(?:" + NUMERAL + r")?\s*(?:" + UNITS + r")\s*[:：]", text_of(row)))


def _ends_scope(row):
    return bool(re.search(r"总量|合计|总计", text_of(row)))


def valid_basis_ref(raw, rows, r, owner, ref):
    """允许同一真实父项内的共享限定，但不放开任意相邻/跨成套引用。"""
    if ref not in rows or owner not in ancestors(rows, r) or basis(raw[ref]) is None:
        return False
    if r != ref and _ends_scope(raw[r]):
        return False
    ancestry = ancestors(rows, r)
    related = {r, *ancestry[:ancestry.index(owner) + 1]}
    if ref in related:
        return True
    if rows[ref]["role"] in {"note", "attribute"} and rows[ref]["parent"] in related:
        if ref > r and not re.search(r"上述|以上|前述", text_of(raw[ref])):
            return False
        # 明确“上述”的后置说明可回指本范围，普通后置备注不能倒用于前文。
        return not any(
            owner not in ancestors(rows, k) or _ends_scope(raw[k]) or bool(_basis_candidates(raw[k]))
            for k in range(min(ref, r) + 1, max(ref, r)) if k in rows)
    if (ref > r or rows[ref]["role"] not in PHYSICAL or not _shared_prefix(raw[ref])
            or rows[ref]["parent"] != owner or rows[r]["parent"] != owner):
        return False
    for k in range(ref + 1, r + 1):
        if owner not in ancestors(rows, k):
            return False
        if _basis_candidates(raw[k]) or _ends_scope(raw[k]):
            return False
    return True


def active_basis_ref(raw, rows, r, owner):
    refs = [k for k in raw if k <= r and valid_basis_ref(raw, rows, r, owner, k)]
    # 最近限定优先，避免每串/每100串等口径发生切换时继续引用旧说明。
    return max(refs) if refs else None


def resolve_scope_total(raw, rows, r):
    """返回per_scope的(总量,来源行)；说明含总数字样但无合法唯一值时禁止回退。"""
    row = rows[r]
    owner, ref = row["quantity_parent"], row["quantity_basis_ref"]
    if (owner not in rows or owner not in raw or ref not in rows or ref not in raw
            or rows[owner]["role"] not in SCOPES or rows[ref]["role"] != "note"
            or rows[ref]["parent"] != owner or not valid_basis_ref(raw, rows, r, owner, ref)):
        raise ValueError("per_scope需要真实祖先范围及适用的直属note")
    denominator = basis(raw[ref])
    unit = str(raw[owner].get("unit") or "").strip()
    if unit and unit != denominator[1]:
        raise ValueError("范围单位与计量口径单位不一致")
    declarations = re.findall(r"合计|总计|总数|总量|(?<!公)共(?!同|用)", text_of(raw[ref]))
    if declarations:
        explicit = count(raw[ref], denominator[1])
        if len(declarations) != 1 or explicit is None:
            raise ValueError("范围说明总数不唯一、单位冲突或无法解析，不得回退到范围原行")
        # group原量与其直属说明都是范围数量；真实设备的采购量不参与此比较。
        original = number(raw[owner].get("quantity"))
        if rows[owner]["role"] == "group" and unit and original is not None and original != explicit[0]:
            raise ValueError("group原行与直属说明的范围总数冲突")
        return explicit[0], ref
    if rows[owner]["role"] != "group" or unit != denominator[1]:
        raise ValueError("说明未给总数时，仅可从单位一致的group原行读取范围基数")
    total = number(raw[owner].get("quantity"))
    if total is None or total < 0:
        raise ValueError("group原行缺少合法非负范围数量，不得补0或1")
    return total, owner


def validate_quantities(raw, rows):
    """给结构纠正提供可定位的计量错误；不自动改写模型角色或补造父项。"""
    errors = []

    def error(r, message):
        errors.append({"code": "INVALID_QUANTITY", "r": r, "path": f"$.rows[{r - 1}]", "message": f"r={r} {message}"})

    for r, row in rows.items():
        if row["role"] not in PHYSICAL:
            continue
        ancestry = ancestors(rows, r)
        qsource = row["qty_from"]
        if qsource is not None and qsource != r and qsource in raw and number(raw[qsource].get("quantity")) is None:
            if (rows[qsource]["role"] not in {"note", "attribute"} or rows[qsource]["parent"] != r
                    or count(raw[qsource], raw[r].get("unit")) is None):
                error(r, "qty_from缺少本实物直属说明中的唯一明确总数；不能从型号或其他对象取数")
        mode, owner, ref = row["quantity_basis"], row["quantity_parent"], row["quantity_basis_ref"]
        if mode in {"per_parent", "per_scope"}:
            allowed = PHYSICAL if mode == "per_parent" else SCOPES
            if owner not in ancestry or rows[owner]["role"] not in allowed or ref not in raw:
                error(r, f"{mode}缺少真实祖先及限定引用")
                continue
            if not valid_basis_ref(raw, rows, r, owner, ref):
                error(r, "计量限定不在本行/祖先/适用的直属说明或同父项共享范围内")
                continue
            denominator = basis(raw[ref])
            parent_unit = str(raw[owner].get("unit") or "").strip()
            if parent_unit and parent_unit != denominator[1]:
                error(r, "限定单位与数量父项单位不一致，不能相乘")
            latest = active_basis_ref(raw, rows, r, owner)
            if latest is not None and basis(raw[latest]) != denominator:
                error(r, f"应采用最近生效的第{latest}行计量限定，不能跨越新的限定")
            if mode == "per_scope":
                try:
                    resolve_scope_total(raw, rows, r)
                except ValueError as exc:
                    error(r, str(exc))
            elif rows[ref]["role"] == "note" and rows[ref]["parent"] == owner:
                explicit = count(raw[ref], denominator[1])
                if _counts(raw[ref]) and explicit is None:
                    error(r, "说明含多个对象、冲突或单位不一致的台数，不能忽略说明而改用父量")
                parent_value = total_from_source(raw, rows, owner)[0] if rows[owner]["quantity_basis"] == "total" else None
                if explicit and parent_value is not None and explicit[0] != parent_value:
                    error(r, "说明范围台数与父实物总量不一致；不能按per_parent选数，应核对是否为per_scope或unknown")
        elif owner is not None or ref is not None:
            error(r, "非逐台/逐套计量不得残留quantity_parent或quantity_basis_ref")
        if mode == "total":
            if _basis_candidates(raw[r]):
                error(r, "本行原文含每台/每串限定，不能直接标为total；缺少适用父项时应为unknown")
            for candidate in ancestry:
                if rows[candidate]["role"] in SCOPES:
                    ref = active_basis_ref(raw, rows, r, candidate)
                    if ref is not None:
                        error(r, f"原文第{ref}行明确单件/每串口径，不能将本行原量标成total；应指定适用父项或范围，依据不足则unknown")
                        break
    return errors


def total_from_source(raw, rows, r):
    row = rows[r]
    source = row["qty_from"] if row["qty_from"] is not None else r
    if source not in raw or source not in rows:
        return None, raw[r].get("unit"), source
    value = number(raw[source].get("quantity"))
    unit = raw[r].get("unit")
    if value is None and (source == r or (rows[source]["role"] in {"note", "attribute"} and rows[source]["parent"] == r)):
        explicit = count(raw[source], unit)
        if explicit:
            return explicit[0], explicit[1], source
    return value, unit, source
