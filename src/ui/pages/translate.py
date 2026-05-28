"""Whole-paper translation workflow page.

Flow: Upload PDF -> Parse to Markdown (Marker) -> Translate sections (LLM) -> Download MD
"""

import asyncio
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

import reflex as rx

from src.core.document_parser import (
    parse_pdf_to_markdown,
    save_markdown,
    unload_marker_models,
)
from src.core.engine import (
    TranslationEngine,
    build_engine,
    get_default_translation_engine,
    has_usable_api_key,
    load_engine_profiles,
)
from src.core.exporter import make_reading_markdown, markdown_to_pdf
from src.core.translator import (
    markdown_to_html,
    merge_bilingual,
    split_markdown_into_sections,
    translate_markdown,
)
from scripts.fix_md_refs import fix_markdown
from src.ui.components.layout import app_shell, page_header, panel, small_label
from src.ui.pages.home_model_service import (
    delete_engine_action,
    save_engine_action,
    select_engine_action,
    start_edit_engine_action,
    test_profile,
)
from src.ui.pages.home_upload_service import save_upload, short_stem
from src.ui.state import UISettingsState


# ---------------------------------------------------------------------------
# Background-task cancel registry
# ---------------------------------------------------------------------------

_task_cancels: dict[str, list[bool]] = {}


def _new_cancel_token() -> str:
    token = uuid.uuid4().hex[:8]
    _task_cancels[token] = [False]
    return token


def _cancel_task(token: str):
    if token in _task_cancels:
        _task_cancels[token][0] = True


def _is_cancelled(token: str) -> bool:
    return _task_cancels.get(token, [True])[0]


def _missing_markdown_images(md_text: str, folder: Path) -> list[str]:
    """Return missing local image refs while ignoring external/data URLs."""
    import re

    missing: list[str] = []
    for ref in re.findall(r"!\[.*?\]\((.+?)\)", md_text):
        ref = ref.strip().strip("<>").split("#", 1)[0]
        parsed = urlparse(ref)
        if parsed.scheme in {"http", "https", "data"}:
            continue
        local_ref = unquote(parsed.path or ref)
        if local_ref and not (folder / local_ref).exists():
            missing.append(ref)
    return missing


class TranslateState(rx.State):
    """UI state for whole-paper translation."""

    def _log(self, msg: str):
        self.logs = self.logs + [msg]
        self.recent_logs = self.logs[-2:]

    file_name: str = ""
    saved_path: str = ""
    folder_path: str = ""
    original_md: str = ""
    translated_md: str = ""
    original_html: str = ""
    translated_html: str = ""
    is_parsing: bool = False
    is_translating: bool = False
    stop_requested: bool = False
    status_message: str = "上传 PDF 或 Markdown 文件，解析后点击「翻译」生成中文译文。"
    progress_step: int = 0
    logs: list[str] = []
    recent_logs: list[str] = []
    show_logs: bool = False
    file_info: str = ""
    bilingual_md: str = ""
    current_task_token: str = ""

    # Engine config form fields
    model_auto: bool = False
    engine_api_key: str = ""
    engine_base_url: str = get_default_translation_engine().base_url
    engine_model: str = get_default_translation_engine().model
    engine_temperature: str = str(get_default_translation_engine().temperature)
    engine_name: str = "DeepSeek 翻译"
    selected_engine_id: str = "env-default"
    saved_engines: list[dict] = load_engine_profiles()
    show_engine_config: bool = False

    # Track which engine is being edited: "" = none, "__new__" = adding, other = editing existing
    editing_engine_id: str = ""

    def set_engine_api_key(self, value: str):
        self.engine_api_key = value

    def set_engine_base_url(self, value: str):
        self.engine_base_url = value

    def set_engine_model(self, value: str):
        self.engine_model = value

    def set_engine_temperature(self, value: str):
        self.engine_temperature = value

    def set_engine_name(self, value: str):
        self.engine_name = value

    def open_engine_config(self):
        self.show_engine_config = True

    def close_engine_config(self):
        self.show_engine_config = False

    def toggle_engine_config(self):
        self.show_engine_config = not self.show_engine_config

    # --- Engine CRUD ---

    def select_engine(self, profile_id: str):
        updates = select_engine_action(self.saved_engines, profile_id)
        if updates:
            for k, v in updates.items():
                setattr(self, k, v)

    def start_edit_engine(self, profile_id: str):
        self.show_engine_config = True
        updates = start_edit_engine_action(self.saved_engines, profile_id)
        if updates:
            for k, v in updates.items():
                setattr(self, k, v)

    def start_new_engine(self):
        defaults = get_default_translation_engine()
        self.show_engine_config = True
        self.editing_engine_id = "__new__"
        self.engine_name = ""
        self.engine_api_key = ""
        self.engine_base_url = defaults.base_url
        self.engine_model = defaults.model
        self.engine_temperature = str(defaults.temperature)

    def cancel_edit(self):
        self.editing_engine_id = ""

    def save_current_engine(self):
        self.saved_engines, pid = save_engine_action(
            self.saved_engines,
            engine_name=self.engine_name,
            engine_api_key=self.engine_api_key,
            engine_base_url=self.engine_base_url,
            engine_model=self.engine_model,
            engine_temperature=self.engine_temperature,
            editing_engine_id=self.editing_engine_id,
        )
        self.selected_engine_id = pid
        self.editing_engine_id = ""
        self.status_message = f"已保存翻译引擎：{self.engine_name.strip() or '翻译引擎'}。"

    def delete_engine(self, profile_id: str):
        self.saved_engines = delete_engine_action(self.saved_engines, profile_id)
        if self.selected_engine_id == profile_id:
            self.selected_engine_id = "env-default"
        if self.editing_engine_id == profile_id:
            self.editing_engine_id = ""
        self.status_message = "已删除翻译引擎。"

    async def test_engine(self, profile_id: str):
        profile = next((p for p in self.saved_engines if p.get("id") == profile_id), None)
        if not profile:
            return
        try:
            await test_profile(profile)
            self.saved_engines = [
                {**p, "status": "ok"} if p.get("id") == profile_id else p
                for p in self.saved_engines
            ]
            self._log(f"引擎 [{profile.get('name', profile_id)}] 连接正常")
        except Exception as exc:
            self.saved_engines = [
                {**p, "status": "fail"} if p.get("id") == profile_id else p
                for p in self.saved_engines
            ]
            self._log(f"引擎 [{profile.get('name', profile_id)}] 连接失败：{exc}")

    # --- PDF Upload / Parse / Translate ---

    async def handle_upload(self, files: list[rx.UploadFile]):
        if not files:
            return
        saved = await save_upload(files[0])

        # Migrate older caches that used the full filename stem as the folder.
        full_stem = Path(saved.safe_name).stem
        if full_stem != saved.stem:
            old_folder = saved.folder.parent / full_stem
            if old_folder.is_dir():
                import shutil

                for item in old_folder.iterdir():
                    if item.suffix.lower() not in {".md", ".json", ".png", ".jpg", ".jpeg", ".webp"}:
                        continue
                    if item.name.startswith(full_stem) and item.suffix.lower() == ".md":
                        target_name = item.name.replace(full_stem, saved.stem, 1)
                    else:
                        target_name = item.name
                    target = saved.folder / target_name
                    if not target.exists():
                        shutil.move(str(item), str(target))
                try:
                    old_folder.rmdir()
                except OSError:
                    pass

        self.file_name = saved.safe_name
        self.saved_path = str(saved.destination)
        self.folder_path = str(saved.folder)
        self.file_info = saved.file_info
        self.translated_md = ""
        self.translated_html = ""
        self.bilingual_md = ""
        self.progress_step = 0
        self.logs = []

        # Reset parsing/translating state in case a previous run was interrupted
        self.is_parsing = False
        self.is_translating = False
        self.stop_requested = False

        if saved.suffix == ".md":
            md_text = saved.data.decode("utf-8")
            raw_path = saved.folder / f"{saved.stem}_raw.md"
            raw_path.write_text(md_text, encoding="utf-8")
            loop = asyncio.get_event_loop()
            fixed = await loop.run_in_executor(None, fix_markdown, md_text)
            fixed_path = saved.folder / f"{saved.stem}.md"
            fixed_path.write_text(fixed, encoding="utf-8")
            self.original_md = fixed
            self.original_html = markdown_to_html(fixed)
            self.translated_html = ""
            self.progress_step = 2
            self._log(f"已上传并修正：{saved.safe_name}")
            self.status_message = "点击「翻译」开始翻译。"
        else:
            self.original_md = ""
            self.original_html = ""
            self.translated_html = ""
            self.progress_step = 1
            self._log(f"已上传：{saved.safe_name}")
            self.status_message = "点击「解析」按钮开始解析。"

    @rx.event(background=True)
    async def parse_paper(self):
        # Snapshot all needed state under the lock
        async with self:
            saved_path = self.saved_path
            if not saved_path:
                self.status_message = "请先上传文件。"
                return

        folder = Path(saved_path).parent
        stem = folder.name

        # Fast path: .md file — no heavy work, lock only for state writes
        if Path(saved_path).suffix.lower() == ".md":
            raw_md = Path(saved_path).read_text(encoding="utf-8")
            raw_path = folder / f"{stem}_raw.md"
            if not raw_path.exists():
                raw_path.write_text(raw_md, encoding="utf-8")
            fixed = fix_markdown(raw_md)
            fixed_path = folder / f"{stem}.md"
            fixed_path.write_text(fixed, encoding="utf-8")
            html = markdown_to_html(fixed)
            async with self:
                self.original_md = fixed
                self.original_html = html
                self.translated_md = ""
                self.translated_html = ""
                self.progress_step = 2
                self._log("Markdown 已修正")
                self.status_message = "点击「翻译」开始翻译。"
            return

        # Fast path: cached .md with all images
        md_path = folder / f"{stem}.md"
        if md_path.exists():
            cached_md = md_path.read_text(encoding="utf-8")
            missing_imgs = _missing_markdown_images(cached_md, folder)
            if not missing_imgs:
                fixed = fix_markdown(cached_md)
                if fixed != cached_md:
                    md_path.write_text(fixed, encoding="utf-8")
                html = markdown_to_html(fixed)
                async with self:
                    self.original_md = fixed
                    self.original_html = html
                    self.translated_md = ""
                    self.translated_html = ""
                    self.progress_step = 2
                    self._log("已加载缓存的 Markdown 文件")
                    self.status_message = "点击「翻译」开始翻译。"
                return

        token = _new_cancel_token()
        try:
            async with self:
                self.current_task_token = token
                self.stop_requested = False
                self.is_parsing = True
                self._log("开始解析 PDF...")
                self.status_message = "正在解析 PDF（首次加载模型可能需要几分钟）..."
            yield

            loop = asyncio.get_event_loop()

            async with self:
                self._log("正在调用 Marker 模型...")
            yield

            # Heavy ML work — runs outside the state lock
            md_text, images = await loop.run_in_executor(
                None, parse_pdf_to_markdown, saved_path
            )
            unload_marker_models()

            if _is_cancelled(token) or self.stop_requested:
                async with self:
                    self._log("已停止解析")
                    self.status_message = "解析已停止。"
                    self.is_parsing = False
                return

            if not md_text or not md_text.strip():
                async with self:
                    self._log("解析失败：Marker 返回了空内容")
                    self.status_message = "解析失败：Marker 返回了空内容。"
                return

            # Check cancel BEFORE any disk writes (P1 fix)
            if _is_cancelled(token) or self.stop_requested:
                async with self:
                    self._log("已停止解析")
                    self.status_message = "解析已停止。"
                    self.is_parsing = False
                return

            async with self:
                self._log("Marker 解析完成，正在保存...")
            yield

            await loop.run_in_executor(None, save_markdown, md_text, saved_path, images)
            raw_path = folder / f"{stem}_raw.md"
            raw_path.write_text(md_text, encoding="utf-8")

            async with self:
                self._log("正在修正引用链接...")
            yield

            fixed = fix_markdown(md_text)
            md_path = folder / f"{stem}.md"
            md_path.write_text(fixed, encoding="utf-8")
            html = markdown_to_html(fixed)

            async with self:
                self.original_md = fixed
                self.original_html = html
                self.translated_md = ""
                self.translated_html = ""
                self.progress_step = 2
                self._log("解析完成")
                self.status_message = "点击「翻译」开始翻译。"
        except Exception as exc:
            async with self:
                self._log(f"解析失败：{exc}")
                self.status_message = f"解析失败：{exc}"
        finally:
            _task_cancels.pop(token, None)
            async with self:
                if self.current_task_token == token:
                    self.current_task_token = ""
                    self.is_parsing = False

    @rx.event(background=True)
    async def translate_paper(self):
        # Snapshot all needed state under the lock
        async with self:
            folder_path = self.folder_path
            original_md = self.original_md
            translated_md = self.translated_md
            stem = Path(folder_path).name if folder_path else ""

            if not original_md and folder_path:
                md_path = Path(folder_path) / f"{stem}.md"
                if md_path.exists():
                    original_md = md_path.read_text(encoding="utf-8")
                    self.original_md = original_md
                    self._log("已从磁盘加载原文 Markdown。")
            if not original_md:
                self.status_message = "请先解析 PDF。"
                return

        # Cached translation
        zh_path = Path(folder_path) / f"{stem}_zh.md"
        if zh_path.exists() and not translated_md:
            raw_zh = zh_path.read_text(encoding="utf-8")
            result_fixed = fix_markdown(raw_zh)
            html = markdown_to_html(result_fixed)
            async with self:
                self.translated_md = result_fixed
                self.translated_html = html
                self.progress_step = 3
                self.status_message = "已加载译文。可以下载或打开文件夹。"
                self._log("译文加载完成。")
            return

        async with self:
            engine = self._build_engine()
            if not has_usable_api_key(engine.api_key):
                self.status_message = "请在翻译引擎里填写 API Key，或在 .env 中配置 TRANSLATE_API_KEY / LLM_API_KEY。"
                return

        token = _new_cancel_token()

        async def on_progress(done: int, total: int):
            async with self:
                self._log(f"翻译进度：{done}/{total}")

        try:
            async with self:
                self.current_task_token = token
                self.stop_requested = False
                self.is_translating = True
                self._log("开始翻译...")
                self.status_message = "正在翻译 Markdown 文档..."
            yield

            # Heavy translation work — runs outside the state lock
            result = await translate_markdown(
                original_md, engine=engine, on_progress=on_progress,
                should_stop=lambda: _is_cancelled(token) or self.stop_requested,
            )

            if _is_cancelled(token) or self.stop_requested:
                async with self:
                    self._log("已停止翻译")
                    self.status_message = "翻译已停止。"
                    self.is_translating = False
                return

            result_fixed = fix_markdown(result)

            # Check if translation actually produced real content
            fail_count = result_fixed.count("<!-- 翻译失败") + result_fixed.count("<!-- 翻译超时")
            total_sections = len(split_markdown_into_sections(original_md))
            if fail_count > 0 and fail_count >= total_sections:
                async with self:
                    self.translated_md = ""
                    self.translated_html = ""
                    self._log(f"翻译失败：所有 {total_sections} 个段落均翻译失败。")
                    self.status_message = "翻译失败：所有段落均翻译失败，请检查 API Key 和网络连接。"
                return

            # Save results to disk (all I/O uses locals, no self)
            bi_md = ""
            if folder_path:
                zh_path.write_text(result_fixed, encoding="utf-8")
                bi_md = merge_bilingual(original_md, result_fixed)
                bi_path = Path(folder_path) / f"{stem}_bilingual.md"
                bi_path.write_text(bi_md, encoding="utf-8")
                reading_path = Path(folder_path) / f"{stem}_reading.md"
                reading_path.write_text(make_reading_markdown(result_fixed), encoding="utf-8")

            html = markdown_to_html(result_fixed)

            async with self:
                self.translated_md = result_fixed
                self.translated_html = html
                if folder_path:
                    self.bilingual_md = bi_md
                    self._log(f"已生成对照文档：{stem}_bilingual.md")
                    self._log(f"已生成精简正文：{stem}_reading.md")
                if fail_count > 0:
                    self._log(f"翻译完成（{fail_count} 个段落失败）")
                    self.status_message = f"翻译完成，但有 {fail_count} 个段落失败。"
                else:
                    self._log("翻译完成")
                    self.status_message = "翻译完成。可以下载或打开文件夹。"
                self.progress_step = 3
        except Exception as exc:
            async with self:
                self._log(f"翻译失败：{exc}")
                self.status_message = f"翻译失败：{exc}"
        finally:
            _task_cancels.pop(token, None)
            async with self:
                if self.current_task_token == token:
                    self.current_task_token = ""
                    self.is_translating = False

    def _base_download_name(self) -> str:
        return short_stem(self.file_name) if self.file_name else "translation"

    def _translation_paths(self) -> tuple[Path, str]:
        if not self.folder_path:
            raise ValueError("没有文件夹路径，无法下载。")
        folder = Path(self.folder_path)
        return folder, folder.name

    def _load_translated_md(self) -> str:
        if self.translated_md:
            return self.translated_md
        folder, stem = self._translation_paths()
        zh_path = folder / f"{stem}_zh.md"
        if zh_path.exists():
            return fix_markdown(zh_path.read_text(encoding="utf-8"))
        raise ValueError("请先完成翻译。")

    def _load_original_md(self) -> str:
        if self.original_md:
            return self.original_md
        folder, stem = self._translation_paths()
        orig_path = folder / f"{stem}.md"
        if orig_path.exists():
            return orig_path.read_text(encoding="utf-8")
        raise ValueError("需要原文 Markdown 才能生成对照版。")

    def _ensure_bilingual_md(self) -> str:
        folder, stem = self._translation_paths()
        bi_path = folder / f"{stem}_bilingual.md"
        if not bi_path.exists():
            content = merge_bilingual(self._load_original_md(), self._load_translated_md())
            bi_path.write_text(content, encoding="utf-8")
            return content
        return bi_path.read_text(encoding="utf-8")

    def _ensure_reading_md(self) -> str:
        folder, stem = self._translation_paths()
        content = make_reading_markdown(self._load_translated_md())
        reading_path = folder / f"{stem}_reading.md"
        reading_path.write_text(content, encoding="utf-8")
        return content

    def _export_content(self, variant: str) -> tuple[str, str, str]:
        if variant == "zh":
            return self._load_translated_md(), "zh", "中文译文"
        if variant == "reading":
            return self._ensure_reading_md(), "reading", "精简正文"
        if variant == "bilingual":
            return self._ensure_bilingual_md(), "bilingual", "中英对照"
        raise ValueError("未知下载类型。")

    async def download_export(self, variant: str, file_format: str):
        try:
            content, suffix, title = self._export_content(variant)
            dl_name = self._base_download_name()
            if file_format == "md":
                yield rx.download(
                    data=content,
                    filename=f"{dl_name}_{suffix}.md",
                    mime_type="text/markdown",
                )
                return

            folder, stem = self._translation_paths()
            pdf_path = folder / f"{stem}_{suffix}.pdf"
            await markdown_to_pdf(content, pdf_path, title=f"{dl_name} - {title}")
            yield rx.download(
                data=pdf_path.read_bytes(),
                filename=f"{dl_name}_{suffix}.pdf",
                mime_type="application/pdf",
            )
        except Exception as exc:
            self.status_message = f"下载失败：{exc}"
            self._log(self.status_message)

    def open_folder(self):
        if not self.folder_path:
            return
        import os
        os.startfile(self.folder_path)

    async def stop_action(self):
        token = self.current_task_token
        if token:
            _cancel_task(token)
        self.stop_requested = True
        self.status_message = "正在停止，等待当前步骤完成..."
        self._log("正在停止...")
        yield

    def toggle_logs(self):
        self.show_logs = not self.show_logs

    def reset_flow(self):
        if self.current_task_token:
            _cancel_task(self.current_task_token)
        self.file_name = ""
        self.saved_path = ""
        self.folder_path = ""
        self.original_md = ""
        self.translated_md = ""
        self.bilingual_md = ""
        self.original_html = ""
        self.translated_html = ""
        self.current_task_token = ""
        self.is_parsing = False
        self.is_translating = False
        self.stop_requested = False
        self.progress_step = 0
        self.logs = []
        self.recent_logs = []
        self.show_logs = False
        self.file_info = ""
        self.status_message = "上传 PDF 或 Markdown 文件，解析后点击「翻译」生成中文译文。"

    def _build_engine(self) -> TranslationEngine:
        return build_engine(
            api_key=self.engine_api_key,
            base_url=self.engine_base_url,
            model=self.engine_model,
            temperature=self.engine_temperature,
        )


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------


def translate_page() -> rx.Component:
    return app_shell("/translate", content())


def content() -> rx.Component:
    return rx.box(
        rx.vstack(
            page_header(
                "论文翻译",
                "上传 PDF → 解析为 Markdown → 整篇翻译 → 下载译文。",
            ),
            rx.box(
                control_bar(),
                width="100%",
                padding="1rem 1.25rem 0",
            ),
            rx.box(
                log_drawer(),
                width="100%",
                padding="0 1.25rem 0",
            ),
            rx.box(
                preview_panel(),
                width="100%",
                padding="1rem 1.25rem 0",
            ),
            spacing="0",
            width="100%",
        ),
        engine_launcher(),
        rx.cond(
            TranslateState.show_engine_config,
            engine_config_overlay(),
            rx.box(),
        ),
        width="100%",
        min_height="100vh",
        position="relative",
    )


# ---------------------------------------------------------------------------
# Control bar (upload / parse / translate / download)
# ---------------------------------------------------------------------------


def download_menu() -> rx.Component:
    return rx.menu.root(
        rx.menu.trigger(
            rx.button(
                rx.icon(tag="download", size=16),
                "下载",
                variant="soft",
                disabled=TranslateState.translated_md == "",
            ),
        ),
        rx.menu.content(
            rx.menu.item(
                rx.icon(tag="file_text", size=14),
                "中文译文 PDF",
                on_click=TranslateState.download_export("zh", "pdf"),
            ),
            rx.menu.item(
                rx.icon(tag="file_text", size=14),
                "精简正文 PDF",
                on_click=TranslateState.download_export("reading", "pdf"),
            ),
            rx.menu.item(
                rx.icon(tag="book_open", size=14),
                "中英对照 PDF",
                on_click=TranslateState.download_export("bilingual", "pdf"),
            ),
            rx.menu.separator(),
            rx.menu.item(
                rx.icon(tag="file_code", size=14),
                "中文译文 Markdown",
                on_click=TranslateState.download_export("zh", "md"),
            ),
            rx.menu.item(
                rx.icon(tag="file_code", size=14),
                "精简正文 Markdown",
                on_click=TranslateState.download_export("reading", "md"),
            ),
            rx.menu.item(
                rx.icon(tag="file_code", size=14),
                "中英对照 Markdown",
                on_click=TranslateState.download_export("bilingual", "md"),
            ),
        ),
    )


def control_bar() -> rx.Component:
    return panel(
        rx.vstack(
            rx.hstack(
                rx.upload(
                    rx.button(
                        rx.icon(tag="upload", size=14),
                        "上传",
                        size="1",
                        variant="soft",
                    ),
                    accept={
                        "application/pdf": [".pdf"],
                        "text/markdown": [".md"],
                        "text/plain": [".md"],
                    },
                    max_files=1,
                    on_drop=TranslateState.handle_upload,
                ),
                rx.button(
                    rx.icon(
                        tag=rx.cond(TranslateState.is_parsing, "loader_circle", rx.cond(TranslateState.progress_step >= 2, "check_circle", "scan_text")),
                        size=16,
                    ),
                    rx.cond(TranslateState.is_parsing, "解析中...", "解析"),
                    on_click=TranslateState.parse_paper,
                    disabled=TranslateState.is_parsing,
                    variant="soft",
                    color_scheme=rx.cond((TranslateState.progress_step >= 2) & (~TranslateState.is_parsing), "green", "gray"),
                ),
                rx.button(
                    rx.icon(
                        tag=rx.cond(TranslateState.is_translating, "loader_circle", rx.cond(TranslateState.progress_step >= 3, "check_circle", "languages")),
                        size=16,
                    ),
                    rx.cond(TranslateState.is_translating, "翻译中...", "翻译"),
                    on_click=TranslateState.translate_paper,
                    disabled=TranslateState.is_translating,
                    variant="soft",
                    color_scheme=rx.cond((TranslateState.progress_step >= 3) & (~TranslateState.is_translating), "green", "gray"),
                ),
                rx.cond(
                    TranslateState.is_parsing | TranslateState.is_translating,
                    rx.button(
                        rx.icon(tag="octagon", size=16),
                        "停止",
                        on_click=TranslateState.stop_action,
                        color_scheme="red",
                        variant="soft",
                    ),
                    rx.box(),
                ),
                download_menu(),
                rx.button(
                    rx.icon(tag="folder_open", size=16),
                    "打开文件夹",
                    on_click=TranslateState.open_folder,
                    variant="soft",
                    color_scheme="gray",
                    disabled=TranslateState.folder_path == "",
                ),
                rx.button(
                    rx.icon(tag="rotate_ccw", size=16),
                    on_click=TranslateState.reset_flow,
                    variant="ghost",
                    color_scheme="gray",
                ),
                spacing="2",
                wrap="wrap",
                align="center",
            ),
            rx.hstack(
                rx.cond(
                    TranslateState.file_info != "",
                    rx.text(TranslateState.file_info, font_size="calc(var(--base-font) * 0.82)", color=UISettingsState.text_color),
                    rx.text("尚未选择文件", font_size="calc(var(--base-font) * 0.82)", color=UISettingsState.muted_text_color),
                ),
                rx.spacer(),
                rx.text(TranslateState.status_message, font_size="calc(var(--base-font) * 0.78)", color=UISettingsState.text_color),
                width="100%",
                align="center",
            ),
            spacing="3",
            width="100%",
        ),
        padding="1rem",
        width="100%",
    )


# ---------------------------------------------------------------------------
# Preview panel (left: original, right: translated)
# ---------------------------------------------------------------------------


def preview_panel() -> rx.Component:
    return panel(
        rx.vstack(
            rx.grid(
                rx.box(
                    rx.text("原文 (Markdown)", font_size="calc(var(--base-font) * 0.84)", font_weight="700", color=UISettingsState.text_color),
                    padding="0.75rem 1rem",
                    border_bottom="1px solid #e5e7eb",
                ),
                rx.box(
                    rx.text("中文译文", font_size="calc(var(--base-font) * 0.84)", font_weight="700", color=UISettingsState.text_color),
                    padding="0.75rem 1rem",
                    border_bottom="1px solid #e5e7eb",
                    border_left="1px solid #e5e7eb",
                ),
                columns="1fr 1fr",
                width="100%",
                bg=UISettingsState.muted_bg,
            ),
            rx.grid(
                rx.box(
                    rx.cond(
                        TranslateState.original_html != "",
                        rx.html(TranslateState.original_html),
                        rx.text("解析后显示原文", font_size="calc(var(--base-font) * 0.84)", color=UISettingsState.muted_text_color),
                    ),
                    padding="1rem",
                    overflow_y="auto",
                    max_height="60vh",
                    font_size="calc(var(--base-font) * 0.88)",
                    line_height="1.7",
                    id="preview-left",
                ),
                rx.box(
                    rx.cond(
                        TranslateState.translated_html != "",
                        rx.html(TranslateState.translated_html),
                        rx.text("翻译后显示中文译文", font_size="calc(var(--base-font) * 0.84)", color=UISettingsState.muted_text_color),
                    ),
                    padding="1rem",
                    border_left="1px solid #e5e7eb",
                    overflow_y="auto",
                    max_height="60vh",
                    font_size="calc(var(--base-font) * 0.88)",
                    line_height="1.7",
                    id="preview-right",
                ),
                columns="1fr 1fr",
                width="100%",
                min_height="400px",
            ),
            rx.script("""
(function(){
  let ticking = false;
  function syncScroll(source, target) {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      const pct = source.scrollTop / (source.scrollHeight - source.clientHeight || 1);
      target.scrollTop = pct * (target.scrollHeight - target.clientHeight);
      ticking = false;
    });
  }
  function setup() {
    const L = document.getElementById('preview-left');
    const R = document.getElementById('preview-right');
    if (!L || !R) return;
    if (L.scrollHeight <= L.clientHeight) return;
    R.addEventListener('scroll', () => syncScroll(R, L));
    L.addEventListener('scroll', () => syncScroll(L, R));
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setup);
  } else {
    setup();
  }
})();
"""),
            spacing="0",
            width="100%",
        ),
        overflow="hidden",
        width="100%",
    )


# ---------------------------------------------------------------------------
# Log drawer (collapsible, bottom)
# ---------------------------------------------------------------------------


def log_drawer() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.icon(
                tag=rx.cond(TranslateState.show_logs, "chevron_down", "chevron_right"),
                size=14,
                color=UISettingsState.muted_text_color,
            ),
            rx.text("运行日志", font_size="calc(var(--base-font) * 0.78)", font_weight="600", color=UISettingsState.text_color),
            rx.text(
                rx.cond(TranslateState.show_logs, "收起", "展开"),
                font_size="calc(var(--base-font) * 0.72)",
                color=UISettingsState.muted_text_color,
                cursor="pointer",
                on_click=TranslateState.toggle_logs,
            ),
            spacing="2",
            cursor="pointer",
            on_click=TranslateState.toggle_logs,
            align="center",
        ),
        rx.cond(
            TranslateState.show_logs,
            # Expanded: show all logs
            rx.box(
                rx.foreach(TranslateState.logs, lambda line: rx.text(
                    line,
                    font_size="calc(var(--base-font) * 0.76)",
                    color=UISettingsState.text_color,
                    font_family="monospace",
                    line_height="1.5",
                )),
                max_height="200px",
                overflow_y="auto",
                padding="0.5rem 0.75rem",
                bg=UISettingsState.muted_bg,
                border_radius="0 0 6px 6px",
                border="1px solid #e5e7eb",
                border_top="none",
            ),
            # Collapsed: show last 2 lines only
            rx.cond(
                TranslateState.recent_logs.length() > 0,
                rx.box(
                    rx.foreach(
                        TranslateState.recent_logs,
                        lambda line: rx.text(
                            line,
                            font_size="calc(var(--base-font) * 0.76)",
                            color=UISettingsState.muted_text_color,
                            font_family="monospace",
                            line_height="1.5",
                            no_of_lines=1,
                        ),
                    ),
                    padding="0.25rem 0.75rem",
                    bg=UISettingsState.muted_bg,
                    border_radius="0 0 6px 6px",
                    border="1px solid #e5e7eb",
                    border_top="none",
                ),
                rx.box(),
            ),
        ),
        width="100%",
    )


# ---------------------------------------------------------------------------
# Engine config module
# ---------------------------------------------------------------------------


def engine_launcher() -> rx.Component:
    return rx.button(
        rx.icon(tag="key_round", size=18),
        rx.vstack(
            rx.hstack(
                rx.text("翻译引擎", font_size="calc(var(--base-font) * 0.82)", font_weight="750"),
                rx.cond(
                    TranslateState.saved_engines.length() > 0,
                    rx.box(
                        rx.text(TranslateState.saved_engines.length(), font_size="calc(var(--base-font) * 0.62)", font_weight="700", color="white"),
                        bg="#2f5bea",
                        border_radius="9999px",
                        padding="0 0.4rem",
                        min_width="18px",
                        height="18px",
                        display="flex",
                        align_items="center",
                        justify_content="center",
                    ),
                    rx.box(),
                ),
                spacing="2",
                align="center",
            ),
            rx.text("配置与切换", font_size="calc(var(--base-font) * 0.66)", color=UISettingsState.muted_text_color),
            spacing="0",
            align_items="start",
        ),
        on_click=TranslateState.open_engine_config,
        position="fixed",
        right="1.5rem",
        bottom="1.5rem",
        z_index="30",
        size="3",
        variant="soft",
        color_scheme="gray",
        box_shadow="0 10px 28px rgba(15, 23, 42, 0.16)",
        border="1px solid",
        border_color=UISettingsState.border_color,
        bg=UISettingsState.surface_bg,
        padding="0.7rem 0.85rem",
        height="auto",
        min_width="148px",
        justify_content="start",
    )


def engine_config_overlay() -> rx.Component:
    return rx.box(
        rx.box(
            engine_panel(),
            width="min(760px, calc(100vw - 3rem))",
            max_height="calc(100vh - 5rem)",
            overflow_y="auto",
        ),
        position="fixed",
        inset="0",
        z_index="40",
        display="flex",
        align_items="center",
        justify_content="center",
        padding="1.5rem",
        bg=rx.cond(UISettingsState.theme == "dark", "rgba(3, 7, 18, 0.62)", "rgba(15, 23, 42, 0.18)"),
        backdrop_filter="blur(2px)",
    )


def engine_panel() -> rx.Component:
    return panel(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="key_round", size=17, color="#2f5bea"),
                rx.hstack(
                    rx.text("翻译引擎", font_size="calc(var(--base-font) * 1)", font_weight="750"),
                    rx.cond(
                        TranslateState.saved_engines.length() > 0,
                        rx.box(
                            rx.text(TranslateState.saved_engines.length(), font_size="calc(var(--base-font) * 0.68)", font_weight="700", color="white"),
                            bg="#2f5bea",
                            border_radius="9999px",
                            padding="0 0.45rem",
                            min_width="20px",
                            height="20px",
                            display="flex",
                            align_items="center",
                            justify_content="center",
                        ),
                        rx.box(),
                    ),
                    spacing="2",
                    align="center",
                ),
                rx.spacer(),
                rx.button(
                    rx.icon(tag="x", size=15),
                    size="1",
                    variant="ghost",
                    color_scheme="gray",
                    on_click=TranslateState.close_engine_config,
                ),
                rx.button(
                    rx.icon(tag="plus", size=15),
                    "添加引擎",
                    size="1",
                    variant="soft",
                    on_click=TranslateState.start_new_engine,
                ),
                width="100%",
                spacing="2",
            ),
            rx.text("可保存多个 OpenAI 兼容引擎，点击修改进入配置。", font_size="calc(var(--base-font) * 0.78)", color=UISettingsState.muted_text_color, line_height="1.55"),
            rx.vstack(
                rx.cond(
                    TranslateState.saved_engines.length() > 0,
                    rx.vstack(
                        rx.foreach(TranslateState.saved_engines, engine_card),
                        spacing="2",
                        width="100%",
                        align_items="stretch",
                    ),
                    rx.box(
                        rx.vstack(
                            rx.icon(tag="server", size=28, color="#cbd5e1"),
                            rx.text("暂无引擎配置", font_size="calc(var(--base-font) * 0.82)", color="#94a3b8", font_weight="500"),
                            rx.text("点击上方「添加引擎」开始配置", font_size="calc(var(--base-font) * 0.72)", color="#cbd5e1"),
                            spacing="2",
                            align="center",
                            padding="2rem 0",
                        ),
                        width="100%",
                    ),
                ),
                spacing="2",
                width="100%",
                align_items="stretch",
            ),
            rx.cond(
                TranslateState.editing_engine_id != "",
                engine_form(),
                rx.box(),
            ),
            spacing="3",
            align_items="start",
        ),
        padding="1rem",
        width="100%",
    )


def engine_card(profile) -> rx.Component:
    is_selected = TranslateState.selected_engine_id == profile["id"]
    is_editing = TranslateState.editing_engine_id == profile["id"]
    return rx.box(
        rx.vstack(
            rx.hstack(
                # Left accent bar for selected state
                rx.box(
                    width="3px",
                    height="100%",
                    min_height="36px",
                    bg=rx.cond(is_selected, "#2f5bea", "transparent"),
                    border_radius="0 3px 3px 0",
                ),
                # Icon
                rx.icon(
                    tag=rx.cond(is_selected, "check_circle", "server"),
                    size=15,
                    color=rx.cond(is_selected, "#2f5bea", UISettingsState.muted_text_color),
                ),
                # Name + tags
                rx.vstack(
                    rx.hstack(
                        rx.text(
                            profile["name"],
                            font_size="calc(var(--base-font) * 0.82)",
                            font_weight=rx.cond(is_selected, "700", "600"),
                            color=UISettingsState.text_color,
                            no_of_lines=1,
                        ),
                        # Model tag
                        rx.box(
                            rx.text(profile["model"], font_size="calc(var(--base-font) * 0.62)", font_weight="600", color="#475569", no_of_lines=1),
                            padding="0.1rem 0.4rem",
                            bg="#f1f5f9",
                            border_radius="4px",
                            border="1px solid #e2e8f0",
                            white_space="nowrap",
                        ),
                        # API key indicator
                        rx.cond(
                            profile["api_key"] != "",
                            rx.box(
                                rx.text("Key", font_size="calc(var(--base-font) * 0.58)", font_weight="600", color="#2f5bea"),
                                padding="0.1rem 0.35rem",
                                bg="#eef2ff",
                                border_radius="4px",
                            ),
                            rx.box(),
                        ),
                        spacing="2",
                        align="center",
                        wrap="wrap",
                    ),
                    rx.text(
                        rx.cond(
                            profile["api_key"] != "",
                            "已配置 API Key",
                            "未配置 API Key",
                        ),
                        font_size="calc(var(--base-font) * 0.64)",
                        color="#94a3b8",
                    ),
                    spacing="1",
                    align_items="start",
                ),
                spacing="2",
                cursor="pointer",
                on_click=TranslateState.select_engine(profile["id"]),
                flex="1",
                min_width="0",
                align="center",
            ),
            # Action row
            rx.hstack(
                # Status badge
                rx.hstack(
                    rx.cond(
                        profile["status"] == "ok",
                        rx.box(
                            rx.hstack(
                                rx.icon(tag="circle", size=8, color="#22c55e"),
                                rx.text("正常", font_size="calc(var(--base-font) * 0.64)", color="#16a34a", font_weight="600"),
                                spacing="1",
                                align="center",
                            ),
                            padding="0.1rem 0.45rem",
                            bg="#f0fdf4",
                            border_radius="9999px",
                        ),
                        rx.cond(
                            profile["status"] == "fail",
                            rx.box(
                                rx.hstack(
                                    rx.icon(tag="circle", size=8, color="#ef4444"),
                                    rx.text("异常", font_size="calc(var(--base-font) * 0.64)", color="#dc2626", font_weight="600"),
                                    spacing="1",
                                    align="center",
                                ),
                                padding="0.1rem 0.45rem",
                                bg="#fef2f2",
                                border_radius="9999px",
                            ),
                            rx.box(
                                rx.text("未检测", font_size="calc(var(--base-font) * 0.64)", color="#94a3b8"),
                                padding="0.1rem 0.45rem",
                            ),
                        ),
                    ),
                    spacing="2",
                    align="center",
                ),
                rx.spacer(),
                rx.button(
                    rx.icon(tag="activity", size=12),
                    size="1",
                    variant="ghost",
                    color_scheme="gray",
                    on_click=TranslateState.test_engine(profile["id"]),
                    _hover={"bg": "#f1f5f9"},
                ),
                rx.button(
                    rx.icon(tag="pencil", size=12),
                    size="1",
                    variant="ghost",
                    color_scheme="gray",
                    on_click=TranslateState.start_edit_engine(profile["id"]),
                    _hover={"bg": "#f1f5f9"},
                ),
                rx.button(
                    rx.icon(tag="trash_2", size=12),
                    size="1",
                    variant="ghost",
                    color_scheme="gray",
                    on_click=TranslateState.delete_engine(profile["id"]),
                    _hover={"bg": "#fef2f2", "color": "#dc2626"},
                ),
                spacing="1",
                align="center",
                padding_left="24px",
            ),
            spacing="1",
            width="100%",
        ),
        padding="0.5rem 0",
        border_radius="10px",
        border=rx.cond(
            is_editing,
            "1.5px solid #2f5bea",
            "1px solid transparent",
        ),
        bg=rx.cond(
            is_selected,
            rx.cond(UISettingsState.theme == "dark", "#1e3a5f", "#f8faff"),
            UISettingsState.surface_bg,
        ),
        box_shadow=rx.cond(
            is_selected,
            "0 1px 3px rgba(47, 91, 234, 0.12)",
            "0 1px 2px rgba(0, 0, 0, 0.04)",
        ),
        _hover={"box_shadow": "0 2px 8px rgba(0, 0, 0, 0.08)"},
        transition="all 0.15s ease",
        width="100%",
    )

def engine_form() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(
                    tag=rx.cond(TranslateState.editing_engine_id == "__new__", "plus_circle", "settings"),
                    size=16,
                    color="#2f5bea",
                ),
                rx.text(
                    rx.cond(TranslateState.editing_engine_id == "__new__", "添加新引擎", "编辑引擎"),
                    font_size="calc(var(--base-font) * 0.92)",
                    font_weight="700",
                ),
                rx.spacer(),
                rx.button(
                    rx.icon(tag="x", size=13),
                    "取消",
                    size="1",
                    variant="ghost",
                    color_scheme="gray",
                    on_click=TranslateState.cancel_edit,
                ),
                width="100%",
                align="center",
            ),
            rx.divider(border_color="#e5e7eb", margin="0.15rem 0"),
            _field("名称", TranslateState.engine_name, TranslateState.set_engine_name, "text", "DeepSeek 翻译"),
            _field("API Key", TranslateState.engine_api_key, TranslateState.set_engine_api_key, "password", "sk-..."),
            _field("Base URL", TranslateState.engine_base_url, TranslateState.set_engine_base_url, "text", "https://api.openai.com/v1"),
            rx.grid(
                _field("Model", TranslateState.engine_model, TranslateState.set_engine_model, "text", "gpt-4o-mini"),
                _field("Temperature", TranslateState.engine_temperature, TranslateState.set_engine_temperature, "text", "0.3"),
                columns="1fr 120px",
                spacing="3",
                width="100%",
            ),
            rx.hstack(
                rx.button(
                    rx.icon(tag="x", size=14),
                    "取消",
                    on_click=TranslateState.cancel_edit,
                    width="100%",
                    variant="soft",
                    color_scheme="gray",
                ),
                rx.button(
                    rx.icon(tag="save", size=14),
                    "保存",
                    on_click=TranslateState.save_current_engine,
                    width="100%",
                ),
                spacing="2",
                width="100%",
            ),
            spacing="2",
            width="100%",
            align_items="start",
        ),
        padding="0.75rem",
        border="1.5px solid #d0d7e2",
        border_radius="10px",
        bg=rx.cond(UISettingsState.theme == "dark", "#1e293b", "#f8fafc"),
        width="100%",
    )

def _field(label: str, value, on_change, input_type: str, placeholder: str) -> rx.Component:
    return rx.vstack(
        small_label(label),
        rx.input(value=value, on_change=on_change, type=input_type, placeholder=placeholder, width="100%", size="2"),
        spacing="1",
        width="100%",
        align_items="start",
    )
