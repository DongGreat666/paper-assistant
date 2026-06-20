import shutil
import tempfile
import unittest
from pathlib import Path

import fitz

from src.core.pdf_annotations import add_highlight, delete_highlight, read_highlights
from src.ui.pages.library import LibraryState


class PdfAnnotationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.pdf_path = Path(self.temp_dir.name) / "annotations.pdf"

        doc = fitz.open()
        page = doc.new_page(width=600, height=800)
        page.insert_text((72, 100), "PDF annotation integration test")
        doc.save(self.pdf_path)
        doc.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_reader_rects_normalize_pixel_and_relative_coordinates(self):
        pixel_rects = [{
            "x1": 100,
            "y1": 200,
            "x2": 300,
            "y2": 220,
            "width": 1000,
            "height": 1200,
            "pageNumber": 1,
        }]
        relative_rects = [{
            "x1": 0.1,
            "y1": 0.2,
            "x2": 0.3,
            "y2": 0.22,
            "width": 1000,
            "height": 1200,
            "pageNumber": 1,
        }]

        normalized_pixels = LibraryState._normalize_reader_rects(None, pixel_rects)
        normalized_relative = LibraryState._normalize_reader_rects(None, relative_rects)

        self.assertAlmostEqual(normalized_pixels[0]["x1"], 0.1)
        self.assertAlmostEqual(normalized_pixels[0]["y1"], 1 / 6)
        self.assertEqual(normalized_pixels[0]["pageNumber"], 1)
        self.assertEqual(normalized_relative[0], {
            "x1": 0.1,
            "y1": 0.2,
            "x2": 0.3,
            "y2": 0.22,
            "pageNumber": 1,
        })

    def test_highlight_round_trip_and_delete_by_id(self):
        annotation_id = "integration-highlight"
        saved = add_highlight(
            str(self.pdf_path),
            page_num=1,
            rects=[{"x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.13}],
            highlight_id=annotation_id,
            text="PDF annotation integration test",
        )

        self.assertTrue(saved)
        loaded = read_highlights(str(self.pdf_path))
        self.assertIn(annotation_id, [item["id"] for item in loaded])
        rect = next(item for item in loaded if item["id"] == annotation_id)["position"]["boundingRect"]
        self.assertGreater(rect["x1"], 1)
        self.assertEqual(rect["width"], 600)
        self.assertEqual(rect["height"], 800)
        self.assertTrue(delete_highlight(str(self.pdf_path), annotation_id))
        self.assertNotIn(annotation_id, [item["id"] for item in read_highlights(str(self.pdf_path))])

    def test_delete_existing_real_pdf_annotation_on_copy(self):
        candidates = list(Path("MyPapers").rglob("*.pdf"))
        annotated_pdf = next(
            (
                path
                for path in candidates
                if read_highlights(str(path))
            ),
            None,
        )
        if annotated_pdf is None:
            self.skipTest("No annotated PDF is available for a real-file copy test")

        copied_pdf = Path(self.temp_dir.name) / annotated_pdf.name
        shutil.copy2(annotated_pdf, copied_pdf)
        before = read_highlights(str(copied_pdf))
        target_id = before[0]["id"]

        self.assertTrue(delete_highlight(str(copied_pdf), target_id))
        self.assertNotIn(target_id, [item["id"] for item in read_highlights(str(copied_pdf))])


if __name__ == "__main__":
    unittest.main()
