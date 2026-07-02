from src.ui.pages.home_upload_service import short_stem, unique_upload_stem


def test_short_stem_can_collide_for_similar_paper_titles():
    first = "Object Detection with Deep Learning A Review.pdf"
    second = "Object detection with multimodal large vision-language models.pdf"

    assert short_stem(first).lower() == short_stem(second).lower()


def test_unique_upload_stem_uses_content_hash_to_avoid_partial_title_collisions():
    first = "Object Detection with Deep Learning A Review.pdf"
    second = "Object detection with multimodal large vision-language models.pdf"

    first_stem = unique_upload_stem(first, b"deep-learning-review")
    second_stem = unique_upload_stem(second, b"multimodal-vlm")

    assert first_stem != second_stem
    assert first_stem.startswith("Object Detection with Deep Learning")
    assert second_stem.startswith("Object detection with multimodal")


def test_unique_upload_stem_changes_when_same_filename_content_changes():
    filename = "Object detection with multimodal large vision-language models.pdf"

    assert unique_upload_stem(filename, b"v1") != unique_upload_stem(filename, b"v2")
