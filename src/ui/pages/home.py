"""Home page entrypoint for document-grounded and standalone chat."""

import reflex as rx

from src.ui.components.layout import app_shell
from src.ui.pages.home_chat import main_content
from src.ui.pages.home_state import HomeState


def home_page() -> rx.Component:
    return app_shell(
        "/",
        main_content(),
        chats=HomeState.conversations,
        on_new_chat=HomeState.new_chat,
        on_chat_click=HomeState.switch_chat,
        on_chat_delete=HomeState.delete_chat,
        active_chat_id=HomeState.conversation_id,
    )
