"""Translation, bilingual merge, and Markdown utilities.

Depends on engine.py for TranslationEngine and config for settings.
"""

from __future__ import annotations

import random
import re
from typing import Iterable

from src.core.engine import TranslationEngine, get_default_translation_engine
from src.utils.http_client import chat_completions_url, chat_message_content, get_client


TRANSLATION_CONCURRENCY = 3
TRANSLATION_MAX_RETRIES = 2
TRANSLATION_RETRY_BASE_DELAY = 1.5
TRANSLATION_STOP_POLL_INTERVAL = 0.25
TRANSLATION_MAX_CHARS = 8000


_EXPLANATION_MARKERS = (
    "--- **改写说明**",
    "---**改写说明**",
    "**改写说明**",
    "改写说明：",
    "说明：",
)


# ---------------------------------------------------------------------------
# Markdown section splitting
# ---------------------------------------------------------------------------

# Pattern to split Markdown by top-level headings. It is only applied to
# lines outside fenced code blocks.
_HEADING_PATTERN = re.compile(r"^(#{1,3}\s+.+)$")
_FENCE_PATTERN = re.compile(r"^\s*(```|~~~)")
_REFERENCES_HEADING_PATTERN = re.compile(
    r"^#{1,6}\s+(?:"
    r"(?:\d+(?:\.\d+)*[.)]?\s+)?"
    r"(?:references|bibliography|works cited|literature cited)"
    r"|参考文献"
    r")\s*$",
    re.IGNORECASE,
)
_APPENDIX_HEADING_PATTERN = re.compile(
    r"^#{1,6}\s+(?:"
    r"appendix(?:es)?(?:\s+.*)?"
    r"|附录(?:\s+.*)?"
    r"|[A-Z](?:\.\d+)*[.)]?\s+.+"
    r")$",
    re.IGNORECASE,
)


def split_markdown_into_sections(md_text: str) -> list[str]:
    """Split Markdown into sections by headings (## or ###).

    Each section includes the heading line and its body.
    If no headings found, split by double newlines (paragraphs).
    """
    lines = md_text.splitlines(keepends=True)
    sections: list[str] = []
    current: list[str] = []
    in_fence = False

    for line in lines:
        if _FENCE_PATTERN.match(line):
            in_fence = not in_fence

        is_heading = not in_fence and bool(_HEADING_PATTERN.match(line.rstrip("\n")))
        if is_heading and current:
            section = "".join(current).strip()
            if section:
                sections.append(section)
            current = [line]
        else:
            current.append(line)

    if current:
        section = "".join(current).strip()
        if section:
            sections.append(section)

    if not any(_HEADING_PATTERN.match(s.splitlines()[0]) for s in sections if s.splitlines()):
        return _split_by_paragraphs(md_text)

    return sections


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


def _is_markdown_table_block(block: str) -> bool:
    """Return whether a Markdown block is a table that should be preserved."""
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    if all(line.startswith("|") for line in lines):
        return True
    separator_pattern = re.compile(
        r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$"
    )
    return sum("|" in line for line in lines) >= 2 and any(
        separator_pattern.match(line) for line in lines
    )


def _split_long_text(text: str, max_chars: int) -> list[str]:
    """Split oversized prose near line, sentence, or whitespace boundaries."""
    if len(text) <= max_chars:
        return [text]

    pieces: list[str] = []
    remaining = text.strip()
    while len(remaining) > max_chars:
        window = remaining[: max_chars + 1]
        candidates = [
            window.rfind("\n"),
            max(window.rfind(mark) for mark in (". ", "? ", "! ", "。", "？", "！", "; ")),
            window.rfind(" "),
        ]
        split_at = max(candidates)
        if split_at < max_chars // 2:
            split_at = max_chars
        else:
            split_at += 1
        pieces.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()

    if remaining:
        pieces.append(remaining)
    return pieces


def split_section_for_translation(
    section: str,
    max_chars: int = TRANSLATION_MAX_CHARS,
) -> list[tuple[str, bool]]:
    """Split a section into bounded translation units and preserved blocks.

    The boolean indicates whether the block should be sent to the translation
    engine. Markdown tables and fenced code blocks are preserved verbatim.
    """
    blocks = [block.strip() for block in re.split(r"\n\s*\n", section) if block.strip()]
    units: list[tuple[str, bool]] = []
    current: list[str] = []
    current_length = 0

    def flush_current() -> None:
        nonlocal current, current_length
        if current:
            units.append(("\n\n".join(current), True))
            current = []
            current_length = 0

    for block in blocks:
        stripped = block.strip()
        preserve = (
            _is_markdown_table_block(block)
            or ("<table" in stripped.lower() and "</table>" in stripped.lower())
            or (stripped.startswith("```") and stripped.endswith("```"))
            or (stripped.startswith("~~~") and stripped.endswith("~~~"))
        )
        if preserve:
            flush_current()
            units.append((block, False))
            continue

        for piece in _split_long_text(block, max_chars):
            added_length = len(piece) + (2 if current else 0)
            if current and current_length + added_length > max_chars:
                flush_current()
                added_length = len(piece)
            current.append(piece)
            current_length += added_length

    flush_current()
    return units


def should_skip_section(section: str) -> bool:
    """Check if a section should be preserved without translation."""
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


def reference_section_indexes(sections: list[str]) -> set[int]:
    """Return the final reference-list range, stopping before any appendix."""
    headings = [
        re.sub(
            r"<span\b[^>]*>\s*</span>\s*",
            "",
            section.strip().splitlines()[0].strip(),
            flags=re.IGNORECASE,
        )
        if section.strip()
        else ""
        for section in sections
    ]
    reference_starts = [
        index
        for index, heading in enumerate(headings)
        if _REFERENCES_HEADING_PATTERN.match(heading)
    ]
    if not reference_starts:
        return set()

    start = reference_starts[-1]
    end = len(sections)
    for index in range(start + 1, len(sections)):
        if _APPENDIX_HEADING_PATTERN.match(headings[index]):
            end = index
            break
    return set(range(start, end))


def clean_translation_output(text: str) -> str:
    """Remove common assistant explanations from translation-only responses."""
    result = (text or "").strip()
    for marker in _EXPLANATION_MARKERS:
        idx = result.find(marker)
        if idx >= 0:
            result = result[:idx].strip()

    for prefix in ("译文：", "翻译：", "中文翻译：", "翻译结果："):
        if result.startswith(prefix):
            result = result[len(prefix):].strip()
            break

    return result


def _code_fence_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip().startswith("```"))


def _validate_translated_markdown_structure(source: str, translated: str) -> None:
    """Reject translations that break Markdown code fences."""
    source_fences = _code_fence_count(source)
    translated_fences = _code_fence_count(translated)
    if source_fences != translated_fences:
        raise ValueError(
            f"Markdown code fence mismatch: source={source_fences}, translated={translated_fences}"
        )


# ---------------------------------------------------------------------------
# Translation via LLM
# ---------------------------------------------------------------------------


async def translate_inline(
    text: str,
    engine: TranslationEngine,
) -> str:
    """Fast inline translation for selected text (word/sentence/paragraph)."""
    messages = [
        {
            "role": "system",
            "content": (
                "你是学术论文翻译器。任务是把用户给出的英文原文忠实翻译成中文。\n"
                "硬性规则：\n"
                "1. 只输出中文译文，不要解释、总结、改写说明、标题或客套话。\n"
                "2. 不要扩写，不要补充原文没有的信息。\n"
                "3. 保留文献引用、数字、模型名、数据集名和专业术语。\n"
                "4. 尽量保持原文句子顺序和段落结构。"
            ),
        },
        {"role": "user", "content": text},
    ]
    client = get_client()
    response = await client.post(
        chat_completions_url(engine.base_url),
        headers={"Authorization": f"Bearer {engine.api_key.strip()}"},
        json={
            "model": engine.model,
            "messages": messages,
            "temperature": 0,
        },
    )
    response.raise_for_status()
    return clean_translation_output(chat_message_content(response.json()))


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
                "1. 仅输出翻译结果，不要添加解释、总结、改写说明、注释或额外内容。\n"
                "2. 忠实翻译原文，不要扩写，不要补充原文没有的信息。\n"
                "3. 保留所有数学公式（LaTeX）、文献引用标记原样不变。\n"
                "4. 翻译需符合中文学术表达习惯。\n"
                "5. 如遇 OCR 导致的断行或碎裂单词，自动修复。\n"
                "6. 严格保留 Markdown 结构：标题层级、列表、表格、图片链接、数学公式分隔符、引用链接不能丢失或新增。\n"
                "7. 严格保留代码块围栏：原文中每一个开头 ``` 和结尾 ``` 都必须在译文中保留，数量和顺序一致。\n"
                "8. 代码块内部不要改成普通 Markdown。以 # 开头的代码注释仍然是代码注释，不能变成 Markdown 标题。\n"
                "9. 代码块内的变量名、函数名、缩进、标点和换行保持不变；只翻译自然语言注释或说明。"
            ),
        },
        {"role": "user", "content": text},
    ]
    client = get_client()
    response = await client.post(
        chat_completions_url(engine.base_url),
        headers={"Authorization": f"Bearer {engine.api_key.strip()}"},
        json={
            "model": engine.model,
            "messages": messages,
            "temperature": engine.temperature,
        },
    )
    response.raise_for_status()
    return clean_translation_output(chat_message_content(response.json()))


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
    reference_indexes = reference_section_indexes(sections)
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
                if result is None:
                    return section
                _validate_translated_markdown_structure(section, result)
                return result
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
        elif idx in reference_indexes or should_skip_section(section):
            result = section
        else:
            translated_units: list[str] = []
            for unit, should_translate in split_section_for_translation(section):
                if should_stop and should_stop():
                    translated_units.append(unit)
                elif not should_translate or should_skip_section(unit):
                    translated_units.append(unit)
                else:
                    async with semaphore:
                        translated_units.append(await _translate_with_retries(unit))
            result = "\n\n".join(translated_units)
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
