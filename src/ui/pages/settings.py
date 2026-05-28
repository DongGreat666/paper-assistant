"""Settings and user profile page."""

import reflex as rx

from config import get_config, read_settings, write_settings
from src.ui.components.layout import app_shell, page_header, panel, small_label
from src.ui.state import UISettingsState

_cfg = get_config()
_sd = read_settings()


class SettingsState(rx.State):
    """Editable settings for the UI."""

    user_name: str = _sd.get("user_name", "研究者")
    role: str = _sd.get("role", "博士生 / 研究员")
    default_model: str = _sd.get("default_model") or _cfg.llm_model
    translate_model: str = _sd.get("translate_model") or _cfg.translate_model or _cfg.llm_model
    qa_model: str = _sd.get("qa_model") or _cfg.qa_model or _cfg.llm_model
    papers_dir: str = _sd.get("papers_dir") or str(_cfg.papers_dir)
    data_dir: str = _sd.get("data_dir") or str(_cfg.data_dir)
    status_message: str = ""

    # Reading preferences (persisted in settings.json)
    pref_show_chat_on_open: bool = _sd.get("pref_show_chat_on_open", True)
    pref_auto_translate: bool = _sd.get("pref_auto_translate", True)
    pref_auto_preview: bool = _sd.get("pref_auto_preview", True)
    pref_save_notes_to_paper_dir: bool = _sd.get("pref_save_notes_to_paper_dir", True)

    def set_user_name(self, value: str):
        self.user_name = value

    def set_role(self, value: str):
        self.role = value

    def set_default_model(self, value: str):
        self.default_model = value

    def set_translate_model(self, value: str):
        self.translate_model = value

    def set_qa_model(self, value: str):
        self.qa_model = value

    def set_papers_dir(self, value: str):
        self.papers_dir = value

    def set_data_dir(self, value: str):
        self.data_dir = value

    def toggle_pref_show_chat_on_open(self, value: bool):
        self.pref_show_chat_on_open = value

    def toggle_pref_auto_translate(self, value: bool):
        self.pref_auto_translate = value

    def toggle_pref_auto_preview(self, value: bool):
        self.pref_auto_preview = value

    def toggle_pref_save_notes_to_paper_dir(self, value: bool):
        self.pref_save_notes_to_paper_dir = value

    def save(self):
        write_settings({
            "user_name": self.user_name,
            "role": self.role,
            "default_model": self.default_model,
            "translate_model": self.translate_model,
            "qa_model": self.qa_model,
            "papers_dir": self.papers_dir,
            "data_dir": self.data_dir,
            "pref_show_chat_on_open": self.pref_show_chat_on_open,
            "pref_auto_translate": self.pref_auto_translate,
            "pref_auto_preview": self.pref_auto_preview,
            "pref_save_notes_to_paper_dir": self.pref_save_notes_to_paper_dir,
        })
        # Reload Config so model/path changes take effect immediately
        get_config().reload()
        self.status_message = "设置已保存，重启后仍然生效。"


def settings_page() -> rx.Component:
    return app_shell("/settings", content())


def content() -> rx.Component:
    return rx.vstack(
        page_header("设置与用户", "用户资料、模型选择、论文目录和阅读偏好集中放在这里。"),
        rx.grid(
            user_panel(),
            model_panel(),
            storage_panel(),
            appearance_panel(),
            preference_panel(),
            columns="repeat(2, minmax(0, 1fr))",
            spacing="4",
            width="100%",
            padding="1.25rem",
        ),
        rx.box(
            rx.hstack(
                rx.cond(SettingsState.status_message != "", rx.text(SettingsState.status_message, color="#2f6b3f", font_size="calc(var(--base-font) * 0.86)")),
                rx.spacer(),
                rx.button(rx.icon(tag="save", size=16), "保存设置", on_click=SettingsState.save),
                width="100%",
            ),
            padding="0 1.25rem 1.25rem",
            width="100%",
        ),
        spacing="0",
        width="100%",
    )


def user_panel() -> rx.Component:
    return panel(
        rx.vstack(
            section_title("用户", "你的身份和默认使用场景。"),
            form_input("显示名称", SettingsState.user_name, SettingsState.set_user_name),
            form_input("身份", SettingsState.role, SettingsState.set_role),
            rx.hstack(
                rx.avatar(fallback="研", size="4"),
                rx.vstack(
                    rx.text(SettingsState.user_name, font_size="calc(var(--base-font) * 0.95)", font_weight="750"),
                    rx.text(SettingsState.role, font_size="calc(var(--base-font) * 0.78)", color="#697386"),
                    spacing="1",
                    align_items="start",
                ),
                spacing="3",
                padding="0.75rem",
                bg="#f8fafc",
                border_radius="8px",
                width="100%",
            ),
            spacing="3",
            align_items="start",
        ),
        padding="1rem",
    )


def model_panel() -> rx.Component:
    return panel(
        rx.vstack(
            section_title("模型", "不同任务可以使用不同模型。"),
            form_input("默认模型", SettingsState.default_model, SettingsState.set_default_model),
            form_input("整篇翻译模型", SettingsState.translate_model, SettingsState.set_translate_model),
            form_input("论文问答模型", SettingsState.qa_model, SettingsState.set_qa_model),
            rx.text("API Key 和 Base URL 继续从项目根目录 .env 读取。", font_size="calc(var(--base-font) * 0.76)", color="#697386"),
            spacing="3",
            align_items="start",
        ),
        padding="1rem",
    )


def storage_panel() -> rx.Component:
    return panel(
        rx.vstack(
            section_title("存储", "论文文件、解析缓存、向量库和聊天记录的位置。"),
            form_input("论文目录", SettingsState.papers_dir, SettingsState.set_papers_dir),
            form_input("数据目录", SettingsState.data_dir, SettingsState.set_data_dir),
            rx.grid(
                storage_stat("解析缓存", "data/cache"),
                storage_stat("向量索引", "data/vector_db"),
                storage_stat("对话历史", "data/chat_history"),
                columns="repeat(3, minmax(0, 1fr))",
                spacing="2",
                width="100%",
            ),
            spacing="3",
            align_items="start",
        ),
        padding="1rem",
    )


def appearance_panel() -> rx.Component:
    return panel(
        rx.vstack(
            section_title("界面", "调整全局字体大小和页面主题。"),
            rx.vstack(
                small_label("字体大小"),
                rx.hstack(
                    rx.button(rx.icon(tag="minus", size=15), size="2", variant="soft", color_scheme="gray", on_click=UISettingsState.decrease_font),
                    rx.box(
                        rx.text(UISettingsState.font_size_css, font_size="calc(var(--base-font) * 1)", font_weight="750", text_align="center"),
                        min_width="68px",
                        padding="0.45rem 0.65rem",
                        border="1px solid #d0d7e2",
                        border_radius="8px",
                    ),
                    rx.button(rx.icon(tag="plus", size=15), size="2", variant="soft", color_scheme="gray", on_click=UISettingsState.increase_font),
                    spacing="2",
                    align="center",
                ),
                rx.text("会影响侧栏、聊天区、设置页和其他页面的基础字号。", font_size="calc(var(--base-font) * 0.76)", color="#697386"),
                spacing="2",
                align_items="start",
                width="100%",
            ),
            rx.vstack(
                small_label("页面主题"),
                rx.hstack(
                    theme_button("浅色", "light"),
                    theme_button("暖色", "warm"),
                    theme_button("深色", "dark"),
                    spacing="2",
                    wrap="wrap",
                ),
                spacing="2",
                align_items="start",
                width="100%",
            ),
            spacing="4",
            align_items="start",
        ),
        padding="1rem",
    )


def theme_button(label: str, value: str) -> rx.Component:
    return rx.button(
        label,
        size="2",
        variant=rx.cond(UISettingsState.theme == value, "solid", "soft"),
        color_scheme=rx.cond(UISettingsState.theme == value, "blue", "gray"),
        on_click=UISettingsState.set_theme(value),
    )


def preference_panel() -> rx.Component:
    return panel(
        rx.vstack(
            section_title("阅读偏好", "默认打开论文后的阅读和翻译行为。"),
            rx.checkbox(
                "打开论文后显示右侧大模型对话",
                checked=SettingsState.pref_show_chat_on_open,
                on_change=SettingsState.toggle_pref_show_chat_on_open,
            ),
            rx.checkbox(
                "划词后自动显示翻译浮层",
                checked=SettingsState.pref_auto_translate,
                on_change=SettingsState.toggle_pref_auto_translate,
            ),
            rx.checkbox(
                "整篇翻译完成后自动进入左右对照预览（即将推出）",
                checked=SettingsState.pref_auto_preview,
                on_change=SettingsState.toggle_pref_auto_preview,
                disabled=True,
            ),
            rx.checkbox(
                "保存批注和笔记到论文同级目录",
                checked=SettingsState.pref_save_notes_to_paper_dir,
                on_change=SettingsState.toggle_pref_save_notes_to_paper_dir,
            ),
            spacing="3",
            align_items="start",
        ),
        padding="1rem",
    )


def section_title(title: str, subtitle: str) -> rx.Component:
    return rx.vstack(
        rx.text(title, font_size="calc(var(--base-font) * 1)", font_weight="750"),
        rx.text(subtitle, font_size="calc(var(--base-font) * 0.78)", color="#697386"),
        spacing="1",
        align_items="start",
    )


def form_input(label: str, value, on_change) -> rx.Component:
    return rx.vstack(
        small_label(label),
        rx.input(value=value, on_change=on_change, width="100%", size="2"),
        spacing="1",
        width="100%",
        align_items="start",
    )


def storage_stat(label: str, path: str) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.text(label, font_size="calc(var(--base-font) * 0.75)", color="#697386"),
            rx.text(path, font_size="calc(var(--base-font) * 0.76)", font_weight="650"),
            spacing="1",
            align_items="start",
        ),
        padding="0.7rem",
        bg="#f8fafc",
        border="1px solid #edf0f3",
        border_radius="8px",
    )
