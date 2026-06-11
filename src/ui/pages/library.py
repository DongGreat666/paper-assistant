"""Paper library and reading workspace page."""

import asyncio
import json
import logging
import os
import re
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import reflex as rx

logger = logging.getLogger(__name__)

from src.core.pdf_annotations import read_highlights, add_highlight, add_underline, add_strikethrough, delete_highlight, add_text_annot, add_freetext_annot, move_freetext_annot, update_annotation_comment
from src.core.engine import (
    TranslationEngine,
    api_key_display,
    build_engine,
    build_engine_from_profile,
    delete_api_secret_refs,
    get_default_translation_engine,
    load_chat_engine_profiles,
    load_engine_profiles,
    save_chat_engine_profiles,
    save_engine_profiles,
)
from src.core.translator import translate_inline, translate_section
from src.core.chat_engine import extract_nearby_text, extract_full_text, build_chat_messages, chat_with_context
from config import get_config, read_settings

UPLOAD_DIR = get_config().papers_dir.resolve()


@dataclass
class PaperItem:
    title: str = ""
    folder: str = ""
    path: str = ""
    size: str = ""


@dataclass
class FolderItem:
    name: str = ""
    count: int = 0
    papers: list[PaperItem] = field(default_factory=list)

# JS for the global event bus that bridges iframe postMessage to Reflex
EVENT_BUS_JS = """
(function() {
  if (!window.__pdfBridge || window.__pdfBridge.version !== 2) {
    window.__pdfBridge = {
      version: 2,
      listeners: {},
      on(key, fn) {
        if (typeof key === 'function') {
          fn = key;
          key = 'default';
        }
        this.listeners[key] = fn;
      },
      emit(data) {
        Object.values(this.listeners).forEach(function(fn) { fn(data); });
      }
    };
  }
  if (!window.__pdfBridgeMessageListenerInstalled) {
    window.__pdfBridgeMessageListenerInstalled = true;
    window.addEventListener('message', function(e) {
      if (e.origin !== window.location.origin) return;
      var iframe = document.querySelector('iframe[src*="pdf-reader"]');
      if (iframe && e.source !== iframe.contentWindow) return;
      if (e.data && e.data.source === 'pdf-reader') {
        window.__pdfBridge.emit(e.data);
      }
    });
  }
})();
"""


def _scan_papers() -> list[dict]:
    """Scan the configured papers directory for PDF papers."""
    papers = []
    if not UPLOAD_DIR.exists():
        return papers
    for folder in sorted(UPLOAD_DIR.iterdir()):
        if not folder.is_dir():
            continue
        if folder.name.startswith("."):
            continue
        for pdf in sorted(folder.glob("*.pdf")):
            papers.append({
                "title": pdf.stem,
                "folder": folder.name,
                "path": f"{folder.name}/{pdf.name}",
                "size": f"{pdf.stat().st_size / 1024:.0f} KB",
            })
    return papers


class LibraryState(rx.State):
    """State for the paper reading workspace."""

    selected_paper: str = ""
    selected_folder: str = ""
    selected_pdf_path: str = ""  # relative to uploaded_files/, e.g. "folder/paper.pdf"
    pdf_reader_url: str = ""
    note_text: str = ""
    chat_input: str = ""

    # Panel visibility
    left_open: bool = False
    right_open: bool = False
    right_panel_width: int = 360
    focus_mode: bool = False

    # Text selection & translation
    selected_text: str = ""
    translation_result: str = ""
    translation_rects: str = ""
    translation_page: int = 0
    is_translating: bool = False
    pending_action: str = ""

    # Right panel tab: "chat" | "notes" | "translate" | "model"
    right_tab: str = "notes"

    # Pinned translations (shown in right panel Translate tab)
    pinned_translations: list[dict] = []

    # Engine config
    engine_api_key: str = ""
    engine_base_url: str = get_default_translation_engine().base_url
    engine_model: str = get_default_translation_engine().model
    engine_profiles: list[dict] = []
    current_engine_id: str = "env-default"
    engine_dropdown_open: bool = False

    papers: list[dict] = []
    folders: list[dict] = []
    folder_tree: list[FolderItem] = []
    expanded_folder: str = ""  # currently expanded folder name (only one at a time)
    new_folder_name: str = ""
    creating_folder: bool = False
    file_status: str = ""
    editing_folder_name: str = ""
    editing_folder_value: str = ""
    editing_paper_path: str = ""
    editing_paper_value: str = ""
    annotations: list[dict] = []
    editing_annotation_id: str = ""
    editing_annotation_note: str = ""

    # Chat state
    chat_messages: list[dict] = []  # [{role, content}]
    chat_loading: bool = False
    selected_page: int = 0  # current page number from PAGE_CHANGED

    # Chat engine config (independent, only configured in model tab)
    chat_engine_api_key: str = ""
    chat_engine_base_url: str = ""
    chat_engine_model: str = ""
    chat_engine_temperature: str = "0.3"

    # Profile editing state
    editing_profile_id: str = ""
    edit_name: str = ""
    edit_api_key: str = ""
    edit_base_url: str = ""
    edit_model: str = ""
    show_all_profiles: bool = False

    # Chat engine profiles (independent, managed in model tab)
    chat_engine_profiles: list[dict] = []
    current_chat_engine_id: str = ""
    editing_chat_profile_id: str = ""
    chat_show_all_profiles: bool = False

    @rx.var
    def visible_engine_profiles(self) -> list[dict]:
        if self.show_all_profiles or len(self.engine_profiles) <= 4:
            return self.engine_profiles
        return self.engine_profiles[:4]

    @rx.var
    def overflow_profile_count(self) -> int:
        if len(self.engine_profiles) <= 4:
            return 0
        return len(self.engine_profiles) - 4

    @rx.var
    def profile_overflow_label(self) -> str:
        c = self.overflow_profile_count
        if c <= 0:
            return ""
        return f"展开全部 ({c})"

    @rx.var
    def visible_chat_engine_profiles(self) -> list[dict]:
        if self.chat_show_all_profiles or len(self.chat_engine_profiles) <= 4:
            return self.chat_engine_profiles
        return self.chat_engine_profiles[:4]

    @rx.var
    def chat_overflow_profile_count(self) -> int:
        if len(self.chat_engine_profiles) <= 4:
            return 0
        return len(self.chat_engine_profiles) - 4

    @rx.var
    def chat_overflow_label(self) -> str:
        c = self.chat_overflow_profile_count
        if c <= 0:
            return ""
        return f"展开全部 ({c})"

    @rx.var
    def current_pinned_id(self) -> str:
        """Return the ID of the pinned translation currently shown, if any."""
        if not self.translation_result:
            return ""
        for e in self.pinned_translations:
            if e.get("result") == self.translation_result:
                return e.get("id", "")
        return ""

    @rx.var
    def right_panel_width_css(self) -> str:
        return f"{self.right_panel_width}px"

    @rx.var
    def right_panel_hidden_margin_css(self) -> str:
        return f"-{self.right_panel_width}px"

    @rx.var
    def chat_panel_open(self) -> bool:
        return self.right_open and self.right_tab == "chat"

    @rx.var
    def right_panel_open(self) -> bool:
        return self.right_open

    def set_right_panel_width(self, width: str):
        try:
            value = int(float(width))
        except (TypeError, ValueError):
            return
        self.right_panel_width = max(280, min(720, value))

    def _selected_pdf_file(self) -> Path | None:
        if not self.selected_pdf_path:
            return None
        direct = Path(self.selected_pdf_path)
        if direct.is_absolute() and direct.exists():
            return direct
        safe = self._safe_pdf_path(self.selected_pdf_path)
        if safe is not None and safe.exists():
            return safe
        return None

    def _chat_pdf_path(self) -> str:
        pdf_path = self._selected_pdf_file()
        return str(pdf_path) if pdf_path else ""

    def _format_error(self, exc: Exception) -> str:
        detail = str(exc).strip() or repr(exc)
        response = getattr(exc, "response", None)
        if response is not None:
            try:
                body = response.text[:500]
            except Exception:
                body = ""
            status = getattr(response, "status_code", "")
            if body:
                return f"{type(exc).__name__} {status}: {body}"
        return f"{type(exc).__name__}: {detail}"

    def load_papers(self):
        """Load papers from the configured papers directory."""
        self.papers = _scan_papers()
        folder_counts: dict[str, int] = {}
        for p in self.papers:
            folder_counts[p["folder"]] = folder_counts.get(p["folder"], 0) + 1
        self.folders = [{"name": k, "count": v} for k, v in folder_counts.items()]
        # Build folder tree — include empty folders too
        tree: dict[str, list[dict]] = {}
        for p in self.papers:
            tree.setdefault(p["folder"], []).append(p)
        # Add empty folders from disk
        if UPLOAD_DIR.exists():
            for d in sorted(UPLOAD_DIR.iterdir()):
                if d.is_dir() and d.name not in tree:
                    tree[d.name] = []
        self.folder_tree = [
            FolderItem(
                name=name,
                count=len(papers),
                papers=[PaperItem(title=p["title"], folder=p["folder"], path=p["path"], size=p["size"]) for p in papers],
            )
            for name, papers in sorted(tree.items())
        ]

    def _safe_name(self, name: str) -> str:
        name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name.strip())
        name = name.rstrip(". ")
        return name or "未命名"

    def _safe_folder_path(self, folder: str) -> Path | None:
        folder = self._safe_name(folder)
        target = (UPLOAD_DIR / folder).resolve()
        if not target.is_relative_to(UPLOAD_DIR.resolve()):
            return None
        return target

    def _safe_pdf_path(self, path: str) -> Path | None:
        target = (UPLOAD_DIR / path).resolve()
        if not target.is_relative_to(UPLOAD_DIR.resolve()) or target.suffix.lower() != ".pdf":
            return None
        return target

    def _send_to_recycle_bin(self, path: Path) -> bool:
        """Move a file/folder to the Windows recycle bin."""
        try:
            if os.name == "nt":
                import ctypes
                from ctypes import wintypes

                class SHFILEOPSTRUCTW(ctypes.Structure):
                    _fields_ = [
                        ("hwnd", wintypes.HWND),
                        ("wFunc", wintypes.UINT),
                        ("pFrom", wintypes.LPCWSTR),
                        ("pTo", wintypes.LPCWSTR),
                        ("fFlags", wintypes.WORD),
                        ("fAnyOperationsAborted", wintypes.BOOL),
                        ("hNameMappings", wintypes.LPVOID),
                        ("lpszProgressTitle", wintypes.LPCWSTR),
                    ]

                op = SHFILEOPSTRUCTW()
                op.wFunc = 0x0003  # FO_DELETE
                op.pFrom = str(path) + "\0\0"
                op.fFlags = 0x0040 | 0x0010 | 0x0400  # recycle, no confirm, no error UI
                return ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) == 0 and not op.fAnyOperationsAborted
            trash = UPLOAD_DIR / ".trash"
            trash.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(trash / path.name))
            return True
        except Exception:
            return False

    def toggle_folder(self, name: str):
        """Toggle expand/collapse of a folder."""
        if self.expanded_folder == name:
            self.expanded_folder = ""
        else:
            self.expanded_folder = name

    def set_new_folder_name(self, name: str):
        self.new_folder_name = name

    def start_create_folder(self):
        self.creating_folder = True

    def cancel_create_folder(self):
        self.creating_folder = False
        self.new_folder_name = ""

    def open_upload_dir(self):
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(UPLOAD_DIR.resolve()))
            self.file_status = "已打开本地论文目录。"
        except Exception as exc:
            self.file_status = f"打开目录失败：{exc}"

    def create_folder(self):
        """Create a new folder in the configured papers directory."""
        name = self._safe_name(self.new_folder_name)
        if not name:
            return
        target = self._safe_folder_path(name)
        if target is None:
            self.file_status = "文件夹名称无效。"
            return
        if target.exists():
            self.file_status = "同名文件夹已存在。"
            return
        try:
            target.mkdir(parents=True, exist_ok=True)
            self.expanded_folder = name
            self.file_status = f"已新建文件夹：{name}"
        except Exception:
            self.file_status = "新建文件夹失败。"
        self.new_folder_name = ""
        self.creating_folder = False
        self.load_papers()

    async def upload_papers(self, files: list[rx.UploadFile]):
        folder = self.expanded_folder or self.selected_folder or "未分类"
        return await self.upload_papers_to_folder(folder, files)

    async def upload_papers_to_folder(self, folder: str, files: list[rx.UploadFile]):
        if not files:
            return
        folder = self._safe_name(folder)
        target_folder = self._safe_folder_path(folder)
        if target_folder is None:
            self.file_status = "上传目标文件夹无效。"
            return
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        target_folder.mkdir(parents=True, exist_ok=True)

        last_saved: Path | None = None
        for upload in files:
            raw_name = Path(upload.filename or "未命名.pdf").name
            stem = self._safe_name(Path(raw_name).stem)
            dest = target_folder / f"{stem}.pdf"
            index = 2
            while dest.exists():
                dest = target_folder / f"{stem} ({index}).pdf"
                index += 1
            data = await upload.read()
            dest.write_bytes(data)
            last_saved = dest

        self.expanded_folder = folder
        self.file_status = f"已上传到：{folder}"
        self.load_papers()
        if last_saved:
            rel = last_saved.resolve().relative_to(UPLOAD_DIR.resolve()).as_posix()
            return self.select_paper(last_saved.stem, folder, rel)

    def start_rename_folder(self, name: str):
        self.editing_folder_name = name
        self.editing_folder_value = name

    def set_editing_folder_value(self, value: str):
        self.editing_folder_value = value

    def cancel_rename_folder(self):
        self.editing_folder_name = ""
        self.editing_folder_value = ""

    def rename_folder(self):
        old_name = self.editing_folder_name
        new_name = self._safe_name(self.editing_folder_value)
        if not old_name or not new_name or old_name == new_name:
            self.cancel_rename_folder()
            return
        old_path = self._safe_folder_path(old_name)
        new_path = self._safe_folder_path(new_name)
        if old_path is None or new_path is None or not old_path.exists() or new_path.exists():
            self.file_status = "文件夹不存在或同名文件夹已存在。"
            return
        try:
            selected_in_folder = self.selected_folder == old_name
            selected_name = self.selected_paper
            selected_pdf = Path(self.selected_pdf_path).name if self.selected_pdf_path else ""
            if selected_in_folder:
                self.selected_paper = ""
                self.selected_folder = ""
                self.selected_pdf_path = ""
                self.pdf_reader_url = ""
                self.annotations = []
            shutil.move(str(old_path), str(new_path))
            self.expanded_folder = new_name
            self.cancel_rename_folder()
            self.load_papers()
            self.file_status = f"已重命名文件夹：{new_name}"
            if selected_in_folder and selected_pdf:
                return self.select_paper(selected_name, new_name, f"{new_name}/{selected_pdf}")
        except Exception as exc:
            self.file_status = f"重命名文件夹失败：{exc}"

    def delete_folder(self, name: str):
        folder_path = self._safe_folder_path(name)
        if folder_path is None or not folder_path.exists():
            self.file_status = "文件夹不存在。"
            return
        if self._send_to_recycle_bin(folder_path):
            if self.selected_folder == name:
                self.selected_paper = ""
                self.selected_folder = ""
                self.selected_pdf_path = ""
                self.pdf_reader_url = ""
            if self.expanded_folder == name:
                self.expanded_folder = ""
            self.file_status = f"已移到回收站：{name}"
            self.load_papers()
        else:
            self.file_status = "移动到回收站失败。"

    def start_rename_paper(self, path: str, title: str):
        self.editing_paper_path = path
        self.editing_paper_value = title

    def set_editing_paper_value(self, value: str):
        self.editing_paper_value = value

    def cancel_rename_paper(self):
        self.editing_paper_path = ""
        self.editing_paper_value = ""

    def rename_paper(self):
        old_path = self._safe_pdf_path(self.editing_paper_path)
        new_title = self._safe_name(self.editing_paper_value)
        if old_path is None or not old_path.exists() or not new_title:
            self.file_status = "PDF 不存在或名称无效。"
            return
        if old_path.stem == new_title:
            self.cancel_rename_paper()
            return
        new_path = old_path.with_name(f"{new_title}.pdf")
        if new_path.exists() and new_path != old_path:
            self.file_status = "同名 PDF 已存在。"
            return
        try:
            shutil.move(str(old_path), str(new_path))
            folder = new_path.parent.name
            rel = new_path.resolve().relative_to(UPLOAD_DIR.resolve()).as_posix()
            was_selected = old_path == self._selected_pdf_file()
            self.cancel_rename_paper()
            self.load_papers()
            if was_selected:
                return self.select_paper(new_path.stem, folder, rel)
            self.expanded_folder = folder
            self.file_status = f"已重命名 PDF：{new_path.stem}"
        except Exception as exc:
            self.file_status = f"重命名 PDF 失败：{exc}"

    def delete_paper(self, path: str):
        pdf_path = self._safe_pdf_path(path)
        if pdf_path is None or not pdf_path.exists():
            self.file_status = "PDF 不存在。"
            return
        was_selected = pdf_path == self._selected_pdf_file()
        if self._send_to_recycle_bin(pdf_path):
            if was_selected:
                self.selected_paper = ""
                self.selected_pdf_path = ""
                self.pdf_reader_url = ""
                self.annotations = []
            self.file_status = f"已移到回收站：{pdf_path.stem}"
            self.load_papers()
        else:
            self.file_status = "移动到回收站失败。"

    def select_paper(self, title: str, folder: str, path: str):
        self.selected_paper = title
        self.selected_folder = folder
        safe_folder = quote(folder)
        safe_file = quote(path.split("/", 1)[1] if "/" in path else path)
        self.pdf_reader_url = f"/pdf-reader/index.html?file=/api/pdf/{safe_folder}/{safe_file}"
        # path is like "folder/filename.pdf" or just "filename.pdf"
        self.selected_pdf_path = path
        self.left_open = False
        self.selected_text = ""
        self.translation_result = ""
        self.translation_rects = ""
        self.translation_page = 0
        # Respect reading preference: auto-open chat panel
        prefs = read_settings()
        if prefs.get("pref_show_chat_on_open", True):
            self.right_open = True
            self.right_tab = "chat"
        # Load existing highlights from PDF into sidebar and send to iframe
        self._load_annotations_from_pdf()
        return self._load_and_send_highlights()

    def _build_engine(self) -> TranslationEngine:
        """Build translation engine, using saved profile if available."""
        if self.engine_api_key.strip():
            return build_engine(
                api_key=self.engine_api_key,
                base_url=self.engine_base_url,
                model=self.engine_model,
                temperature=0.2,
            )
        # Otherwise, try to load the first saved profile with a valid API key
        try:
            profiles = load_engine_profiles()
            for p in profiles:
                if p.get("has_api_key"):
                    return build_engine_from_profile(p)
        except Exception as e:
            logger.debug(f"Failed to load engine profiles, using default: {e}")
        return get_default_translation_engine()

    def _build_chat_engine(self) -> TranslationEngine:
        """Build the selected chat engine, resolving its latest key reference."""
        for profile in load_chat_engine_profiles():
            if profile.get("id") == self.current_chat_engine_id:
                return build_engine_from_profile(profile, default_profile="qa")
        return build_engine(
            api_key=self.chat_engine_api_key,
            base_url=self.chat_engine_base_url,
            model=self.chat_engine_model,
            temperature=self.chat_engine_temperature,
            default_profile="qa",
        )

    def _chat_engine_supports_vision(self, engine: TranslationEngine) -> bool:
        """Return whether the selected chat engine is likely to accept image_url parts."""
        model = (engine.model or "").lower()
        base_url = (engine.base_url or "").lower()
        vision_markers = (
            "moonshot",
            "kimi",
            "gpt-4o",
            "gpt-4.1",
            "vision",
            "vl",
            "glm-4v",
            "gemini",
            "claude-3",
        )
        return any(marker in model or marker in base_url for marker in vision_markers)

    def _get_note_path(self) -> Path | None:
        """Get the note.md path in the same folder as the PDF."""
        pdf_path = self._selected_pdf_file()
        if pdf_path is None:
            return None
        return pdf_path.parent / "note.md"

    def _remove_note_entry(self, kind: str, text: str):
        """Remove a matching entry from note.md."""
        if not read_settings().get("pref_save_notes_to_paper_dir", True):
            return
        note_path = self._get_note_path()
        if not note_path or not note_path.exists():
            return
        try:
            lines = note_path.read_text(encoding="utf-8").splitlines(keepends=True)
        except Exception:
            return
        # Match line containing both the kind and text snippet
        snippet = text[:40] if text else ""
        new_lines = []
        skip_next = False
        for line in lines:
            if skip_next:
                # Skip the "> note" continuation line
                if line.strip().startswith(">"):
                    skip_next = False
                    continue
                else:
                    skip_next = False
            if snippet and kind in line and snippet in line:
                skip_next = True  # also skip possible "> note" line after
                continue
            new_lines.append(line)
        try:
            note_path.write_text("".join(new_lines), encoding="utf-8")
        except Exception:
            pass

    def _append_note(self, kind: str, text: str, note: str = ""):
        """Append an entry to note.md in the PDF's folder."""
        if not read_settings().get("pref_save_notes_to_paper_dir", True):
            return
        note_path = self._get_note_path()
        if not note_path:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        content = note or text
        entry = f"- **[{now}] {kind}**：{text}"
        if note:
            entry += f"\n  > {note}"
        entry += "\n"
        try:
            existing = note_path.read_text(encoding="utf-8") if note_path.exists() else ""
        except Exception:
            existing = ""
        if not existing:
            existing = f"# {self.selected_paper or '笔记'}\n\n"
        try:
            note_path.write_text(existing + entry, encoding="utf-8")
        except Exception:
            pass

    def _load_annotations_from_pdf(self):
        """Load existing PDF annotations into the sidebar list."""
        pdf_path = self._selected_pdf_file()
        if pdf_path is None:
            return
        try:
            raw = read_highlights(str(pdf_path))
        except Exception:
            return
        kind_map = {
            "highlight": "高亮",
            "underline": "下划线",
            "strikethrough": "删除线",
            "comment": "批注",
            "translation": "翻译",
        }
        loaded = []
        for h in raw:
            ann_type = h.get("_type", "highlight")
            text = h.get("content", {}).get("text", "")
            comment = h.get("comment", {})
            note = comment.get("text", "") if isinstance(comment, dict) else ""
            trans = comment.get("translation", "") if isinstance(comment, dict) else ""
            loaded.append({
                "id": h.get("id", ""),
                "kind": "批注" if ann_type == "highlight" and note else kind_map.get(ann_type, "高亮"),
                "text": text or trans,
                "note": note,
                "color": h.get("_color", ""),
                "annotation_type": ann_type,
            })
        self.annotations = loaded

    def _load_and_send_highlights(self, delay_ms: int = 1500):
        """Read highlights from PDF and send to iframe without reloading it."""
        if not self.selected_pdf_path:
            return
        safe_path = self.selected_pdf_path.replace("\\", "/")
        return rx.call_script(
            f"""setTimeout(function() {{
              fetch('/api/pdf-highlights?path=' + encodeURIComponent({json.dumps(safe_path)}))
                .then(r => r.json())
                .then(data => {{
                  var iframe = document.querySelector('iframe[src*="pdf-reader"]');
                  if (iframe && iframe.contentWindow) {{
                    iframe.contentWindow.postMessage({{type: 'LOAD_HIGHLIGHTS', highlights: data}}, window.location.origin);
                  }}
                }})
                .catch(() => {{}});
            }}, {delay_ms})"""
        )

    def toggle_left(self):
        self.left_open = not self.left_open
        if self.focus_mode:
            self.focus_mode = False

    def toggle_right(self):
        self.right_open = not self.right_open
        if self.focus_mode:
            self.focus_mode = False

    def toggle_focus(self):
        self.focus_mode = not self.focus_mode
        if self.focus_mode:
            self.left_open = False
            self.right_open = False

    def load_engines(self):
        """Load available translation engine profiles."""
        self.engine_profiles = load_engine_profiles()
        if not any(p.get("id") == self.current_engine_id for p in self.engine_profiles):
            self.current_engine_id = self.engine_profiles[0]["id"] if self.engine_profiles else "env-default"
        # Load chat engine profiles
        self.chat_engine_profiles = load_chat_engine_profiles()
        if not self.current_chat_engine_id or not any(
            p.get("id") == self.current_chat_engine_id for p in self.chat_engine_profiles
        ):
            self.current_chat_engine_id = self.chat_engine_profiles[0]["id"] if self.chat_engine_profiles else ""
            self._apply_chat_engine()

    def select_engine(self, profile_id: str):
        """Select a translation engine by profile ID."""
        self.current_engine_id = profile_id
        self.engine_dropdown_open = False
        # Update engine config from the selected profile
        for p in self.engine_profiles:
            if p.get("id") == profile_id:
                self.engine_api_key = api_key_display(p)
                self.engine_base_url = p.get("base_url", "")
                self.engine_model = p.get("model", "")
                break

    def set_chat_engine_api_key(self, value: str):
        self.chat_engine_api_key = value

    def set_chat_engine_base_url(self, value: str):
        self.chat_engine_base_url = value

    def set_chat_engine_model(self, value: str):
        self.chat_engine_model = value

    # --- Profile CRUD ---

    def start_edit_profile(self, profile_id: str):
        """Expand a profile for editing."""
        self.editing_profile_id = profile_id
        self.editing_chat_profile_id = ""
        if profile_id == "new":
            self.edit_name = ""
            self.edit_api_key = ""
            self.edit_base_url = ""
            self.edit_model = ""
        else:
            for p in self.engine_profiles:
                if p.get("id") == profile_id:
                    self.edit_name = p.get("name", "")
                    self.edit_api_key = api_key_display(p)
                    self.edit_base_url = p.get("base_url", "")
                    self.edit_model = p.get("model", "")
                    break

    def cancel_edit_profile(self):
        self.editing_profile_id = ""
        self.editing_chat_profile_id = ""

    # --- Chat engine profile CRUD ---

    def load_chat_engines(self):
        self.chat_engine_profiles = load_chat_engine_profiles()
        if not any(p.get("id") == self.current_chat_engine_id for p in self.chat_engine_profiles):
            self.current_chat_engine_id = self.chat_engine_profiles[0]["id"] if self.chat_engine_profiles else ""
            self._apply_chat_engine()

    def _apply_chat_engine(self):
        for p in self.chat_engine_profiles:
            if p.get("id") == self.current_chat_engine_id:
                self.chat_engine_api_key = api_key_display(p)
                self.chat_engine_base_url = p.get("base_url", "")
                self.chat_engine_model = p.get("model", "")
                self.chat_engine_temperature = p.get("temperature", "0.3")
                break

    def select_chat_engine(self, profile_id: str):
        self.current_chat_engine_id = profile_id
        self._apply_chat_engine()

    def start_edit_chat_profile(self, profile_id: str):
        self.editing_profile_id = ""
        self.editing_chat_profile_id = profile_id
        if profile_id == "new":
            self.edit_name = ""
            self.edit_api_key = ""
            self.edit_base_url = ""
            self.edit_model = ""
        else:
            for p in self.chat_engine_profiles:
                if p.get("id") == profile_id:
                    self.edit_name = p.get("name", "")
                    self.edit_api_key = api_key_display(p)
                    self.edit_base_url = p.get("base_url", "")
                    self.edit_model = p.get("model", "")
                    break

    def cancel_edit_chat_profile(self):
        self.editing_chat_profile_id = ""

    def save_chat_profile(self):
        if not self.edit_name.strip():
            return
        eid = self.editing_chat_profile_id
        if eid == "new":
            eid = f"chat-{len(self.chat_engine_profiles)}"
        model = self.edit_model.strip()
        temperature = "1" if model.startswith("kimi-k2.") else "0.3"
        profile = {
            "id": eid,
            "name": self.edit_name.strip(),
            "api_key": self.edit_api_key.strip(),
            "base_url": self.edit_base_url.strip(),
            "model": model,
            "temperature": temperature,
        }
        updated = False
        new_list = []
        for p in self.chat_engine_profiles:
            if p.get("id") == eid:
                new_list.append(profile)
                updated = True
            else:
                new_list.append(p)
        if not updated:
            new_list.append(profile)
        self.chat_engine_profiles = new_list
        save_chat_engine_profiles(new_list)
        self.editing_chat_profile_id = ""
        # Auto-select if it's the first profile
        if self.current_chat_engine_id == eid or not self.current_chat_engine_id:
            self.current_chat_engine_id = eid
            self._apply_chat_engine()

    def delete_chat_profile(self, profile_id: str):
        removed = [p for p in self.chat_engine_profiles if p.get("id") == profile_id]
        delete_api_secret_refs([
            ref
            for p in removed
            for ref in [p.get("api_key_ref", ""), f"chat:{profile_id}"]
        ])
        new_list = [p for p in self.chat_engine_profiles if p.get("id") != profile_id]
        self.chat_engine_profiles = new_list
        save_chat_engine_profiles(new_list)
        if self.current_chat_engine_id == profile_id:
            self.current_chat_engine_id = new_list[0]["id"] if new_list else ""
            self._apply_chat_engine()

    def toggle_chat_show_all(self):
        self.chat_show_all_profiles = not self.chat_show_all_profiles

    def set_edit_name(self, value: str):
        self.edit_name = value

    def set_edit_api_key(self, value: str):
        self.edit_api_key = value

    def set_edit_base_url(self, value: str):
        self.edit_base_url = value

    def set_edit_model(self, value: str):
        self.edit_model = value

    def save_profile(self):
        """Save the currently editing profile."""
        if not self.edit_name.strip():
            return
        eid = self.editing_profile_id
        if eid == "new":
            eid = f"custom-{len(self.engine_profiles)}"
        profile = {
            "id": eid,
            "name": self.edit_name.strip(),
            "api_key": self.edit_api_key.strip(),
            "base_url": self.edit_base_url.strip(),
            "model": self.edit_model.strip(),
            "temperature": "0.2",
        }
        # Update or append
        updated = False
        new_list = []
        for p in self.engine_profiles:
            if p.get("id") == eid:
                new_list.append(profile)
                updated = True
            else:
                new_list.append(p)
        if not updated:
            new_list.append(profile)
        self.engine_profiles = new_list
        save_engine_profiles(new_list)
        self.editing_profile_id = ""

    def delete_profile(self, profile_id: str):
        """Delete a profile by ID."""
        removed = [p for p in self.engine_profiles if p.get("id") == profile_id]
        delete_api_secret_refs([
            ref
            for p in removed
            for ref in [p.get("api_key_ref", ""), f"engine:{profile_id}"]
        ])
        new_list = [p for p in self.engine_profiles if p.get("id") != profile_id]
        self.engine_profiles = new_list
        save_engine_profiles(new_list)

    def toggle_show_all(self):
        self.show_all_profiles = not self.show_all_profiles

    def toggle_engine_dropdown(self):
        """Toggle the engine selection dropdown."""
        self.engine_dropdown_open = not self.engine_dropdown_open
        if self.engine_dropdown_open and not self.engine_profiles:
            self.load_engines()

    @rx.var
    def current_engine_display(self) -> str:
        """Display name of the current engine."""
        for p in self.engine_profiles:
            if p.get("id") == self.current_engine_id:
                return p.get("name", p.get("model", "未知"))
        return "翻译引擎"

    def set_note(self, text: str):
        self.note_text = text

    def set_right_tab(self, tab: str):
        """Switch right panel tab. Toggle off if same tab clicked again."""
        if tab == "model" and not self.engine_profiles:
            self.load_engines()
        if self.right_open and self.right_tab == tab:
            self.right_open = False
            # Disable auto-translate when closing
            return rx.call_script(
                """(function() {
                  var iframe = document.querySelector('iframe[src*="pdf-reader"]');
                  if (iframe && iframe.contentWindow) {
                    iframe.contentWindow.postMessage({type: 'AUTO_TRANSLATE', enabled: false}, window.location.origin);
                  }
                })()"""
            )
        else:
            self.right_tab = tab
            self.right_open = True
            # Enable auto-translate when translate tab is active and preference is on
            auto_ok = read_settings().get("pref_auto_translate", True)
            enabled = "true" if tab == "translate" and auto_ok else "false"
            return rx.call_script(
                f"""(function() {{
                  var iframe = document.querySelector('iframe[src*="pdf-reader"]');
                  if (iframe && iframe.contentWindow) {{
                    iframe.contentWindow.postMessage({{type: 'AUTO_TRANSLATE', enabled: {enabled}}}, window.location.origin);
                  }}
                }})()"""
            )

    def set_chat_input(self, text: str):
        self.chat_input = text

    def save_note(self):
        if self.note_text.strip() and self.selected_text.strip():
            note_content = self.note_text.strip()
            self.annotations = [{
                "id": str(uuid.uuid4())[:8],
                "kind": "笔记",
                "text": self.selected_text,
                "note": note_content,
            }] + list(self.annotations)
            self._append_note("笔记", self.selected_text, note_content)
        self.note_text = ""

    def clear_chat(self):
        self.chat_messages = []
        self.chat_input = ""
        self.chat_loading = False

    def _attach_explanation_to_chat(self, text: str, result: str, image_data: str = ""):
        """Add a floating explanation to the Q&A thread so follow-up questions keep context."""
        quote = (text or "").strip() or ("框选图片区域" if image_data else "选中文本")
        prompt = "解释框选图片区域" if image_data else "解释选中文本"
        self.chat_messages = [
            *self.chat_messages,
            {"role": "user", "content": prompt, "quote": quote},
            {"role": "assistant", "content": result, "quote": ""},
        ]
        self.right_open = True
        self.right_tab = "chat"

    def handle_page_changed(self, page: int):
        self.selected_page = page

    async def send_chat(self):
        """Send a chat message with context injection."""
        if not self.chat_input.strip() or self.chat_loading:
            return
        user_msg = self.chat_input.strip()
        sel_text = self.selected_text or ""
        chat_msg = {"role": "user", "content": user_msg, "quote": sel_text}
        self.chat_messages = [*self.chat_messages, chat_msg]
        self.chat_input = ""
        self.selected_text = ""
        self.chat_loading = True
        yield

        try:
            page_num = self.selected_page
            nearby = ""
            full_text = ""
            loop = asyncio.get_event_loop()
            pdf_path = self._chat_pdf_path()
            if pdf_path:
                full_text = await loop.run_in_executor(
                    None, extract_full_text, pdf_path
                )
                if sel_text:
                    nearby = await loop.run_in_executor(
                        None, extract_nearby_text,
                        pdf_path, page_num, sel_text,
                    )

            engine = self._build_chat_engine()
            messages = build_chat_messages(
                user_query=user_msg,
                scope="paper",
                paper_title=self.selected_paper,
                selected_text=sel_text,
                nearby_text=nearby,
                full_text=full_text,
                annotations=self.annotations,
                chat_history=self.chat_messages[:-1],
            )
            result = await chat_with_context(messages, engine)
            self.chat_messages = [*self.chat_messages, {"role": "assistant", "content": result, "quote": ""}]
        except Exception as e:
            self.chat_messages = [*self.chat_messages, {"role": "assistant", "content": f"错误：{e}", "quote": ""}]
        finally:
            self.chat_loading = False

    async def handle_ask_ai(self, action: str):
        """Handle ASK_AI message from PDF reader toolbar — auto-sends."""
        self.right_open = True
        self.right_tab = "chat"
        if action == "explain":
            self.chat_input = "请解释这段内容的含义"
        elif action == "summarize":
            self.chat_input = "请总结这段内容"
        else:
            self.chat_input = "请分析这段内容"
        yield
        async for _ in self.send_chat():
            pass

    @rx.event(background=True)
    async def handle_explain_request(
        self,
        id: str,
        text: str = "",
        image: str = "",
        rects: str = "",
        page: int = 0,
        mode: str = "floating",
    ):
        """Explain selected text or an area selection in a floating PDF popup."""
        if not id:
            return

        selected = (text or "").strip()
        image_data = (image or "").strip()
        send_to_sidebar = mode == "sidebar"
        quote = selected or ("框选图片区域" if image_data else "")
        async with self:
            self.selected_text = quote
            self.translation_rects = rects
            self.translation_page = page
            engine = self._build_chat_engine()
        yield

        if send_to_sidebar:
            async with self:
                self.right_open = True
                self.right_tab = "chat"
                self.chat_input = ""
                self.chat_loading = True
                self.chat_messages = [
                    *self.chat_messages,
                    {"role": "user", "content": "解释", "quote": quote},
                ]
            yield

        try:
            if image_data:
                if not self._chat_engine_supports_vision(engine):
                    result = (
                        f"当前问答引擎「{engine.model}」看起来不支持图片/公式截图解释。"
                        "请切换到 Kimi、GPT-4o、Qwen-VL、GLM-4V 等视觉模型，"
                        "或直接选中文字后再点解释。"
                    )
                    if send_to_sidebar:
                        async with self:
                            self.chat_messages = [
                                *self.chat_messages,
                                {"role": "assistant", "content": result, "quote": ""},
                            ]
                            self.chat_loading = False
                    else:
                        yield rx.call_script(
                            f"""(function() {{
                              var iframe = document.querySelector('iframe[src*="pdf-reader"]');
                              if (iframe && iframe.contentWindow) {{
                                iframe.contentWindow.postMessage({{type: 'EXPLAIN_RESULT', id: {json.dumps(id)}, explanation: {json.dumps(result)}}}, window.location.origin);
                              }}
                            }})()"""
                        )
                    return
                system = (
                    "你是学术论文阅读助手。请自然解释用户框选的论文图片、公式、表格或图示。"
                    "重点围绕框选区域本身，说明它在表达什么、各部分之间是什么关系。"
                    "不要复述任务，不要写分析过程，不要泛泛扩展到整篇论文。"
                    "如果局部看不清，就只解释看得清的部分。"
                )
                prompt = (
                    "解释这块框选区域。根据内容自然组织回答；需要展开就展开，需要简短就简短。"
                )
                messages: list[dict] = [
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": image_data}},
                            {"type": "text", "text": prompt},
                        ],
                    },
                ]
            else:
                if send_to_sidebar:
                    page_num = page or self.selected_page
                    nearby = ""
                    full_text = ""
                    loop = asyncio.get_event_loop()
                    pdf_path = self._chat_pdf_path()
                    if pdf_path:
                        full_text = await loop.run_in_executor(
                            None, extract_full_text, pdf_path
                        )
                        if selected:
                            nearby = await loop.run_in_executor(
                                None, extract_nearby_text, pdf_path, page_num, selected
                            )
                    messages = build_chat_messages(
                        user_query="解释",
                        scope="paper",
                        paper_title=self.selected_paper,
                        selected_text=selected,
                        nearby_text=nearby,
                        full_text=full_text,
                        annotations=self.annotations,
                        chat_history=self.chat_messages[:-1],
                    )
                else:
                    system = (
                        "你是学术论文阅读助手。请自然解释用户选中的论文文字。"
                        "只围绕选中文本本身，说明核心意思、关键术语和它在论证中的作用。"
                        "不要复述任务，不要写分析过程，不要翻译全文，不要泛泛扩展到整篇论文。"
                    )
                    prompt = (
                        "解释下面这段论文内容。根据内容自然组织回答；需要展开就展开，需要简短就简短。\n\n"
                        f"{selected}"
                    )
                    messages = [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ]

            result = await chat_with_context(messages, engine, max_tokens=4000)
        except Exception as exc:
            result = f"解释失败：{self._format_error(exc)}"

        if send_to_sidebar:
            async with self:
                self.chat_messages = [
                    *self.chat_messages,
                    {"role": "assistant", "content": result, "quote": ""},
                ]
                self.chat_loading = False
        else:
            yield rx.call_script(
                f"""(function() {{
                  var iframe = document.querySelector('iframe[src*="pdf-reader"]');
                  if (iframe && iframe.contentWindow) {{
                    iframe.contentWindow.postMessage({{type: 'EXPLAIN_RESULT', id: {json.dumps(id)}, explanation: {json.dumps(result)}}}, window.location.origin);
                  }}
                }})()"""
            )

    # --- Text selection from react-pdf-highlighter ---

    def handle_select(self, text: str):
        """Handle text selection from the PDF reader iframe.

        Just stores selection. Auto-translate is handled by TRANSLATE_REQUEST
        from the PDF reader, which sets translation_result itself.
        """
        self.selected_text = text
        self.translation_rects = ""
        self.translation_page = 0

    async def do_action(self, text: str, action: str):
        """Process an action on selected text.

        Args:
            text: Selected text string.
            action: Action type (translate/highlight/annotate/note).
        """
        self.selected_text = text
        self.translation_result = ""
        self.pending_action = action
        self.right_open = True
        if action == "translate":
            await self.translate_selection()
        elif action == "highlight":
            anno = {
                "id": str(uuid.uuid4())[:8],
                "kind": "高亮",
                "text": text,
                "note": "",
            }
            self.annotations = [anno] + list(self.annotations)
        elif action == "note":
            self.note_text = text

    def handle_highlight_added(self, id: str, text: str, color: str = "#FFD700", rects: str = "", page: int = 0, annotation_type: str = "highlight"):
        """Handle a highlight or underline created in the PDF reader.

        Args:
            id: Highlight ID.
            text: Highlighted text.
            color: Hex color string.
            rects: JSON string of rects [{x1,y1,x2,y2,width,height,pageNumber}].
            page: 1-based page number.
            annotation_type: "highlight" or "underline".
        """
        self.right_open = True
        self.right_tab = "notes"
        annotation_id = id or str(uuid.uuid4())[:8]
        if any(a.get("id") == annotation_id for a in self.annotations):
            return
        kind = "下划线" if annotation_type == "underline" else "删除线" if annotation_type == "strikethrough" else "高亮"
        anno = {
            "id": annotation_id,
            "kind": kind,
            "text": text,
            "note": "",
            "color": color,
            "annotation_type": annotation_type,
        }
        self.annotations = [anno] + list(self.annotations)
        self._append_note(kind, text)
        # Write to PDF file
        pdf_path = self._selected_pdf_file()
        if pdf_path and rects and page:
            try:
                parsed_rects = json.loads(rects)
                # Rects from react-pdf-highlighter are in rendered page coordinates.
                # width/height fields = rendered page dimensions at current zoom.
                # Convert to relative 0-1 by dividing by rendered dimensions.
                converted = []
                for r in parsed_rects:
                    rw = r.get("width", 0) or 1
                    rh = r.get("height", 0) or 1
                    converted.append({
                        "x1": r.get("x1", 0) / rw,
                        "y1": r.get("y1", 0) / rh,
                        "x2": r.get("x2", 0) / rw,
                        "y2": r.get("y2", 0) / rh,
                    })

                if annotation_type == "underline":
                    add_underline(
                        str(pdf_path),
                        page_num=page,
                        rects=converted,
                        color_hex=color,
                        highlight_id=annotation_id,
                        text=text,
                    )
                elif annotation_type == "strikethrough":
                    add_strikethrough(
                        str(pdf_path),
                        page_num=page,
                        rects=converted,
                        color_hex=color,
                        highlight_id=annotation_id,
                        text=text,
                    )
                else:
                    add_highlight(
                        str(pdf_path),
                        page_num=page,
                        rects=converted,
                        color_hex=color,
                        highlight_id=annotation_id,
                        text=text,
                    )
            except Exception as e:
                logger.warning(f"Failed to write highlight to PDF: {e}")
        return self._load_and_send_highlights(delay_ms=250)

    def handle_highlight_deleted(self, id: str):
        """Handle a highlight deleted in the PDF reader."""
        self.annotations = [a for a in self.annotations if a.get("id") != id]
        # Delete from PDF file — single annotation per id
        pdf_path = self._selected_pdf_file()
        if pdf_path and id:
            try:
                delete_highlight(str(pdf_path), id)
            except Exception as e:
                logger.warning(f"Failed to delete highlight from PDF: {e}")

    def delete_annotation(self, id: str):
        """Delete an annotation from the right panel — also removes from PDF, note.md, and iframe."""
        # Find the annotation to get kind/text for note.md removal
        target = next((a for a in self.annotations if a.get("id") == id), None)
        if target:
            self._remove_note_entry(target.get("kind", ""), target.get("text", ""))
        self.annotations = [a for a in self.annotations if a.get("id") != id]
        pdf_path = self._selected_pdf_file()
        if pdf_path and id:
            try:
                delete_highlight(str(pdf_path), id)
            except Exception as e:
                logger.warning(f"Failed to delete annotation from PDF: {e}")
        return rx.call_script(
            f"""(function() {{
              var iframe = document.querySelector('iframe[src*="pdf-reader"]');
              if (iframe && iframe.contentWindow) {{
                iframe.contentWindow.postMessage({{type: 'REMOVE_HIGHLIGHT', id: {json.dumps(id)}}}, window.location.origin);
              }}
            }})()"""
        )

    def start_edit_annotation(self, id: str):
        target = next((a for a in self.annotations if a.get("id") == id), None)
        if not target:
            return
        self.editing_annotation_id = id
        self.editing_annotation_note = target.get("note", "")

    def set_editing_annotation_note(self, value: str):
        self.editing_annotation_note = value

    def cancel_edit_annotation(self):
        self.editing_annotation_id = ""
        self.editing_annotation_note = ""

    def save_annotation_edit(self):
        annot_id = self.editing_annotation_id
        note = self.editing_annotation_note.strip()
        if not annot_id:
            return
        target = next((a for a in self.annotations if a.get("id") == annot_id), None)
        if not target:
            self.cancel_edit_annotation()
            return

        old_note = target.get("note", "")
        self.annotations = [
            {**a, "note": note} if a.get("id") == annot_id else a
            for a in self.annotations
        ]

        pdf_path = self._selected_pdf_file()
        if pdf_path:
            try:
                update_annotation_comment(str(pdf_path), annot_id, note)
            except Exception as e:
                logger.warning(f"Failed to update annotation comment in PDF: {e}")

        if old_note != note:
            self._remove_note_entry(target.get("kind", ""), target.get("text", ""))
            self._append_note(target.get("kind", "批注"), target.get("text", ""), note)

        self.cancel_edit_annotation()
        return rx.call_script(
            f"""(function() {{
              var iframe = document.querySelector('iframe[src*="pdf-reader"]');
              if (iframe && iframe.contentWindow) {{
                iframe.contentWindow.postMessage({{
                  type: 'UPDATE_HIGHLIGHT_COMMENT',
                  id: {json.dumps(annot_id)},
                  comment: {json.dumps(note)}
                }}, window.location.origin);
              }}
            }})()"""
        )

    def _normalize_reader_rects(self, parsed_rects: list[dict]) -> list[dict]:
        """Normalize PDF-reader rects to page-relative coordinates."""
        converted = []
        for r in parsed_rects:
            if r.get("placement"):
                converted.append(r)
                continue
            rw = r.get("width", 0) or 0
            rh = r.get("height", 0) or 0
            max_coord = max(
                abs(float(r.get("x1", 0) or 0)),
                abs(float(r.get("y1", 0) or 0)),
                abs(float(r.get("x2", 0) or 0)),
                abs(float(r.get("y2", 0) or 0)),
            )
            if rw and rh and max_coord > 1:
                converted.append({
                    "x1": r.get("x1", 0) / rw,
                    "y1": r.get("y1", 0) / rh,
                    "x2": r.get("x2", 0) / rw,
                    "y2": r.get("y2", 0) / rh,
                    "pageNumber": r.get("pageNumber", 1),
                })
            else:
                converted.append({
                    "x1": r.get("x1", 0),
                    "y1": r.get("y1", 0),
                    "x2": r.get("x2", 0),
                    "y2": r.get("y2", 0),
                    "pageNumber": r.get("pageNumber", 1),
                })
        return converted

    async def handle_translate_request(self, id: str, text: str, rects: str = "", page: int = 0, mode: str = "sidebar"):
        """Handle a translation request from the PDF reader.

        Two modes:
        - Auto-translate (translate tab already open): result shown in sidebar only.
        - Toolbar button (translate tab closed): result sent back as floating popup.
        """
        if not text.strip():
            return

        self.selected_text = text
        self.translation_rects = rects
        self.translation_page = page
        show_floating = mode == "floating"

        if not show_floating:
            self.right_open = True
            self.right_tab = "translate"

        # Unpin previous if currently showing a pinned translation
        if self.current_pinned_id:
            self.pinned_translations = [e for e in self.pinned_translations if e.get("id") != self.current_pinned_id]

        self.is_translating = True
        self.translation_result = ""
        try:
            engine = self._build_engine()
            result = await translate_inline(text.strip(), engine)
        except Exception as exc:
            result = f"翻译失败：{exc}"
        self.is_translating = False
        self.translation_result = result

        if show_floating:
            return rx.call_script(
                f"""(function() {{
                  var iframe = document.querySelector('iframe[src*="pdf-reader"]');
                  if (iframe && iframe.contentWindow) {{
                    iframe.contentWindow.postMessage({{type: 'TRANSLATE_RESULT', id: {json.dumps(id)}, translation: {json.dumps(result)}}}, window.location.origin);
                  }}
                }})()"""
            )
        # Auto-translate: result stays in sidebar, no floating popup

    def handle_save_translation(self, id: str, text: str, translation: str, rects: str = "", page: int = 0):
        """Save a translation as a Highlight annotation with translation as content.

        Writes a single PDF Highlight (no FreeText). Translation is stored in
        the annotation's content field and shows on hover in any PDF reader.
        """
        pdf_path = self._selected_pdf_file()
        if not translation.strip() or not pdf_path:
            return
        try:
            parsed_rects = json.loads(rects) if rects else []
            if parsed_rects and page:
                normalized_rects = self._normalize_reader_rects(parsed_rects)
                source_rects = [r for r in normalized_rects if not r.get("placement")]
                if source_rects:
                    source_page = int(source_rects[0].get("pageNumber") or page)
                    add_highlight(
                        str(pdf_path),
                        page_num=source_page,
                        rects=source_rects,
                        color_hex="#FFD700",
                        highlight_id=id,
                        text=translation,
                        subject="translation",
                    )
        except Exception as e:
            logger.warning(f"Failed to save translation to PDF: {e}")

        # Add to annotations list
        anno = {
            "id": id,
            "kind": "翻译",
            "text": text[:80],
            "note": translation,
            "annotation_type": "translation",
        }
        self.annotations = [anno] + list(self.annotations)
        self._append_note("翻译", text[:80], translation)

        # Update the highlight in the iframe without full reload
        annotation_id = json.dumps(id)
        trans_json = json.dumps(translation)
        return rx.call_script(
            f"""(function() {{
              var iframe = document.querySelector('iframe[src*="pdf-reader"]');
              if (iframe && iframe.contentWindow) {{
                iframe.contentWindow.postMessage({{type: 'UPDATE_HIGHLIGHT_COMMENT', id: {annotation_id}, comment: {trans_json}}}, window.location.origin);
                iframe.contentWindow.postMessage({{type: 'UPDATE_HIGHLIGHT_TYPE', id: {annotation_id}, annotationType: 'translation'}}, window.location.origin);
              }}
            }})()"""
        )

    def handle_move_freetext(self, id: str, text: str, rects: str = "", page: int = 0):
        """Move an already written visible translation/comment annotation."""
        pdf_path = self._selected_pdf_file()
        if not id or not text.strip() or not pdf_path:
            return
        try:
            parsed_rects = self._normalize_reader_rects(json.loads(rects)) if rects else []
            if parsed_rects and page:
                move_freetext_annot(
                    str(pdf_path),
                    annot_id=id,
                    page_num=page,
                    rects=parsed_rects,
                    text=text,
                )
        except Exception as e:
            logger.warning(f"Failed to move freetext annotation: {e}")
        return self._load_and_send_highlights(delay_ms=250)

    def pin_translation(self, id: str, text: str, result: str, rects: str = "", page: int = 0):
        """Pin a floating translation to the right panel Translate tab."""
        entry = {
            "id": id,
            "text": text,
            "result": result,
            "rects": rects,
            "page": page,
        }
        # Avoid duplicates
        self.pinned_translations = [e for e in self.pinned_translations if e.get("id") != id]
        self.pinned_translations = [entry] + list(self.pinned_translations)
        # Fill the translate tab with this entry
        self.selected_text = text
        self.translation_result = result
        self.translation_rects = rects
        self.translation_page = page
        self.right_open = True
        self.right_tab = "translate"

    def place_current_translation(self):
        """Save the current sidebar translation to PDF as a highlight annotation."""
        if not self.translation_result.strip():
            return
        annotation_id = self.current_pinned_id or str(uuid.uuid4())[:8]
        return self.handle_save_translation(
            id=annotation_id,
            text=self.selected_text,
            translation=self.translation_result,
            rects=self.translation_rects or "[]",
            page=self.translation_page or 0,
        )

    def unpin_translation(self, id: str):
        """Unpin a translation from the sidebar — send it back to floating popup."""
        entry = None
        for e in self.pinned_translations:
            if e.get("id") == id:
                entry = e
                break
        if not entry:
            return
        self.pinned_translations = [e for e in self.pinned_translations if e.get("id") != id]
        # Send UNPIN_TRANSLATION to iframe so it reappears as floating popup
        return rx.call_script(
            f"""(function() {{
              var iframe = document.querySelector('iframe[src*="pdf-reader"]');
              if (iframe && iframe.contentWindow) {{
                iframe.contentWindow.postMessage({{
                  type: 'UNPIN_TRANSLATION',
                  id: {json.dumps(entry.get("id", ""))},
                  text: {json.dumps(entry.get("text", ""))},
                  result: {json.dumps(entry.get("result", ""))},
                  rects: {entry.get("rects", "[]")},
                  page: {entry.get("page", 0)}
                }}, window.location.origin);
              }}
            }})()"""
        )

    def unpin_current(self):
        """Switch from sidebar translate mode back to floating popup mode."""
        self.right_open = False
        self.selected_text = ""
        self.translation_result = ""
        self.translation_rects = ""
        self.translation_page = 0
        return rx.call_script(
            """(function() {
              var iframe = document.querySelector('iframe[src*="pdf-reader"]');
              if (iframe && iframe.contentWindow) {
                iframe.contentWindow.postMessage({type: 'AUTO_TRANSLATE', enabled: false}, window.location.origin);
              }
            })()"""
        )

    def handle_annotation_added(self, id: str, text: str, comment: str, rects: str = "", page: int = 0):
        """Handle a sticky note annotation from the PDF reader.

        Args:
            id: Annotation ID.
            text: The selected text.
            comment: The user's annotation comment.
            rects: JSON string of relative-coordinate rects.
            page: 1-based page number.
        """
        self.right_open = True
        self.right_tab = "notes"
        anno = {
            "id": id or str(uuid.uuid4())[:8],
            "kind": "批注",
            "text": text,
            "note": comment,
        }
        self.annotations = [anno] + list(self.annotations)
        self._append_note("批注", text, comment)
        # Store the user's note on the PDF highlight itself so PDF readers show it on hover.
        pdf_path = self._selected_pdf_file()
        if pdf_path and rects and page:
            try:
                parsed_rects = self._normalize_reader_rects(json.loads(rects))
                source_page = int(parsed_rects[0].get("pageNumber") or page)
                add_highlight(
                    str(pdf_path),
                    page_num=source_page,
                    rects=parsed_rects,
                    color_hex="#FFD700",
                    highlight_id=id,
                    text=comment,
                )
            except Exception as e:
                logger.warning(f"Failed to add annotation to PDF: {e}")
        return self._load_and_send_highlights(delay_ms=250)

    async def translate_selection(self):
        """Translate the selected text using the configured engine."""
        if not self.selected_text.strip():
            return
        self.is_translating = True
        self.translation_result = ""
        try:
            engine = self._build_engine()
            result = await translate_section(self.selected_text.strip(), "中文", engine)
            self.translation_result = result
        except Exception as exc:
            self.translation_result = f"翻译失败：{exc}"
        finally:
            self.is_translating = False

    @rx.var
    def preview_selected(self) -> str:
        """Truncated preview of selected text, max ~30 chars."""
        t = (self.selected_text or "").replace("\n", " ")
        if len(t) <= 30:
            return t
        return t[:30] + "…"

    def clear_selection(self):
        self.selected_text = ""
        self.translation_result = ""
