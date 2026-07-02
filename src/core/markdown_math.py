"""Normalize common model-generated LaTeX delimiters for Markdown renderers."""

import re


_CODE_SPAN_PATTERN = re.compile(r"(```[\s\S]*?```|`[^`\n]*`)")
# Marker escapes the square brackets around linked citations as ``[\[...\]]``.
# The opening ``\[`` in that sequence is Markdown punctuation, not a TeX math
# delimiter.  Requiring it not to be immediately preceded by ``[`` keeps those
# citations intact while still accepting normal LaTeX ``\[...\]`` blocks.
_DISPLAY_MATH_PATTERN = re.compile(r"(?<!\[)\\\[\s*([\s\S]*?)\s*\\\]")
_INLINE_MATH_PATTERN = re.compile(r"\\\((.+?)\\\)")


def normalize_math_delimiters(text: str) -> str:
    """Convert LaTeX delimiters unsupported by remark-math, preserving code."""
    if not text or ("\\(" not in text and "\\[" not in text):
        return text

    parts = _CODE_SPAN_PATTERN.split(text)
    for index in range(0, len(parts), 2):
        part = _DISPLAY_MATH_PATTERN.sub(lambda match: f"\n$$\n{match.group(1)}\n$$\n", parts[index])
        parts[index] = _INLINE_MATH_PATTERN.sub(lambda match: f"${match.group(1)}$", part)
    return "".join(parts)


def normalize_message_math(messages: list[dict]) -> list[dict]:
    """Return chat messages with renderable math in assistant content."""
    return [
        {
            **message,
            "content": normalize_math_delimiters(str(message.get("content", ""))),
        }
        if message.get("role") == "assistant"
        else message
        for message in messages
    ]
