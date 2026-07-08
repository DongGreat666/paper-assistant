from pathlib import Path

import src.core.document_parser as document_parser


def _with_text_layer(value: bool):
    original = document_parser._has_usable_pdf_text_layer
    document_parser._has_usable_pdf_text_layer = lambda _path: value
    return original


def test_marker_config_keeps_table_ocr_fallback_for_text_layer_pdf():
    original = _with_text_layer(True)
    try:
        config = document_parser._marker_config_for_pdf(Path("paper.pdf"))
    finally:
        document_parser._has_usable_pdf_text_layer = original


    assert config["disable_ocr"] is True
    assert config["TableProcessor_disable_ocr"] is False
    assert config["TableProcessor_table_rec_batch_size"] == 2
    assert config["TableProcessor_detection_batch_size"] == 2
    assert config["TableProcessor_recognition_batch_size"] == 16


def test_marker_config_keeps_default_ocr_for_scanned_pdf():
    original = _with_text_layer(False)
    try:
        config = document_parser._marker_config_for_pdf(Path("scan.pdf"))
    finally:
        document_parser._has_usable_pdf_text_layer = original

    assert config == {}


def test_marker_config_can_disable_equation_processor():
    original = _with_text_layer(True)
    try:
        config = document_parser._marker_config_for_pdf(Path("paper.pdf"), disable_equations=True)
    finally:
        document_parser._has_usable_pdf_text_layer = original


    assert config["_disable_equation_processor"] is True
