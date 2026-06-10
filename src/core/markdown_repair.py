"""Marker-generated Markdown heading hierarchy repair."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

@dataclass
class RepairReport:
    warnings: list[str] = field(default_factory=list)
    headings_fixed: int = 0

    def warn(self, msg: str):
        self.warnings.append(msg)

    def to_dict(self) -> dict:
        return {
            "headings_fixed": self.headings_fixed,
            "warnings": self.warnings,
        }


# ===========================================================================
# Heading level repair
# ===========================================================================

_RE_ATX_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
_RE_FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
_RE_DECIMAL_PREFIX = re.compile(
    r"^(\d+(?:\.\d+)*)(?:[ \t]*([.)。．:：])[ \t]*|[ \t]+)(.+)$"
)
_RE_ROMAN_PREFIX = re.compile(
    r"^([IVXLCDM]+)(?:[ \t]*([.)。．:：])[ \t]*|[ \t]+)(.+)$"
)
_RE_ALPHA_DOTTED_PREFIX = re.compile(
    r"^([A-Za-z](?:\.\d+)+)(?:[ \t]*([.)。．:：])[ \t]*|[ \t]+)(.+)$"
)
_RE_ALPHA_PREFIX = re.compile(
    r"^([A-Za-z])(?:[ \t]*([.)。．:：])[ \t]*|[ \t]+)(.+)$"
)
_RE_CHINESE_ORDINAL_PREFIX = re.compile(
    r"^[零〇一二三四五六七八九十百]+[、.。．)）:：][ \t]*(.+)$"
)
_SPECIAL_HEADINGS = {
    "abstract",
    "摘要",
    "references",
    "bibliography",
    "works cited",
    "参考文献",
    "致谢",
    "acknowledgements",
    "acknowledgments",
    "appendix",
    "appendices",
    "附录",
}
_COMMON_SECTION_WORDS = {
    "introduction",
    "background",
    "motivation",
    "method",
    "methods",
    "methodology",
    "approach",
    "related work",
    "related works",
    "experiment",
    "experiments",
    "evaluation",
    "evaluations",
    "results",
    "discussion",
    "conclusion",
    "conclusions",
    "limitations",
    "broader impacts",
    "future work",
    "引言",
    "介绍",
    "背景",
    "方法",
    "方法论",
    "相关工作",
    "实验",
    "评估",
    "结果",
    "讨论",
    "结论",
    "局限性",
    "未来工作",
}


@dataclass
class HeadingRecord:
    """One heading collected without deciding whether it belongs to the outline."""

    order: int
    line_index: int
    raw_level: int
    raw_text: str
    visible_text: str
    normalized_text: str
    prefix_kind: str = "none"
    marker: str = ""
    marker_path: tuple[str, ...] = ()
    marker_delimiter: str = ""
    previous_text: str = ""
    next_text: str = ""
    after_appendix: bool = False
    after_references: bool = False
    duplicate_count: int = 1

    @property
    def kind(self) -> str:
        """Compatibility alias used by diagnostics written for the old scanner."""
        if self.normalized_text in _SPECIAL_HEADINGS:
            return "special"
        return self.prefix_kind

    @property
    def depth(self) -> int:
        return len(self.marker_path)


def _visible_heading_text(text: str) -> str:
    """Strip inline anchors/formatting before classifying a heading."""
    visible = re.sub(r"<[^>]+>", "", text)
    visible = re.sub(r"[*_`~]+", "", visible)
    return re.sub(r"\s+", " ", visible).strip()


def _parse_heading_prefix(visible: str) -> tuple[str, str, tuple[str, ...], str]:
    """Extract an optional outline marker after the heading has been collected."""
    if match := _RE_DECIMAL_PREFIX.match(visible):
        marker, delimiter = match.group(1), match.group(2) or ""
        kind = "number_paren" if delimiter == ")" and "." not in marker else "decimal"
        return kind, marker, tuple(marker.split(".")), delimiter

    if match := _RE_ALPHA_DOTTED_PREFIX.match(visible):
        marker, delimiter = match.group(1), match.group(2) or ""
        kind = "upper_alpha" if marker[0].isupper() else "lower_alpha"
        return kind, marker, tuple(marker.split(".")), delimiter

    if match := _RE_ROMAN_PREFIX.match(visible):
        marker, delimiter = match.group(1), match.group(2) or ""
        roman = marker.upper()
        if len(roman) > 1 or roman in {"I", "V", "X"}:
            return "roman", roman, (roman,), delimiter

    if match := _RE_ALPHA_PREFIX.match(visible):
        marker, delimiter = match.group(1), match.group(2) or ""
        kind = "upper_alpha" if marker.isupper() else "lower_alpha"
        return kind, marker, (marker,), delimiter

    return "none", "", (), ""


def _make_heading_record(
    order: int,
    line_index: int,
    hashes: str,
    heading_text: str,
    *,
    after_appendix: bool,
    after_references: bool,
) -> HeadingRecord:
    visible = _visible_heading_text(heading_text)
    normalized = visible.lower().strip(" :：#")
    prefix_kind, marker, marker_path, delimiter = _parse_heading_prefix(visible)
    return HeadingRecord(
        order=order,
        line_index=line_index,
        raw_level=len(hashes),
        raw_text=heading_text,
        visible_text=visible,
        normalized_text=normalized,
        prefix_kind=prefix_kind,
        marker=marker,
        marker_path=marker_path,
        marker_delimiter=delimiter,
        after_appendix=after_appendix,
        after_references=after_references,
    )


def scan_heading_records(text: str) -> list[HeadingRecord]:
    """Collect every ATX heading first; classification never controls collection."""
    records: list[HeadingRecord] = []
    fence_char = ""
    fence_length = 0
    after_appendix = False
    after_references = False

    for line_index, line in enumerate(text.splitlines()):
        fence = _RE_FENCE.match(line)
        if fence:
            marker = fence.group(1)
            if not fence_char:
                fence_char = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_length:
                fence_char = ""
                fence_length = 0
            continue

        if fence_char:
            continue

        match = _RE_ATX_HEADING.match(line)
        if match:
            record = _make_heading_record(
                len(records),
                line_index,
                match.group(1),
                match.group(2).strip(),
                after_appendix=after_appendix,
                after_references=after_references,
            )
            records.append(record)
            if record.normalized_text in {"appendix", "appendices", "附录"}:
                after_appendix = True
            if record.normalized_text in {
                "references",
                "bibliography",
                "works cited",
                "参考文献",
            }:
                after_references = True

    counts: dict[str, int] = {}
    for record in records:
        counts[record.normalized_text] = counts.get(record.normalized_text, 0) + 1
    for index, record in enumerate(records):
        record.previous_text = records[index - 1].visible_text if index else ""
        record.next_text = records[index + 1].visible_text if index + 1 < len(records) else ""
        record.duplicate_count = counts[record.normalized_text]

    return records


def _sequence_members(records: list[HeadingRecord], kind: str) -> set[int]:
    """Find records participating in a repeated or advancing marker sequence."""
    candidates = [record for record in records if record.prefix_kind == kind]
    if len(candidates) < 2:
        return set()

    def value(record: HeadingRecord) -> int | None:
        root = record.marker_path[0] if record.marker_path else ""
        if kind in {"decimal", "number_paren"} and root.isdigit():
            return int(root)
        if kind == "roman":
            values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
            total = previous = 0
            for char in reversed(root):
                current = values.get(char, 0)
                total += -current if current < previous else current
                previous = max(previous, current)
            return total or None
        if kind in {"upper_alpha", "lower_alpha"} and len(root) == 1:
            return ord(root.lower()) - ord("a") + 1
        return None

    sequence_candidates = candidates
    if kind == "decimal":
        sequence_candidates = [record for record in candidates if record.depth == 1]

    accepted_roots: set[str] = set()
    for index, record in enumerate(sequence_candidates):
        current = value(record)
        if current is None:
            continue
        neighbours = (
            sequence_candidates[max(0, index - 1): index]
            + sequence_candidates[index + 1: index + 2]
        )
        if any(
            (other_value := value(other)) is not None
            and (other_value == current + 1 or other_value == current - 1 or other_value == 1)
            for other in neighbours
        ):
            accepted_roots.add(record.marker_path[0])

    if kind == "decimal":
        grouped: dict[str, list[HeadingRecord]] = {}
        for record in candidates:
            grouped.setdefault(record.marker_path[0], []).append(record)
        for root, members in grouped.items():
            has_parent = any(member.depth == 1 for member in members)
            child_count = sum(member.depth > 1 for member in members)
            if has_parent and child_count or child_count >= 2:
                accepted_roots.add(root)

    return {
        record.line_index
        for record in candidates
        if record.marker_path and record.marker_path[0] in accepted_roots
    }


def _heading_payload(record: HeadingRecord) -> str:
    """Return heading text without its optional outline marker."""
    patterns = {
        "decimal": _RE_DECIMAL_PREFIX,
        "number_paren": _RE_DECIMAL_PREFIX,
        "roman": _RE_ROMAN_PREFIX,
        "upper_alpha": _RE_ALPHA_DOTTED_PREFIX if record.depth > 1 else _RE_ALPHA_PREFIX,
        "lower_alpha": _RE_ALPHA_DOTTED_PREFIX if record.depth > 1 else _RE_ALPHA_PREFIX,
    }
    pattern = patterns.get(record.prefix_kind)
    if pattern and (match := pattern.match(record.visible_text)):
        return match.group(3).strip()
    return record.visible_text.strip()


def _is_common_section(record: HeadingRecord) -> bool:
    """Recognize common paper sections after removing an optional marker."""
    payload = _heading_payload(record).lower().strip(" :：.-、")
    if match := _RE_CHINESE_ORDINAL_PREFIX.match(payload):
        payload = match.group(1).strip(" :：.-、")
    return payload in _SPECIAL_HEADINGS or payload in _COMMON_SECTION_WORDS


def _looks_like_section_title(record: HeadingRecord) -> bool:
    """Use content only as supporting evidence after the full scan."""
    payload = _heading_payload(record).strip(" :：.-")
    if not payload:
        return False
    lowered = payload.lower()
    if _is_common_section(record):
        return True
    if any("\u4e00" <= char <= "\u9fff" for char in payload):
        return True
    letters = [char for char in payload if char.isalpha()]
    if not letters:
        return False
    return payload[0].isupper() or sum(char.isupper() for char in letters) >= len(letters) * 0.6


def _is_invalid_top_level_candidate(record: HeadingRecord) -> bool:
    """Reject numbered top-level candidates whose actual title starts lowercase."""
    if record.depth != 1 or record.prefix_kind not in {"decimal", "roman"}:
        return False
    payload = _heading_payload(record).lstrip()
    first_letter = next((char for char in payload if char.isalpha()), "")
    return bool(first_letter and first_letter.isascii() and first_letter.islower())


def _prune_primary_lines(
    records: list[HeadingRecord],
    lines: set[int],
    kind: str,
) -> set[int]:
    """Remove individual outliers after a numbering system has been accepted."""
    if not lines:
        return set()
    lines = {
        record.line_index
        for record in records
        if record.line_index in lines and not _is_invalid_top_level_candidate(record)
    }
    if kind != "decimal":
        return lines

    members = [record for record in records if record.line_index in lines]
    grouped: dict[str, list[HeadingRecord]] = {}
    for record in members:
        if record.marker_path:
            grouped.setdefault(record.marker_path[0], []).append(record)

    retained: set[int] = set()
    for root_members in grouped.values():
        parents = [record for record in root_members if record.depth == 1]
        children = [record for record in root_members if record.depth > 1]
        title_like_parents = [record for record in parents if _looks_like_section_title(record)]

        if title_like_parents:
            retained.update(record.line_index for record in title_like_parents)
            retained.update(record.line_index for record in children)
        elif children and len(parents) == 1:
            retained.add(parents[0].line_index)
            retained.update(record.line_index for record in children)
        elif len(children) >= 2:
            retained.update(record.line_index for record in children)

    return retained


def select_outline_records(
    records: list[HeadingRecord],
) -> tuple[set[int], str, set[int], set[int]]:
    """Prune the full temporary heading list down to a coherent paper outline."""
    roman_lines = _sequence_members(records, "roman")
    decimal_lines = _sequence_members(records, "decimal")
    has_paper_landmarks = any(
        record.normalized_text in _SPECIAL_HEADINGS
        or _is_common_section(record)
        for record in records
    )

    def keep_sequence(lines: set[int], kind: str) -> set[int]:
        members = [record for record in records if record.line_index in lines]
        roots = {
            record.marker_path[0]
            for record in members
            if record.marker_path and (kind != "decimal" or record.depth == 1)
        }
        has_children = any(
            record.depth > 1 for record in members
        ) or (
            kind == "roman"
            and any(
                record.prefix_kind in {"upper_alpha", "number_paren", "lower_alpha"}
                for record in records
            )
        )
        title_like = sum(_looks_like_section_title(record) for record in members)
        if (
            len(roots) < 3
            and not has_children
            and not has_paper_landmarks
        ):
            return set()
        if not has_children and not has_paper_landmarks and title_like < max(2, len(members) // 2):
            return set()
        return lines

    roman_lines = keep_sequence(roman_lines, "roman")
    decimal_lines = keep_sequence(decimal_lines, "decimal")
    roman_lines = _prune_primary_lines(records, roman_lines, "roman")
    decimal_lines = _prune_primary_lines(records, decimal_lines, "decimal")

    primary_kind = ""
    if roman_lines and decimal_lines:
        primary_kind = "roman" if min(roman_lines) < min(decimal_lines) else "decimal"
    elif roman_lines:
        primary_kind = "roman"
    elif decimal_lines:
        primary_kind = "decimal"

    primary_lines = roman_lines if primary_kind == "roman" else decimal_lines
    outline_lines = set(primary_lines)

    if primary_kind == "roman":
        active_roman = False
        active_alpha = False
        active_number = False
        for record in records:
            if record.line_index in primary_lines:
                active_roman = True
                active_alpha = False
                active_number = False
                continue
            if not active_roman:
                continue
            if record.prefix_kind == "upper_alpha":
                outline_lines.add(record.line_index)
                active_alpha = True
                active_number = False
            elif record.prefix_kind == "number_paren" and active_alpha:
                outline_lines.add(record.line_index)
                active_number = True
            elif record.prefix_kind == "lower_alpha" and active_number:
                outline_lines.add(record.line_index)
    elif primary_kind == "decimal":
        for record in records:
            if (
                record.prefix_kind == "upper_alpha"
                and (record.after_appendix or record.after_references)
            ):
                outline_lines.add(record.line_index)
            elif (
                record.line_index in roman_lines
                and (record.after_appendix or record.after_references)
            ):
                outline_lines.add(record.line_index)

    for record in records:
        if record.normalized_text in _SPECIAL_HEADINGS:
            outline_lines.add(record.line_index)
        elif _is_common_section(record) and not _is_invalid_top_level_candidate(record):
            outline_lines.add(record.line_index)

    if primary_lines:
        first_primary = min(primary_lines)
        reference_lines = [
            record.line_index
            for record in records
            if record.normalized_text in {
                "references",
                "bibliography",
                "works cited",
                "参考文献",
            }
        ]
        body_end = min(reference_lines, default=float("inf"))
        for record in records:
            if (
                record.prefix_kind == "none"
                and record.raw_level >= 2
                and first_primary < record.line_index < body_end
                and _looks_like_section_title(record)
            ):
                outline_lines.add(record.line_index)

    return outline_lines, primary_kind, roman_lines, decimal_lines


def build_heading_replacements(records: list[HeadingRecord]) -> dict[int, int]:
    """Infer this document's outline from the complete heading sequence."""
    replacements: dict[int, int] = {}
    outline_lines, primary_kind, roman_lines, decimal_lines = select_outline_records(records)
    primary_lines = roman_lines if primary_kind == "roman" else decimal_lines

    first_outline_line = min(outline_lines, default=None)
    title = next(
        (
            record
            for record in records
            if record.prefix_kind == "none"
            and record.raw_level == 1
            and (first_outline_line is None or record.line_index < first_outline_line)
        ),
        None,
    )
    if title is not None:
        replacements[title.line_index] = 1

    for record in records:
        if record.line_index not in outline_lines:
            continue
        if record.line_index in primary_lines:
            if primary_kind == "decimal":
                replacements[record.line_index] = min(record.depth + 1, 6)
            else:
                replacements[record.line_index] = 2
        elif record.normalized_text in _SPECIAL_HEADINGS:
            replacements[record.line_index] = 2
        elif _is_common_section(record):
            replacements[record.line_index] = 2
        elif primary_kind == "roman":
            if record.prefix_kind == "upper_alpha":
                replacements[record.line_index] = min(record.depth + 2, 6)
            elif record.prefix_kind == "number_paren":
                replacements[record.line_index] = 4
            elif record.prefix_kind == "lower_alpha":
                replacements[record.line_index] = min(record.depth + 4, 6)
            elif (
                record.line_index in decimal_lines
                and (record.after_appendix or record.after_references)
            ):
                replacements[record.line_index] = min(record.depth + 1, 6)
        elif primary_kind == "decimal" and record.prefix_kind == "upper_alpha":
            if record.after_appendix or record.after_references:
                replacements[record.line_index] = min(record.depth + 1, 6)
        elif (
            primary_kind == "decimal"
            and record.line_index in roman_lines
            and (record.after_appendix or record.after_references)
        ):
            replacements[record.line_index] = 2

    return replacements


def repair_heading_levels(text: str, report: RepairReport) -> str:
    """Repair headings after one global scan, then apply replacements once."""
    lines = text.split("\n")
    records = scan_heading_records(text)
    replacements = build_heading_replacements(records)
    records_by_line = {record.line_index: record for record in records}

    for line_index, new_level in replacements.items():
        record = records_by_line[line_index]
        if record.raw_level == new_level:
            continue
        lines[line_index] = f"{'#' * new_level} {record.raw_text}"
        report.headings_fixed += 1

    return "\n".join(lines)


# ===========================================================================
# Orchestrator
# ===========================================================================

def repair_marker_markdown(text: str) -> tuple[str, RepairReport]:
    """Repair only the Markdown heading hierarchy."""
    report = RepairReport()
    text = repair_heading_levels(text, report)
    return text, report


def repair_file(input_path: Path, output_path: Path | None = None) -> tuple[Path, Path, RepairReport]:
    """Repair a Markdown file on disk and write output + report."""
    import json

    source = input_path.read_text(encoding="utf-8")
    repaired, report = repair_marker_markdown(source)

    if output_path is None:
        output_path = input_path.with_name(f"{input_path.stem}_rule_repaired.md")
    report_path = output_path.with_name(f"{output_path.stem}_report.json")

    output_path.write_text(repaired, encoding="utf-8")
    report_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path, report_path, report
