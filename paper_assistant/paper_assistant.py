"""Reflex app entry point for Paper Assistant."""

from pathlib import Path

import reflex as rx
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse

from src.core.pdf_annotations import read_highlights
from src.ui.pages.home import home_page
from src.ui.pages.library import LibraryState
from src.ui.pages.library_ui import library_page
from src.ui.pages.settings import settings_page
from src.ui.pages.translate import translate_page

# --- PDF file serving ---
UPLOAD_DIR = Path("uploaded_files").resolve()


async def serve_pdf(request: Request):
    """Serve a PDF file from the uploaded_files directory."""
    file_path = request.path_params["path"]
    full_path = (UPLOAD_DIR / file_path).resolve()

    # Security: prevent path traversal
    if not str(full_path).startswith(str(UPLOAD_DIR)):
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    if not full_path.exists() or not full_path.is_file():
        return JSONResponse({"error": "Not found"}, status_code=404)

    return FileResponse(
        str(full_path),
        media_type="application/pdf",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "no-cache, must-revalidate",
        },
    )


async def pdf_highlights(request: Request):
    """Read highlight annotations from a PDF file."""
    file_path = request.query_params.get("path", "")
    if not file_path:
        return JSONResponse([], status_code=200)

    full_path = Path(file_path).resolve()
    # Security: prevent path traversal
    if not str(full_path).startswith(str(UPLOAD_DIR)):
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    if not full_path.exists() or not full_path.is_file():
        return JSONResponse([], status_code=200)

    highlights = read_highlights(str(full_path))
    return JSONResponse(highlights)


# --- Pages ---
def index() -> rx.Component:
    return home_page()


app = rx.App()

# Register custom API routes
app._api.add_route("/api/pdf/{path:path}", serve_pdf)
app._api.add_route("/api/pdf-highlights", pdf_highlights)

app.add_page(index, route="/", title="Paper Assistant")
app.add_page(translate_page, route="/translate", title="论文翻译")
app.add_page(library_page, route="/library", title="我的论文", on_load=LibraryState.load_papers)
app.add_page(settings_page, route="/settings", title="设置与用户")
