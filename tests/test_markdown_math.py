from src.core.markdown_math import normalize_math_delimiters


def test_normalizes_latex_math_delimiters():
    source = "Inline \\(x + 1\\) and display:\n\\[x^2 + y^2\\]"

    rendered = normalize_math_delimiters(source)

    assert "$x + 1$" in rendered
    assert "$$\nx^2 + y^2\n$$" in rendered


def test_preserves_marker_linked_citations():
    source = (
        r"YOLO series [\[23,](#page-6-0) [24,](#page-6-1) "
        r"[25,](#page-6-2) [1,](#page-5-0) [7\]](#page-6-3) always"
    )

    assert normalize_math_delimiters(source) == source


def test_preserves_math_delimiters_inside_code():
    source = r"Use `\[not math\]` in code."

    assert normalize_math_delimiters(source) == source
