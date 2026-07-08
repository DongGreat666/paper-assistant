from src.core.web_search import (
    SearchResult,
    _parse_json_object,
    format_search_context,
    should_trigger_web_search,
)


def test_should_trigger_web_search_for_chinese_keywords():
    assert should_trigger_web_search("帮我查一下这篇论文最新代码")
    assert should_trigger_web_search("联网搜索一下 LDM")
    assert should_trigger_web_search("现在最常用的扩散模型是什么")


def test_should_not_trigger_web_search_for_plain_paper_question():
    assert not should_trigger_web_search("解释一下这篇论文的 latent space")


def test_format_search_context_includes_urls():
    context = format_search_context([
        SearchResult(title="Example", url="https://example.com", snippet="A short snippet")
    ])

    assert "## 联网搜索结果" in context
    assert "Example" in context
    assert "https://example.com" in context
    assert "A short snippet" in context


def test_parse_json_object_from_markdown_fence():
    data = _parse_json_object(
        '```json\n{"should_search": true, "queries": ["latent diffusion current"], "reason": "fresh"}\n```'
    )

    assert data["should_search"] is True
    assert data["queries"] == ["latent diffusion current"]
