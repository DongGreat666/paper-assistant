"""PDF and DOCX → Markdown conversion.

Heavy dependencies (torch, marker, surya) are lazy-loaded.
Marker parsing runs in an isolated subprocess to prevent OOM crashes
from killing the main Reflex backend.
"""

from __future__ import annotations

import gc
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import paths  # noqa: F401 — sets MODEL_CACHE_DIR before marker/surya imports


# ---------------------------------------------------------------------------
# Marker — PDF → Markdown  (subprocess-isolated)
# ---------------------------------------------------------------------------

_LEGACY_MARKER_WORKER_SCRIPT = """\
import sys, json, gc, os, traceback, datetime, faulthandler
os.environ["MODEL_CACHE_DIR"] = sys.argv[1]
sys.path.insert(0, os.getcwd())
pdf_path = sys.argv[2]
result_path = sys.argv[3]
log_path = sys.argv[4] if len(sys.argv) > 4 else ""

def log(msg):
    line = f"[{datetime.datetime.now().isoformat(timespec='seconds')}] [marker-worker] {msg}"
    print(line, flush=True)
    if log_path:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\\n")

try:
    import paths  # noqa — sets MODEL_CACHE_DIR
    import torch

    log("Freeing memory before model load...")
    gc.collect()

    log("Loading models...")
    from marker.models import create_model_dict
    from marker.converters.pdf import PdfConverter

    models = create_model_dict(dtype=torch.float16)
    log("Models loaded.")

    gc.collect()

    log("Creating converter...")
    converter = PdfConverter(artifact_dict=models)
    log("Converter ready.")

    log(f"Parsing {pdf_path}...")
    with torch.no_grad():
        rendered = converter(pdf_path)

    md_text = rendered.markdown or ""
    images = rendered.images if hasattr(rendered, "images") and rendered.images else {}
    log(f"Parsing done. Markdown: {len(md_text)} chars, Images: {len(images)}")

    del converter, models
    gc.collect()

    # Serialize images
    img_dir = os.path.join(os.path.dirname(result_path), "_marker_images")
    os.makedirs(img_dir, exist_ok=True)
    img_names = []
    for name, img_data in images.items():
        img_path = os.path.join(img_dir, name)
        if hasattr(img_data, "save"):
            img_data.save(img_path)
        else:
            with open(img_path, "wb") as f:
                f.write(img_data)
        img_names.append(name)

    with open(result_path, "w", encoding="utf-8") as f:
        json.dump({"markdown": md_text, "images": img_names, "img_dir": img_dir}, f)

    log("Done.")

except MemoryError:
    log("ERROR: Out of memory. Please close other applications (PyCharm, Chrome, etc.) and try again.")
    sys.exit(1)
except Exception as e:
    log(f"ERROR: {e}")
    traceback.print_exc()
    sys.exit(1)
"""

_MARKER_WORKER_SCRIPT = """\
import sys, json, gc, os, traceback, datetime, faulthandler

def log(msg):
    line = f"[{datetime.datetime.now().isoformat(timespec='seconds')}] [marker-worker] {msg}"
    print(line, flush=True)
    path = os.environ.get("MARKER_WORKER_LOG", "")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\\n")

def main():
    os.environ["MODEL_CACHE_DIR"] = sys.argv[1]
    os.environ["MARKER_WORKER_LOG"] = sys.argv[4] if len(sys.argv) > 4 else ""
    worker_threads = str(max(2, min(8, os.cpu_count() or 4)))
    os.environ.setdefault("LOKY_MAX_CPU_COUNT", worker_threads)
    os.environ.setdefault("OMP_NUM_THREADS", worker_threads)
    os.environ.setdefault("MKL_NUM_THREADS", worker_threads)
    sys.path.insert(0, os.getcwd())
    pdf_path = sys.argv[2]
    result_path = sys.argv[3]
    config = {}
    if len(sys.argv) > 5 and sys.argv[5]:
        with open(sys.argv[5], "r", encoding="utf-8") as f:
            config = json.load(f)
    trace_file = None
    if os.environ["MARKER_WORKER_LOG"]:
        trace_file = open(os.environ["MARKER_WORKER_LOG"], "a", encoding="utf-8")
        faulthandler.enable(file=trace_file)
        faulthandler.dump_traceback_later(180, repeat=True, file=trace_file)

    try:
        import paths  # noqa
        import torch

        log("Freeing memory before model load...")
        gc.collect()

        log("Loading models...")
        from marker.models import create_model_dict
        from marker.converters.pdf import PdfConverter

        models = create_model_dict(dtype=torch.float16)
        log("Models loaded.")

        gc.collect()

        log("Creating converter...")
        log(f"Marker config: {config}")
        converter = PdfConverter(artifact_dict=models, config=config)
        log("Converter ready.")

        log(f"Parsing {pdf_path}...")
        with torch.no_grad():
            rendered = converter(pdf_path)

        md_text = rendered.markdown or ""
        images = rendered.images if hasattr(rendered, "images") and rendered.images else {}
        log(f"Parsing done. Markdown: {len(md_text)} chars, Images: {len(images)}")

        del converter, models
        gc.collect()

        img_dir = os.path.join(os.path.dirname(result_path), "_marker_images")
        os.makedirs(img_dir, exist_ok=True)
        img_names = []
        for name, img_data in images.items():
            img_path = os.path.join(img_dir, name)
            if hasattr(img_data, "save"):
                img_data.save(img_path)
            else:
                with open(img_path, "wb") as f:
                    f.write(img_data)
            img_names.append(name)

        with open(result_path, "w", encoding="utf-8") as f:
            json.dump({"markdown": md_text, "images": img_names, "img_dir": img_dir}, f)

        log("Done.")
        faulthandler.cancel_dump_traceback_later()
        if trace_file:
            trace_file.close()

    except MemoryError:
        log("ERROR: Out of memory.")
        faulthandler.cancel_dump_traceback_later()
        if trace_file:
            trace_file.close()
        sys.exit(1)
    except Exception as e:
        log(f"ERROR: {e}")
        traceback.print_exc()
        faulthandler.cancel_dump_traceback_later()
        if trace_file:
            trace_file.close()
        sys.exit(1)

if __name__ == "__main__":
    main()
"""


def _force_free_memory():
    """Aggressively free memory before heavy ML work."""
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def check_available_memory(min_mb: int = 6000) -> tuple[bool, int]:
    """Check if enough memory is available for Marker parsing.

    Returns (ok, available_mb). This is only a guardrail before starting
    Marker; parsing still uses the normal Marker pipeline.
    """
    try:
        import psutil
        avail = psutil.virtual_memory().available // (1024 * 1024)
        return avail >= min_mb, avail
    except ImportError:
        return True, -1  # can't check, assume OK


def _has_usable_pdf_text_layer(pdf_path: Path) -> bool:
    """Return True when a PDF already contains enough selectable text."""
    try:
        import fitz

        with fitz.open(pdf_path) as doc:
            if doc.page_count == 0:
                return False
            pages_with_text = 0
            total_chars = 0
            for page in doc:
                text_len = len(page.get_text("text").strip())
                total_chars += text_len
                if text_len >= 80:
                    pages_with_text += 1
            return total_chars >= 500 and pages_with_text >= max(1, doc.page_count // 2)
    except Exception:
        return False


def parse_pdf_to_markdown(pdf_path: str | Path) -> tuple[str, dict]:
    """Convert PDF to Markdown via Marker in an isolated subprocess.

    Returns (markdown_text, images_dict).
    """
    pdf_path = Path(pdf_path)
    project_root = Path(__file__).resolve().parent.parent.parent
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)
    worker_log_path = log_dir / "marker_worker.log"
    worker_log_path.write_text("", encoding="utf-8")
    marker_config = {"disable_ocr": True} if _has_usable_pdf_text_layer(pdf_path) else {}

    with tempfile.TemporaryDirectory(prefix="marker_") as tmpdir:
        result_path = Path(tmpdir) / "result.json"
        config_path = Path(tmpdir) / "config.json"
        worker_script = Path(tmpdir) / "marker_worker.py"
        config_path.write_text(json.dumps(marker_config), encoding="utf-8")
        worker_script.write_text(_MARKER_WORKER_SCRIPT, encoding="utf-8")

        try:
            proc = subprocess.Popen(
                [sys.executable, str(worker_script), str(project_root / "models"),
                 str(pdf_path), str(result_path), str(worker_log_path), str(config_path)],
                cwd=str(project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            stdout_lines: list[str] = []
            output_queue: queue.Queue[str | None] = queue.Queue()
            marker_timeout = int(os.environ.get("MARKER_PARSE_TIMEOUT_SECONDS", "7200"))

            assert proc.stdout is not None

            def _read_stdout() -> None:
                try:
                    for line in proc.stdout:
                        output_queue.put(line)
                finally:
                    output_queue.put(None)

            reader = threading.Thread(target=_read_stdout, daemon=True)
            reader.start()

            started_at = time.monotonic()
            reader_done = False
            while True:
                if time.monotonic() - started_at > marker_timeout:
                    proc.kill()
                    proc.wait(timeout=10)
                    raise TimeoutError(
                        f"Marker 解析超时，已终止 worker。超时上限：{marker_timeout} 秒。"
                    )

                try:
                    line = output_queue.get(timeout=1)
                except queue.Empty:
                    if proc.poll() is not None and reader_done:
                        break
                    continue

                if line is None:
                    reader_done = True
                    if proc.poll() is not None:
                        break
                    continue

                stdout_lines.append(line)
                print(line, end="", flush=True)

            returncode = proc.wait()
            stdout = "".join(stdout_lines).strip()
            stderr = stdout

            if returncode != 0:
                # Detect OOM
                if "MemoryError" in stderr or "allocate" in stderr or "out of memory" in stderr.lower():
                    raise MemoryError(
                        "Marker 解析内存不足。请关闭 PyCharm、Chrome 等大型应用后重试。"
                    )
                if "Unexpected exit from worker" in stdout:
                    raise MemoryError(
                        "Marker 内部 worker 崩溃（通常因内存不足）。请关闭其他应用后重试。"
                    )
                raise RuntimeError(
                    f"Marker 解析失败 (exit={returncode}):\n{stderr[-800:]}"
                )

            with open(result_path, "r", encoding="utf-8") as f:
                result = json.load(f)

            md_text = result["markdown"]
            img_dir = result.get("img_dir", "")
            images = {}
            for name in result.get("images", []):
                img_path = Path(img_dir) / name
                if img_path.exists():
                    images[name] = img_path.read_bytes()

            return md_text, images

        except (MemoryError, TimeoutError, RuntimeError):
            raise


def unload_marker_models() -> None:
    """Release GPU/CPU memory after Marker parsing."""
    _force_free_memory()


def save_markdown(md_text: str, pdf_path: str | Path, images: dict | None = None) -> Path:
    """Save Markdown and images next to the original PDF. Returns the .md path."""
    md_path = Path(pdf_path).with_suffix(".md")
    md_path.write_text(md_text, encoding="utf-8")
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

    _heading_levels = {
        "Heading": 1, "heading 1": 1, "heading 2": 2, "heading 3": 3,
        "heading 4": 4, "heading 5": 5, "heading 6": 6,
    }

    def _para_to_md(para) -> str:
        style_name = (para.style.name or "").lower()
        for prefix, level in _heading_levels.items():
            if style_name.startswith(prefix.lower()):
                return f"{'#' * level} {para.text.strip()}"
        text = para.text.strip()
        if not text:
            return ""
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
