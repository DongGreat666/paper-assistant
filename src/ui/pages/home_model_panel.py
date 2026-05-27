"""Model configuration panel for the home chat page."""

import reflex as rx

from src.ui.components.layout import small_label
from src.ui.pages.home_state import HomeState
from src.ui.state import UISettingsState

def model_settings_panel() -> rx.Component:
    return rx.box(
        rx.vstack(
            # Header with auto mode toggle
            rx.hstack(
                rx.vstack(
                    rx.hstack(
                        rx.text("自动模式", font_size="calc(var(--base-font) * 0.9)", font_weight="700"),
                        rx.switch(checked=HomeState.model_auto, on_change=HomeState.toggle_model_auto),
                        spacing="2",
                        align="center",
                    ),
                    rx.text(
                        rx.cond(HomeState.model_auto, "将使用 .env 中的问答模型。", "使用自定义配置的模型。"),
                        font_size="calc(var(--base-font) * 0.74)",
                        color=UISettingsState.muted_text_color,
                    ),
                    spacing="1",
                    align_items="start",
                ),
                rx.spacer(),
                rx.icon(
                    tag="x",
                    size=16,
                    cursor="pointer",
                    color=UISettingsState.muted_text_color,
                    _hover={"color": UISettingsState.text_color},
                    on_click=HomeState.toggle_model_settings,
                ),
                width="100%",
                align="center",
            ),
            rx.divider(border_color=UISettingsState.border_color, margin="0.25rem 0"),
            # Add engine button
            rx.button(
                rx.icon(tag="plus", size=14),
                "配置自定义模型",
                size="1",
                variant="soft",
                color_scheme="gray",
                on_click=HomeState.start_new_engine,
                width="100%",
                justify_content="start",
            ),
            # Engine list (only when manual mode)
            rx.cond(
                ~HomeState.model_auto,
                rx.vstack(
                    rx.hstack(
                        rx.text("已保存的模型", font_size="calc(var(--base-font) * 0.76)", color=UISettingsState.muted_text_color, font_weight="650"),
                        rx.cond(
                            HomeState.saved_engines.length() > 0,
                            rx.box(
                                rx.text(HomeState.saved_engines.length(), font_size="calc(var(--base-font) * 0.62)", font_weight="700", color="white"),
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
                    rx.vstack(
                        rx.cond(
                            HomeState.saved_engines.length() > 0,
                            rx.vstack(
                                rx.foreach(HomeState.saved_engines, engine_card),
                                spacing="2",
                                width="100%",
                                align_items="stretch",
                            ),
                            rx.box(
                                rx.vstack(
                                    rx.icon(tag="server", size=22, color="#cbd5e1"),
                                    rx.text("暂无配置", font_size="calc(var(--base-font) * 0.78)", color="#94a3b8", font_weight="500"),
                                    spacing="1",
                                    align="center",
                                    padding="1.2rem 0",
                                ),
                                width="100%",
                            ),
                        ),
                        spacing="2",
                        width="100%",
                        align_items="stretch",
                    ),
                    spacing="2",
                    width="100%",
                    align_items="start",
                ),
                rx.box(),
            ),
            # Engine form
            rx.cond(HomeState.editing_engine_id != "", engine_form(), rx.box()),
            spacing="3",
            align_items="start",
            width="100%",
        ),
        margin="0.1rem 0 0.75rem",
        padding="0.85rem",
        border="1px solid",
        border_color=UISettingsState.border_color,
        border_radius="10px",
        bg=UISettingsState.surface_bg,
        box_shadow="0 8px 24px rgba(16, 24, 40, 0.1)",
        max_height="55vh",
        overflow_y="auto",
    )


def engine_card(profile) -> rx.Component:
    is_selected = HomeState.selected_engine_id == profile["id"]
    is_editing = HomeState.editing_engine_id == profile["id"]
    return rx.box(
        rx.hstack(
            rx.box(
                width="3px",
                align_self="stretch",
                bg=rx.cond(is_selected, "#2f5bea", "transparent"),
                border_radius="999px",
            ),
            rx.icon(
                tag=rx.cond(is_selected, "check_circle", "server"),
                size=16,
                color=rx.cond(is_selected, "#2f5bea", UISettingsState.muted_text_color),
            ),
            rx.vstack(
                rx.hstack(
                    rx.text(
                        profile["name"],
                        font_size="calc(var(--base-font) * 0.8)",
                        font_weight=rx.cond(is_selected, "720", "620"),
                        color=UISettingsState.text_color,
                        no_of_lines=1,
                    ),
                    rx.box(
                        rx.text(profile["model"], font_size="calc(var(--base-font) * 0.6)", font_weight="600", color="#475569", no_of_lines=1),
                        padding="0.08rem 0.35rem",
                        bg="#f1f5f9",
                        border_radius="4px",
                        border="1px solid #e2e8f0",
                        white_space="nowrap",
                    ),
                    spacing="2",
                    align="center",
                    wrap="wrap",
                    width="100%",
                ),
                rx.hstack(
                    rx.cond(
                        profile["status"] == "ok",
                        rx.text("正常", font_size="calc(var(--base-font) * 0.62)", color="#16a34a", font_weight="600"),
                        rx.cond(
                            profile["status"] == "fail",
                            rx.text("异常", font_size="calc(var(--base-font) * 0.62)", color="#dc2626", font_weight="600"),
                            rx.box(),
                        ),
                    ),
                    rx.cond(
                        profile["api_key"] != "",
                        rx.text("Key已配置", font_size="calc(var(--base-font) * 0.62)", color="#94a3b8"),
                        rx.text("未配置 Key", font_size="calc(var(--base-font) * 0.62)", color="#cbd5e1"),
                    ),
                    spacing="2",
                    align="center",
                ),
                spacing="1",
                align_items="start",
                flex="1",
                min_width="0",
                on_click=HomeState.select_engine(profile["id"]),
                cursor="pointer",
            ),
            rx.menu.root(
                rx.menu.trigger(
                    rx.button(rx.icon(tag="ellipsis", size=15), size="1", variant="ghost", color_scheme="gray", title="更多操作"),
                ),
                rx.menu.content(
                    rx.menu.item(rx.icon(tag="check", size=14), "设为当前模型", on_click=HomeState.select_engine(profile["id"])),
                    rx.menu.item(rx.icon(tag="activity", size=14), "测试连接", on_click=HomeState.test_engine(profile["id"])),
                    rx.menu.item(rx.icon(tag="pencil", size=14), "编辑", on_click=HomeState.start_edit_engine(profile["id"])),
                    rx.menu.item(rx.icon(tag="trash_2", size=14), "删除", color="red", on_click=HomeState.delete_engine(profile["id"])),
                ),
            ),
            spacing="2",
            align="center",
            width="100%",
        ),
        padding="0.55rem 0.65rem",
        border_radius="8px",
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
            "0 1px 3px rgba(47, 91, 234, 0.1)",
            "none",
        ),
        _hover={"box_shadow": "0 2px 6px rgba(0, 0, 0, 0.06)"},
        transition="all 0.15s ease",
        width="100%",
    )


def engine_form() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(
                    tag=rx.cond(HomeState.editing_engine_id == "__new__", "plus_circle", "settings"),
                    size=15,
                    color="#2f5bea",
                ),
                rx.text(
                    rx.cond(HomeState.editing_engine_id == "__new__", "添加新模型", "编辑模型"),
                    font_size="calc(var(--base-font) * 0.9)",
                    font_weight="700",
                ),
                rx.spacer(),
                rx.button(
                    rx.icon(tag="x", size=12),
                    size="1",
                    variant="ghost",
                    color_scheme="gray",
                    on_click=HomeState.cancel_edit,
                ),
                width="100%",
                align="center",
            ),
            rx.divider(border_color="#e5e7eb", margin="0.15rem 0"),
            _field("名称", HomeState.engine_name, HomeState.set_engine_name, "text", "论文问答模型"),
            _field("API Key", HomeState.engine_api_key, HomeState.set_engine_api_key, "password", "sk-..."),
            _field("Base URL", HomeState.engine_base_url, HomeState.set_engine_base_url, "text", "https://api.openai.com/v1"),
            rx.grid(
                _field("Model", HomeState.engine_model, HomeState.set_engine_model, "text", "gpt-4o-mini"),
                _field("Temperature", HomeState.engine_temperature, HomeState.set_engine_temperature, "text", "0.3"),
                columns="1fr 96px",
                spacing="3",
                width="100%",
            ),
            rx.hstack(
                rx.button(
                    rx.icon(tag="x", size=13),
                    "取消",
                    on_click=HomeState.cancel_edit,
                    width="100%",
                    variant="soft",
                    color_scheme="gray",
                ),
                rx.button(
                    rx.icon(tag="save", size=13),
                    "保存",
                    on_click=HomeState.save_current_engine,
                    width="100%",
                ),
                spacing="2",
                width="100%",
            ),
            spacing="2",
            width="100%",
            align_items="start",
        ),
        padding="0.7rem",
        border="1.5px solid #d0d7e2",
        border_radius="8px",
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
