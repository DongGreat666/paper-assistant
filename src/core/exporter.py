"""Export translated Markdown variants to lightweight PDFs."""

from __future__ import annotations

import re
from html import escape
from pathlib import Path

import markdown


_REFERENCE_HEADING = re.compile(
    r"^(references|bibliography|works cited|参考文献|参考资料)$",
    re.IGNORECASE,
)
_APPENDIX_HEADING = re.compile(
    r"^(appendix|appendices|附录|[A-Z](?:\.\d+)*\s+.+)$",
    re.IGNORECASE,
)
_FIGURE_CAPTION = re.compile(r"^(?:figure|fig\.?|图)\s*[\dA-Za-z一二三四五六七八九十]+[.:：、\s]", re.IGNORECASE)
_TABLE_CAPTION = re.compile(r"^(?:table|tab\.?|表)\s*[\dA-Za-z一二三四五六七八九十]+[.:：、\s]", re.IGNORECASE)
_HTML_TABLE_START = re.compile(r"<table\b", re.IGNORECASE)
_HTML_TABLE_END = re.compile(r"</table\s*>", re.IGNORECASE)


def _heading_text(line: str) -> str:
    """Normalize a Markdown heading so formatted headings are easy to match."""
    text = line.strip()
    text = re.sub(r"^#{1,6}\s*", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[*_`~]+", "", text)
    text = re.sub(r"^\s*(?:[IVXLCDM]+|\d+)\s*[.)、．]\s*", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip(" :：.-")


def _is_markdown_table_line(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith("|") and stripped.endswith("|"):
        return True
    return bool(re.match(r"^\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?$", stripped))


def _is_image_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("![") or bool(re.match(r"^<img\b", stripped, re.IGNORECASE))


def _is_figure_caption(line: str) -> bool:
    return bool(_FIGURE_CAPTION.match(line.strip()))


def _is_table_caption(line: str) -> bool:
    return bool(_TABLE_CAPTION.match(line.strip()))


_CODE_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*=")
_CODE_SHAPE_DECL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\[[^\]]+\]\s*[-=]")
_CODE_NAME_DECL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*-\s+")
_FENCED_CODE_BLOCK = re.compile(r"```[^\n]*\n(.*?)\n```", re.DOTALL)


def _looks_like_orphan_code_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith("# "):
        return True
    if _CODE_ASSIGNMENT.match(stripped):
        return True
    if _CODE_SHAPE_DECL.match(stripped):
        return True
    if _CODE_NAME_DECL.match(stripped):
        return True
    return False


def _repair_orphan_code_fences(md_text: str) -> str:
    """Add a missing opening fence before code-like blocks with only a closer."""
    lines = md_text.splitlines()
    repaired: list[str] = []
    in_fence = False

    for line in lines:
        if line.strip().startswith("```"):
            if in_fence:
                in_fence = False
                repaired.append(line)
                continue

            start = len(repaired)
            while start > 0 and _looks_like_orphan_code_line(repaired[start - 1]):
                start -= 1
            while start < len(repaired) and not repaired[start].strip():
                start += 1

            block = repaired[start:]
            codeish = sum(1 for item in block if item.strip() and _looks_like_orphan_code_line(item))
            if codeish >= 3:
                repaired.insert(start, "```python")
                repaired.append(line)
                continue

            in_fence = True
            repaired.append(line)
            continue

        repaired.append(line)

    return "\n".join(repaired)


def repair_markdown_code_fences(md_text: str) -> str:
    """Repair code-like Markdown blocks whose opening fence was dropped."""
    return _repair_orphan_code_fences(md_text)


def _is_paper_pseudocode_block(code: str) -> bool:
    lines = [line.strip() for line in code.splitlines() if line.strip()]
    if len(lines) < 4:
        return False
    comment_lines = sum(1 for line in lines if line.startswith("# "))
    code_lines = sum(
        1
        for line in lines
        if _CODE_ASSIGNMENT.match(line) or _CODE_SHAPE_DECL.match(line) or _CODE_NAME_DECL.match(line)
    )
    return comment_lines >= 2 and code_lines >= 2


def _render_pseudocode_block(match: re.Match[str]) -> str:
    code = match.group(1)
    if not _is_paper_pseudocode_block(code):
        return match.group(0)

    rendered: list[str] = ["> **伪代码**  ", ">  "]
    for raw_line in code.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            rendered.append(">  ")
        elif stripped.startswith("# "):
            rendered.append(f"> **{stripped[2:].strip()}**  ")
        else:
            rendered.append(f"> `{stripped}`  ")
    return "\n".join(rendered)


def format_markdown_for_display(md_text: str) -> str:
    """Make parsed paper pseudocode readable in previews and exported PDFs."""
    repaired = _repair_orphan_code_fences(md_text)
    return _FENCED_CODE_BLOCK.sub(_render_pseudocode_block, repaired)


def make_compact_markdown(md_text: str) -> str:
    """Return a compact version without figures, tables, or references.

    Appendix content is kept. The function removes obvious image/table blocks
    and their captions, while leaving ordinary prose and formulas untouched.
    """
    md_text = _repair_orphan_code_fences(md_text)
    lines = md_text.splitlines()
    keep = [True] * len(lines)

    in_refs = False
    in_html_table = False
    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        heading = _heading_text(line) if line.startswith("#") else ""

        if in_refs:
            if line.startswith("#") and _APPENDIX_HEADING.match(heading):
                in_refs = False
            else:
                keep[i] = False
                continue

        if line.startswith("#") and _REFERENCE_HEADING.match(heading):
            keep[i] = False
            in_refs = True
            continue

        if in_html_table:
            keep[i] = False
            if _HTML_TABLE_END.search(line):
                in_html_table = False
            continue
        if _HTML_TABLE_START.search(line):
            keep[i] = False
            in_html_table = not bool(_HTML_TABLE_END.search(line))
            if i > 0 and _is_table_caption(lines[i - 1]):
                keep[i - 1] = False
            continue

        if _is_image_line(line):
            keep[i] = False
            if i + 1 < len(lines) and _is_figure_caption(lines[i + 1]):
                keep[i + 1] = False
            continue

        if _is_markdown_table_line(line):
            keep[i] = False
            if i > 0 and _is_table_caption(lines[i - 1]):
                keep[i - 1] = False
            continue

        if _is_figure_caption(line) or _is_table_caption(line):
            keep[i] = False

    compact = "\n".join(line for line, ok in zip(lines, keep) if ok)
    compact = re.sub(r"\n{3,}", "\n\n", compact).strip()
    return compact


def make_reading_markdown(md_text: str) -> str:
    """Return a compact body-only reading version.

    This keeps headings, normal prose, and formulas, while dropping image lines,
    tables, and everything after the references heading.
    """
    return make_compact_markdown(md_text)


def markdown_to_html_document(md_text: str, title: str = "", base_dir: str | Path | None = None) -> str:
    """Render Markdown into a printable HTML document."""
    md_text = format_markdown_for_display(md_text)
    body = markdown.markdown(
        md_text,
        extensions=["extra", "sane_lists", "toc"],
        output_format="html5",
    )
    base_tag = ""
    if base_dir:
        base_href = Path(base_dir).resolve().as_uri().rstrip("/") + "/"
        base_tag = f'<base href="{escape(base_href)}">'

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
{base_tag}
<title>{escape(title or "Markdown Export")}</title>
<style>
@page {{
  size: A4;
  margin: 18mm 17mm;
}}
html {{
  background: #fff;
}}
body {{
  color: #24292f;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans CJK SC",
    "Microsoft YaHei", "PingFang SC", Arial, sans-serif;
  font-size: 14.5px;
  line-height: 1.72;
  margin: 0;
  word-break: break-word;
}}
h1, h2, h3, h4, h5, h6 {{
  color: #111827;
  font-weight: 700;
  line-height: 1.32;
  margin: 1.35em 0 0.55em;
  break-after: avoid;
}}
h1 {{
  font-size: 31px;
  margin-top: 0;
}}
h2 {{ font-size: 22px; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.18em; }}
h3 {{ font-size: 18px; }}
h4, h5, h6 {{ font-size: 15.5px; }}
p {{ margin: 0.85em 0; }}
a {{ color: #0969da; text-decoration: none; }}
strong {{ font-weight: 700; }}
em {{ color: #374151; }}
blockquote {{
  border-left: 4px solid #d0d7de;
  color: #57606a;
  margin: 1em 0;
  padding: 0.1em 0 0.1em 1em;
}}
code {{
  background: #f6f8fa;
  border-radius: 4px;
  font-family: Consolas, "SFMono-Regular", monospace;
  font-size: 0.92em;
  padding: 0.12em 0.32em;
}}
pre {{
  background: #f6f8fa;
  border-radius: 6px;
  overflow: auto;
  padding: 0.9em 1em;
}}
pre code {{ background: transparent; padding: 0; }}
table {{
  border-collapse: collapse;
  display: block;
  margin: 1em 0;
  overflow-x: auto;
  width: 100%;
}}
th, td {{
  border: 1px solid #d0d7de;
  padding: 0.42em 0.65em;
}}
th {{ background: #f6f8fa; font-weight: 700; }}
img {{
  display: block;
  margin: 1em auto;
  max-width: 100%;
}}
hr {{
  border: 0;
  border-top: 1px solid #d8dee4;
  margin: 1.5em 0;
}}
.toc, .toc ul {{
  list-style: none;
  padding-left: 1em;
}}
</style>
</head>
<body>
{body}
</body>
</html>
"""


async def markdown_to_pdf(md_text: str, output_path: str | Path, title: str = "") -> Path:
    """Render Markdown to PDF through Chromium's print engine."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    from playwright.async_api import async_playwright

    html = markdown_to_html_document(md_text, title=title, base_dir=output.parent)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html, wait_until="networkidle")
        await page.pdf(
            path=str(output),
            format="A4",
            print_background=True,
            margin={"top": "18mm", "right": "17mm", "bottom": "18mm", "left": "17mm"},
        )
        await browser.close()
    return output
