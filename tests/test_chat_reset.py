import unittest
from types import SimpleNamespace

from src.ui.pages.home_state import HomeState
from src.ui.pages.library import LibraryState


class ChatResetTests(unittest.TestCase):
    def test_home_clear_chat_resets_draft_and_document_context(self):
        state = SimpleNamespace(
            input_text="unfinished question",
            messages=[{"role": "user", "content": "hello"}],
            conversation_id="abcdef123456",
            file_name="paper.pdf",
            saved_path="uploaded_files/paper.pdf",
            folder_path="uploaded_files/paper",
            file_info="paper.pdf | 1 KB",
            paper_md="# Paper",
            paper_ready=True,
            is_preparing=True,
            is_chatting=True,
            status_message="",
        )
        state._reset_chat_workspace = lambda message: HomeState._reset_chat_workspace(state, message)

        HomeState.clear_chat.fn(state)

        self.assertEqual(state.input_text, "")
        self.assertEqual(state.messages, [])
        self.assertEqual(state.file_name, "")
        self.assertFalse(state.paper_ready)
        self.assertFalse(state.is_chatting)

    def test_library_clear_chat_resets_input_but_keeps_paper_context(self):
        state = SimpleNamespace(
            chat_messages=[{"role": "user", "content": "hello"}],
            chat_input="unfinished question",
            chat_loading=True,
            selected_pdf_path="CV/paper.pdf",
        )

        LibraryState.clear_chat.fn(state)

        self.assertEqual(state.chat_messages, [])
        self.assertEqual(state.chat_input, "")
        self.assertFalse(state.chat_loading)
        self.assertEqual(state.selected_pdf_path, "CV/paper.pdf")


if __name__ == "__main__":
    unittest.main()
