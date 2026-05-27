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


def _heading_text(line: str) -> str:
    """Normalize a Markdown heading so formatted headings are easy to match."""
    text = line.strip()
    text = re.sub(r"^#{1,6}\s*", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[*_`~]+", "", text)
    text = re.sub(r"^\s*(?:[IVXLCDM]+|\d+)\s*[.)、．]\s*", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip(" :：.-")


def make_reading_markdown(md_text: str) -> str:
    """Return a compact body-only reading version.

    This keeps headings, normal prose, and formulas, while dropping image lines,
    tables, and everything after the references heading.
    """
    lines: list[str] = []
    for raw_line in md_text.splitlines():
        line = raw_line.strip()
        if line.startswith("#") and _REFERENCE_HEADING.match(_heading_text(line)):
            break

        if line.startswith("!["):
            continue
        if line.startswith("<!--") and line.endswith("-->"):
            continue
        if line.startswith("|") and line.endswith("|"):
            continue
        if re.match(r"^[-:| ]{3,}$", line):
            continue

        lines.append(raw_line)

    compact = "\n".join(lines)
    compact = re.sub(r"\n{3,}", "\n\n", compact).strip()
    return compact


def markdown_to_html_document(md_text: str, title: str = "", base_dir: str | Path | None = None) -> str:
    """Render Markdown into a printable HTML document."""
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
