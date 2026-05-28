"""Chat streaming and context helpers for the home page."""

from src.core.engine import TranslationEngine
from src.utils.http_client import chat_completions_url, get_client

MAX_CONTEXT_CHARS = 18000


def trim_context(text: str) -> str:
    """Trim paper context to fit within token limits, keeping head and tail."""
    text = text.strip()
    if len(text) <= MAX_CONTEXT_CHARS:
        return text
    head = text[: int(MAX_CONTEXT_CHARS * 0.65)]
    tail = text[-int(MAX_CONTEXT_CHARS * 0.35) :]
    return f"{head}\n\n...[中间内容已省略]...\n\n{tail}"


async def stream_chat_completion(
    messages: list[dict],
    engine: TranslationEngine,
    max_tokens: int = 1800,
):
    """Stream chat completion tokens via SSE. Yields partial text chunks."""
    import json as _json

    client = get_client()
    async with client.stream(
        "POST",
        chat_completions_url(engine.base_url),
        headers={"Authorization": f"Bearer {engine.api_key.strip()}"},
        json={
            "model": engine.model,
            "messages": messages,
            "temperature": engine.temperature,
            "max_tokens": max_tokens,
            "stream": True,
        },
    ) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload.strip() == "[DONE]":
                break
            try:
                chunk = _json.loads(payload)
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    yield content
            except (_json.JSONDecodeError, IndexError, KeyError):
                continue
