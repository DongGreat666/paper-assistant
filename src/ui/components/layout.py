"""Shared application shell for the paper assistant workspace."""

import reflex as rx

from config import get_config
from src.ui.state import UISettingsState


NAV_ITEMS = [
    ("message_square", "聊天", "/"),
    ("library", "我的论文", "/library"),
    ("languages", "论文翻译", "/translate"),
    ("settings", "设置", "/settings"),
]


def app_shell(
    active: str,
    content: rx.Component,
    aside: rx.Component | None = None,
    sidebar_body: rx.Component | None = None,
    chats: list[dict] | None = None,
    on_new_chat=None,
    on_chat_click=None,
    on_chat_delete=None,
    active_chat_id: str = "",
) -> rx.Component:
    """Render the three-column workspace layout."""
    children = [
        sidebar(active, chats, on_new_chat, on_chat_click, on_chat_delete, active_chat_id, sidebar_body),
        rx.box(content, flex="1", min_width="0", height="100vh", overflow_y="auto"),
    ]
    if aside is not None:
        children.append(rx.box(aside, width="320px", min_width="320px", height="100vh"))

    return rx.box(
        rx.html(
            "<style>:root { --base-font: "
            + UISettingsState.base_font_css
            + "; }</style>"
        ),
        rx.hstack(
            *children,
            spacing="0",
            width="100%",
            align="stretch",
        ),
        width="100%",
        min_height="100vh",
        bg=UISettingsState.app_bg,
        color=UISettingsState.text_color,
        font_family="Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    )


def sidebar(
    active: str,
    chats=None,
    on_new_chat=None,
    on_chat_click=None,
    on_chat_delete=None,
    active_chat_id=None,
    body: rx.Component | None = None,
) -> rx.Component:
    sidebar_width = "300px" if body is not None else "260px"
    expanded_width = sidebar_width
    collapsed_width = "18px"
    nav_items = NAV_ITEMS
    # Build chat list only when chats Var is provided (home page)
    if body is not None:
        primary_action = rx.box()
        sidebar_main = rx.box(
            body,
            flex="1",
            min_height="0",
            overflow="hidden",
            width="100%",
        )
    elif chats is not None:
        primary_action = rx.box()
        chat_items = rx.box(
            rx.hstack(
                rx.text("聊天", font_size="calc(var(--base-font) * 0.82)", font_weight="700", color=UISettingsState.text_color),
                rx.spacer(),
                rx.button(
                    rx.icon(tag="message_square_plus", size=14),
                    "新建",
                    size="1",
                    variant="soft",
                    color_scheme="gray",
                    on_click=on_new_chat if on_new_chat is not None else rx.redirect("/"),
                    font_size="calc(var(--base-font) * 0.7)",
                ),
                width="100%",
                align="center",
            ),
            rx.text(
                "聊天记录",
                font_size="calc(var(--base-font) * 0.66)",
                color=UISettingsState.muted_text_color,
                line_height="1.35",
                margin_top="0.35rem",
                margin_bottom="0.65rem",
            ),
            rx.vstack(
                rx.foreach(
                    chats,
                    lambda c: chat_entry(c, on_chat_click, on_chat_delete, active_chat_id),
                ),
                spacing="1",
                width="100%",
                align_items="stretch",
            ),
            padding="10px 10px 12px",
            width="100%",
            height="100%",
            overflow_y="auto",
            overflow_x="hidden",
        )
        sidebar_main = rx.box(
            chat_items,
            flex="1",
            overflow_y="auto",
            width="100%",
        )
    else:
        primary_action = rx.box(
            rx.link(
                rx.button(
                    rx.icon(tag="book_open", size=16),
                    "打开论文库",
                    width="100%",
                    variant="soft",
                    color_scheme="gray",
                    justify_content="start",
                ),
                href="/library",
                width="100%",
                text_decoration="none",
                _hover={"text_decoration": "none"},
            ),
            padding="0.75rem",
            width="100%",
        )
        chat_items = rx.box()
        sidebar_main = rx.box(
            chat_items,
            flex="1",
            overflow_y="auto",
            width="100%",
        )

    sidebar_content = rx.vstack(
        rx.hstack(
            rx.box(
                rx.icon(tag="book_open_text", size=22, color="white"),
                width="36px",
                height="36px",
                display="flex",
                align_items="center",
                justify_content="center",
                bg=rx.cond(UISettingsState.theme == "dark", "#31415f", "#243b53"),
                border_radius="8px",
            ),
            rx.vstack(
                rx.text("Paper Assistant", font_size="calc(var(--base-font) * 0.96)", font_weight="700", line_height="1.1"),
                rx.text("学术阅读工作台", font_size="calc(var(--base-font) * 0.74)", color=UISettingsState.muted_text_color),
                spacing="1",
                align_items="start",
            ),
            spacing="3",
            padding="1.1rem 1rem",
            width="100%",
        ),
        rx.divider(border_color=UISettingsState.border_color),
        primary_action,
        sidebar_main,
        rx.vstack(
            *[nav_item(icon, label, href, active == href) for icon, label, href in nav_items],
            spacing="1",
            padding="0.85rem 0.75rem 0.75rem",
            width="100%",
        ),
        rx.vstack(
            rx.text("本地论文目录", font_size="calc(var(--base-font) * 0.72)", color="#8a94a6"),
            rx.text(str(get_config().papers_dir), font_size="calc(var(--base-font) * 0.78)", color="#3b4556", font_weight="600"),
            spacing="1",
            align_items="start",
            padding="1rem",
            width="100%",
        ),
        width="100%",
        height="100vh",
        opacity=rx.cond(UISettingsState.sidebar_collapsed, "0", "1"),
        pointer_events=rx.cond(UISettingsState.sidebar_collapsed, "none", "auto"),
        transition="opacity 0.12s ease",
    )

    return rx.box(
        sidebar_content,
        rx.button(
            rx.icon(tag=rx.cond(UISettingsState.sidebar_collapsed, "panel_left_open", "panel_left_close"), size=14),
            on_click=UISettingsState.toggle_sidebar,
            variant="ghost",
            color_scheme="gray",
            size="1",
            title=rx.cond(UISettingsState.sidebar_collapsed, "展开侧栏", "折叠侧栏"),
            position="absolute",
            top="50%",
            right="-13px",
            transform="translateY(-50%)",
            width="26px",
            height="48px",
            min_width="26px",
            padding="0",
            bg=UISettingsState.surface_bg,
            border="1px solid",
            border_color=UISettingsState.border_color,
            border_radius="999px",
            box_shadow="0 2px 8px rgba(16, 24, 40, 0.08)",
            z_index="20",
        ),
        width=rx.cond(UISettingsState.sidebar_collapsed, collapsed_width, expanded_width),
        min_width=rx.cond(UISettingsState.sidebar_collapsed, collapsed_width, expanded_width),
        bg=UISettingsState.surface_bg,
        border_right="1px solid",
        border_color=UISettingsState.border_color,
        position="relative",
        overflow="visible",
        transition="width 0.18s ease, min-width 0.18s ease",
    )


def chat_entry(chat, on_click, on_delete, active_id) -> rx.Component:
    cid = chat["id"]
    is_active = cid == active_id
    return rx.hstack(
        rx.icon(tag="message_square", size=15, color=UISettingsState.muted_text_color),
        rx.vstack(
            rx.text(
                chat["title"],
                font_size="calc(var(--base-font) * 0.82)",
                color=rx.cond(is_active, UISettingsState.text_color, UISettingsState.muted_text_color),
                font_weight=rx.cond(is_active, "650", "400"),
                no_of_lines=1,
            ),
            rx.hstack(
                rx.cond(
                    chat["paper"] != "",
                    rx.text(chat["paper"], font_size="calc(var(--base-font) * 0.67)", color="#8a94a6", no_of_lines=1),
                    rx.box(),
                ),
                rx.cond(
                    chat["engine"] != "",
                    rx.text(chat["engine"], font_size="calc(var(--base-font) * 0.6)", color="#a0aec0", no_of_lines=1),
                    rx.box(),
                ),
                rx.text(chat["time_label"], font_size="calc(var(--base-font) * 0.67)", color="#8a94a6", no_of_lines=1),
                spacing="2",
            ),
            spacing="0",
            align_items="start",
            flex="1",
            min_width="0",
        ),
        rx.box(
            rx.icon(
                tag="trash_2",
                size=14,
                color="#c9cdd4",
                cursor="pointer",
                _hover={"color": "#ef4444"},
            ),
            on_click=on_delete(cid),
            z_index="1",
        ),
        spacing="2",
        padding="0.58rem 0.6rem",
        border_radius="7px",
        bg=rx.cond(is_active, UISettingsState.muted_bg, "transparent"),
        cursor="pointer",
        _hover={"bg": UISettingsState.muted_bg},
        on_click=on_click(cid),
        align="center",
        width="100%",
    )


def nav_item(icon: str, label: str, href: str, active: bool) -> rx.Component:
    return rx.link(
        rx.hstack(
            rx.icon(tag=icon, size=18),
            rx.text(label, font_size="calc(var(--base-font) * 0.9)", font_weight="650" if active else "500"),
            spacing="3",
            align="center",
            padding="0.68rem 0.75rem",
            border_radius="8px",
            bg=UISettingsState.muted_bg if active else "transparent",
            color=UISettingsState.text_color if active else UISettingsState.muted_text_color,
            width="100%",
        ),
        href=href,
        width="100%",
        text_decoration="none",
        _hover={"text_decoration": "none"},
    )


def page_header(title: str, subtitle: str, action: rx.Component | None = None) -> rx.Component:
    children = [
        rx.vstack(
            rx.text(title, font_size="calc(var(--base-font) * 1.55)", font_weight="750", line_height="1.15"),
            rx.text(subtitle, font_size="calc(var(--base-font) * 0.9)", color=UISettingsState.muted_text_color),
            spacing="2",
            align_items="start",
        ),
        rx.spacer(),
    ]
    if action is not None:
        children.append(action)

    return rx.hstack(
        *children,
        width="100%",
        padding="1.25rem 1.5rem",
        bg=UISettingsState.surface_bg,
        border_bottom="1px solid",
        border_color=UISettingsState.border_color,
        align="center",
    )


def panel(*children: rx.Component, **props) -> rx.Component:
    defaults = {
        "bg": UISettingsState.surface_bg,
        "border": "1px solid",
        "border_color": UISettingsState.border_color,
        "border_radius": "8px",
        "box_shadow": "0 1px 2px rgba(16, 24, 40, 0.04)",
    }
    defaults.update(props)
    return rx.box(
        *children,
        **defaults,
    )


def small_label(text: str) -> rx.Component:
    return rx.text(text, font_size="calc(var(--base-font) * 0.75)", color=UISettingsState.muted_text_color, font_weight="650")
