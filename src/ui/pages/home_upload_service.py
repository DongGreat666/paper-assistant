"""Upload persistence and lightweight document context helpers for home chat."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.fix_md_refs import fix_markdown
from src.core.document_parser import (
    parse_docx_to_markdown,
)


UPLOAD_DIR = Path("uploaded_files")
MAX_PDF_CONTEXT_CHARS = 60000


@dataclass(frozen=True)
class SavedUpload:
    safe_name: str
    suffix: str
    stem: str
    folder: Path
    destination: Path
    data: bytes
    file_info: str


def short_stem(filename: str, max_len: int = 20) -> str:
    """Truncate filename stem for user-facing generated filenames."""
    stem = Path(filename).stem
    return stem[:max_len] if len(stem) > max_len else stem


def file_info(data: bytes, filename: str) -> str:
    size_kb = len(data) / 1024
    info = f"{filename}  |  {size_kb:.0f} KB"
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        page_count = data.count(b"/Type /Page") or data.count(b"/Type/Page")
        if page_count > 0:
            info += f"  |  ~{page_count} 页"
    return info


def extract_pdf_text_fast(pdf_path: str | Path, max_chars: int = MAX_PDF_CONTEXT_CHARS) -> str:
    """Extract plain PDF text quickly for chat context.

    Home upload is optimized for "ask this file now", so it avoids Marker and
    uses PyMuPDF text extraction. The translation page still performs full
    layout-aware PDF -> Markdown parsing.
    """
    import fitz

    path = Path(pdf_path)
    chunks: list[str] = [f"# {path.stem}", ""]
    used = 0
    with fitz.open(str(path)) as doc:
        for page_index, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if not text:
                continue
            page_block = f"\n\n## Page {page_index}\n\n{text}"
            remaining = max_chars - used
            if remaining <= 0:
                break
            if len(page_block) > remaining:
                chunks.append(page_block[:remaining])
                chunks.append("\n\n[内容已截断，仅保留前部文本用于快速问答。]")
                break
            chunks.append(page_block)
            used += len(page_block)
    return "\n".join(chunks).strip()


async def save_upload(upload: Any) -> SavedUpload:
    safe_name = Path(upload.filename).name
    suffix = Path(safe_name).suffix.lower()
    stem = short_stem(safe_name)
    folder = UPLOAD_DIR / stem
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / safe_name
    data = await upload.read()
    destination.write_bytes(data)

    return SavedUpload(
        safe_name=safe_name,
        suffix=suffix,
        stem=stem,
        folder=folder,
        destination=destination,
        data=data,
        file_info=file_info(data, safe_name),
    )


async def prepare_document(upload: SavedUpload) -> str:
    """Create or reuse markdown context for a saved upload."""
    md_path = upload.folder / f"{upload.stem}.md"
    quick_md_path = upload.folder / f"{upload.stem}_quick.md"
    loop = asyncio.get_event_loop()

    if upload.suffix == ".pdf":
        if quick_md_path.exists():
            return quick_md_path.read_text(encoding="utf-8")
        md_text = await loop.run_in_executor(None, extract_pdf_text_fast, upload.destination)
        quick_md_path.write_text(md_text, encoding="utf-8")
        return md_text

    if md_path.exists():
        original_text = md_path.read_text(encoding="utf-8")
        md_text = await loop.run_in_executor(None, lambda: fix_markdown(original_text))
        if md_text != original_text:
            md_path.write_text(md_text, encoding="utf-8")
        return md_text

    if upload.suffix in (".md", ".txt"):
        md_text = upload.data.decode("utf-8", errors="replace")
        if upload.suffix == ".txt":
            display_name = Path(upload.safe_name).stem
            md_text = f"# {display_name}\n\n{md_text}"
        md_text = await loop.run_in_executor(None, fix_markdown, md_text)
        md_path.write_text(md_text, encoding="utf-8")
        return md_text

    if upload.suffix in (".docx", ".doc"):
        md_text = await loop.run_in_executor(
            None,
            parse_docx_to_markdown,
            str(upload.destination),
        )
        raw_path = upload.folder / f"{upload.stem}_raw.md"
        raw_path.write_text(md_text, encoding="utf-8")
        md_text = await loop.run_in_executor(None, fix_markdown, md_text)
        md_path.write_text(md_text, encoding="utf-8")
        return md_text

    return ""
