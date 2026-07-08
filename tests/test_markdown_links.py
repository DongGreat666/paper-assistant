from src.core.markdown_links import normalize_escaped_brackets_in_link_labels


def test_normalizes_single_marker_citation_in_markdown_source():
    source = r"YOLO [\[23\]](#page-6-0)"

    assert normalize_escaped_brackets_in_link_labels(source) == (
        "YOLO [[23](#page-6-0)]"
    )


def test_normalizes_grouped_marker_citation_in_markdown_source():
    source = (
        r"[\[23,](#page-6-0) [24,](#page-6-1) "
        r"[25,](#page-6-2) [7\]](#page-6-3)"
    )

    assert normalize_escaped_brackets_in_link_labels(source) == (
        "[[23,](#page-6-0) [24,](#page-6-1) "
        "[25,](#page-6-2) [7](#page-6-3)]"
    )


def test_normalizes_brackets_split_across_different_links():
    source = (
        r"[\[24](#page-35-43)] and [[12\]](#page-34-8)"
    )

    assert normalize_escaped_brackets_in_link_labels(source) == (
        "[[24](#page-35-43)] and [[12](#page-34-8)]"
    )


def test_migrates_entity_form_to_readable_markdown():
    source = "[&#91;23&#93;](#page-6-0)"

    assert normalize_escaped_brackets_in_link_labels(source) == (
        "[[23](#page-6-0)]"
    )


def test_migrates_existing_nested_links_to_entity_labels():
    source = "[[1,](#page-9-0) [48](#page-11-1)] and [[49](#page-11-0)]"

    assert normalize_escaped_brackets_in_link_labels(source) == (
        "[[1,](#page-9-0) [48](#page-11-1)] and [[49](#page-11-0)]"
    )


def test_keeps_already_paired_double_bracket_citation_link():
    source = "baseline [[49]](#page-11-0)"

    assert normalize_escaped_brackets_in_link_labels(source) == (
        "baseline [[49](#page-11-0)]"
    )


def test_collapses_duplicate_entity_closing_bracket_in_link_label():
    source = "[&#91;3&#93;&#93;](#page-9-3) and [52&#93;&#93;](#page-11-4)"

    assert normalize_escaped_brackets_in_link_labels(source) == (
        "[[3](#page-9-3)] and [52](#page-11-4)]"
    )


def test_repairs_page_links_with_chinese_parentheses():
    source = "文献[[49]（#page-11-0）] 和 [1]（#page-2-1）"

    assert normalize_escaped_brackets_in_link_labels(source) == (
        "文献[[49](#page-11-0)] 和 [1]（#page-2-1）"
    )


def test_unescapes_parentheses_inside_link_labels_without_moving_them():
    source = r"Prior work [\(Zareian et al., 2021\)](#page-13-0) and Fig. [1\)](#page-1-0)."

    assert normalize_escaped_brackets_in_link_labels(source) == (
        "Prior work [(Zareian et al., 2021)](#page-13-0) and Fig. [1)](#page-1-0)."
    )


def test_unescapes_equation_reference_parentheses_inside_link_label():
    source = r"See Eq. [\(2\)](#page-3-1)."

    assert normalize_escaped_brackets_in_link_labels(source) == (
        "See Eq. [(2)](#page-3-1)."
    )


def test_keeps_link_targets_that_contain_parentheses():
    source = r"Remote Sens [2025;17\(4\):719.](http://refhub.elsevier.com/S2590-0056(26)00062-7/sb20)"

    assert normalize_escaped_brackets_in_link_labels(source) == (
        "Remote Sens [2025;17(4):719.](http://refhub.elsevier.com/S2590-0056(26)00062-7/sb20)"
    )


def test_repairs_author_year_citation_without_numeric_label():
    source = r"GANs [\(Goodfellow et al., 2014\)](#page-11-0)"

    assert normalize_escaped_brackets_in_link_labels(source) == (
        "GANs [(Goodfellow et al., 2014)](#page-11-0)"
    )


def test_keeps_non_citation_page_links_unchanged():
    source = (
        "See [Fig. 2](#page-2-0), [Table 1](#page-3-1), "
        "[Section 3.1](#page-5-0), and Eq. [(1)](#page-2-1)."
    )

    assert normalize_escaped_brackets_in_link_labels(source) == source


def test_repairs_author_year_page_link_but_not_plain_page_number():
    source = (
        r"GANs [\(Kingma & Dhariwal, 2018\)](#page-12-3), "
        r"see [2](#page-2-0)."
    )

    assert normalize_escaped_brackets_in_link_labels(source) == (
        "GANs [(Kingma & Dhariwal, 2018)](#page-12-3), "
        "see [2](#page-2-0)."
    )


def test_does_not_change_real_display_math():
    source = "\\[x^2 + y^2\\]"

    assert normalize_escaped_brackets_in_link_labels(source) == source
