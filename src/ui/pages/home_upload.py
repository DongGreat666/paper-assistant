"""Upload controls and file status UI for the home chat page."""

import reflex as rx

from src.ui.pages.home_state import HomeState
from src.ui.state import UISettingsState


def current_file_chip() -> rx.Component:
    return rx.hstack(
        rx.icon(
            tag=rx.cond(HomeState.paper_ready, "file_check_2", rx.cond(HomeState.is_preparing, "loader_circle", "file_text")),
            size=16,
            color=rx.cond(HomeState.paper_ready, "#16a34a", UISettingsState.muted_text_color),
        ),
        rx.text(HomeState.file_info, font_size="calc(var(--base-font) * 0.78)", color="#3b4556", font_weight="600"),
        rx.cond(
            HomeState.paper_ready,
            rx.text("可问答", font_size="calc(var(--base-font) * 0.72)", color="#16a34a"),
            rx.text(rx.cond(HomeState.is_preparing, "准备中", "仅已保存"), font_size="calc(var(--base-font) * 0.72)", color="#8a94a6"),
        ),
        spacing="2",
        padding="0.45rem 0.65rem",
        border="1px solid",
        border_color=UISettingsState.border_color,
        border_radius="8px",
        bg=UISettingsState.surface_bg,
        box_shadow="0 1px 2px rgba(16, 24, 40, 0.04)",
    )


def upload_button() -> rx.Component:
    return rx.upload(
        rx.button(
            rx.icon(tag="paperclip", size=17),
            rx.cond(HomeState.is_preparing, "准备中...", "上传文件"),
            variant="soft",
            color_scheme="gray",
            size="2",
            disabled=HomeState.is_preparing,
            type="button",
        ),
        accept={
            "application/pdf": [".pdf"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
            "application/msword": [".doc"],
            "text/markdown": [".md"],
            "text/plain": [".txt", ".md"],
        },
        max_files=1,
        on_drop=HomeState.handle_upload,
        border="0",
        padding="0",
    )
