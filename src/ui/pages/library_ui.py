"""UI components for the library/reading workspace page.

Extracted from library.py to separate UI from state logic.
"""

import reflex as rx

from src.ui.components.layout import app_shell, panel
from src.ui.state import UISettingsState
from src.ui.pages.library import (
    EVENT_BUS_JS,
    FolderItem,
    LibraryState,
    PaperItem,
)


def library_page() -> rx.Component:
    return app_shell("/library", content(), sidebar_body=_library_tab())


def content() -> rx.Component:
    return rx.box(
        # Hidden elements for iframe → Reflex bridge
        rx.el.input(id="pdf-select-text", type="hidden"),
        rx.el.input(id="pdf-hl-id", type="hidden"),
        rx.el.input(id="pdf-hl-text", type="hidden"),
        rx.el.input(id="pdf-hl-color", type="hidden"),
        rx.el.input(id="pdf-hl-rects", type="hidden"),
        rx.el.input(id="pdf-hl-page", type="hidden"),
        rx.el.input(id="pdf-hl-type", type="hidden", value="highlight"),
        rx.el.input(id="pdf-del-id", type="hidden"),
        rx.el.input(id="pdf-trans-id", type="hidden"),
        rx.el.input(id="pdf-trans-text", type="hidden"),
        rx.el.input(id="pdf-trans-rects", type="hidden"),
        rx.el.input(id="pdf-trans-page", type="hidden"),
        rx.el.input(id="pdf-trans-mode", type="hidden", value="sidebar"),
        rx.el.input(id="pdf-anno-id", type="hidden"),
        rx.el.input(id="pdf-anno-text", type="hidden"),
        rx.el.input(id="pdf-anno-comment", type="hidden"),
        rx.el.input(id="pdf-anno-rects", type="hidden"),
        rx.el.input(id="pdf-anno-page", type="hidden"),
        rx.el.input(id="pdf-save-id", type="hidden"),
        rx.el.input(id="pdf-save-text", type="hidden"),
        rx.el.input(id="pdf-save-translation", type="hidden"),
        rx.el.input(id="pdf-save-rects", type="hidden"),
        rx.el.input(id="pdf-save-page", type="hidden"),
        rx.el.input(id="pdf-move-id", type="hidden"),
        rx.el.input(id="pdf-move-text", type="hidden"),
        rx.el.input(id="pdf-move-rects", type="hidden"),
        rx.el.input(id="pdf-move-page", type="hidden"),
        rx.button(
            id="pdf-select-trigger",
            on_click=LibraryState.handle_select(
                rx.Var("document.getElementById('pdf-select-text').value"),
            ),
            style={"display": "none"},
        ),
        rx.button(
            id="pdf-hl-trigger",
            on_click=LibraryState.handle_highlight_added(
                rx.Var("document.getElementById('pdf-hl-id').value"),
                rx.Var("document.getElementById('pdf-hl-text').value"),
                rx.Var("document.getElementById('pdf-hl-color').value"),
                rx.Var("document.getElementById('pdf-hl-rects').value"),
                rx.Var("parseInt(document.getElementById('pdf-hl-page').value) || 0"),
                rx.Var("document.getElementById('pdf-hl-type').value || 'highlight'"),
            ),
            style={"display": "none"},
        ),
        rx.button(
            id="pdf-del-trigger",
            on_click=LibraryState.handle_highlight_deleted(
                rx.Var("document.getElementById('pdf-del-id').value"),
            ),
            style={"display": "none"},
        ),
        rx.button(
            id="pdf-trans-trigger",
            on_click=LibraryState.handle_translate_request(
                rx.Var("document.getElementById('pdf-trans-id').value"),
                rx.Var("document.getElementById('pdf-trans-text').value"),
                rx.Var("document.getElementById('pdf-trans-rects').value"),
                rx.Var("parseInt(document.getElementById('pdf-trans-page').value) || 0"),
                rx.Var("document.getElementById('pdf-trans-mode').value || 'sidebar'"),
            ),
            style={"display": "none"},
        ),
        rx.button(
            id="pdf-anno-trigger",
            on_click=LibraryState.handle_annotation_added(
                rx.Var("document.getElementById('pdf-anno-id').value"),
                rx.Var("document.getElementById('pdf-anno-text').value"),
                rx.Var("document.getElementById('pdf-anno-comment').value"),
                rx.Var("document.getElementById('pdf-anno-rects').value"),
                rx.Var("parseInt(document.getElementById('pdf-anno-page').value) || 0"),
            ),
            style={"display": "none"},
        ),
        rx.button(
            id="pdf-save-trigger",
            on_click=LibraryState.handle_save_translation(
                rx.Var("document.getElementById('pdf-save-id').value"),
                rx.Var("document.getElementById('pdf-save-text').value"),
                rx.Var("document.getElementById('pdf-save-translation').value"),
                rx.Var("document.getElementById('pdf-save-rects').value"),
                rx.Var("parseInt(document.getElementById('pdf-save-page').value) || 0"),
            ),
            style={"display": "none"},
        ),
        rx.button(
            id="pdf-move-trigger",
            on_click=LibraryState.handle_move_freetext(
                rx.Var("document.getElementById('pdf-move-id').value"),
                rx.Var("document.getElementById('pdf-move-text').value"),
                rx.Var("document.getElementById('pdf-move-rects').value"),
                rx.Var("parseInt(document.getElementById('pdf-move-page').value) || 0"),
            ),
            style={"display": "none"},
        ),
        # Hidden inputs for PIN_TRANSLATION
        rx.el.input(id="pdf-pin-id", type="hidden"),
        rx.el.input(id="pdf-pin-text", type="hidden"),
        rx.el.input(id="pdf-pin-result", type="hidden"),
        rx.el.input(id="pdf-pin-rects", type="hidden"),
        rx.el.input(id="pdf-pin-page", type="hidden"),
        rx.button(
            id="pdf-pin-trigger",
            on_click=LibraryState.pin_translation(
                rx.Var("document.getElementById('pdf-pin-id').value"),
                rx.Var("document.getElementById('pdf-pin-text').value"),
                rx.Var("document.getElementById('pdf-pin-result').value"),
                rx.Var("document.getElementById('pdf-pin-rects').value"),
                rx.Var("parseInt(document.getElementById('pdf-pin-page').value) || 0"),
            ),
            style={"display": "none"},
        ),
        # Hidden inputs for EXPLAIN_REQUEST
        rx.el.input(id="pdf-explain-id", type="hidden"),
        rx.el.input(id="pdf-explain-text", type="hidden"),
        rx.el.input(id="pdf-explain-image", type="hidden"),
        rx.el.input(id="pdf-explain-rects", type="hidden"),
        rx.el.input(id="pdf-explain-page", type="hidden"),
        rx.button(
            id="pdf-explain-trigger",
            on_click=LibraryState.handle_explain_request(
                rx.Var("document.getElementById('pdf-explain-id').value"),
                rx.Var("document.getElementById('pdf-explain-text').value"),
                rx.Var("document.getElementById('pdf-explain-image').value"),
                rx.Var("document.getElementById('pdf-explain-rects').value"),
                rx.Var("parseInt(document.getElementById('pdf-explain-page').value) || 0"),
            ),
            style={"display": "none"},
        ),
        # Hidden inputs for PAGE_CHANGED
        rx.el.input(id="pdf-page-num", type="hidden"),
        rx.button(
            id="pdf-page-trigger",
            on_click=LibraryState.handle_page_changed(
                rx.Var("parseInt(document.getElementById('pdf-page-num').value) || 0"),
            ),
            style={"display": "none"},
        ),
        # Event bus: listens for messages from react-pdf-highlighter iframe
        rx.script(EVENT_BUS_JS + """
window.__pdfBridge.on('library-page', function(msg) {
  if (msg.type === 'SELECT' && msg.text) {
    document.getElementById('pdf-select-text').value = msg.text;
    document.getElementById('pdf-select-trigger').click();
  }
  if (msg.type === 'HIGHLIGHT_ADDED' && msg.highlight) {
    var dedupeKey = msg.id || '';
    var now = Date.now();
    window.__pdfHighlightSeen = window.__pdfHighlightSeen || {};
    if (dedupeKey && window.__pdfHighlightSeen[dedupeKey] && now - window.__pdfHighlightSeen[dedupeKey] < 5000) {
      return;
    }
    if (dedupeKey) {
      window.__pdfHighlightSeen[dedupeKey] = now;
    }
    var pos = msg.highlight.position || {};
    var rects = pos.rects || [];
    var page = pos.pageNumber || 0;
    document.getElementById('pdf-hl-id').value = msg.id || '';
    document.getElementById('pdf-hl-text').value = (msg.highlight.content && msg.highlight.content.text) || '';
    document.getElementById('pdf-hl-color').value = msg.color || '#FFD700';
    document.getElementById('pdf-hl-rects').value = JSON.stringify(rects);
    document.getElementById('pdf-hl-page').value = page;
    document.getElementById('pdf-hl-type').value = msg.annotationType || 'highlight';
    document.getElementById('pdf-hl-trigger').click();
  }
  if (msg.type === 'HIGHLIGHT_DELETED' && msg.id) {
    document.getElementById('pdf-del-id').value = msg.id;
    document.getElementById('pdf-del-trigger').click();
  }
  if (msg.type === 'UNDO') {
    document.getElementById('pdf-del-trigger').click();
  }
  if (msg.type === 'TRANSLATE_REQUEST' && msg.text) {
    document.getElementById('pdf-trans-id').value = msg.id || '';
    document.getElementById('pdf-trans-text').value = msg.text || '';
    document.getElementById('pdf-trans-rects').value = JSON.stringify(msg.rects || []);
    document.getElementById('pdf-trans-page').value = msg.page || 0;
    document.getElementById('pdf-trans-mode').value = msg.mode || 'sidebar';
    document.getElementById('pdf-trans-trigger').click();
  }
  if (msg.type === 'ANNOTATION_ADDED' && msg.comment) {
    document.getElementById('pdf-anno-id').value = msg.id || '';
    document.getElementById('pdf-anno-text').value = msg.text || '';
    document.getElementById('pdf-anno-comment').value = msg.comment || '';
    document.getElementById('pdf-anno-rects').value = JSON.stringify(msg.rects || []);
    document.getElementById('pdf-anno-page').value = msg.page || 0;
    document.getElementById('pdf-anno-trigger').click();
  }
  if (msg.type === 'SAVE_TRANSLATION' && msg.translation) {
    document.getElementById('pdf-save-id').value = msg.id || '';
    document.getElementById('pdf-save-text').value = msg.text || '';
    document.getElementById('pdf-save-translation').value = msg.translation || '';
    document.getElementById('pdf-save-rects').value = JSON.stringify(msg.rects || []);
    document.getElementById('pdf-save-page').value = msg.page || 0;
    document.getElementById('pdf-save-trigger').click();
  }
  if (msg.type === 'MOVE_FREETEXT' && msg.text) {
    document.getElementById('pdf-move-id').value = msg.id || '';
    document.getElementById('pdf-move-text').value = msg.text || '';
    document.getElementById('pdf-move-rects').value = JSON.stringify(msg.rects || []);
    document.getElementById('pdf-move-page').value = msg.page || 0;
    document.getElementById('pdf-move-trigger').click();
  }
  if (msg.type === 'PIN_TRANSLATION' && msg.result) {
    document.getElementById('pdf-pin-id').value = msg.id || '';
    document.getElementById('pdf-pin-text').value = msg.text || '';
    document.getElementById('pdf-pin-result').value = msg.result || '';
    document.getElementById('pdf-pin-rects').value = JSON.stringify(msg.rects || []);
    document.getElementById('pdf-pin-page').value = msg.page || 0;
    document.getElementById('pdf-pin-trigger').click();
  }
  if (msg.type === 'EXPLAIN_REQUEST') {
    document.getElementById('pdf-explain-id').value = msg.id || '';
    document.getElementById('pdf-explain-text').value = msg.text || '';
    document.getElementById('pdf-explain-image').value = msg.image || '';
    document.getElementById('pdf-explain-rects').value = JSON.stringify(msg.rects || []);
    document.getElementById('pdf-explain-page').value = msg.page || 0;
    document.getElementById('pdf-explain-trigger').click();
  }
  if (msg.type === 'PAGE_CHANGED') {
    document.getElementById('pdf-page-num').value = msg.page || 0;
    document.getElementById('pdf-page-trigger').click();
  }
});
"""),
        # Top toolbar
        toolbar(),
        # Main area
        rx.box(
            pdf_area(),
            right_content_panel(),
            activity_bar(),
            display="flex",
            width="100%",
            height="calc(100vh - 48px)",
            overflow="hidden",
            min_height="0",
        ),
        width="100%",
        height="100vh",
        overflow="hidden",
    )


def toolbar() -> rx.Component:
    return rx.hstack(
        rx.text(
            rx.cond(LibraryState.selected_paper != "", LibraryState.selected_paper, "Paper Assistant 阅读器"),
            font_size="calc(var(--base-font) * 0.88)",
            font_weight="650",
            no_of_lines=1,
            flex="1",
            text_align="center",
        ),
        width="100%",
        height="48px",
        padding="0 12px",
        bg=UISettingsState.surface_bg,
        border_bottom=f"1px solid {UISettingsState.border_color}",
        align="center",
        spacing="2",
        flex_shrink="0",
    )


# ---------------------------------------------------------------------------
# Left panel
# ---------------------------------------------------------------------------


def left_panel() -> rx.Component:
    return rx.box(
        rx.box(
            rx.hstack(
                rx.text("论文库", font_size="calc(var(--base-font) * 0.9)", font_weight="700"),
                rx.spacer(),
                rx.upload(
                    rx.button(rx.icon(tag="upload", size=14), variant="ghost", size="1", title="导入论文"),
                    accept={"application/pdf": [".pdf"]},
                    max_files=10,
                    border="0",
                    padding="0",
                ),
                width="100%",
                padding="12px 12px 8px 12px",
            ),
            rx.box(
                rx.icon(tag="search", size=14, color=UISettingsState.muted_text_color, position="absolute", left="8px", top="50%", style={"transform": "translateY(-50%)"}),
                rx.input(placeholder="搜索...", size="1", width="100%", padding_left="28px"),
                position="relative",
                padding="0 12px 8px 12px",
            ),
            rx.box(
                rx.foreach(LibraryState.folders, folder_item),
                padding="0 12px",
            ),
            rx.divider(margin="4px 12px"),
            rx.box(
                rx.foreach(LibraryState.papers, paper_item),
                overflow_y="auto",
                flex="1",
                padding="4px 12px",
                width="100%",
            ),
            display="flex",
            flex_direction="column",
            height="100%",
            width="100%",
        ),
        width="280px",
        min_width="280px",
        height="100%",
        bg=UISettingsState.surface_bg,
        border_right=f"1px solid {UISettingsState.border_color}",
        style={"transition": "margin-left 0.2s ease, opacity 0.2s ease"},
        margin_left=rx.cond(LibraryState.left_open, "0px", "-280px"),
        opacity=rx.cond(LibraryState.left_open, "1", "0"),
        overflow="hidden",
        flex_shrink="0",
    )


def folder_item(folder) -> rx.Component:
    return rx.hstack(
        rx.icon(tag="folder", size=14, color=UISettingsState.muted_text_color),
        rx.text(folder["name"], font_size="calc(var(--base-font) * 0.78)", font_weight="600", color=UISettingsState.text_color, no_of_lines=1, flex="1", font_family="'Microsoft YaHei', sans-serif", text_align="left"),
        rx.text(folder["count"], font_size="calc(var(--base-font) * 0.7)", color=UISettingsState.muted_text_color),
        width="100%",
        padding="5px 6px",
        border_radius="5px",
        cursor="pointer",
        _hover={"bg": UISettingsState.muted_bg},
    )


def paper_item(paper: PaperItem) -> rx.Component:
    is_selected = LibraryState.selected_paper == paper.title
    return rx.box(
        rx.cond(
            LibraryState.editing_paper_path == paper.path,
            rx.hstack(
                rx.input(
                    value=LibraryState.editing_paper_value,
                    on_change=LibraryState.set_editing_paper_value,
                    on_key_down=lambda key: rx.cond(
                        key == "Enter",
                        LibraryState.rename_paper,
                        rx.cond(key == "Escape", LibraryState.cancel_rename_paper, rx.noop()),
                    ),
                    size="1",
                    flex="1",
                    height="26px",
                ),
                rx.button("保存", size="1", variant="soft", color_scheme="blue", on_click=LibraryState.rename_paper, font_size="calc(var(--base-font) * 0.68)"),
                rx.button("取消", size="1", variant="ghost", color_scheme="gray", on_click=LibraryState.cancel_rename_paper, font_size="calc(var(--base-font) * 0.68)"),
                width="100%",
                spacing="1",
                align="center",
            ),
            rx.hstack(
                rx.vstack(
                    rx.text(paper.title, font_size="calc(var(--base-font) * 0.7)", font_weight="680", color=UISettingsState.text_color, line_height="1.28", no_of_lines=2, text_align="left", font_family="'Microsoft YaHei', sans-serif"),
                    rx.text(paper.size, font_size="calc(var(--base-font) * 0.6)", color=UISettingsState.muted_text_color),
                    spacing="0",
                    align_items="start",
                    flex="1",
                    min_width="0",
                    on_click=LibraryState.select_paper(paper.title, paper.folder, paper.path),
                    cursor="pointer",
                ),
                rx.menu.root(
                    rx.menu.trigger(
                        rx.button(rx.icon(tag="ellipsis", size=15), size="1", variant="ghost", color_scheme="gray", title="更多操作"),
                    ),
                    rx.menu.content(
                        rx.menu.item(rx.icon(tag="pencil", size=14), "重命名", on_click=LibraryState.start_rename_paper(paper.path, paper.title)),
                        rx.menu.item(rx.icon(tag="trash_2", size=14), "移到回收站", color="red", on_click=LibraryState.delete_paper(paper.path)),
                    ),
                    class_name="paper-actions",
                ),
                width="100%",
                align="center",
                spacing="1",
            ),
        ),
        class_name="paper-row",
        width="100%",
        padding="6px 6px",
        border_radius="6px",
        text_align="left",
        bg=rx.cond(is_selected, rx.cond(UISettingsState.theme == "dark", "#1e3a5f", "#eff4ff"), "transparent"),
        border=rx.cond(is_selected, "1px solid #b8c7ff", "1px solid transparent"),
        _hover={"bg": rx.cond(is_selected, rx.cond(UISettingsState.theme == "dark", "#1e3a5f", "#eff4ff"), UISettingsState.muted_bg)},
    )


# ---------------------------------------------------------------------------
# PDF area with floating toolbar
# ---------------------------------------------------------------------------


def pdf_area() -> rx.Component:
    return rx.box(
        rx.cond(
            LibraryState.pdf_reader_url != "",
            rx.el.iframe(
                src=LibraryState.pdf_reader_url,
                style={
                    "border": "none",
                    "display": "block",
                    "width": "100%",
                    "height": "100%",
                },
            ),
            empty_state(),
        ),
        flex="1",
        min_width="0",
        min_height="0",
        height="100%",
        bg=UISettingsState.app_bg,
    )


def empty_state() -> rx.Component:
    return rx.vstack(
        rx.icon(tag="book_open", size=52, color="#c1c7d0"),
        rx.text("从左侧选择一篇论文", font_size="calc(var(--base-font) * 0.95)", color=UISettingsState.muted_text_color, font_weight="500"),
        rx.text(
            "也可以在左侧论文库导入新的 PDF",
            font_size="calc(var(--base-font) * 0.78)", color="#b0b8c4",
        ),
        spacing="3",
        align="center",
        justify="center",
        height="100%",
    )




# ---------------------------------------------------------------------------
# Shared styles for model tab
# ---------------------------------------------------------------------------

_SECTION_TITLE = dict(font_size="calc(var(--base-font) * 0.82)", font_weight="650", color=UISettingsState.text_color)
_SECTION_SUBTITLE = dict(font_size="calc(var(--base-font) * 0.72)", color=UISettingsState.muted_text_color)
_INPUT_STYLE = dict(
    font_size="calc(var(--base-font) * 0.72)",
    padding="4px 8px",
    border_radius="5px",
    border=f"1px solid {UISettingsState.border_color}",
    width="100%",
)
_ROW_STYLE = dict(
    padding="8px 10px",
    border_radius="6px",
    cursor="pointer",
    height="auto",
    display="flex",
)
_EDIT_AREA_STYLE = dict(
    padding="8px",
    border_radius="6px",
    border=f"1px solid {UISettingsState.border_color}",
    bg=UISettingsState.muted_bg,
)


def _edit_form(show_name: bool = False, show_delete: bool = False, on_save=None, on_delete=None) -> rx.Component:
    """Shared edit form for engine config fields."""
    return rx.vstack(
        rx.cond(
            show_name,
            rx.el.input(
                placeholder="引擎名称",
                value=LibraryState.edit_name,
                on_change=LibraryState.set_edit_name,
                **_INPUT_STYLE,
            ),
            rx.box(),
        ),
        rx.el.input(
            placeholder="API Key",
            value=LibraryState.edit_api_key,
            on_change=LibraryState.set_edit_api_key,
            **_INPUT_STYLE,
        ),
        rx.el.input(
            placeholder="Base URL",
            value=LibraryState.edit_base_url,
            on_change=LibraryState.set_edit_base_url,
            **_INPUT_STYLE,
        ),
        rx.el.input(
            placeholder="Model",
            value=LibraryState.edit_model,
            on_change=LibraryState.set_edit_model,
            **_INPUT_STYLE,
        ),
        rx.hstack(
            rx.button(
                "保存",
                on_click=on_save,
                variant="solid",
                size="1",
                bg="#2563eb",
                color="white",
                style={"font_size": "calc(var(--base-font) * 0.72)", "border_radius": "4px"},
            ),
            rx.button(
                "取消",
                on_click=LibraryState.cancel_edit_profile,
                variant="ghost",
                size="1",
                style={"font_size": "calc(var(--base-font) * 0.72)"},
            ),
            rx.cond(
                show_delete,
                rx.button(
                    "删除",
                    on_click=on_delete,
                    variant="ghost",
                    size="1",
                    color="red",
                    style={"font_size": "calc(var(--base-font) * 0.72)"},
                ),
                rx.box(),
            ),
            spacing="2",
            align="center",
        ),
        spacing="2",
        width="100%",
        **_EDIT_AREA_STYLE,
    )


def _profile_collapsed(profile: rx.Var[dict]) -> rx.Component:
    """Single profile row — collapsed view."""
    is_selected = profile["id"] == LibraryState.current_engine_id
    return rx.button(
        rx.hstack(
            rx.icon(
                tag="cpu", size=14,
                color=rx.cond(is_selected, "#2563eb", "#6b7280"),
            ),
            rx.vstack(
                rx.text(profile["name"], font_size="calc(var(--base-font) * 0.78)", font_weight="600", no_of_lines=1),
                rx.text(profile["model"], font_size="calc(var(--base-font) * 0.68)", color=UISettingsState.muted_text_color, no_of_lines=1),
                spacing="0",
                align_items="start",
                flex="1",
                min_width="0",
            ),
            rx.cond(
                is_selected,
                rx.icon(tag="check", size=14, color="#2563eb"),
                rx.box(),
            ),
            rx.button(
                rx.icon(tag="pencil", size=12, color=UISettingsState.muted_text_color),
                on_click=LibraryState.start_edit_profile(profile["id"]),
                variant="ghost",
                size="1",
                style={"padding": "2px", "min_width": "auto"},
            ),
            width="100%",
            align="center",
            spacing="2",
        ),
        on_click=LibraryState.select_engine(profile["id"]),
        variant="ghost",
        size="1",
        width="100%",
        bg=rx.cond(is_selected, rx.cond(UISettingsState.theme == "dark", "#1e3a5f", "#eff6ff"), "transparent"),
        border=rx.cond(is_selected, "1px solid #bfdbfe", "1px solid transparent"),
        **_ROW_STYLE,
    )


def _profile_item(profile: rx.Var[dict]) -> rx.Component:
    """Single profile — collapsed or expanded inline."""
    return rx.box(
        rx.cond(
            profile["id"] == LibraryState.editing_profile_id,
            _edit_form(
                show_name=True,
                show_delete=True,
                on_save=LibraryState.save_profile,
                on_delete=LibraryState.delete_profile(profile["id"]),
            ),
            _profile_collapsed(profile),
        ),
        width="100%",
    )


def _chat_profile_collapsed(profile: rx.Var[dict]) -> rx.Component:
    """Single chat profile row — collapsed view."""
    is_selected = profile["id"] == LibraryState.current_chat_engine_id
    return rx.button(
        rx.hstack(
            rx.icon(
                tag="cpu", size=14,
                color=rx.cond(is_selected, "#2563eb", "#6b7280"),
            ),
            rx.vstack(
                rx.text(profile["name"], font_size="calc(var(--base-font) * 0.78)", font_weight="600", no_of_lines=1),
                rx.text(profile["model"], font_size="calc(var(--base-font) * 0.68)", color=UISettingsState.muted_text_color, no_of_lines=1),
                spacing="0",
                align_items="start",
                flex="1",
                min_width="0",
            ),
            rx.cond(
                is_selected,
                rx.icon(tag="check", size=14, color="#2563eb"),
                rx.box(),
            ),
            rx.button(
                rx.icon(tag="pencil", size=12, color=UISettingsState.muted_text_color),
                on_click=LibraryState.start_edit_chat_profile(profile["id"]),
                variant="ghost",
                size="1",
                style={"padding": "2px", "min_width": "auto"},
            ),
            width="100%",
            align="center",
            spacing="2",
        ),
        on_click=LibraryState.select_chat_engine(profile["id"]),
        variant="ghost",
        size="1",
        width="100%",
        bg=rx.cond(is_selected, rx.cond(UISettingsState.theme == "dark", "#1e3a5f", "#eff6ff"), "transparent"),
        border=rx.cond(is_selected, "1px solid #bfdbfe", "1px solid transparent"),
        **_ROW_STYLE,
    )


def _chat_profile_item(profile: rx.Var[dict]) -> rx.Component:
    """Single chat profile — collapsed or expanded inline."""
    return rx.box(
        rx.cond(
            profile["id"] == LibraryState.editing_chat_profile_id,
            _edit_form(
                show_name=True,
                show_delete=True,
                on_save=LibraryState.save_chat_profile,
                on_delete=LibraryState.delete_chat_profile(profile["id"]),
            ),
            _chat_profile_collapsed(profile),
        ),
        width="100%",
    )


def _model_tab() -> rx.Component:
    """Model/engine settings tab content."""
    return rx.vstack(
        # ============================================================
        # Translation Engine Section
        # ============================================================
        rx.text("翻译引擎", **_SECTION_TITLE),
        rx.text("选择用于翻译的 AI 模型", **_SECTION_SUBTITLE),

        # Profile list (max 4 when collapsed)
        rx.foreach(
            LibraryState.visible_engine_profiles,
            _profile_item,
        ),

        # Expand/collapse toggle (when > 4 profiles)
        rx.cond(
            LibraryState.overflow_profile_count > 0,
            rx.cond(
                LibraryState.show_all_profiles,
                rx.button(
                    rx.hstack(
                        rx.text("收起", font_size="calc(var(--base-font) * 0.72)", color=UISettingsState.muted_text_color),
                        rx.icon(tag="chevron_up", size=12, color=UISettingsState.muted_text_color),
                        spacing="1",
                        align="center",
                    ),
                    on_click=LibraryState.toggle_show_all,
                    variant="ghost",
                    size="1",
                    width="100%",
                    style={"font_size": "calc(var(--base-font) * 0.72)", "border_radius": "4px"},
                ),
                rx.button(
                    rx.hstack(
                        rx.text(LibraryState.profile_overflow_label,
                            font_size="calc(var(--base-font) * 0.72)", color=UISettingsState.muted_text_color),
                        rx.icon(tag="chevron_down", size=12, color=UISettingsState.muted_text_color),
                        spacing="1",
                        align="center",
                    ),
                    on_click=LibraryState.toggle_show_all,
                    variant="ghost",
                    size="1",
                    width="100%",
                    style={"font_size": "calc(var(--base-font) * 0.72)", "border_radius": "4px"},
                ),
            ),
            rx.box(),
        ),

        # Add engine button
        rx.button(
            rx.hstack(
                rx.icon(tag="plus", size=13),
                rx.text("添加引擎", font_size="calc(var(--base-font) * 0.72)"),
                spacing="1",
                align="center",
            ),
            on_click=LibraryState.start_edit_profile("new"),
            variant="ghost",
            size="1",
            width="100%",
            style={"font_size": "calc(var(--base-font) * 0.72)", "border_radius": "4px", "color": "#2563eb"},
        ),

        # New profile edit form
        rx.cond(
            LibraryState.editing_profile_id == "new",
            _edit_form(
                show_name=True,
                show_delete=False,
                on_save=LibraryState.save_profile,
            ),
            rx.box(),
        ),

        rx.divider(margin="8px 0"),

        # ============================================================
        # Chat Engine Section
        # ============================================================
        rx.text("问答引擎", **_SECTION_TITLE),
        rx.text("选择用于论文问答的 AI 模型", **_SECTION_SUBTITLE),

        # Profile list (max 4 when collapsed)
        rx.foreach(
            LibraryState.visible_chat_engine_profiles,
            _chat_profile_item,
        ),

        # Expand/collapse toggle (when > 4 profiles)
        rx.cond(
            LibraryState.chat_overflow_profile_count > 0,
            rx.cond(
                LibraryState.chat_show_all_profiles,
                rx.button(
                    rx.hstack(
                        rx.text("收起", font_size="calc(var(--base-font) * 0.72)", color=UISettingsState.muted_text_color),
                        rx.icon(tag="chevron_up", size=12, color=UISettingsState.muted_text_color),
                        spacing="1",
                        align="center",
                    ),
                    on_click=LibraryState.toggle_chat_show_all,
                    variant="ghost",
                    size="1",
                    width="100%",
                    style={"font_size": "calc(var(--base-font) * 0.72)", "border_radius": "4px"},
                ),
                rx.button(
                    rx.hstack(
                        rx.text(LibraryState.chat_overflow_label,
                            font_size="calc(var(--base-font) * 0.72)", color=UISettingsState.muted_text_color),
                        rx.icon(tag="chevron_down", size=12, color=UISettingsState.muted_text_color),
                        spacing="1",
                        align="center",
                    ),
                    on_click=LibraryState.toggle_chat_show_all,
                    variant="ghost",
                    size="1",
                    width="100%",
                    style={"font_size": "calc(var(--base-font) * 0.72)", "border_radius": "4px"},
                ),
            ),
            rx.box(),
        ),

        # Add engine button
        rx.button(
            rx.hstack(
                rx.icon(tag="plus", size=13),
                rx.text("添加引擎", font_size="calc(var(--base-font) * 0.72)"),
                spacing="1",
                align="center",
            ),
            on_click=LibraryState.start_edit_chat_profile("new"),
            variant="ghost",
            size="1",
            width="100%",
            style={"font_size": "calc(var(--base-font) * 0.72)", "border_radius": "4px", "color": "#2563eb"},
        ),

        # New profile edit form
        rx.cond(
            LibraryState.editing_chat_profile_id == "new",
            _edit_form(
                show_name=True,
                show_delete=False,
                on_save=LibraryState.save_chat_profile,
            ),
            rx.box(),
        ),

        spacing="2",
        align_items="start",
        padding="12px",
        width="100%",
        height="100%",
        overflow_y="auto",
    )


def _folder_tree_item(folder: FolderItem) -> rx.Component:
    """A folder in the tree view with expandable papers."""
    is_expanded = LibraryState.expanded_folder == folder.name
    return rx.box(
        rx.cond(
            LibraryState.editing_folder_name == folder.name,
            rx.hstack(
                rx.input(
                    value=LibraryState.editing_folder_value,
                    on_change=LibraryState.set_editing_folder_value,
                    on_key_down=lambda key: rx.cond(
                        key == "Enter",
                        LibraryState.rename_folder,
                        rx.cond(key == "Escape", LibraryState.cancel_rename_folder, rx.noop()),
                    ),
                    size="1",
                    flex="1",
                    height="26px",
                ),
                rx.button("保存", size="1", variant="soft", color_scheme="blue", on_click=LibraryState.rename_folder, font_size="calc(var(--base-font) * 0.68)"),
                rx.button("取消", size="1", variant="ghost", color_scheme="gray", on_click=LibraryState.cancel_rename_folder, font_size="calc(var(--base-font) * 0.68)"),
                width="100%",
                spacing="1",
                align="center",
                padding="4px 2px",
            ),
            rx.hstack(
                rx.hstack(
                    rx.cond(
                        is_expanded,
                        rx.text("▼", font_size="11px", color=UISettingsState.muted_text_color),
                        rx.text("▶", font_size="11px", color=UISettingsState.muted_text_color),
                    ),
                    rx.icon(tag="folder", size=13, color="#eab308"),
                    rx.text(folder.name, font_size="calc(var(--base-font) * 0.74)", font_weight="600", color=UISettingsState.text_color, no_of_lines=1, flex="1", min_width="0", font_family="'Microsoft YaHei', sans-serif", text_align="left"),
                    rx.text(folder.count.to(str), font_size="calc(var(--base-font) * 0.64)", color=UISettingsState.muted_text_color, min_width="16px", text_align="right"),
                    on_click=LibraryState.toggle_folder(folder.name),
                    flex="1",
                    min_width="0",
                    spacing="2",
                    align="center",
                    cursor="pointer",
                ),
                rx.menu.root(
                    rx.menu.trigger(
                        rx.button(rx.icon(tag="ellipsis", size=15), size="1", variant="ghost", color_scheme="gray", title="更多操作"),
                    ),
                    rx.menu.content(
                        rx.menu.item(rx.icon(tag="pencil", size=14), "重命名", on_click=LibraryState.start_rename_folder(folder.name)),
                        rx.menu.item(rx.icon(tag="trash_2", size=14), "移到回收站", color="red", on_click=LibraryState.delete_folder(folder.name)),
                    ),
                    class_name="folder-actions",
                ),
                class_name="folder-row",
                width="100%",
                align="center",
                spacing="2",
                padding="5px 4px",
                border_radius="6px",
                _hover={"bg": UISettingsState.muted_bg},
            ),
        ),
        # Papers (shown when expanded)
        rx.cond(
            is_expanded,
            rx.box(
                rx.foreach(folder.papers, paper_item),
                padding_left="14px",
                width="100%",
                overflow_x="hidden",
            ),
            rx.box(),
        ),
        width="100%",
    )


def _library_tab() -> rx.Component:
    """Paper library tab content with folder tree."""
    return rx.vstack(
        rx.html(
            """
            <style>
              .folder-actions, .paper-actions {
                opacity: 0;
                width: 0;
                overflow: hidden;
                transition: opacity .12s ease, width .12s ease;
              }
              .folder-row:hover .folder-actions, .paper-row:hover .paper-actions {
                opacity: 1;
                width: 28px;
              }
            </style>
            """
        ),
        rx.hstack(
            rx.text("我的论文", font_size="calc(var(--base-font) * 0.82)", font_weight="700", color=UISettingsState.text_color),
            rx.spacer(),
            rx.upload(
                rx.button(
                    rx.icon(tag="upload", size=14),
                    "导入",
                    variant="soft",
                    color_scheme="blue",
                    size="1",
                    title="导入论文",
                    font_size="calc(var(--base-font) * 0.7)",
                ),
                accept={"application/pdf": [".pdf"]},
                max_files=10,
                on_drop=LibraryState.upload_papers,
                border="0",
                padding="0",
            ),
            rx.menu.root(
                rx.menu.trigger(
                    rx.button(rx.icon(tag="ellipsis", size=15), variant="ghost", color_scheme="gray", size="1", title="更多"),
                ),
                rx.menu.content(
                    rx.menu.item(rx.icon(tag="folder_plus", size=14), "新建文件夹", on_click=LibraryState.start_create_folder),
                    rx.menu.item(rx.icon(tag="folder_open", size=14), "打开本地目录", on_click=LibraryState.open_upload_dir),
                ),
            ),
            width="100%",
            align="center",
            spacing="1",
        ),
        rx.cond(
            LibraryState.creating_folder,
            rx.hstack(
                rx.input(
                    placeholder="文件夹名称",
                    size="1",
                    flex="1",
                    value=LibraryState.new_folder_name,
                    on_change=LibraryState.set_new_folder_name,
                    height="28px",
                ),
                rx.button(
                    "保存",
                    size="1",
                    variant="soft",
                    color_scheme="blue",
                    on_click=LibraryState.create_folder,
                    font_size="calc(var(--base-font) * 0.68)",
                ),
                rx.button(
                    "取消",
                    size="1",
                    variant="ghost",
                    color_scheme="gray",
                    on_click=LibraryState.cancel_create_folder,
                    font_size="calc(var(--base-font) * 0.68)",
                ),
                width="100%",
                align="center",
                spacing="1",
            ),
            rx.box(),
        ),
        rx.cond(
            LibraryState.file_status != "",
            rx.text(
                LibraryState.file_status,
                font_size="calc(var(--base-font) * 0.64)",
                color=UISettingsState.muted_text_color,
                no_of_lines=2,
                line_height="1.35",
                width="100%",
            ),
            rx.box(),
        ),
        # Folder tree
        rx.box(
            rx.foreach(LibraryState.folder_tree, _folder_tree_item),
            overflow_y="auto",
            overflow_x="hidden",
            flex="1",
            width="100%",
            min_width="0",
        ),
        spacing="2",
        align_items="start",
        padding="10px 10px 12px",
        width="100%",
        height="100%",
        overflow_y="hidden",
        overflow_x="hidden",
    )


def _chat_message(msg: rx.Var[dict]) -> rx.Component:
    """Render a single chat message with optional quote block."""
    is_user = msg["role"] == "user"
    has_quote = msg["quote"] != ""
    return rx.box(
        rx.cond(
            is_user,
            # User message: right-aligned, blue bubble
            rx.box(
                rx.cond(
                    has_quote,
                    rx.box(
                        rx.text(msg["quote"], font_size="calc(var(--base-font) * 0.72)", color="rgba(255,255,255,0.75)", line_height="1.5", no_of_lines=1, style={"overflow": "hidden", "text-overflow": "ellipsis", "white_space": "nowrap"}),
                        border_left="2px solid rgba(255,255,255,0.4)",
                        padding_left="6px",
                        margin_bottom="4px",
                    ),
                    rx.box(),
                ),
                rx.text(msg["content"], font_size="calc(var(--base-font) * 0.82)", color="white", line_height="1.6", word_break="break-word"),
                bg="#3b82f6",
                border_radius="12px 12px 2px 12px",
                padding="8px 12px",
                max_width="90%",
                margin_left="auto",
            ),
            # AI message: left-aligned, gray bubble
            rx.box(
                rx.text(msg["content"], font_size="calc(var(--base-font) * 0.82)", line_height="1.6", color=UISettingsState.text_color, word_break="break-word"),
                bg=UISettingsState.muted_bg,
                border_radius="12px 12px 12px 2px",
                padding="8px 12px",
                max_width="90%",
            ),
        ),
        width="100%",
    )


def _scope_btn(label: str, scope_value: str) -> rx.Component:
    """A single scope toggle button."""
    is_active = LibraryState.chat_scope == scope_value
    return rx.button(
        label,
        size="1",
        variant="ghost",
        on_click=LibraryState.set_chat_scope(scope_value),
        bg=rx.cond(is_active, rx.cond(UISettingsState.theme == "dark", "#1e3a5f", "#eff6ff"), "transparent"),
        color=rx.cond(is_active, "#2563eb", "#6b7280"),
        border=rx.cond(is_active, "1px solid #bfdbfe", "1px solid transparent"),
        font_size="calc(var(--base-font) * 0.72)",
        font_weight=rx.cond(is_active, "600", "400"),
        border_radius="6px",
        cursor="pointer",
    )


def _chat_tab() -> rx.Component:
    """Paper Q&A tab content with scope selector and message list."""
    return rx.vstack(
        rx.vstack(
            rx.hstack(
                rx.text("论文问答", font_size="calc(var(--base-font) * 1.05)", font_weight="700", color=UISettingsState.text_color),
                rx.spacer(),
                rx.button(
                    rx.icon(tag="plus", size=13),
                    "新问答",
                    size="1",
                    variant="ghost",
                    on_click=LibraryState.clear_chat,
                    font_size="calc(var(--base-font) * 0.7)",
                ),
                width="100%",
                align="center",
            ),
            rx.text("针对当前论文或选中文本提问", font_size="calc(var(--base-font) * 0.72)", color=UISettingsState.muted_text_color),
            spacing="1",
            align_items="start",
            width="100%",
        ),
        # Scope selector
        rx.hstack(
            rx.text("作用域", font_size="calc(var(--base-font) * 0.72)", color=UISettingsState.muted_text_color, font_weight="600"),
            rx.hstack(
                _scope_btn("选区", "selection"),
                _scope_btn("论文", "paper"),
                spacing="1",
            ),
            width="100%",
            align="center",
            justify="between",
            padding="0 2px",
        ),
        # Selected text reference card — moved into input area below
        # (see input area section)
        # Message list
        rx.box(
            rx.cond(
                LibraryState.chat_messages.length() == 0,
                rx.box(
                    rx.text("选中文本后可在此提问，或切换到全文模式。", font_size="calc(var(--base-font) * 0.76)", color=UISettingsState.muted_text_color, text_align="center", padding="40px 0"),
                    width="100%",
                ),
                rx.vstack(
                    rx.foreach(LibraryState.chat_messages, _chat_message),
                    spacing="3",
                    width="100%",
                ),
            ),
            overflow_y="auto",
            flex="1",
            width="100%",
            padding="4px",
        ),
        # Loading indicator
        rx.cond(
            LibraryState.chat_loading,
            rx.hstack(
                rx.text("思考中...", font_size="calc(var(--base-font) * 0.72)", color=UISettingsState.muted_text_color),
                spacing="2",
                align="center",
                padding="4px 0",
            ),
            rx.box(),
        ),
        # Input area — context indicator + question input
        rx.box(
            # Context indicator — shows what will be sent to the model
            rx.cond(
                LibraryState.selected_text != "",
                # Mode A: text selected → show reference quote
                rx.box(
                    rx.hstack(
                        rx.text(">", font_size="calc(var(--base-font) * 0.82)", color="#3b82f6", font_weight="700"),
                        rx.text(
                            LibraryState.preview_selected,
                            font_size="calc(var(--base-font) * 0.78)",
                            color=UISettingsState.text_color,
                            line_height="1.6",
                            flex="1",
                        ),
                        rx.button(rx.icon(tag="x", size=12), size="1", variant="ghost", color_scheme="gray", on_click=LibraryState.clear_selection, style={"cursor": "pointer", "padding": "0", "height": "auto", "min_width": "auto", "line_height": "1"}),
                        width="100%",
                        align="start",
                        spacing="2",
                    ),
                    border_left="3px solid #3b82f6",
                    bg=rx.cond(UISettingsState.theme == "dark", "#1a2744", "#f8faff"),
                    border_radius="6px",
                    padding="6px 10px",
                    width="100%",
                    margin_bottom="6px",
                ),
                rx.cond(
                    LibraryState.chat_scope == "paper",
                    # Paper scope, no selection
                    rx.hstack(
                        rx.icon(tag="book_open", size=12, color=UISettingsState.muted_text_color),
                        rx.text("全文模式", font_size="calc(var(--base-font) * 0.72)", color=UISettingsState.muted_text_color),
                        spacing="1",
                        align="center",
                        padding="4px 8px",
                        bg=UISettingsState.muted_bg,
                        border_radius="6px",
                        width="100%",
                        margin_bottom="6px",
                    ),
                    rx.box(),
                ),
            ),
            rx.el.form(
                rx.hstack(
                    rx.el.input(
                        placeholder="输入你的问题...",
                        value=LibraryState.chat_input,
                        on_change=LibraryState.set_chat_input,
                        flex="1",
                        size="1",
                        border_radius="8px",
                        border=f"1px solid {UISettingsState.border_color}",
                        padding="6px 10px",
                        font_size="calc(var(--base-font) * 0.82)",
                    ),
                    rx.button(
                        rx.icon(tag="send", size=14),
                        size="1",
                        type="submit",
                        disabled=LibraryState.chat_loading,
                        bg="#3b82f6",
                        color="white",
                    ),
                    width="100%",
                    spacing="2",
                    align="center",
                ),
                on_submit=LibraryState.send_chat,
                width="100%",
            ),
            width="100%",
        ),
        # Clear button
        rx.cond(
            LibraryState.chat_messages.length() > 0,
            rx.button(
                rx.icon(tag="trash_2", size=12),
                "清空问答",
                size="1",
                variant="ghost",
                color_scheme="gray",
                on_click=LibraryState.clear_chat,
                font_size="calc(var(--base-font) * 0.68)",
                width="100%",
            ),
            rx.box(),
        ),
        spacing="2",
        align_items="start",
        padding="12px",
        width="100%",
        height="100%",
    )


def _notes_tab() -> rx.Component:
    """Notes tab content."""
    return rx.box(
        rx.vstack(
            rx.vstack(
                rx.text(
                    "PDF 批注",
                    font_size="calc(var(--base-font) * 1.05)",
                    font_weight="700",
                    color=UISettingsState.text_color,
                ),
                rx.text(
                    "高亮、下划线、删除线和笔记",
                    font_size="calc(var(--base-font) * 0.72)",
                    color=UISettingsState.muted_text_color,
                ),
                spacing="1",
                align_items="start",
                width="100%",
                padding_bottom="4px",
            ),
            rx.foreach(LibraryState.annotations, annotation_item),
            spacing="2",
            width="100%",
            padding="12px",
        ),
        overflow_y="auto",
        width="100%",
        height="100%",
    )


def _translate_tab() -> rx.Component:
    """Translate tab — 原文 + 译文, with 取消固定 when pinned."""
    return rx.vstack(
        rx.cond(
            LibraryState.selected_text != "",
            rx.vstack(
                # Original text
                rx.hstack(
                    rx.text("原文", font_size="calc(var(--base-font) * 0.72)", color=UISettingsState.muted_text_color, font_weight="600"),
                    rx.spacer(),
                    rx.button(
                        rx.icon(tag="x", size=12), size="1", variant="ghost",
                        color_scheme="gray", on_click=LibraryState.clear_selection,
                    ),
                    width="100%", align="center",
                ),
                panel(
                    rx.text(LibraryState.selected_text, font_size="calc(var(--base-font) * 0.78)", color=UISettingsState.text_color, line_height="1.6"),
                    padding="8px", width="100%", bg=UISettingsState.muted_bg, max_height="120px", overflow_y="auto",
                ),
                # Loading
                rx.cond(
                    LibraryState.is_translating,
                    rx.hstack(rx.spinner(size="1"), rx.text("翻译中...", font_size="calc(var(--base-font) * 0.76)", color=UISettingsState.muted_text_color), spacing="2"),
                    rx.box(),
                ),
                # Translation result
                rx.cond(
                    LibraryState.translation_result != "",
                    rx.vstack(
                        rx.hstack(
                            rx.text("译文", font_size="calc(var(--base-font) * 0.72)", color=UISettingsState.muted_text_color, font_weight="600"),
                            rx.spacer(),
                            rx.button(
                                rx.icon(tag="pin_off", size=12),
                                "取消固定",
                                size="1",
                                variant="ghost",
                                color_scheme="red",
                                on_click=LibraryState.unpin_current,
                                font_size="calc(var(--base-font) * 0.68)",
                            ),
                            width="100%", align="center",
                        ),
                        panel(
                            rx.text(LibraryState.translation_result, font_size="calc(var(--base-font) * 0.78)", color=UISettingsState.text_color, line_height="1.6"),
                            padding="8px", width="100%", bg=rx.cond(UISettingsState.theme == "dark", "#1a2744", "#f0f7ff"), overflow_y="auto",
                        ),
                        rx.button(
                            rx.icon(tag="file_text", size=13),
                            "写入 PDF",
                            on_click=LibraryState.place_current_translation,
                            size="1",
                            variant="soft",
                            color_scheme="blue",
                            width="100%",
                            font_size="calc(var(--base-font) * 0.72)",
                        ),
                        spacing="1", width="100%",
                    ),
                    rx.box(),
                ),
                spacing="2", width="100%", align_items="start",
            ),
            rx.vstack(
                rx.icon(tag="languages", size=32, color="#d1d5db"),
                rx.text("选中文本后自动翻译", font_size="calc(var(--base-font) * 0.76)", color=UISettingsState.muted_text_color),
                rx.text("或通过工具栏翻译按钮悬浮显示", font_size="calc(var(--base-font) * 0.68)", color="#b0b7c3"),
                spacing="2", align="center", justify="center", flex="1", width="100%", padding_top="60px",
            ),
        ),
        spacing="2", align_items="start", padding="12px", width="100%", height="100%", overflow_y="auto",
    )


def _act_btn(icon: str, tab_id: str, title: str) -> rx.Component:
    """An activity bar icon button."""
    return rx.button(
        rx.icon(tag=icon, size=20),
        rx.text(title, font_size="10px"),
        on_click=LibraryState.set_right_tab(tab_id),
        variant="ghost",
        size="1",
        width="100%",
        style={
            "display": "flex",
            "flex_direction": "column",
            "align_items": "center",
            "justify_content": "center",
            "gap": "2px",
            "padding": "10px 0",
            "height": "auto",
            "border": "none",
            "background": "transparent",
            "cursor": "pointer",
        },
    )


def activity_bar() -> rx.Component:
    """Always-visible icon strip on the right edge."""
    return rx.box(
        _act_btn("circle_help", "chat", "问答"),
        _act_btn("cpu", "model", "模型"),
        _act_btn("languages", "translate", "翻译"),
        _act_btn("notebook_pen", "notes", "批注"),
        display="flex",
        flex_direction="column",
        width="48px",
        min_width="48px",
        height="100%",
        bg=UISettingsState.muted_bg,
        border_left=f"1px solid {UISettingsState.border_color}",
        align_items="center",
        padding_top="4px",
        spacing="0",
        flex_shrink="0",
    )


def right_content_panel() -> rx.Component:
    """Slide-in content panel next to the activity bar."""
    return rx.box(
        rx.cond(
            LibraryState.right_tab == "chat",
            _chat_tab(),
            rx.box(),
        ),
        rx.cond(
            LibraryState.right_tab == "notes",
            _notes_tab(),
            rx.box(),
        ),
        rx.cond(
            LibraryState.right_tab == "translate",
            _translate_tab(),
            rx.box(),
        ),
        rx.cond(
            LibraryState.right_tab == "model",
            _model_tab(),
            rx.box(),
        ),
        width="320px",
        min_width="320px",
        height="100%",
        bg=UISettingsState.surface_bg,
        border_left=f"1px solid {UISettingsState.border_color}",
        overflow="hidden",
        style={
            "transition": "margin-right 0.2s ease, opacity 0.2s ease",
            "pointer-events": rx.cond(LibraryState.right_open, "auto", "none"),
        },
        margin_right=rx.cond(LibraryState.right_open, "0px", "-320px"),
        opacity=rx.cond(LibraryState.right_open, "1", "0"),
        flex_shrink="0",
    )


def annotation_item(item) -> rx.Component:
    return panel(
        rx.hstack(
            rx.vstack(
                rx.text(item["kind"], font_size="calc(var(--base-font) * 0.68)", color="#2f5bea", font_weight="700"),
                rx.text(item["text"], font_size="calc(var(--base-font) * 0.75)", color=UISettingsState.text_color),
                rx.text(item["note"], font_size="calc(var(--base-font) * 0.72)", color=UISettingsState.muted_text_color),
                spacing="1",
                align_items="start",
                flex="1",
                min_width="0",
            ),
            rx.button(
                rx.icon(tag="trash-2", size=14),
                on_click=LibraryState.delete_annotation(item["id"]),
                variant="ghost",
                size="1",
                color=UISettingsState.muted_text_color,
                flex_shrink="0",
                _hover={"color": "#ef4444"},
            ),
            align_items="start",
            width="100%",
        ),
        padding="6px",
        width="100%",
    )
