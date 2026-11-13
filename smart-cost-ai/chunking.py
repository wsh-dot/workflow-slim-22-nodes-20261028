"""Bound output rows while keeping the complete source available to every chunk.

The token estimate is a planning limit, not a guarantee about a model's response
length. Callers still need to reject truncated responses and validate the merged
structure against the complete file.
"""
from __future__ import annotations

import copy
import math
import re
from collections.abc import Mapping


DEFAULT_ANALYSIS_OPTIONS = {
    "chunk_rows": 32,
    "estimated_output_tokens_per_row": 320,
    "output_budget_ratio": 0.7,
}

_CHAPTER_TITLE = re.compile(r"^(?:第[一二三四五六七八九十百千万零〇0-9]+[章节篇部]|[一二三四五六七八九十百千万]+[、．.])")
_CHAPTER_SERIAL = re.compile(r"^(?:第[一二三四五六七八九十百千万零〇0-9]+[章节篇部]|[一二三四五六七八九十百千万]+[、．.]?)$")
_NUMERIC_SERIAL = re.compile(r"[0-9]+(?:\.[0-9]+)*")


def _row_ids(prepared: dict) -> list[int]:
    rows = prepared.get("rows")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("prepared.rows must be a list of source rows")
    ids = [row.get("r") for row in rows]
    if any(type(r) is not int or r <= 0 for r in ids) or ids != sorted(set(ids)):
        raise ValueError("source r values must be positive, unique, and in file order")
    return ids


def _row_limit(config) -> int:
    options = getattr(config, "analysis_options", {})
    if not isinstance(options, Mapping):
        raise ValueError("analysis_options must be an object")
    values = {**DEFAULT_ANALYSIS_OPTIONS, **options}
    for key in ("chunk_rows", "estimated_output_tokens_per_row"):
        if type(values[key]) is not int or values[key] <= 0:
            raise ValueError(f"{key} must be a positive integer")
    ratio = values["output_budget_ratio"]
    if (type(ratio) not in (int, float) or not math.isfinite(ratio)
            or not 0 < ratio <= 1):
        raise ValueError("output_budget_ratio must be finite and in (0, 1]")
    output_tokens = config.model.get("max_output_tokens")
    if type(output_tokens) is not int or output_tokens <= 0:
        raise ValueError("max_output_tokens must be a positive integer")
    budget_rows = math.floor(output_tokens * ratio / values["estimated_output_tokens_per_row"])
    if budget_rows < 1:
        raise ValueError("output budget cannot accommodate one estimated output row")
    return min(values["chunk_rows"], budget_rows)


def _text(value) -> str:
    return str(value).strip() if value is not None else ""


def _chapter_start(row: dict) -> bool:
    # A bare item number or an equipment name is not evidence of a section.
    if any(_text(row.get(field)) for field in ("unit", "quantity", "nominal_size")):
        return False
    description = _text(row.get("description"))
    serial = _text(row.get("serial_no"))
    return bool(description and (_CHAPTER_TITLE.match(description) or _CHAPTER_SERIAL.fullmatch(serial)))


def _serial_path(row: dict) -> tuple[int, ...] | None:
    value = _text(row.get("serial_no")).replace("．", ".").rstrip(".")
    if not _NUMERIC_SERIAL.fullmatch(value):
        return None
    return tuple(int(part) for part in value.split("."))


def _descendant(path, parent) -> bool:
    return path is not None and len(path) > len(parent) and path[:len(parent)] == parent


def _preferred_boundaries(rows: list[dict]) -> set[int]:
    """Return offsets between rows; hints never change, drop, or label a row."""
    size = len(rows)
    chapters = {i for i, row in enumerate(rows) if _chapter_start(row)}
    boundaries = {0, size, *chapters}
    serials = [_serial_path(row) for row in rows]
    protected_until = 0
    for index, parent in enumerate(serials):
        if parent is None or index < protected_until:
            continue
        # Require an actual child sequence before treating a serial as a group.
        following = next((i for i in range(index + 1, size) if serials[i] is not None or i in chapters), size)
        if following == size or following in chapters or not _descendant(serials[following], parent):
            continue
        end = following + 1
        while end < size and end not in chapters and (serials[end] is None or _descendant(serials[end], parent)):
            end += 1
        boundaries.update((index, end))
        # Keep nested groups inside their complete outer group where it fits.
        protected_until = end
    return boundaries


def plan_chunks(prepared: dict, config) -> list[list[int]]:
    """Plan consecutive output windows using original, file-wide ``r`` values.

    The maximum window size is the smaller of ``chunk_rows`` and the estimated
    output-token capacity. Complete section/serial groups are preferred where
    they fit. Oversized groups use bounded windows and rely on complete source
    context; their hierarchy must be resolved and validated by the caller.
    ``analysis_options`` is optional on older Config objects.
    """
    ids = _row_ids(prepared)
    limit = _row_limit(config)
    if len(ids) <= limit:
        return [ids] if ids else []
    boundaries = _preferred_boundaries(prepared["rows"])
    chunks = []
    start = 0
    while start < len(ids):
        hard_end = min(start + limit, len(ids))
        end = max((offset for offset in boundaries if start < offset <= hard_end), default=hard_end)
        chunks.append(ids[start:end])
        start = end
    return chunks


def packet_for_chunk(prepared: dict, targets: list[int], known_decisions: list[dict]) -> dict:
    """Copy complete source plus the output window and previous model structure.

    ``confirmed_decisions`` retains the caller's original trusted decisions.
    Historical model rows are untrusted context in ``structure_context`` and
    cannot override source text or enterprise classification rules. Mutating a
    returned packet does not mutate the source, history, or another packet.
    """
    ids = _row_ids(prepared)
    if (not isinstance(targets, list) or not targets
            or any(type(r) is not int for r in targets)):
        raise ValueError("output_rows must be a nonempty list of original r values")
    positions = {r: i for i, r in enumerate(ids)}
    if any(r not in positions for r in targets):
        raise ValueError("output_rows contains an unknown source r")
    start = positions[targets[0]]
    if ids[start:start + len(targets)] != targets:
        raise ValueError("output_rows must be a consecutive window in source order")
    if not isinstance(known_decisions, list) or any(not isinstance(row, dict) for row in known_decisions):
        raise ValueError("structure_context must be a list of previous model rows")
    packet = copy.deepcopy(prepared)
    packet["output_rows"] = list(targets)
    target_set = set(targets)
    packet["context_rows"] = [r for r in ids if r not in target_set]
    packet["structure_context"] = copy.deepcopy(known_decisions)
    packet["context_is_model_output"] = True
    return packet
