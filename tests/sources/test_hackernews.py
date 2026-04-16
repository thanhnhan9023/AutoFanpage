import json
from pathlib import Path

import pytest
from autofanpage.sources.hackernews import (
    filter_and_rank, matches_topic, to_result,
)


@pytest.fixture
def items(fixtures_dir):
    return json.loads((fixtures_dir / "hn_items.json").read_text())


def test_matches_topic_substring_any_word():
    assert matches_topic("GPT-5 released today", "AI automation") is False
    assert matches_topic("New AI chip beats H100", "AI automation") is True
    assert matches_topic("automated workflow wins", "AI automation") is True


def test_matches_topic_case_insensitive():
    assert matches_topic("OPENAI ships GPT", "openai") is True


def test_filter_rejects_low_score(items):
    out = filter_and_rank(items, topic="AI", min_points=100, limit=10)
    ids = [i["id"] for i in out]
    assert 2 not in ids  # score 80 < 100


def test_filter_rejects_non_story(items):
    out = filter_and_rank(items, topic="hiring", min_points=0, limit=10)
    ids = [i["id"] for i in out]
    assert 5 not in ids  # type=job


def test_filter_requires_topic_match(items):
    out = filter_and_rank(items, topic="GPT", min_points=0, limit=10)
    titles = [i["title"] for i in out]
    assert "GPT-5 released" in titles
    assert "Unrelated story" not in titles


def test_sorted_by_score_desc(items):
    out = filter_and_rank(items, topic="AI OR GPT", min_points=0, limit=10)
    scores = [i["score"] for i in out]
    assert scores == sorted(scores, reverse=True)


def test_limit(items):
    out = filter_and_rank(items, topic="a", min_points=0, limit=1)
    assert len(out) == 1


def test_to_result_has_required_shape():
    item = {"id": 42, "title": "t", "url": "https://x.com",
            "score": 150, "by": "u", "descendants": 9, "time": 1744156800}
    r = to_result(item)
    assert r["title"] == "t"
    assert r["url"] == "https://x.com"
    assert r["points"] == 150
    assert r["by"] == "u"
    assert r["descendants"] == 9
    assert r["hn_url"] == "https://news.ycombinator.com/item?id=42"
    assert r["created_at"].startswith("2025-") or r["created_at"].startswith("2024-")


def test_to_result_ask_hn_uses_hn_url_as_url():
    item = {"id": 2, "title": "Ask HN", "url": None,
            "score": 80, "by": "u", "descendants": 5, "time": 1744156800}
    r = to_result(item)
    assert r["url"] == r["hn_url"]
