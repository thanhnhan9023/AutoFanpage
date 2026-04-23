import pytest
from autofanpage.schemas import validate
from autofanpage.errors import SchemaError
from autofanpage.schemas import (
    INSIGHTS_SCHEMA,
    REVIEWED_INSIGHTS_SCHEMA,
    PUBLISH_RESULTS_SCHEMA,
    POSTS_SCHEMA,
)


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


def test_validate_profile_accepts_tavily_backend():
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
            "perplexity": {"enabled": False, "backend": "tavily"},
            "twitter_via_perplexity": {"enabled": False},
            "reddit": {"enabled": False, "subreddits": [], "min_score": 0,
                       "time_filter": "week", "top_per_sub": 0},
            "hackernews": {"enabled": True, "min_points": 10},
        },
    }
    validate("profile", valid)


def test_validate_profile_accepts_perplexity_backend():
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
            "perplexity": {"enabled": False, "backend": "perplexity"},
            "twitter_via_perplexity": {"enabled": False},
            "reddit": {"enabled": False, "subreddits": [], "min_score": 0,
                       "time_filter": "week", "top_per_sub": 0},
            "hackernews": {"enabled": True, "min_points": 10},
        },
    }
    validate("profile", valid)


def test_validate_profile_rejects_unknown_perplexity_backend():
    invalid = {
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
            "perplexity": {"enabled": False, "backend": "unknown"},
            "twitter_via_perplexity": {"enabled": False},
            "reddit": {"enabled": False, "subreddits": [], "min_score": 0,
                       "time_filter": "week", "top_per_sub": 0},
            "hackernews": {"enabled": True, "min_points": 10},
        },
    }
    with pytest.raises(SchemaError):
        validate("profile", invalid)


def test_validate_profile_accepts_facebook_page_latest_source():
    valid = {
        "name": "page_hourly_repost",
        "page_id": "123",
        "access_token_ref": "secret:fb_test",
        "topic": "AI",
        "language": "vi",
        "post_times": ["08:00", "12:00", "16:00", "20:00"],
        "timezone": "Asia/Ho_Chi_Minh",
        "min_posts_required": 1,
        "max_sources_per_platform": 12,
        "sources": {
            "youtube": {"enabled": False},
            "perplexity": {"enabled": False},
            "twitter_via_perplexity": {"enabled": False},
            "reddit": {"enabled": False, "subreddits": [], "min_score": 0,
                       "time_filter": "week", "top_per_sub": 0},
            "hackernews": {"enabled": False, "min_points": 0},
            "facebook_page_latest": {
                "enabled": True,
                "backend": "browser_use_mcp",
                "page_url": "https://www.facebook.com/0xSojalSec"
            },
        },
        "writing": {"style": "ai5phut"},
    }
    validate("profile", valid)


def test_validate_profile_rejects_unknown_facebook_page_latest_backend():
    invalid = {
        "name": "page_hourly_repost",
        "page_id": "123",
        "access_token_ref": "secret:fb_test",
        "topic": "AI",
        "language": "vi",
        "post_times": ["08:00", "12:00", "16:00", "20:00"],
        "timezone": "Asia/Ho_Chi_Minh",
        "min_posts_required": 1,
        "max_sources_per_platform": 12,
        "sources": {
            "youtube": {"enabled": False},
            "perplexity": {"enabled": False},
            "twitter_via_perplexity": {"enabled": False},
            "reddit": {"enabled": False, "subreddits": [], "min_score": 0,
                       "time_filter": "week", "top_per_sub": 0},
            "hackernews": {"enabled": False, "min_points": 0},
            "facebook_page_latest": {
                "enabled": True,
                "backend": "selenium",
                "page_url": "https://www.facebook.com/0xSojalSec"
            },
        },
    }
    with pytest.raises(SchemaError):
        validate("profile", invalid)


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


def test_insights_schema_requires_all_four_keys():
    ok = {
        "overview": "short paragraph",
        "pain_points": ["p1", "p2"],
        "insights": ["i1", "i2"],
        "gap_topics": ["g1"],
        "source_urls": ["https://example.com/a"],
        "language": "vi",
    }
    validate("insights", ok)

    bad = dict(ok)
    bad.pop("insights")
    with pytest.raises(Exception):
        validate("insights", bad)


def test_insights_schema_rejects_non_string_items():
    bad = {
        "overview": "x",
        "pain_points": ["p"],
        "insights": [123],
        "gap_topics": [],
        "source_urls": [],
        "language": "vi",
    }
    with pytest.raises(Exception):
        validate("insights", bad)


def test_reviewed_insights_schema_total_must_equal_sum():
    ok = {
        "approved": [
            {
                "insight": "AI usage climbing 40% in SMBs",
                "scores": {"relevance": 5, "novelty": 4, "viral": 4, "actionable": 3},
                "total": 16,
                "suggested_post_type": "news",
                "hook_angle": "40% jump in 6 months",
                "source_url": "https://example.com/a",
            }
        ],
        "rejected": [
            {"insight": "too generic", "total": 9, "reason": "below threshold"},
        ],
    }
    validate("reviewed_insights", ok)


def test_reviewed_insights_rejects_bad_post_type():
    bad = {
        "approved": [
            {
                "insight": "x",
                "scores": {"relevance": 1, "novelty": 1, "viral": 1, "actionable": 1},
                "total": 4,
                "suggested_post_type": "meme",
                "hook_angle": "",
                "source_url": "",
            }
        ],
        "rejected": [],
    }
    with pytest.raises(Exception):
        validate("reviewed_insights", bad)


def test_posts_schema_allows_null_content_for_unfilled_slots():
    ok = {
        "posts": [
            {"time": "08:00", "type": "news", "content": "...", "first_comment": "..."},
            {"time": "12:00", "type": "guide", "content": None, "first_comment": None},
            {"time": "16:00", "type": "opinion", "content": "...", "first_comment": "..."},
            {"time": "20:00", "type": "case_study", "content": None, "first_comment": None},
        ],
        "language": "vi",
    }
    validate("posts", ok)


def test_posts_schema_requires_exactly_four_posts_with_correct_types():
    bad = {
        "posts": [
            {"time": "08:00", "type": "news", "content": "x", "first_comment": "x"},
            {"time": "12:00", "type": "news", "content": None, "first_comment": None},
            {"time": "16:00", "type": "opinion", "content": None, "first_comment": None},
            {"time": "20:00", "type": "case_study", "content": None, "first_comment": None},
        ],
        "language": "vi",
    }
    validate("posts", bad)


def test_publish_results_schema_accepts_valid():
    validate("publish_results", {
        "page": "page_test",
        "date": "2026-04-16",
        "posts": [
            {"time": "08:00", "type": "news", "post_id": "123_456",
             "comment_id": "123_789", "status": 200},
        ],
    })


def test_publish_results_schema_rejects_missing_page():
    with pytest.raises(Exception):
        validate("publish_results", {
            "date": "2026-04-16",
            "posts": [],
        })


def test_publish_results_allows_null_ids_for_failed_slots():
    validate("publish_results", {
        "page": "page_test",
        "date": "2026-04-16",
        "posts": [
            {"time": "08:00", "type": "news", "post_id": None,
             "comment_id": None, "status": 400},
        ],
    })
