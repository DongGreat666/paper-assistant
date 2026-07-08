"""Reusable web search API for chat, translation, and future tools.

The module is intentionally provider-neutral.  Callers ask for search results,
then decide how to use the returned snippets in their own prompts.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlparse

from config import get_config
from src.core.engine import TranslationEngine
from src.utils.http_client import chat_completions_url, chat_message_content, get_client


AUTO_SEARCH_KEYWORDS = (
    "联网",
    "搜索",
    "搜一下",
    "查一下",
    "查找",
    "网上",
    "网页",
    "最新",
    "最近",
    "今天",
    "现在",
    "当前",
    "新闻",
    "资料",
    "来源",
    "引用",
    "链接",
)


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""


@dataclass(frozen=True)
class SearchPlan:
    should_search: bool
    queries: list[str]
    reason: str = ""


def should_trigger_web_search(query: str) -> bool:
    """Return True when a user query sounds time-sensitive or asks to search."""
    normalized = (query or "").strip().lower()
    if not normalized:
        return False
    english_keywords = (
        "search web",
        "web search",
        "look up",
        "latest",
        "recent",
        "today",
        "current",
        "news",
        "source",
        "citation",
        "url",
    )
    return any(keyword in normalized for keyword in AUTO_SEARCH_KEYWORDS + english_keywords)


async def plan_web_search(
    question: str,
    engine: TranslationEngine,
    *,
    paper_context: str = "",
    chat_history: list[dict] | None = None,
    force_search: bool = False,
) -> SearchPlan:
    """Ask the LLM whether web search is needed and which queries to run."""
    question = (question or "").strip()
    if not question:
        return SearchPlan(False, [], "empty question")

    history_lines = []
    for item in (chat_history or [])[-6:]:
        role = item.get("role", "")
        content = str(item.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            history_lines.append(f"{role}: {content[:600]}")

    hint = "用户已手动开启联网搜索；除非问题完全不需要外部信息，否则应生成搜索 query。" if force_search else (
        "用户没有手动开启联网搜索；只有确实需要外部/最新信息时才搜索。"
    )
    keyword_hint = "用户问题含联网触发词。" if should_trigger_web_search(question) else "用户问题未明显要求联网。"
    system = (
        "你是一个搜索规划器，只输出 JSON，不要输出 Markdown。\n"
        "任务：根据用户问题、论文上下文和聊天历史判断是否需要联网搜索，并生成 1-3 个具体搜索 query。\n"
        "需要搜索的情况：用户问最新/当前/近况/代码/后续工作/引用来源/网页链接/论文外事实，"
        "或问题里的“这个方法/它/现在”等需要结合论文上下文转换成明确搜索词。\n"
        "不需要搜索的情况：论文内容本身足以回答、用户只是要求解释/总结/翻译/改写。\n"
        "输出格式严格为：{\"should_search\": boolean, \"queries\": [string], \"reason\": string}。"
    )
    user = (
        f"联网策略：{hint}\n"
        f"关键词提示：{keyword_hint}\n\n"
        f"用户问题：\n{question}\n\n"
        f"聊天历史：\n{chr(10).join(history_lines) or '无'}\n\n"
        f"论文上下文节选：\n{paper_context[:3000] or '无'}"
    )
    try:
        client = get_client()
        response = await client.post(
            chat_completions_url(engine.base_url),
            headers={"Authorization": f"Bearer {engine.api_key.strip()}"},
            json={
                "model": engine.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0,
                "max_tokens": 350,
            },
        )
        response.raise_for_status()
        content = chat_message_content(response.json())
        data = _parse_json_object(content)
        should_search = bool(data.get("should_search"))
        queries = [
            _clean_text(str(query))
            for query in data.get("queries", [])
            if _clean_text(str(query))
        ][:3]
        if should_search and not queries:
            queries = [question]
        return SearchPlan(
            should_search=should_search and bool(queries),
            queries=queries,
            reason=_clean_text(str(data.get("reason", ""))),
        )
    except Exception as exc:
        if force_search or should_trigger_web_search(question):
            return SearchPlan(True, [question], f"planner failed: {exc}")
        return SearchPlan(False, [], f"planner failed: {exc}")


async def web_search(query: str, max_results: int | None = None) -> list[SearchResult]:
    """Search the web with the configured provider.

    Supported providers:
    - ``duckduckgo``: no key, HTML endpoint fallback.
    - ``brave``: set ``WEB_SEARCH_API_KEY``.
    - ``bing``: set ``WEB_SEARCH_API_KEY``.
    - ``serpapi``: set ``WEB_SEARCH_API_KEY``.
    """
    cfg = get_config()
    query = (query or "").strip()
    if not query:
        return []
    limit = max(1, min(max_results or cfg.web_search_max_results or 5, 10))
    provider = (cfg.web_search_provider or "duckduckgo").strip().lower()
    if provider == "brave":
        return await _search_brave(query, limit, cfg.web_search_api_key)
    if provider == "bing":
        return await _search_bing(query, limit, cfg.web_search_api_key)
    if provider == "serpapi":
        return await _search_serpapi(query, limit, cfg.web_search_api_key)
    return await _search_duckduckgo(query, limit)


async def web_search_many(queries: list[str], max_results: int | None = None) -> list[SearchResult]:
    """Run multiple searches and merge duplicate URLs while preserving order."""
    merged: list[SearchResult] = []
    seen: set[str] = set()
    for query in queries:
        for result in await web_search(query, max_results=max_results):
            key = result.url.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(result)
    cfg = get_config()
    limit = max(1, min(max_results or cfg.web_search_max_results or 5, 10))
    return merged[:limit]


def format_search_context(results: list[SearchResult]) -> str:
    """Format search results as compact prompt context with source URLs."""
    if not results:
        return ""
    lines = ["## 联网搜索结果"]
    for index, result in enumerate(results, start=1):
        lines.append(
            "\n".join(
                part
                for part in (
                    f"[{index}] {result.title}",
                    f"URL: {result.url}",
                    f"摘要: {result.snippet}" if result.snippet else "",
                )
                if part
            )
        )
    return "\n\n".join(lines)


async def _search_brave(query: str, limit: int, api_key: str) -> list[SearchResult]:
    if not api_key:
        return []
    client = get_client()
    response = await client.get(
        "https://api.search.brave.com/res/v1/web/search",
        headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
        params={"q": query, "count": limit},
    )
    response.raise_for_status()
    web = response.json().get("web", {})
    return [
        SearchResult(
            title=_clean_text(item.get("title", "")),
            url=item.get("url", ""),
            snippet=_clean_text(item.get("description", "")),
        )
        for item in web.get("results", [])[:limit]
        if item.get("url")
    ]


async def _search_bing(query: str, limit: int, api_key: str) -> list[SearchResult]:
    if not api_key:
        return []
    client = get_client()
    response = await client.get(
        "https://api.bing.microsoft.com/v7.0/search",
        headers={"Ocp-Apim-Subscription-Key": api_key},
        params={"q": query, "count": limit, "responseFilter": "Webpages"},
    )
    response.raise_for_status()
    values = response.json().get("webPages", {}).get("value", [])
    return [
        SearchResult(
            title=_clean_text(item.get("name", "")),
            url=item.get("url", ""),
            snippet=_clean_text(item.get("snippet", "")),
        )
        for item in values[:limit]
        if item.get("url")
    ]


async def _search_serpapi(query: str, limit: int, api_key: str) -> list[SearchResult]:
    if not api_key:
        return []
    client = get_client()
    response = await client.get(
        "https://serpapi.com/search.json",
        params={"engine": "google", "q": query, "api_key": api_key, "num": limit},
    )
    response.raise_for_status()
    values = response.json().get("organic_results", [])
    return [
        SearchResult(
            title=_clean_text(item.get("title", "")),
            url=item.get("link", ""),
            snippet=_clean_text(item.get("snippet", "")),
        )
        for item in values[:limit]
        if item.get("link")
    ]


class _DuckDuckGoHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchResult] = []
        self._in_title = False
        self._in_snippet = False
        self._current_title: list[str] = []
        self._current_url = ""
        self._current_snippet: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        classes = attr.get("class", "")
        if tag == "a" and "result__a" in classes:
            self._flush()
            self._in_title = True
            self._current_title = []
            self._current_url = _decode_duckduckgo_url(attr.get("href", ""))
        elif tag in {"a", "div"} and "result__snippet" in classes:
            self._in_snippet = True
            self._current_snippet = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_title:
            self._in_title = False
        elif tag in {"a", "div"} and self._in_snippet:
            self._in_snippet = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._current_title.append(data)
        elif self._in_snippet:
            self._current_snippet.append(data)

    def close(self) -> None:
        super().close()
        self._flush()

    def _flush(self) -> None:
        title = _clean_text(" ".join(self._current_title))
        url = self._current_url.strip()
        if title and url and all(existing.url != url for existing in self.results):
            self.results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=_clean_text(" ".join(self._current_snippet)),
                )
            )
        self._current_title = []
        self._current_url = ""
        self._current_snippet = []


async def _search_duckduckgo(query: str, limit: int) -> list[SearchResult]:
    client = get_client()
    response = await client.post(
        "https://html.duckduckgo.com/html/",
        data={"q": query},
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    parser = _DuckDuckGoHTMLParser()
    parser.feed(response.text)
    parser.close()
    return parser.results[:limit]


def _decode_duckduckgo_url(raw_url: str) -> str:
    raw_url = html.unescape(raw_url or "")
    parsed = urlparse(raw_url)
    if parsed.query:
        uddg = parse_qs(parsed.query).get("uddg")
        if uddg:
            return unquote(uddg[0])
    return raw_url


def _clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _parse_json_object(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return {}
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    return data if isinstance(data, dict) else {}
