"""Shared UI preferences."""

import reflex as rx

from config import read_settings, write_settings


_ui_defaults = read_settings()


class UISettingsState(rx.State):
    """Global visual preferences shared by all pages."""

    font_size: int = _ui_defaults.get("font_size", 18)
    theme: str = _ui_defaults.get("theme", "light")
    sidebar_collapsed: bool = False

    def _persist(self):
        """Write theme and font_size to settings.json, merging with other keys."""
        write_settings({"theme": self.theme, "font_size": self.font_size})

    def set_font_size(self, value):
        raw = value[0] if isinstance(value, list) else value
        try:
            self.font_size = max(15, min(24, int(raw)))
        except (TypeError, ValueError):
            self.font_size = 18
        self._persist()

    def set_theme(self, value: str):
        self.theme = value
        self._persist()

    def decrease_font(self):
        self.font_size = max(15, self.font_size - 1)
        self._persist()

    def increase_font(self):
        self.font_size = min(24, self.font_size + 1)
        self._persist()

    def toggle_sidebar(self):
        self.sidebar_collapsed = not self.sidebar_collapsed

    @rx.var
    def font_size_css(self) -> str:
        return f"{self.font_size}px"

    @rx.var
    def base_font_css(self) -> str:
        """CSS variable declaration for use on the root element."""
        return f"{self.font_size}px"

    @rx.var
    def app_bg(self) -> str:
        if self.theme == "dark":
            return "#111827"
        if self.theme == "warm":
            return "#f7f2ea"
        return "#f6f7f9"

    @rx.var
    def surface_bg(self) -> str:
        if self.theme == "dark":
            return "#172033"
        if self.theme == "warm":
            return "#fffaf2"
        return "white"

    @rx.var
    def muted_bg(self) -> str:
        if self.theme == "dark":
            return "#202b40"
        if self.theme == "warm":
            return "#f2eadf"
        return "#f4f6f8"

    @rx.var
    def text_color(self) -> str:
        if self.theme == "dark":
            return "#edf2f7"
        return "#16181d"

    @rx.var
    def muted_text_color(self) -> str:
        if self.theme == "dark":
            return "#a9b4c7"
        return "#697386"

    @rx.var
    def border_color(self) -> str:
        if self.theme == "dark":
            return "#2f3b52"
        if self.theme == "warm":
            return "#e7dccf"
        return "#e5e7eb"
