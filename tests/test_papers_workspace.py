import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.ui.pages import home_upload_service


class FakeUpload:
    filename = "paper.pdf"

    async def read(self):
        return b"%PDF-1.4 test"


class PapersWorkspaceTests(unittest.TestCase):
    def test_upload_and_generated_files_share_one_paper_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            papers_dir = Path(temp_dir) / "MyPapers"

            with patch.object(home_upload_service, "PAPERS_DIR", papers_dir):
                saved = asyncio.run(home_upload_service.save_upload(FakeUpload()))

            self.assertEqual(saved.folder, papers_dir / "paper")
            self.assertEqual(saved.destination, papers_dir / "paper" / "paper.pdf")
            self.assertTrue(saved.destination.exists())


if __name__ == "__main__":
    unittest.main()
