"""Shared engine configuration components.

Extracted from library.py and translate.py to reduce code duplication.
"""

import reflex as rx

from src.ui.components.layout import small_label
from src.ui.state import UISettingsState


def engine_field(
    label: str,
    value: rx.Var,
    on_change,
    input_type: str = "text",
    placeholder: str = "",
) -> rx.Component:
    """Render a single engine configuration field."""
    return rx.vstack(
        small_label(label),
        rx.input(
            value=value,
            on_change=on_change,
            type=input_type,
            placeholder=placeholder,
            width="100%",
            size="2",
        ),
        spacing="1",
        width="100%",
        align_items="start",
    )


def engine_status_badge(status: rx.Var[str]) -> rx.Component:
    """Render engine status badge (ok/fail/unchecked)."""
    return rx.cond(
        status == "ok",
        rx.box(
            rx.hstack(
                rx.icon(tag="circle", size=8, color="#22c55e"),
                rx.text(
                    "正常",
                    font_size="calc(var(--base-font) * 0.64)",
                    color="#16a34a",
                    font_weight="600",
                ),
                spacing="1",
                align="center",
            ),
            padding="0.1rem 0.45rem",
            bg="#f0fdf4",
            border_radius="9999px",
        ),
        rx.cond(
            status == "fail",
            rx.box(
                rx.hstack(
                    rx.icon(tag="circle", size=8, color="#ef4444"),
                    rx.text(
                        "异常",
                        font_size="calc(var(--base-font) * 0.64)",
                        color="#dc2626",
                        font_weight="600",
                    ),
                    spacing="1",
                    align="center",
                ),
                padding="0.1rem 0.45rem",
                bg="#fef2f2",
                border_radius="9999px",
            ),
            rx.box(
                rx.text(
                    "未检测",
                    font_size="calc(var(--base-font) * 0.64)",
                    color="#94a3b8",
                ),
                padding="0.1rem 0.45rem",
            ),
        ),
    )


def engine_action_buttons(
    profile_id: rx.Var[str],
    on_test,
    on_edit,
    on_delete,
) -> rx.Component:
    """Render engine action buttons (test/edit/delete)."""
    return rx.hstack(
        rx.spacer(),
        rx.button(
            rx.icon(tag="activity", size=12),
            size="1",
            variant="ghost",
            color_scheme="gray",
            on_click=on_test(profile_id),
            _hover={"bg": "#f1f5f9"},
        ),
        rx.button(
            rx.icon(tag="pencil", size=12),
            size="1",
            variant="ghost",
            color_scheme="gray",
            on_click=on_edit(profile_id),
            _hover={"bg": "#f1f5f9"},
        ),
        rx.button(
            rx.icon(tag="trash_2", size=12),
            size="1",
            variant="ghost",
            color_scheme="gray",
            on_click=on_delete(profile_id),
            _hover={"bg": "#fef2f2", "color": "#dc2626"},
        ),
        spacing="1",
        align="center",
        padding_left="24px",
    )


def engine_count_badge(count: rx.Var[int]) -> rx.Component:
    """Render engine count badge."""
    return rx.cond(
        count > 0,
        rx.box(
            rx.text(
                count,
                font_size="calc(var(--base-font) * 0.62)",
                font_weight="700",
                color="white",
            ),
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
    )
