"""Context-Aware Workspace Chat engine.

Provides PDF text extraction (PyMuPDF) and LLM chat with context injection.
"""

from __future__ import annotations

import fitz  # PyMuPDF

from src.core.engine import TranslationEngine
from src.utils.http_client import get_client


# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def extract_page_text(pdf_path: str, page_num: int) -> str:
    """Extract text content from a specific page."""
    doc = fitz.open(pdf_path)
    try:
        text = doc[page_num].get_text("text")
    except IndexError:
        text = ""
    finally:
        doc.close()
    return text.strip()


def extract_full_text(pdf_path: str, max_chars: int = 30000) -> str:
    """Extract full document text, truncated to max_chars."""
    doc = fitz.open(pdf_path)
    try:
        parts: list[str] = []
        total = 0
        for page in doc:
            t = page.get_text("text")
            if total + len(t) > max_chars:
                parts.append(t[: max_chars - total])
                break
            parts.append(t)
            total += len(t)
        return "\n".join(parts).strip()
    finally:
        doc.close()


def extract_nearby_text(
    pdf_path: str,
    page_num: int,
    selected_text: str,
    context_chars: int = 2000,
) -> str:
    """Extract paragraphs near the selected text (context_chars/2 before and after)."""
    page_text = extract_page_text(pdf_path, page_num)
    if not page_text or not selected_text:
        return page_text[:context_chars]

    # Try to locate the selected text in the page (use first 50 chars as anchor)
    anchor = selected_text[:50].strip()
    idx = page_text.find(anchor)
    if idx < 0:
        # Fallback: return the first context_chars of the page
        return page_text[:context_chars]

    half = context_chars // 2
    start = max(0, idx - half)
    end = min(len(page_text), idx + len(selected_text) + half)
    return page_text[start:end].strip()


# ---------------------------------------------------------------------------
# LLM chat call
# ---------------------------------------------------------------------------

async def chat_with_context(
    messages: list[dict],
    engine: TranslationEngine,
    max_tokens: int = 2000,
) -> str:
    """Call an OpenAI-compatible chat completions endpoint."""
    client = get_client()
    response = await client.post(
        f"{engine.base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {engine.api_key.strip()}"},
        json={
            "model": engine.model,
            "messages": messages,
            "temperature": engine.temperature,
            "max_tokens": max_tokens,
        },
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def build_chat_messages(
    user_query: str,
    scope: str,
    paper_title: str,
    selected_text: str,
    nearby_text: str,
    full_text: str,
    annotations: list[dict],
    chat_history: list[dict],
) -> list[dict]:
    """Build a messages list with injected context for the LLM."""

    system = (
        "你是一个学术论文阅读助手。用户正在阅读一篇论文，"
        "请根据提供的上下文回答问题。回答要简洁、准确、有条理。"
        "如果上下文不足以回答，请说明。"
    )

    # Assemble context sections
    ctx = [f"## 当前论文\n{paper_title}"]

    if selected_text:
        ctx.append(f"## 选中文本\n{selected_text}")

    if scope == "paper" and full_text:
        ctx.append(f"## 论文全文（节选）\n{full_text}")
    elif selected_text and nearby_text:
        ctx.append(f"## 选区附近段落\n{nearby_text}")

    if annotations:
        ann_lines = "\n".join(
            f"- [{a.get('kind', '')}] {a.get('text', '')}"
            for a in annotations[:10]
        )
        ctx.append(f"## 用户已有注释\n{ann_lines}")

    system += "\n\n" + "\n\n".join(ctx)

    # Build user message — inline selected text for highest priority
    user_content = user_query
    if selected_text:
        user_content = f"关于以下选中文本：\n\n{selected_text}\n\n---\n\n{user_query}"

    # Build final messages list
    msgs: list[dict] = [{"role": "system", "content": system}]
    for h in chat_history[-10:]:
        msgs.append({"role": h["role"], "content": h["content"]})
    msgs.append({"role": "user", "content": user_content})

    return msgs
