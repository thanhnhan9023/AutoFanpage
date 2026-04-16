import json
import pytest

from autofanpage.sources.perplexity import parse_completion, shape_items


@pytest.fixture
def resp(fixtures_dir):
    return json.loads((fixtures_dir / "perplexity_response.json").read_text())


def test_parse_completion_splits_numbered_lines(resp):
    items = parse_completion(resp)
    assert len(items) == 3
    assert "GPT-5" in items[0]["title"]
    assert items[0]["url"] == "https://openai.com/blog/gpt5"
    assert items[1]["url"] == "https://anthropic.com/claude4"
    assert items[2]["url"] == "https://techcrunch.com/ai-funding"


def test_parse_completion_uses_hostname_as_source(resp):
    items = parse_completion(resp)
    assert items[0]["source"] == "openai.com"
    assert items[1]["source"] == "anthropic.com"
    assert items[2]["source"] == "techcrunch.com"


def test_parse_completion_handles_missing_citations():
    out = parse_completion({
        "choices": [{"message": {"content": "1. foo\n2. bar"}}],
    })
    assert out == []


def test_shape_items_dedupes_by_url():
    raw = [
        {"title": "a", "url": "https://x/1", "summary": "", "source": "x"},
        {"title": "b", "url": "https://x/1", "summary": "", "source": "x"},
        {"title": "c", "url": "https://x/2", "summary": "", "source": "x"},
    ]
    out = shape_items(raw, limit=10)
    urls = [i["url"] for i in out]
    assert urls == ["https://x/1", "https://x/2"]


def test_shape_items_respects_limit():
    raw = [
        {"title": str(i), "url": f"https://x/{i}", "summary": "", "source": "x"}
        for i in range(5)
    ]
    assert len(shape_items(raw, limit=3)) == 3
