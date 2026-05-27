"""Chat layout and message composer for the home page."""

import reflex as rx

from src.ui.pages.home_model_panel import model_settings_panel
from src.ui.pages.home_state import HomeState
from src.ui.pages.home_upload import upload_button
from src.ui.state import UISettingsState


def main_content() -> rx.Component:
    return rx.box(
        top_bar(),
        chat_workspace(),
        width="100%",
        height="100vh",
        bg=UISettingsState.app_bg,
        overflow="hidden",
    )


def top_bar() -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.text("Paper Assistant", font_size="calc(var(--base-font) * 0.98)", font_weight="720", line_height="1.1"),
            rx.text(
                rx.cond(HomeState.model_auto, "当前模型：自动", f"当前模型：{HomeState.engine_name}"),
                font_size="calc(var(--base-font) * 0.74)",
                color=UISettingsState.muted_text_color,
            ),
            spacing="1",
            align_items="start",
        ),
        rx.spacer(),
        rx.cond(
            HomeState.file_info != "",
            rx.hstack(
                rx.icon(tag="file_text", size=15, color=UISettingsState.muted_text_color),
                rx.text(HomeState.file_name, font_size="calc(var(--base-font) * 0.78)", color=UISettingsState.text_color, no_of_lines=1),
                spacing="2",
                max_width="360px",
            ),
            rx.box(),
        ),
        width="100%",
        height="56px",
        padding="0.65rem 1.25rem",
        bg=rx.cond(UISettingsState.theme == "dark", "rgba(17, 24, 39, 0.86)", "rgba(251, 251, 250, 0.86)"),
        backdrop_filter="blur(10px)",
        border_bottom="1px solid",
        border_color=UISettingsState.border_color,
        align="center",
    )


def chat_workspace() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.box(
                rx.vstack(
                    rx.cond(
                        HomeState.messages.length() > 0,
                        messages_panel(),
                        empty_state(),
                    ),
                    spacing="4",
                    width="100%",
                    max_width="1180px",
                    margin="0 auto",
                    padding="2rem 1.25rem 9.5rem",
                ),
                flex="1",
                overflow_y="auto",
                width="100%",
            ),
            rx.box(
                chat_input(),
                width="100%",
                max_width="1180px",
                margin="0 auto",
                padding="0 1.25rem 1.2rem",
                position="absolute",
                left="0",
                right="0",
                bottom="0",
                bg=rx.cond(
                    UISettingsState.theme == "dark",
                    "linear-gradient(180deg, rgba(17,24,39,0), #111827 28%)",
                    rx.cond(
                        UISettingsState.theme == "warm",
                        "linear-gradient(180deg, rgba(247,242,234,0), #f7f2ea 28%)",
                        "linear-gradient(180deg, rgba(251,251,250,0), #fbfbfa 28%)",
                    ),
                ),
            ),
            spacing="0",
            width="100%",
            height="calc(100vh - 56px)",
            align_items="stretch",
            position="relative",
        ),
        bg=UISettingsState.app_bg,
        width="100%",
    )


def empty_state() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.text(
                "今天想读什么？",
                font_size="calc(var(--base-font) * 1.45)",
                font_weight="760",
                text_align="center",
            ),
            rx.text(
                "上传 PDF、Word 或 Markdown 文件后提问，按 Enter 发送。",
                font_size="calc(var(--base-font) * 0.92)",
                color=UISettingsState.muted_text_color,
                text_align="center",
                max_width="640px",
            ),
            spacing="3",
            align="center",
        ),
        min_height="46vh",
        width="100%",
    )


def messages_panel() -> rx.Component:
    return rx.vstack(
        rx.foreach(HomeState.messages, message_bubble),
        spacing="4",
        width="100%",
        align_items="stretch",
    )


def message_bubble(message) -> rx.Component:
    is_user = message["role"] == "user"
    return rx.hstack(
        rx.cond(is_user, rx.spacer(), rx.box()),
        rx.cond(
            is_user,
            rx.box(
                rx.text(
                    message["content"],
                    white_space="pre-wrap",
                    font_size="calc(var(--base-font) * 0.9)",
                    line_height="1.65",
                    color="white",
                ),
                max_width="72%",
                padding="0.65rem 0.85rem",
                bg="#1788f2",
                border="1px solid #1788f2",
                border_radius="12px",
            ),
            rx.box(
                rx.markdown(
                    message["content"],
                    component_map={
                        "p": lambda text: rx.text(text, font_size="calc(var(--base-font) * 0.95)", line_height="1.8", color=UISettingsState.text_color, margin_bottom="0.7rem"),
                    },
                ),
                max_width="920px",
                padding="0.25rem 0",
                color=UISettingsState.text_color,
            ),
        ),
        rx.cond(is_user, rx.box(), rx.spacer()),
        width="100%",
    )


def chat_input() -> rx.Component:
    return rx.box(
        rx.form(
            rx.vstack(
                rx.el.input(
                    id="chat-composer-input",
                    placeholder="问论文任何问题...",
                    value=HomeState.input_text,
                    on_change=HomeState.set_input,
                    type="text",
                    width="100%",
                    border="0",
                    bg="transparent",
                    padding="1rem 1rem 0.75rem",
                    outline="none",
                    font_size="inherit",
                    _focus={"box_shadow": "none"},
                ),
                spacing="0",
                width="100%",
            ),
            on_submit=HomeState.submit,
        ),
        rx.hstack(
            upload_button(),
            rx.button(
                rx.icon(tag="workflow", size=15),
                rx.cond(HomeState.model_auto, "自动", HomeState.engine_name),
                rx.icon(tag="chevron_down", size=14),
                size="2",
                variant="soft",
                color_scheme="gray",
                type="button",
                on_click=HomeState.toggle_model_settings,
            ),
            rx.cond(
                HomeState.model_auto,
                rx.text("自动模型", font_size="calc(var(--base-font) * 0.74)", color=UISettingsState.muted_text_color),
                rx.text("自定义", font_size="calc(var(--base-font) * 0.74)", color=UISettingsState.muted_text_color),
            ),
            rx.spacer(),
            rx.button(
                rx.icon(tag=rx.cond(HomeState.is_chatting, "loader_circle", "send"), size=17),
                rx.cond(HomeState.is_chatting, "生成中", "发送"),
                id="chat-composer-submit",
                size="2",
                disabled=HomeState.is_chatting | HomeState.is_preparing,
                on_click=HomeState.submit,
            ),
            width="100%",
            align="center",
            padding="0.35rem 1rem 0.65rem",
            spacing="2",
        ),
        rx.cond(
            HomeState.model_settings_open,
            model_settings_panel(),
            rx.box(),
        ),
        width="100%",
        bg=UISettingsState.surface_bg,
        border="1px solid",
        border_color=UISettingsState.border_color,
        border_radius="16px",
        box_shadow="0 12px 30px rgba(16, 24, 40, 0.12)",
    )
