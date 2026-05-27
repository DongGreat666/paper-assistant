"""PDF and DOCX → Markdown conversion.

Heavy dependencies (torch, marker, surya) are lazy-loaded.
"""

from __future__ import annotations

from pathlib import Path

import paths  # noqa: F401 — sets MODEL_CACHE_DIR before marker/surya imports


# ---------------------------------------------------------------------------
# Marker — PDF → Markdown
# ---------------------------------------------------------------------------

_marker_converter = None


def _get_marker_converter():
    """Lazy-load Marker converter (heavy ML models)."""
    global _marker_converter
    if _marker_converter is None:
        import torch
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict

        models = create_model_dict(dtype=torch.float16)

        _marker_converter = PdfConverter(artifact_dict=models)
    return _marker_converter


def parse_pdf_to_markdown(pdf_path: str | Path) -> tuple[str, dict]:
    """Convert PDF to Markdown via Marker. Returns (markdown_text, images_dict)."""
    from scripts.fix_md_refs import fix_markdown

    converter = _get_marker_converter()
    rendered = converter(str(pdf_path))
    images = rendered.images if hasattr(rendered, "images") and rendered.images else {}
    return fix_markdown(rendered.markdown), images


def unload_marker_models() -> None:
    """Release GPU memory after Marker parsing. Keeps models in RAM for reuse."""
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def save_markdown(md_text: str, pdf_path: str | Path, images: dict | None = None) -> Path:
    """Save Markdown and images next to the original PDF. Returns the .md path."""
    md_path = Path(pdf_path).with_suffix(".md")
    md_path.write_text(md_text, encoding="utf-8")
    # Save extracted images
    if images:
        for name, img_data in images.items():
            img_path = md_path.parent / name
            if hasattr(img_data, "save"):
                img_data.save(str(img_path))
            else:
                img_path.write_bytes(img_data)
    return md_path


# ---------------------------------------------------------------------------
# DOCX → Markdown
# ---------------------------------------------------------------------------


def parse_docx_to_markdown(docx_path: str | Path) -> str:
    """Convert a .docx file to Markdown text."""
    from docx import Document
    from docx.table import Table as DocxTable
    from docx.text.paragraph import Paragraph

    doc = Document(str(docx_path))
    lines: list[str] = []

    # Heading style name prefix mapping
    _heading_levels = {
        "Heading": 1, "heading 1": 1, "heading 2": 2, "heading 3": 3,
        "heading 4": 4, "heading 5": 5, "heading 6": 6,
    }

    def _para_to_md(para) -> str:
        style_name = (para.style.name or "").lower()
        # Check heading
        for prefix, level in _heading_levels.items():
            if style_name.startswith(prefix.lower()):
                return f"{'#' * level} {para.text.strip()}"
        text = para.text.strip()
        if not text:
            return ""
        # Bold/italic from runs
        parts: list[str] = []
        for run in para.runs:
            t = run.text
            if not t:
                continue
            if run.bold and run.italic:
                parts.append(f"***{t}***")
            elif run.bold:
                parts.append(f"**{t}**")
            elif run.italic:
                parts.append(f"*{t}*")
            else:
                parts.append(t)
        return "".join(parts) if parts else text

    def _table_to_md(table: DocxTable) -> str:
        rows: list[str] = []
        for i, row in enumerate(table.rows):
            cells = [cell.text.strip().replace("|", "\\|") for cell in row.cells]
            rows.append("| " + " | ".join(cells) + " |")
            if i == 0:
                rows.append("| " + " | ".join(["---"] * len(cells)) + " |")
        return "\n".join(rows)

    # Iterate through document body elements in order
    for element in doc.element.body:
        tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag
        if tag == "p":
            para = Paragraph(element, doc)
            md = _para_to_md(para)
            if md:
                lines.append(md)
        elif tag == "tbl":
            table = DocxTable(element, doc)
            lines.append(_table_to_md(table))

    return "\n\n".join(lines)
