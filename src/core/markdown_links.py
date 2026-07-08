"""Normalize Markdown links emitted by document converters."""

import re


_INLINE_LINK_PATTERN = re.compile(
    r"\[(?P<label>(?:\\.|[^\\\]\n])*)\]\((?P<target>(?:\\.|[^\\()\n]|\([^()\n]*\))+)\)"
)
_DOUBLE_BRACKET_LINK_PATTERN = re.compile(
    r"\[\[(?P<label>[^\\\]\n]+)\]\]\((?P<target>(?:\\.|[^\\()\n]|\([^()\n]*\))+)\)"
)
_NESTED_LINK_START_PATTERN = re.compile(
    r"\[\[(?=(?:\\.|[^\\\]\n])*\]\((?:\\.|[^\\()\n]|\([^()\n]*\))+\))"
)
_NESTED_LINK_END_PATTERN = re.compile(
    r"(?<!!)\[(?P<label>(?:\\.|[^\\\]\n])*)\]\((?P<target>(?:\\.|[^\\()\n]|\([^()\n]*\))+)\)\]"
)
_CHINESE_PAREN_PAGE_LINK_PATTERN = re.compile(
    r"\[{1,2}(?P<label>[^\]\n]+?)\]（(?P<target>#page-[^）\s]+)）\]?"
)
_YEAR_PATTERN = re.compile(r"(?:19|20)\d{2}")
_NUMERIC_CITATION_LABEL_PATTERN = re.compile(
    r"^\s*\[?\s*-?\d+(?:\s*(?:,|;|–|-)\s*-?\d+)*\s*,?\s*\]?\s*$"
)
_FIGURE_TABLE_SECTION_LABEL_PATTERN = re.compile(
    r"^\s*(?:fig(?:ure)?\.?|table|tab\.?|sec(?:tion)?\.?|appendix|eq(?:uation)?\.?)\s*",
    re.IGNORECASE,
)


def _citation_label_parts(label: str) -> tuple[str, str, str]:
    """Return visible label and citation bracket wrappers."""
    visible = label.strip()
    prefix = ""
    suffix = ""
    while visible.startswith(r"\["):
        prefix, visible = "[", visible[2:].lstrip()
    while visible.startswith("&#91;"):
        prefix, visible = "[", visible[5:].lstrip()
    while visible.startswith("["):
        prefix, visible = "[", visible[1:].lstrip()
    while visible.endswith(r"\]"):
        visible, suffix = visible[:-2].rstrip(), "]"
    while visible.endswith("&#93;"):
        visible, suffix = visible[:-5].rstrip(), "]"
    while visible.endswith("]"):
        visible, suffix = visible[:-1].rstrip(), "]"
    return visible, prefix, suffix


def _looks_like_citation_label(label: str) -> bool:
    """Return whether a page-link label looks like a bibliography citation."""
    visible, prefix, suffix = _citation_label_parts(label)
    unescaped = visible.replace(r"\(", "(").replace(r"\)", ")")
    compact = unescaped.strip()
    if prefix or suffix:
        return True
    if _FIGURE_TABLE_SECTION_LABEL_PATTERN.match(compact):
        return False
    if re.fullmatch(r"\(?\s*[A-Za-z]?\d+(?:\.\d+)*\s*\)?\.?", compact):
        return False
    if _NUMERIC_CITATION_LABEL_PATTERN.match(compact):
        return True
    if _YEAR_PATTERN.search(compact) and (
        "et al" in compact
        or "&" in compact
        or "," in compact
        or compact.startswith("(")
        or compact.endswith(")")
    ):
        return True
    return False


def normalize_escaped_brackets_in_link_labels(text: str) -> str:
    r"""Replace TeX-like delimiter escapes inside Markdown link labels.

    Marker emits citations such as ``[\[23\]](#page-1-0)``.  Although some
    Markdown renderers display that correctly, math-aware renderers can treat
    ``\[`` as a TeX delimiter.  Keep linked citations as a paired outer-bracket
    wrapper around the page link, such as ``[[23](#ref)]``.

    Marker also emits link labels such as ``[\(Zareian et al., 2021\)](#ref)``
    and ``[1\)](#fig)``.  In Markdown link labels those backslashes are only
    escaping literal parentheses, but KaTeX-enabled renderers may see
    ``\(...\)`` as inline math.  Keep the parentheses in the label and remove
    only the escape slashes.
    """

    def replace(match: re.Match[str]) -> str:
        label = match.group("label")
        target = match.group("target")
        prefix = ""
        suffix = ""
        if target.startswith("#page-") and _looks_like_citation_label(label):
            label, prefix, suffix = _citation_label_parts(label)
        unescaped_label = label.replace(r"\(", "(").replace(r"\)", ")")
        if prefix or suffix:
            return f"{prefix}[{unescaped_label}]({target}){suffix}"
        if unescaped_label == label:
            return match.group(0)
        return f"[{unescaped_label}]({target})"

    def replace_chinese_paren_link(match: re.Match[str]) -> str:
        has_outer_citation_bracket = match.group(0).lstrip().startswith("[[")
        if has_outer_citation_bracket or _looks_like_citation_label(match.group("label")):
            return (
            f"[[{match.group('label')}]({match.group('target')})]"
            )
        return match.group(0)

    normalized = _CHINESE_PAREN_PAGE_LINK_PATTERN.sub(replace_chinese_paren_link, text)
    normalized = _DOUBLE_BRACKET_LINK_PATTERN.sub(
        lambda match: f"[[{match.group('label')}]({match.group('target')})]"
        if match.group("target").startswith("#page-")
        else match.group(0),
        normalized,
    )
    normalized = _INLINE_LINK_PATTERN.sub(replace, normalized)

    def replace_nested_end(match: re.Match[str]) -> str:
        return f"[{match.group('label')}]({match.group('target')})]"

    return _NESTED_LINK_END_PATTERN.sub(replace_nested_end, normalized)
