"""Fix Markdown citation references for clean rendering.

Handles two citation styles:
1. Numbered: [5], [5, 2, 29], [6-9]
2. Author-Year: (Author, Year), (Author et al., Year)

General strategy (pipeline order matters):
  0.  merge_fragmented_citations — Marker 把 [14, 19, 25] 拆成碎片链接，先合并
  0b. fix_page_anchor_citations — 处理所有 #page-XX-X 锚点问题：
      - 双层链接 [[text](#ref-X)](#page-Y) → [text](#ref-X)
      - 断片 [(Author](#page-X) → (Author（括号误入链接文本）
      - 引用类 #page → 转 #ref（按年份匹配）；非引用类（Section/Figure）保留
      - 相邻引用链接合并：[A](#ref) [B](#ref), 2020 → [A, B, 2020](#ref)
  1.  fix_escaped_parens — 清除 KaTeX 误加的 escaped parens
  2.  _parse_numbered_refs — 从 References 区提取 [N] → ref-N 映射
  3.  _parse_author_year_refs — 从 References 区提取 (Author, Year) → ref-XX 映射
      年份提取优先匹配括号内的 (Year)，避免 arXiv ID 干扰
  4.  convert_numbered_citations — 正文 [N] → [N](#ref-N)
  5.  convert_author_year_citations — 正文 (Author, Year) → [Author, Year](#ref-XX)
  6.  add_ref_anchors — 在 References 区添加 <a id="ref-XX"> 锚点
  7.  fix_bracket_spacing — 修复 ]( 后紧跟字母的间距

遇到新问题时的排查思路：
  1. python scripts/maintenance/fix_md_refs.py <file> --dry-run 看 diff
  2. 用 --diagnose 模式查看文件中各类引用模式的统计
  3. 检查是哪个 pipeline 阶段遗漏，对应修改

Usage:
  python scripts/maintenance/fix_md_refs.py <file_or_dir> [--dry-run] [--diagnose]
"""

import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Find References section — from heading to next same-level heading (or EOF)
# ---------------------------------------------------------------------------

def _find_refs_section(md: str) -> tuple[int, int] | None:
    """Find the References section boundaries.
    Returns (start, end) character offsets, or None if not found.
    Matches English "References" and Chinese "参考文献".
    """
    m = re.search(r"^(#{1,6})\s+.*(?:[Rr]eference|参考文献)", md, re.MULTILINE)
    if m is None:
        return None

    start = m.start()
    level = m.group(1)

    # Find next heading at the same or higher level (fewer/equal #).
    pattern = rf"^#{{1,{len(level)}}}\s+\S"
    rest = md[m.end():]
    m2 = re.search(pattern, rest, re.MULTILINE)
    end = m.end() + m2.start() if m2 else len(md)

    return start, end


# ---------------------------------------------------------------------------
# Step 1: Remove \( \) that KaTeX misparses
# ---------------------------------------------------------------------------

_ESCAPED_PAREN = re.compile(r"\\([()])")


def _clean_link_text(m: re.Match) -> str:
    text_part = _ESCAPED_PAREN.sub(r"\1", m.group(1))
    return f"[{text_part}]({m.group(2)})"


def fix_escaped_parens(md: str) -> str:
    md = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _clean_link_text, md)
    lines = md.split("\n")
    out = []
    in_math = in_code = False
    for line in lines:
        s = line.strip()
        if s.startswith("```"):
            in_code = not in_code
        elif "$$" in s:
            count = s.count("$$")
            if count % 2 == 1:
                in_math = not in_math
        if not in_code and not in_math:
            line = _ESCAPED_PAREN.sub(r"\1", line)
        out.append(line)
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Step 2: Parse numbered references [N] from References section
# ---------------------------------------------------------------------------

def _parse_numbered_refs(md: str) -> dict[str, str]:
    """Scan References section for [N] entries. Returns {N: ref_id}."""
    section = _find_refs_section(md)
    if section is None:
        return {}

    refs_text = md[section[0]:section[1]]
    number_map: dict[str, str] = {}

    for m in re.finditer(r"\[(\d+)\]", refs_text):
        num = m.group(1)
        if num not in number_map:
            number_map[num] = f"ref-{num}"

    return number_map


# ---------------------------------------------------------------------------
# Step 3: Parse Author-Year references from References section
# ---------------------------------------------------------------------------

def _parse_author_year_refs(md: str) -> dict[str, str]:
    """Scan References section for (Author, Year) patterns.
    Returns {author-year-slug: ref_id}.
    """
    section = _find_refs_section(md)
    if section is None:
        return {}

    refs_text = md[section[0]:section[1]]
    ay_map: dict[str, str] = {}
    seen: dict[str, int] = {}

    for m in re.finditer(r"^[-\s]*(?:\[(\d+)\]\s*)?(.+)", refs_text, re.MULTILINE):
        line = m.group(2).strip()
        if not line:
            continue

        cite = _extract_cite_from_ref(line)
        if not cite:
            continue

        author_part, year = cite
        slug = _make_slug(author_part, year)

        if slug in seen:
            seen[slug] += 1
            slug = f"{slug}-{seen[slug]}"
        else:
            seen[slug] = 0

        num = m.group(1)
        ref_id = f"ref-{num}" if num else f"ref-{slug}"
        ay_map[slug] = ref_id

    return ay_map


def _extract_cite_from_ref(line: str) -> tuple[str, str] | None:
    """Extract (surname, year) from a reference line.

    Prefers the year in parentheses (APA style) to avoid matching arXiv IDs
    like arXiv:2009.11462 or arXiv:1909.08593.
    """
    # Prefer year in parentheses: (2020) or , (2020).
    paren_m = re.search(r"\(((?:19|20)\d{2})\)", line)
    if paren_m:
        year = paren_m.group(1)
        year_pos = paren_m.start()
    else:
        years = re.findall(r"\b((?:19|20)\d{2})\b", line)
        if not years:
            return None
        year = years[0]  # First year is usually the publication year
        year_pos = line.find(year)

    before_year = line[:year_pos].strip().rstrip(",").strip()

    before_year = re.sub(r"^\[\d+\]\s*", "", before_year)
    before_year = before_year.rstrip(",:").strip()

    if not before_year:
        return None

    surname = None

    m = re.match(r"^([A-Z][a-z]+),\s*[A-Z]", before_year)
    if m:
        surname = m.group(1)
    else:
        author_text = re.split(r"\s+et\s+al\.?", before_year)[0]
        author_text = re.split(r"\.\s+", author_text)[0]
        words = author_text.split()
        for w in reversed(words):
            clean = w.strip(",:;'\"")
            if clean and clean[0].isupper() and len(clean) > 1:
                surname = clean
                break

    if not surname:
        return None

    return surname.lower(), year


def _make_slug(surname: str, year: str) -> str:
    return f"{surname.lower().strip(',:;')}-{year}"


# ---------------------------------------------------------------------------
# Protected ranges — the core state machine
# ---------------------------------------------------------------------------

def _find_protected_ranges(text: str) -> list[tuple[int, int]]:
    """Scan text and return (start, end) ranges that must not be modified.

    Detects (in priority order):
    - Fenced code blocks: ``` ... ```
    - Display math: $$ ... $$  (on separate lines)
    - Headings: # ...
    - Inline code: `...` (matching backtick count)
    - Inline math: $...$ or $$...$$  (within a line)
    - HTML comments: <!-- ... -->
    """
    ranges: list[tuple[int, int]] = []
    pos = 0
    length = len(text)

    while pos < length:
        ch = text[pos]

        # --- Fenced code block: ``` at start of line ---
        if ch == "`" and _is_line_start(text, pos):
            fence_len = _count_char(text, pos, "`")
            if fence_len >= 3:
                # Find closing fence: ``` at start of a later line
                close_pat = re.compile(
                    r"^[ ]{0,3}" + "`" * fence_len + r"[ ]*$",
                    re.MULTILINE,
                )
                m = close_pat.search(text, pos + fence_len)
                end = m.end() if m else length
                ranges.append((pos, end))
                pos = end
                continue

        # --- Display math: $$ alone on a line ---
        if ch == "$" and _is_line_start(text, pos) and text[pos : pos + 2] == "$$":
            # Check if $$ is alone on the line (display math) or has content after (inline)
            line_end_pos = text.find("\n", pos)
            if line_end_pos == -1:
                line_end_pos = length
            rest_of_line = text[pos + 2 : line_end_pos].strip()
            if rest_of_line == "":
                # $$ is alone — display math block, find closing $$
                close = text.find("\n$$", pos + 2)
                if close != -1:
                    close_line_end = text.find("\n", close + 3)
                    end = close_line_end + 1 if close_line_end != -1 else length
                    ranges.append((pos, end))
                    pos = end
                    continue
                else:
                    ranges.append((pos, length))
                    break
            # else: $$ has content after — fall through to inline detection

        # --- Heading: # at start of line ---
        if ch == "#" and _is_line_start(text, pos):
            m = re.match(r"#{1,6}\s", text[pos:])
            if m:
                end = text.find("\n", pos)
                end = end + 1 if end != -1 else length
                ranges.append((pos, end))
                pos = end
                continue

        # --- Inline delimiter: ` or $ ---
        if ch in ("`", "$"):
            # Find all inline ranges for this delimiter on the current line
            line_end = text.find("\n", pos)
            if line_end == -1:
                line_end = length
            line_text = text[pos:line_end]

            inline = _find_inline_ranges(line_text, pos)
            if inline:
                ranges.extend(inline)
                # Jump past the last inline range on this line
                pos = inline[-1][1]
                continue
            else:
                pos += 1
                continue

        # --- HTML comment: <!-- ---
        if text[pos : pos + 4] == "<!--":
            close = text.find("-->", pos + 4)
            end = close + 3 if close != -1 else length
            ranges.append((pos, end))
            pos = end
            continue

        pos += 1

    return ranges


def _is_line_start(text: str, pos: int) -> bool:
    return pos == 0 or text[pos - 1] == "\n"


def _count_char(text: str, pos: int, ch: str) -> int:
    count = 0
    while pos + count < len(text) and text[pos + count] == ch:
        count += 1
    return count


def _find_inline_ranges(line: str, offset: int) -> list[tuple[int, int]]:
    """Find inline code (`) and inline math ($) ranges within a single line.
    Returns absolute positions (offset + local).
    """
    delim_re = re.compile(r"(?<!\\)(`+|(?<!\$)\${1,2}(?!\$))")
    delims: list[tuple[str, int]] = []

    for m in delim_re.finditer(line):
        delims.append((m.group(1), m.start()))

    ranges: list[tuple[int, int]] = []
    i = 0
    while i < len(delims):
        raw, raw_pos = delims[i]
        delim_len = len(raw)

        if raw[0] == "`":
            for j in range(i + 1, len(delims)):
                close_raw, close_pos = delims[j]
                if close_raw[0] == "`" and len(close_raw) == delim_len:
                    ranges.append((offset + raw_pos, offset + close_pos + delim_len))
                    i = j + 1
                    break
            else:
                i += 1
        elif raw[0] == "$":
            # Opening $ must not have space after; closing $ must not have space before
            if raw_pos + delim_len < len(line) and line[raw_pos + delim_len] == " ":
                i += 1
                continue
            for j in range(i + 1, len(delims)):
                close_raw, close_pos = delims[j]
                if close_raw[0] == "$" and len(close_raw) == delim_len:
                    if close_pos > 0 and line[close_pos - 1] == " ":
                        continue
                    ranges.append((offset + raw_pos, offset + close_pos + delim_len))
                    i = j + 1
                    break
            else:
                i += 1
        else:
            i += 1

    return ranges


def _overlaps_protected(start: int, end: int, protected: list[tuple[int, int]]) -> bool:
    for ps, pe in protected:
        if ps >= end:
            break
        if pe > start:
            return True
    return False


# ---------------------------------------------------------------------------
# Step 4: Convert numbered citations in body text
# ---------------------------------------------------------------------------

_CITE_NUM = re.compile(r"(?<!\()\[(\d+(?:\s*[-,]\s*\d+)*)\](?!\()")

# Word-boundary labels before [N] that indicate non-citation references
_NON_CITE_LABELS = re.compile(
    r"\b(?:figure|table|fig\.?|tab\.?|equation|eq\.?|chart|listing|algorithm|section|sec\.?|appendix)\s*$",
    re.IGNORECASE,
)

# Math context: [N] after these words is likely a value, not a citation
_NON_CITE_MATH = re.compile(
    r"(?:range|interval|between|from|value|score|probability|output|∈)\s+(?:of\s*)?$",
    re.IGNORECASE,
)


def _expand_nums(raw: str) -> list[str]:
    tokens = re.split(r"\s*,\s*", raw)
    nums = []
    for t in tokens:
        t = t.strip()
        range_m = re.match(r"^(\d+)\s*-\s*(\d+)$", t)
        if range_m:
            nums.extend(str(n) for n in range(int(range_m.group(1)), int(range_m.group(2)) + 1))
        else:
            nums.append(t)
    return nums


def _link_nums(nums: list[str], number_map: dict[str, str]) -> str:
    parts = []
    for n in nums:
        n = n.strip()
        ref_id = number_map.get(n)
        if ref_id:
            parts.append(f"[{n}](#{ref_id})")
        else:
            parts.append(f"[{n}]")
    return ", ".join(parts)


def convert_numbered_citations(md: str, number_map: dict[str, str]) -> str:
    """Convert [5], [5, 2, 29], [6-9] to links in body text.

    Uses protected-range detection to skip code, math, headings, etc.
    """
    if not number_map:
        return md

    section = _find_refs_section(md)
    body = md[:section[0]] if section else md
    refs = md[section[0]:section[1]] if section else ""
    tail = md[section[1]:] if section else ""

    protected = _find_protected_ranges(body)

    def _repl(m: re.Match) -> str:
        start, end = m.start(), m.end()
        if _overlaps_protected(start, end, protected):
            return m.group(0)
        # Check for non-citation label immediately before [N]
        before = body[max(0, start - 30):start]
        if _NON_CITE_LABELS.search(before):
            return m.group(0)
        # Check for math context (e.g. "range of [0], [1]")
        if _NON_CITE_MATH.search(before):
            return m.group(0)
        nums = _expand_nums(m.group(1))
        return _link_nums(nums, number_map)

    body = _CITE_NUM.sub(_repl, body)
    return body + refs + tail


# ---------------------------------------------------------------------------
# Step 5: Convert Author-Year citations in body text
# ---------------------------------------------------------------------------

_CITE_AY = re.compile(
    r"\(([A-Z][a-z]+(?:\s+et\s+al\.?)?(?:\s+and\s+[A-Z][a-z]+)?)\s*,\s*((?:\d{4}(?:\s*,\s*)?)+)\)"
)


def convert_author_year_citations(md: str, ay_map: dict[str, str]) -> str:
    """Convert (Author, Year) to links in body text.

    Uses protected-range detection to skip code, math, headings, etc.
    """
    if not ay_map:
        return md

    section = _find_refs_section(md)
    body = md[:section[0]] if section else md
    refs = md[section[0]:section[1]] if section else ""
    tail = md[section[1]:] if section else ""

    protected = _find_protected_ranges(body)

    def _repl(m: re.Match) -> str:
        start, end = m.start(), m.end()
        if _overlaps_protected(start, end, protected):
            return m.group(0)
        author_raw = m.group(1).strip()
        years_raw = m.group(2).strip()
        years = re.split(r"\s*,\s*", years_raw)
        parts = []
        for year in years:
            year = year.strip()
            if not year:
                continue
            ref_id = _lookup_ay(author_raw, year, ay_map)
            if ref_id:
                parts.append(f"[{author_raw}, {year}](#{ref_id})")
            else:
                parts.append(f"({author_raw}, {year})")
        return "; ".join(parts)

    body = _CITE_AY.sub(_repl, body)
    return body + refs + tail


def _lookup_ay(author_raw: str, year: str, ay_map: dict[str, str]) -> str | None:
    text = re.sub(r"\s+et\s+al\.?\s*", " ", author_raw).strip()
    text = re.sub(r"\s+and\s+[A-Z][a-z]+", "", text).strip()
    words = text.split()

    for w in reversed(words):
        clean = w.strip(",:;'\"")
        if clean and clean[0].isupper() and len(clean) > 1:
            slug = _make_slug(clean, year)
            if slug in ay_map:
                return ay_map[slug]

    if words:
        slug = _make_slug(words[0], year)
        if slug in ay_map:
            return ay_map[slug]

    return None


# ---------------------------------------------------------------------------
# Step 6: Add anchors to References section
# ---------------------------------------------------------------------------

def add_ref_anchors(md: str, number_map: dict[str, str], ay_map: dict[str, str]) -> str:
    """Add <a id="ref-..."></a> anchors in the References section."""
    section = _find_refs_section(md)
    if section is None:
        return md

    before = md[:section[0]]
    refs_section = md[section[0]:section[1]]
    after = md[section[1]:]

    # Remove old Marker <span id="page-XX-X">...</span> wrappers
    refs_section = re.sub(
        r'<span\s+id="page-\d+-\d+">(.*?)</span>', r"\1", refs_section
    )

    # Add anchors for numbered references
    if number_map:
        def _num_repl(m: re.Match) -> str:
            prefix = m.group(1)
            num = m.group(2)
            ref_id = number_map.get(num)
            if ref_id:
                return f'{prefix}<a id="{ref_id}"></a>[{num}]'
            return m.group(0)

        refs_section = re.sub(r"^([-\s]*)\[(\d+)\]", _num_repl, refs_section, flags=re.MULTILINE)

    return before + refs_section + after


# ---------------------------------------------------------------------------
# Step 7: Fix missing space after ] before word
# ---------------------------------------------------------------------------

_LINK_NO_SPACE = re.compile(r"\]\(#[^)]+\)(?=[A-Za-z])")


def fix_bracket_spacing(md: str) -> str:
    return _LINK_NO_SPACE.sub(lambda m: m.group(0) + " ", md)


# ---------------------------------------------------------------------------
# Step 0: Merge fragmented Marker citation links
# ---------------------------------------------------------------------------

_FRAG_CITE = re.compile(
    r"(?:\[(?:\\?\[)?\d+\\?[,.\]]?\]\(#page-\d+-\d+\)(?:\s+(?=\[))?)+"
)

_FRAG_LINK_TEXT = re.compile(r"\[\\?\[?(\d+)\\?[,.\]]?\]")


def merge_fragmented_citations(md: str) -> str:
    """Merge fragmented Marker citation links into clean [N, M, ...] text.

    Before: [\\[14,](#page-10-2) [19,](#page-10-3) [25\\]](#page-11-2)
    After:  [14, 19, 25]
    """
    def _merge_repl(m: re.Match) -> str:
        fragment = m.group(0)
        nums = _FRAG_LINK_TEXT.findall(fragment)
        if not nums:
            return fragment
        return "[" + ", ".join(nums) + "]"

    return _FRAG_CITE.sub(_merge_repl, md)


# ---------------------------------------------------------------------------
# Step 0b: Fix translated citation links with #page-XX-X anchors
# ---------------------------------------------------------------------------

# Match adjacent page-anchor links: [text](#page-X-Y) or [text](#page-X-Y) [text](#page-X-Y)
_PAGE_ANCHOR_LINK = re.compile(
    r"\[([^\]]+)\]\(#page-\d+-\d+\)"
    r"(?:\s*\[([^\]]+)\]\(#page-\d+-\d+\))?"
)


def fix_page_anchor_citations(md: str) -> str:
    """Fix translated citation links that use #page-XX-X anchors.

    Strategy:
    1. Unwrap double-links: [text](#ref-X)](#page-Y) → [text](#ref-X)
    2. For remaining #page-XX-X citation links, try to find a matching #ref-XX
       anchor in the document and replace the link target.
    3. If no matching #ref-XX exists, strip the link but keep the text.
    4. Non-citation #page links (Section, Figure) are left as-is.
    """
    # Step 1: Unwrap double-links — preserve inner #ref link
    # [[text](#ref-X)](#page-Y) → [text](#ref-X)
    # Group 1 captures [text](#ref-X) including the opening bracket
    md = re.sub(
        r"\[([^\]]+\]\(#ref-[a-zA-Z0-9_-]+\))\]\(#page-\d+-\d+\)",
        r"\1",
        md,
    )

    # Step 1b: Fix broken fragments where ( is inside the link text
    # [(Zhou](#page-14-2) → (Zhou — allows later author-year matching
    md = re.sub(
        r"\[\(([A-Z][a-z]+)\]\(#page-\d+-\d+\)",
        r"(\1",
        md,
    )

    # Step 2: Build a map of year → #ref-XX from existing reference links
    # e.g. "2017" → "#ref-schulman-2017" from [Schulman et al., 2017](#ref-schulman-2017)
    ref_year_map: dict[str, str] = {}
    for m in re.finditer(r"\]\(#(ref-[a-zA-Z0-9_-]+)\)", md):
        ref_id = m.group(1)
        year_m = re.search(r"(\d{4})", ref_id)
        if year_m:
            ref_year_map.setdefault(year_m.group(1), f"#{ref_id}")

    # Step 3: Replace #page-XX-X citation links with #ref-XX where possible
    _PAGE_CITE = re.compile(r"\[([^\]]*)\]\(#page-\d+-\d+\)")

    def _replace_cite(m: re.Match) -> str:
        text = m.group(1)
        # Check if it's a citation (contains year or 等人/et al.)
        if not re.search(r"(?:19|20)\d{2}|等人|et al\.?", text):
            return m.group(0)  # Not a citation, leave as-is
        # Try to find matching #ref anchor by year
        year_m = re.search(r"(?:19|20)\d{4}", text)
        if year_m and year_m.group(0) in ref_year_map:
            return f"[{text}]({ref_year_map[year_m.group(0)]})"
        # No matching ref found — strip link, keep text
        return text

    md = _PAGE_CITE.sub(_replace_cite, md)

    # Step 4: Group adjacent citation links and merge
    # Re-find remaining citation links (some may now point to #ref)
    _CITE_LINK = re.compile(r"\[([^\]]+)\]\(#ref-[a-zA-Z0-9_-]+\)")
    matches = list(_CITE_LINK.finditer(md))
    if not matches:
        return md

    def _clean_text(text: str) -> str:
        return text.strip().rstrip("；;,，）)）").lstrip("（(")

    # Group adjacent citation links
    groups = []
    i = 0
    while i < len(matches):
        m = matches[i]
        start = m.start()
        end = m.end()
        texts = [_clean_text(m.group(1))]
        ref_ids = [m.group(0).split("](")[1].rstrip(")")]  # keep ref ids
        j = i + 1
        while j < len(matches):
            between = md[end:matches[j].start()]
            if between.strip() == "":
                texts.append(_clean_text(matches[j].group(1)))
                ref_ids.append(matches[j].group(0).split("](")[1].rstrip(")"))
                end = matches[j].end()
                j += 1
            else:
                break
        # Only merge if 2+ adjacent links
        if len(texts) >= 2:
            groups.append((start, end, texts, ref_ids))
        i = j

    # Replace groups in reverse order
    for start, end, texts, ref_ids in reversed(groups):
        year_match = re.match(r"^(\(?\s*(?:19|20)\d{2}\s*\)?)$", texts[-1])
        if year_match and len(texts) >= 2:
            authors = texts[:-1]
            year = year_match.group(1).strip("() ")
            # Link to the last ref_id (most specific)
            replacement = f"[{', '.join(authors)}, {year}]({ref_ids[-1]})"
        else:
            # Keep individual links — don't merge
            parts = []
            for t, r in zip(texts, ref_ids):
                parts.append(f"[{t}]({r})")
            replacement = "".join(parts)
        md = md[:start] + replacement + md[end:]

    return md


# ---------------------------------------------------------------------------
# Orchestrate
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# File processing
# ---------------------------------------------------------------------------

def process_file(path: Path, dry_run: bool = False) -> bool:
    """Citation auto-fixing has been removed; keep CLI diagnostics only."""
    print(f"  SKIPPED: {path.name} (citation auto-fix removed)")
    return False


def diagnose_file(path: Path) -> None:
    """Diagnose citation patterns in a single .md file.

    Reports counts and examples for each pattern category.
    Useful for investigating new citation issues.
    """
    text = path.read_text(encoding="utf-8")
    print(f"\n{'='*60}")
    print(f"  DIAGNOSE: {path.name}")
    print(f"{'='*60}")

    # 1. Reference section
    section = _find_refs_section(text)
    if section:
        ref_text = text[section[0]:section[1]]
        ref_lines = [l for l in ref_text.split("\n") if l.strip() and not re.match(r"^#{1,6}\s", l)]
        print(f"\n[References] Found at char {section[0]}-{section[1]}, {len(ref_lines)} entries")
        # Show heading
        heading = text[section[0]:text.index("\n", section[0])]
        print(f"  Heading: {heading!r}")
    else:
        print(f"\n[References] NOT FOUND — no #ref anchors will be generated")

    # 2. Pattern counts
    patterns = {
        "ref_link": [],           # [text](#ref-X)
        "page_link": [],          # [text](#page-X-Y)
        "double_link": [],        # [[text](#ref-X)](#page-Y)
        "bare_ay": [],            # (Author, Year) without link
        "bare_num": [],           # [N] without link
        "broken_frag": [],        # [(Author](#page-X)
        "section_ref": [],        # [3.3](#page-X) — section/figure refs
        "escaped_paren": [],      # \( \) in links
        "fragmented": [],         # Marker碎片: [\\[14,](#page-X)
    }

    # ref links
    for m in re.finditer(r"\[([^\]]+)\]\(#ref-[a-zA-Z0-9_-]+\)", text):
        before = text[max(0, m.start()-1):m.start()]
        if before == "[":
            patterns["double_link"].append(m.group(0)[:60])
        else:
            patterns["ref_link"].append(m.group(1)[:40])

    # page links
    for m in re.finditer(r"\[([^\]]+)\]\(#page-\d+-\d+\)", text):
        text_match = m.group(1)
        before = text[max(0, m.start()-1):m.start()]
        if before == "[":
            patterns["double_link"].append(m.group(0)[:60])
        elif re.match(r"^\(?\d+\.\d+", text_match) or re.match(r"^\d+\)", text_match) or re.match(r"^[A-Z]\.?\d*\)?\.?$", text_match):
            patterns["section_ref"].append(text_match[:40])
        elif text_match.startswith("("):
            patterns["broken_frag"].append(text_match[:40])
        else:
            patterns["page_link"].append(text_match[:40])

    # bare (Author, Year)
    for m in re.finditer(r"(?<!\]\()(?<!\[)\(([A-Z][a-z]+(?:\s+et al\.?)?,\s*(?:19|20)\d{2})\)", text):
        patterns["bare_ay"].append(m.group(1)[:40])

    # bare [N]
    for m in re.finditer(r"(?<!\[)\[(\d+)\](?!\()", text):
        num = int(m.group(1))
        if num < 1000:  # Skip years like [2022]
            before = text[max(0, m.start()-30):m.start()]
            if not re.search(r"(?:figure|table|fig|tab|section|eq)\s*$", before, re.IGNORECASE):
                patterns["bare_num"].append(m.group(1))

    # escaped parens in links
    for m in re.finditer(r"\[([^\]]*\\[()][^\]]*)\]\([^)]+\)", text):
        patterns["escaped_paren"].append(m.group(0)[:60])

    # fragmented citations
    for m in re.finditer(r"\[\\?\[?\d+\\?[,.\]]?\]\(#page-\d+-\d+\)", text):
        patterns["fragmented"].append(m.group(0)[:60])

    # 3. Report
    print(f"\n[Pattern Counts]")
    for name, items in patterns.items():
        unique = list(set(items))
        if items:
            print(f"  {name}: {len(items)} total, {len(unique)} unique")
            for u in unique[:3]:
                print(f"    {u}")
            if len(unique) > 3:
                print(f"    ... and {len(unique)-3} more")
        else:
            print(f"  {name}: 0")

    # 4. Year extraction test on reference section
    if section:
        print(f"\n[Year Extraction Test]")
        ay_map = _parse_author_year_refs(text)
        bad_years = {k: v for k, v in ay_map.items()
                     if any(y in k for y in ["1908", "1909", "2009", "2002", "2005", "2010"])}
        if bad_years:
            print(f"  SUSPICIOUS year mappings (possible arXiv ID conflict):")
            for k, v in bad_years.items():
                print(f"    {k} -> {v}")
        else:
            print(f"  All {len(ay_map)} year mappings look correct")

    print()


def main():
    if len(sys.argv) < 2:
        print("Usage: python fix_md_refs.py <file_or_dir> [--dry-run] [--diagnose]")
        sys.exit(1)

    target = Path(sys.argv[1])
    dry_run = "--dry-run" in sys.argv
    diagnose = "--diagnose" in sys.argv

    if target.is_file():
        files = [target]
    elif target.is_dir():
        files = sorted(target.glob("**/*.md"))
    else:
        print(f"Not found: {target}")
        sys.exit(1)

    if not files:
        print("No .md files found.")
        return

    if diagnose:
        for f in files:
            diagnose_file(f)
        return

    print(f"Scanning {len(files)} file(s)..." + (" (dry-run)" if dry_run else ""))
    fixed_count = 0
    for f in files:
        if process_file(f, dry_run):
            fixed_count += 1
    print(f"\nDone. {fixed_count}/{len(files)} files {'would be ' if dry_run else ''}fixed.")


if __name__ == "__main__":
    main()
