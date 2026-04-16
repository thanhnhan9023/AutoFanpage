import json
import pytest

from autofanpage.merge import merge_sources


@pytest.fixture
def run_dir(tmp_path):
    (tmp_path / "youtube_results.json").write_text(json.dumps({
        "source": "youtube",
        "fetched_at": "2026-04-15T06:00:00+07:00",
        "items": [{
            "title": "yt1", "url": "https://youtu.be/1", "video_id": "1",
            "channel": "c", "views": 150000, "subscribers": 20000,
            "published_at": "2026-04-10T00:00:00Z",
        }],
    }))
    (tmp_path / "hackernews_results.json").write_text(json.dumps({
        "source": "hackernews",
        "fetched_at": "2026-04-15T06:00:00+07:00",
        "items": [{
            "title": "hn1", "url": "https://hn1",
            "points": 300, "by": "u", "descendants": 40,
            "created_at": "2026-04-14T00:00:00Z",
            "hn_url": "https://news.ycombinator.com/item?id=1",
        }],
    }))
    (tmp_path / "perplexity_results.json").write_text(json.dumps({
        "source": "perplexity",
        "fetched_at": "2026-04-15T06:00:00+07:00",
        "news": [{"title": "n1", "url": "https://n1", "summary": "", "source": "n.com"}],
        "reports": [{"title": "r1", "url": "https://r1", "summary": "", "source": "r.com"}],
        "twitter": [{"title": "t1", "url": "https://x.com/u/1", "summary": "", "source": "x.com"}],
    }))
    (tmp_path / "reddit_results.json").write_text(json.dumps({
        "source": "reddit",
        "fetched_at": "2026-04-15T06:00:00+07:00",
        "items": [{
            "title": "rd1", "url": "https://reddit.com/r/x/comments/1",
            "subreddit": "ChatGPT", "score": 800, "num_comments": 50,
            "author": "u", "permalink": "/r/x/1", "created_at": "2026-04-14T00:00:00Z",
            "is_self": False, "external_url": "",
        }],
    }))
    return tmp_path


def test_merge_combines_all_sources(run_dir):
    out = merge_sources(
        profile="page_vn_ai", topic="AI", language="vi",
        artifacts={
            "youtube": run_dir / "youtube_results.json",
            "hackernews": run_dir / "hackernews_results.json",
            "perplexity": run_dir / "perplexity_results.json",
            "reddit": run_dir / "reddit_results.json",
        },
        failures={},
        max_per_platform=12,
    )
    platforms_in_urls = {u["platform"] for u in out["urls"]}
    assert "youtube" in platforms_in_urls
    assert "hackernews" in platforms_in_urls
    assert "reddit" in platforms_in_urls
    assert "perplexity" in platforms_in_urls
    assert out["sources_succeeded"] == [
        "youtube", "hackernews", "perplexity", "reddit",
    ]
    assert out["sources_failed"] == []
    assert out["counts_per_platform"] == {
        "youtube": 1, "hackernews": 1, "perplexity": 3, "reddit": 1,
    }
    assert len(out["urls"]) == 6


def test_merge_records_failures(run_dir):
    out = merge_sources(
        profile="p", topic="T", language="vi",
        artifacts={"youtube": run_dir / "youtube_results.json"},
        failures={"reddit": "timeout after 3 retries"},
        max_per_platform=12,
    )
    assert out["sources_succeeded"] == ["youtube"]
    assert out["sources_failed"] == [{"source": "reddit", "error": "timeout after 3 retries"}]


def test_merge_uses_score_field_uniformly(run_dir):
    out = merge_sources(
        profile="p", topic="T", language="vi",
        artifacts={
            "youtube": run_dir / "youtube_results.json",
            "hackernews": run_dir / "hackernews_results.json",
            "reddit": run_dir / "reddit_results.json",
        },
        failures={},
        max_per_platform=12,
    )
    by_plat = {u["platform"]: u for u in out["urls"]}
    assert by_plat["youtube"]["score_or_views"] == 150000
    assert by_plat["hackernews"]["score_or_views"] == 300
    assert by_plat["reddit"]["score_or_views"] == 800


def test_merge_deduplicates_by_url(run_dir):
    (run_dir / "hackernews_results.json").write_text(json.dumps({
        "source": "hackernews",
        "fetched_at": "2026-04-15T06:00:00+07:00",
        "items": [{
            "title": "same as yt1", "url": "https://youtu.be/1",
            "points": 500, "by": "u", "descendants": 10,
            "created_at": "2026-04-14T00:00:00Z",
            "hn_url": "https://news.ycombinator.com/item?id=2",
        }],
    }))
    out = merge_sources(
        profile="p", topic="T", language="vi",
        artifacts={
            "youtube": run_dir / "youtube_results.json",
            "hackernews": run_dir / "hackernews_results.json",
        },
        failures={},
        max_per_platform=12,
    )
    urls = [u["url"] for u in out["urls"]]
    assert urls.count("https://youtu.be/1") == 1


def test_merge_caps_per_platform(run_dir):
    (run_dir / "youtube_results.json").write_text(json.dumps({
        "source": "youtube",
        "fetched_at": "2026-04-15T06:00:00+07:00",
        "items": [
            {"title": f"yt{i}", "url": f"https://youtu.be/{i}", "video_id": str(i),
             "channel": "c", "views": 200000 - i * 1000, "subscribers": 10000,
             "published_at": "2026-04-10T00:00:00Z"}
            for i in range(5)
        ],
    }))
    out = merge_sources(
        profile="p", topic="T", language="vi",
        artifacts={"youtube": run_dir / "youtube_results.json"},
        failures={},
        max_per_platform=1,
    )
    assert out["counts_per_platform"]["youtube"] == 1
    assert len(out["urls"]) == 1
    assert out["urls"][0]["score_or_views"] == 200000
