"""Translation, bilingual merge, and Markdown utilities.

Depends on engine.py for TranslationEngine and config for settings.
"""

from __future__ import annotations

import random
import re
from typing import Iterable

from src.core.engine import TranslationEngine, get_default_translation_engine
from src.utils.http_client import get_client


TRANSLATION_CONCURRENCY = 3
TRANSLATION_MAX_RETRIES = 2
TRANSLATION_RETRY_BASE_DELAY = 1.5
TRANSLATION_STOP_POLL_INTERVAL = 0.25


# ---------------------------------------------------------------------------
# Markdown section splitting
# ---------------------------------------------------------------------------

# Pattern to split Markdown by top-level headings
_HEADING_PATTERN = re.compile(r"^(#{1,3}\s+.+)$", re.MULTILINE)


def split_markdown_into_sections(md_text: str) -> list[str]:
    """Split Markdown into sections by headings (## or ###).

    Each section includes the heading line and its body.
    If no headings found, split by double newlines (paragraphs).
    """
    parts = _HEADING_PATTERN.split(md_text)

    if len(parts) <= 1:
        # No headings found — split by blank lines
        return _split_by_paragraphs(md_text)

    sections: list[str] = []
    i = 0
    # parts[0] is text before first heading (preamble)
    if parts[0].strip():
        sections.append(parts[0])

    while i < len(parts):
        if _HEADING_PATTERN.match(parts[i]):
            heading = parts[i]
            body = parts[i + 1] if i + 1 < len(parts) else ""
            sections.append(heading + body)
            i += 2
        else:
            if parts[i].strip():
                sections.append(parts[i])
            i += 1

    return [s for s in sections if s.strip()]


def _split_by_paragraphs(md_text: str, max_chars: int = 3000) -> list[str]:
    """Split Markdown by double newlines, merging small paragraphs."""
    blocks = re.split(r"\n\s*\n", md_text)
    sections: list[str] = []
    current = ""

    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if len(current) + len(block) + 2 > max_chars and current:
            sections.append(current)
            current = block
        else:
            current = current + "\n\n" + block if current else block

    if current.strip():
        sections.append(current)

    return sections


def should_skip_section(section: str) -> bool:
    """Check if a section is pure formula/image and should not be translated."""
    stripped = section.strip()

    # Pure display math block
    if stripped.startswith("$$") and stripped.endswith("$$"):
        return True

    # Pure image
    if re.match(r"^!\[.*?\]\(.*?\)$", stripped):
        return True

    # Very short (likely just a label or separator)
    if len(stripped) < 20:
        return True

    return False


# ---------------------------------------------------------------------------
# Translation via LLM
# ---------------------------------------------------------------------------


async def translate_inline(
    text: str,
    engine: TranslationEngine,
) -> str:
    """Fast inline translation for selected text (word/sentence/paragraph).

    Optimized for speed: minimal prompt, no formatting rules.
    """
    messages = [
        {"role": "system", "content": "将用户输入翻译为中文，直接输出译文。"},
        {"role": "user", "content": text},
    ]
    client = get_client()
    response = await client.post(
        f"{engine.base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {engine.api_key.strip()}"},
        json={
            "model": engine.model,
            "messages": messages,
            "temperature": 0.1,
        },
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


async def translate_section(
    text: str,
    target_language: str,
    engine: TranslationEngine,
) -> str:
    """Translate a single Markdown section via LLM."""
    messages = [
        {
            "role": "system",
            "content": (
                "你是学术论文翻译专家。请将用户提供的英文文本翻译为中文。\n"
                "规则：\n"
                "1. 仅输出翻译结果，不要添加解释、注释或额外内容。\n"
                "2. 保留所有数学公式（LaTeX）、文献引用标记原样不变。\n"
                "3. 翻译需符合中文学术表达习惯。\n"
                "4. 如遇 OCR 导致的断行或碎裂单词，自动修复。"
            ),
        },
        {"role": "user", "content": text},
    ]
    client = get_client()
    response = await client.post(
        f"{engine.base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {engine.api_key.strip()}"},
        json={
            "model": engine.model,
            "messages": messages,
            "temperature": engine.temperature,
        },
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


async def translate_markdown(
    md_text: str,
    target_language: str = "中文",
    engine: TranslationEngine | None = None,
    on_progress=None,
    should_stop=None,
    task_timeout: float = 90,
) -> str:
    """Translate a full Markdown document section by section (concurrently).

    Args:
        md_text: Original Markdown text.
        target_language: Target language name.
        engine: Translation engine to use.
        on_progress: Optional async callback(translated_count, total_count).
        should_stop: Optional callable returning True to abort early.
        task_timeout: Per-section timeout in seconds (default 90).

    Returns:
        Translated Markdown text.
    """
    import asyncio

    engine = engine or get_default_translation_engine()
    sections = split_markdown_into_sections(md_text)
    total = len(sections)
    translated_count = 0
    semaphore = asyncio.Semaphore(TRANSLATION_CONCURRENCY)

    async def _sleep_or_stop(delay: float) -> bool:
        remaining = delay
        while remaining > 0:
            if should_stop and should_stop():
                return True
            step = min(TRANSLATION_STOP_POLL_INTERVAL, remaining)
            await asyncio.sleep(step)
            remaining -= step
        return bool(should_stop and should_stop())

    async def _translate_once(section: str) -> str | None:
        task = asyncio.create_task(translate_section(section, target_language, engine))
        elapsed = 0.0
        try:
            while not task.done():
                if should_stop and should_stop():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    return None
                if elapsed >= task_timeout:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    raise asyncio.TimeoutError()
                step = min(TRANSLATION_STOP_POLL_INTERVAL, task_timeout - elapsed)
                await asyncio.sleep(step)
                elapsed += step
            return await task
        except Exception:
            if not task.done():
                task.cancel()
            raise

    async def _translate_with_retries(section: str) -> str:
        last_error: Exception | None = None
        for attempt in range(TRANSLATION_MAX_RETRIES + 1):
            if should_stop and should_stop():
                return section
            try:
                result = await _translate_once(section)
                return section if result is None else result
            except asyncio.TimeoutError as exc:
                last_error = exc
                if attempt >= TRANSLATION_MAX_RETRIES:
                    return f"<!-- 翻译超时 ({task_timeout}s) -->\n\n{section}"
            except Exception as exc:
                last_error = exc
                if attempt >= TRANSLATION_MAX_RETRIES:
                    return f"<!-- 翻译失败: {exc} -->\n\n{section}"

            if should_stop and should_stop():
                return section
            delay = TRANSLATION_RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.4)
            if await _sleep_or_stop(delay):
                return section

        return f"<!-- 翻译失败: {last_error} -->\n\n{section}"

    async def _translate_one(idx: int, section: str) -> tuple[int, str]:
        nonlocal translated_count
        if should_stop and should_stop():
            result = section
        elif should_skip_section(section):
            result = section
        else:
            async with semaphore:
                if should_stop and should_stop():
                    result = section
                else:
                    result = await _translate_with_retries(section)
        translated_count += 1
        if on_progress:
            await on_progress(translated_count, total)
        return idx, result

    tasks = [_translate_one(i, s) for i, s in enumerate(sections)]
    results = await asyncio.gather(*tasks)

    # Reassemble in original order
    translated_parts = [""] * total
    for idx, text in results:
        translated_parts[idx] = text

    return "\n\n".join(translated_parts)


# ---------------------------------------------------------------------------
# Bilingual merge
# ---------------------------------------------------------------------------

_NON_TEXT = re.compile(
    r"^\s*(?:"
    r"#{1,6}\s+"               # heading
    r"|!\["                     # image
    r"|\$\$"                    # display math
    r"|\|.*\|"                  # table row
    r"|<(?:table|img|details|span)"  # HTML block elements
    r"|---|\*\*\*|___"          # horizontal rule
    r"|(?:图|Figure|Fig\.)\s*\d+[：:.]"  # figure caption
    r"|(?:表|Table|Tab\.)\s*\d+[：:.]"   # table caption
    r")",
)


def _strip_non_text(text: str) -> str:
    """Keep only paragraph text, remove headings/images/formulas/tables."""
    blocks = re.split(r"\n\s*\n", text)
    paras = []
    for block in blocks:
        lines = block.strip().split("\n")
        # Skip if any line looks like non-text content
        skip = False
        for line in lines:
            if line.strip() and _NON_TEXT.match(line.strip()):
                skip = True
                break
        if not skip and block.strip():
            paras.append(block.strip())
    return "\n\n".join(paras)


def _to_blockquote(text: str) -> str:
    """Wrap text in a markdown blockquote (preserves inline markdown like links)."""
    lines = text.split("\n")
    return "\n".join(f"> {line}" for line in lines)


def merge_bilingual(original_md: str, translated_md: str) -> str:
    """Merge English + Chinese section-by-section into a bilingual Markdown.

    Strategy: split both docs by headings (##/###/####), match sections 1:1.
    Before Abstract: English only. After Abstract: each section = English then Chinese.
    """
    _HEADING = re.compile(r"^(#{1,6}\s+.+)$", re.MULTILINE)

    def _split_sections(md: str) -> list[str]:
        parts = _HEADING.split(md)
        sections: list[str] = []
        i = 0
        if parts[0].strip():
            sections.append(parts[0])
        while i < len(parts):
            if _HEADING.match(parts[i]):
                heading = parts[i]
                body = parts[i + 1] if i + 1 < len(parts) else ""
                sections.append(heading + body)
                i += 2
            else:
                if parts[i].strip():
                    sections.append(parts[i])
                i += 1
        return [s for s in sections if s.strip()]

    en_sections = _split_sections(original_md)
    zh_sections = _split_sections(translated_md)

    # Find where Abstract starts
    abstract_idx = 0
    for i, sec in enumerate(en_sections):
        if re.match(r"^#{1,6}\s+.*[Aa]bstract", sec.strip()):
            abstract_idx = i
            break

    parts: list[str] = []
    zh_sec_idx = 0

    for sec_idx, en_sec in enumerate(en_sections):
        # Before Abstract: English only
        if sec_idx < abstract_idx:
            parts.append(en_sec.strip())
            parts.append("\n\n")
            if zh_sec_idx < len(zh_sections):
                zh_sec_idx += 1
            continue

        # Get matching Chinese section
        zh_sec = zh_sections[zh_sec_idx].strip() if zh_sec_idx < len(zh_sections) else ""
        zh_sec_idx += 1

        # Output English section, then Chinese paragraphs as blockquote
        parts.append(en_sec.strip())
        zh_text = _strip_non_text(zh_sec)
        if zh_text:
            parts.append(f"\n\n{_to_blockquote(zh_text)}")
        parts.append("\n\n")

    return "".join(parts)


# ---------------------------------------------------------------------------
# Markdown → HTML (for display)
# ---------------------------------------------------------------------------


def markdown_to_html(md_text: str) -> str:
    """Convert Markdown to HTML for display in the browser."""
    import markdown as md_lib

    return md_lib.markdown(
        md_text,
        extensions=["tables", "fenced_code", "codehilite", "toc"],
    )
