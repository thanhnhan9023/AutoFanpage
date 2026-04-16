import json
import pytest

from autofanpage.sources.reddit import filter_and_rank, to_result


@pytest.fixture
def listing(fixtures_dir):
    return json.loads((fixtures_dir / "reddit_listing.json").read_text())


def test_filter_rejects_stickied(listing):
    out = filter_and_rank(listing, min_score=0, top_n=10)
    assert all(not (p.get("stickied")) for p in out)


def test_filter_rejects_nsfw(listing):
    out = filter_and_rank(listing, min_score=0, top_n=10)
    assert all(not p.get("over_18") for p in out)


def test_filter_rejects_below_min_score(listing):
    out = filter_and_rank(listing, min_score=100, top_n=10)
    titles = [p["title"] for p in out]
    assert "AI agents beat humans at coding" not in titles


def test_filter_sorts_by_score_desc(listing):
    out = filter_and_rank(listing, min_score=0, top_n=10)
    scores = [p["score"] for p in out]
    assert scores == sorted(scores, reverse=True)


def test_filter_respects_top_n(listing):
    out = filter_and_rank(listing, min_score=0, top_n=1)
    assert len(out) == 1


def test_to_result_shape():
    post = {
        "title": "t", "subreddit": "ChatGPT",
        "score": 500, "num_comments": 120, "author": "u",
        "permalink": "/r/ChatGPT/comments/1/t/",
        "url": "https://ext.com/a",
        "created_utc": 1744156800, "is_self": False,
    }
    r = to_result(post)
    assert r["title"] == "t"
    assert r["url"] == "https://reddit.com/r/ChatGPT/comments/1/t/"
    assert r["external_url"] == "https://ext.com/a"
    assert r["subreddit"] == "ChatGPT"
    assert r["score"] == 500
    assert r["is_self"] is False
    assert r["created_at"].startswith("202")
