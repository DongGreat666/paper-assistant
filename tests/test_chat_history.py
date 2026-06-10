import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core import chat_history


class ChatHistoryPathSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.history_dir = self.root / "history"
        self.history_patch = patch.object(chat_history, "HISTORY_DIR", self.history_dir)
        self.history_patch.start()

    def tearDown(self):
        self.history_patch.stop()
        self.temp_dir.cleanup()

    def test_normal_conversation_can_be_saved_loaded_and_deleted(self):
        conv = chat_history.new_conversation(messages=[{"role": "user", "content": "hello"}])

        chat_history.save(conv)

        self.assertEqual(chat_history.load(conv["id"])["id"], conv["id"])
        self.assertTrue(chat_history.delete(conv["id"]))
        self.assertIsNone(chat_history.load(conv["id"]))

    def test_traversal_id_cannot_read_or_delete_outside_history(self):
        outside = self.root / "outside.json"
        outside.write_text('{"secret": true}', encoding="utf-8")

        self.assertIsNone(chat_history.load("../outside"))
        self.assertFalse(chat_history.delete("../outside"))
        self.assertTrue(outside.exists())

    def test_save_rejects_invalid_id(self):
        with self.assertRaises(ValueError):
            chat_history.save({"id": "../outside", "messages": []})

    def test_list_uses_valid_filename_id_not_untrusted_json_id(self):
        self.history_dir.mkdir()
        valid_id = "abcdef123456"
        (self.history_dir / f"{valid_id}.json").write_text(
            json.dumps({"id": "../outside", "title": "safe", "updated_at": ""}),
            encoding="utf-8",
        )
        (self.history_dir / "invalid.json").write_text("{}", encoding="utf-8")

        conversations = chat_history.list_conversations()

        self.assertEqual([item["id"] for item in conversations], [valid_id])


if __name__ == "__main__":
    unittest.main()
