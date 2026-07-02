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


def normalize_escaped_brackets_in_link_labels(text: str) -> str:
    r"""Replace TeX-like delimiter escapes inside Markdown link labels.

    Marker emits citations such as ``[\[23\]](#page-1-0)``.  Although some
    Markdown renderers display that correctly, math-aware renderers can treat
    ``\[`` as a TeX delimiter.  Use HTML entities for the visible citation
    brackets so the source remains a plain Markdown link, such as
    ``[&#91;23&#93;](#ref)``.

    Marker also emits link labels such as ``[\(Zareian et al., 2021\)](#ref)``
    and ``[1\)](#fig)``.  In Markdown link labels those backslashes are only
    escaping literal parentheses, but KaTeX-enabled renderers may see
    ``\(...\)`` as inline math.  Keep the parentheses in the label and remove
    only the escape slashes.
    """

    def replace(match: re.Match[str]) -> str:
        label = match.group("label")
        prefix = ""
        suffix = ""
        if label.startswith(r"\["):
            prefix, label = "&#91;", label[2:]
        elif label.startswith("&#91;"):
            prefix, label = "&#91;", label[5:]
        if label.endswith(r"\]"):
            label, suffix = label[:-2], "&#93;"
        elif label.endswith("&#93;"):
            label, suffix = label[:-5], "&#93;"
        unescaped_label = label.replace(r"\(", "(").replace(r"\)", ")")
        full_label = f"{prefix}{unescaped_label}{suffix}"
        if full_label.endswith("&#93;&#93;"):
            full_label = full_label[:-5]
        if not prefix and not suffix and full_label == label:
            return match.group(0)
        return f"[{full_label}]({match.group('target')})"

    normalized = _CHINESE_PAREN_PAGE_LINK_PATTERN.sub(
        lambda match: f"[&#91;{match.group('label')}&#93;]({match.group('target')})",
        text,
    )
    normalized = _DOUBLE_BRACKET_LINK_PATTERN.sub(
        lambda match: f"[&#91;{match.group('label')}&#93;]({match.group('target')})",
        normalized,
    )
    normalized = _INLINE_LINK_PATTERN.sub(replace, normalized)
    normalized = _NESTED_LINK_START_PATTERN.sub("[&#91;", normalized)

    def replace_nested_end(match: re.Match[str]) -> str:
        return f"[{match.group('label')}&#93;]({match.group('target')})"

    return _NESTED_LINK_END_PATTERN.sub(replace_nested_end, normalized)
