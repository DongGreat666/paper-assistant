"""Upload persistence and lightweight document context helpers for home chat."""

import asyncio
import base64
import hashlib
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import get_config
from src.core.document_parser import parse_docx_to_markdown


PAPERS_DIR = get_config().papers_dir.resolve()
CHAT_UPLOAD_DIR = (get_config().data_dir / "chat_uploads").resolve()
PROJECT_ROOT = Path(__file__).resolve().parents[3]
TRANSLATE_UPLOAD_DIR = (PROJECT_ROOT / "paper_translation").resolve()
MAX_PDF_CONTEXT_CHARS = 60000
MAX_IMAGE_SIDE = 2000


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
    stem = Path(filename).stem.strip()
    # Windows silently normalizes trailing spaces/dots in directory names.
    # Strip them before constructing paths so mkdir() and write_bytes() refer
    # to the same directory.
    shortened = stem[:max_len].rstrip(" .")
    return shortened or "document"


def unique_upload_stem(filename: str, data: bytes, max_prefix_len: int = 64) -> str:
    """Return a readable, collision-resistant folder name for persisted uploads.

    Translation caches are keyed by folder name. A plain truncated title can
    collide for papers with the same leading words, so include a short content
    digest while keeping the title readable in the filesystem.
    """
    raw_stem = Path(filename).stem.strip()
    prefix = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", raw_stem)
    prefix = re.sub(r"\s+", " ", prefix).strip(" .")
    if len(prefix) > max_prefix_len:
        prefix = prefix[:max_prefix_len].rstrip(" .")
    digest = hashlib.sha1(data).hexdigest()[:10]
    return f"{prefix or 'document'}-{digest}"


def file_info(data: bytes, filename: str) -> str:
    size_kb = len(data) / 1024
    info = f"{filename}  |  {size_kb:.0f} KB"
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        page_count = data.count(b"/Type /Page") or data.count(b"/Type/Page")
        if page_count > 0:
            info += f"  |  ~{page_count} 页"
    return info


def image_data_url(data: bytes, _filename: str) -> str:
    """Return a reasonably sized data URL suitable for vision-model requests."""
    from PIL import Image

    with Image.open(io.BytesIO(data)) as image:
        image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
        if image.mode in {"RGBA", "LA"}:
            background = Image.new("RGB", image.size, "white")
            background.paste(image, mask=image.getchannel("A"))
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=90, optimize=True)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


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
    """Save an upload permanently for workflows such as full translation."""
    return await _save_upload_to(upload, PAPERS_DIR)


async def save_translation_upload(upload: Any) -> SavedUpload:
    """Save a full-paper translation upload in the translation workspace."""
    return await _save_upload_to(upload, TRANSLATE_UPLOAD_DIR, unique_folder=True)


async def save_chat_upload(upload: Any) -> SavedUpload:
    """Save a temporary source file for the home chat workflow."""
    return await _save_upload_to(upload, CHAT_UPLOAD_DIR)


async def _save_upload_to(upload: Any, root: Path, *, unique_folder: bool = False) -> SavedUpload:
    safe_name = Path(upload.filename).name
    suffix = Path(safe_name).suffix.lower()
    data = await upload.read()
    stem = unique_upload_stem(safe_name, data) if unique_folder else short_stem(safe_name)
    folder = root / stem
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / safe_name
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
    md_path = upload.folder / f"{upload.stem}.parsed.md"
    loop = asyncio.get_event_loop()

    if upload.suffix == ".pdf":
        md_text = await loop.run_in_executor(None, extract_pdf_text_fast, upload.destination)
        md_path.write_text(md_text, encoding="utf-8")
        return md_text

    if upload.suffix in (".md", ".txt"):
        md_text = upload.data.decode("utf-8", errors="replace")
        if upload.suffix == ".txt":
            display_name = Path(upload.safe_name).stem
            md_text = f"# {display_name}\n\n{md_text}"
        md_path.write_text(md_text, encoding="utf-8")
        return md_text

    if upload.suffix == ".docx":
        md_text = await loop.run_in_executor(
            None,
            parse_docx_to_markdown,
            str(upload.destination),
        )
        md_path.write_text(md_text, encoding="utf-8")
        return md_text

    return ""


def delete_upload_source(upload: SavedUpload) -> None:
    """Delete only the uploaded source, leaving parsed Markdown intact."""
    try:
        upload.destination.unlink(missing_ok=True)
    except OSError:
        pass
