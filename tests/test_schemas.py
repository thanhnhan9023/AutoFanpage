import pytest
from autofanpage.schemas import validate
from autofanpage.errors import SchemaError


def test_validate_profile_accepts_valid_payload():
    valid = {
        "name": "page_test",
        "page_id": "123",
        "access_token_ref": "secret:fb_test",
        "topic": "AI",
        "language": "en",
        "post_times": ["08:00", "12:00", "16:00", "20:00"],
        "timezone": "UTC",
        "min_posts_required": 2,
        "max_sources_per_platform": 12,
        "sources": {
            "youtube": {"enabled": False},
            "perplexity": {"enabled": False},
            "twitter_via_perplexity": {"enabled": False},
            "reddit": {"enabled": False, "subreddits": [], "min_score": 0,
                       "time_filter": "week", "top_per_sub": 0},
            "hackernews": {"enabled": True, "min_points": 10},
        },
    }
    validate("profile", valid)


def test_validate_profile_rejects_missing_page_id():
    invalid = {"name": "x", "post_times": ["08:00", "12:00", "16:00", "20:00"]}
    with pytest.raises(SchemaError) as exc:
        validate("profile", invalid)
    assert exc.value.artifact == "profile"
    assert any("page_id" in v for v in exc.value.violations)


def test_validate_hackernews_results_requires_wrapped_object():
    with pytest.raises(SchemaError):
        validate("hackernews_results", [{"title": "wrong shape"}])
    validate("hackernews_results", {
        "source": "hackernews",
        "fetched_at": "2026-04-15T00:00:00Z",
        "items": [],
    })


def test_validate_hackernews_item_requires_points():
    item = {"title": "x", "url": "http://x", "by": "u", "descendants": 0,
            "created_at": "2026-04-15T00:00:00Z", "hn_url": "http://h"}
    with pytest.raises(SchemaError):
        validate("hackernews_results", {
            "source": "hackernews",
            "fetched_at": "2026-04-15T00:00:00Z",
            "items": [item],
        })


from autofanpage.schemas import (
    YOUTUBE_RESULTS_SCHEMA,
    PERPLEXITY_RESULTS_SCHEMA,
    REDDIT_RESULTS_SCHEMA,
    MERGED_SOURCES_SCHEMA,
)


def test_youtube_schema_accepts_valid():
    validate("youtube_results", {
        "source": "youtube",
        "fetched_at": "2026-04-15T06:00:00+07:00",
        "items": [{
            "title": "t", "url": "https://youtu.be/x",
            "video_id": "x", "channel": "c",
            "views": 150000, "subscribers": 50000,
            "published_at": "2026-04-10T00:00:00Z",
        }],
    })


def test_youtube_schema_rejects_missing_views():
    with pytest.raises(SchemaError):
        validate("youtube_results", {
            "source": "youtube",
            "fetched_at": "2026-04-15T06:00:00+07:00",
            "items": [{"title": "t", "url": "u", "video_id": "x",
                       "channel": "c", "published_at": "..."}],
        })


def test_perplexity_schema_accepts_valid():
    validate("perplexity_results", {
        "source": "perplexity",
        "fetched_at": "2026-04-15T06:00:00+07:00",
        "news": [{"title": "t", "url": "https://a", "summary": "s", "source": "a.com"}],
        "reports": [{"title": "t", "url": "https://b", "summary": "s", "source": "b.com"}],
        "twitter": [{"title": "t", "url": "https://x.com/u/status/1",
                     "summary": "s", "source": "x.com"}],
    })


def test_reddit_schema_accepts_valid():
    validate("reddit_results", {
        "source": "reddit",
        "fetched_at": "2026-04-15T06:00:00+07:00",
        "items": [{
            "title": "t", "url": "https://reddit.com/r/x/comments/1",
            "subreddit": "ChatGPT", "score": 500,
            "num_comments": 120, "author": "u",
            "permalink": "/r/ChatGPT/comments/1",
            "created_at": "2026-04-12T10:00:00Z",
            "is_self": False, "external_url": "https://ext.com/a",
        }],
    })


def test_merged_sources_schema_accepts_valid():
    validate("merged_sources", {
        "profile": "page_vn_ai",
        "topic": "AI automation business",
        "language": "vi",
        "fetched_at": "2026-04-15T06:00:00+07:00",
        "sources_succeeded": ["youtube", "hackernews"],
        "sources_failed": [{"source": "reddit", "error": "..."}],
        "counts_per_platform": {"youtube": 1, "hackernews": 1},
        "urls": [{
            "url": "https://u", "title": "t", "platform": "youtube",
            "score_or_views": 150000, "created_at": "2026-04-10T00:00:00Z",
        }],
    })
