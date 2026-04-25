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


def test_validate_profile_rejects_unknown_writing_style():
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
        },
        "writing": {"style": "other"},
    }
    with pytest.raises(SchemaError):
        validate("profile", invalid)


def test_validate_profile_accepts_hourly_review_writer_fields():
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
                "page_url": "https://www.facebook.com/0xSojalSec"
            },
        },
        "writing": {
            "style": "ai5phut",
            "review_model": "minimax/MiniMax-M2.7",
            "review_api_key_ref": "secret:writer_gateway_key",
            "review_max_rounds": 3,
        },
    }
    validate("profile", valid)


def test_validate_profile_accepts_useapi_image_block():
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
                "page_url": "https://www.facebook.com/0xSojalSec"
            },
        },
        "publishing": {
            "backend": "mixpost_ui",
            "mixpost": {
                "base_url": "https://mixpost.example.test",
                "storage_state_path": "/tmp/state.json",
                "headless": True,
            },
            "images": {
                "enabled": True,
                "provider": "useapi_google_flow",
                "fallback_provider": "local_playwright_card",
                "useapi_base_url": "https://api.useapi.net",
                "useapi_token_ref": "secret:useapi_token",
                "google_flow_account_ref": "secret:useapi_google_flow_account",
                "capsolver_api_key_ref": "secret:capsolver_api_key",
                "require_image_for_publish": True,
                "overlay_mode": "none",
                "candidate_count": 4,
                "canvas": {
                    "width": 1080,
                    "height": 1350,
                    "theme": "ai5phut",
                },
            },
        },
    }
    validate("profile", valid)


def test_validate_profile_accepts_zai_image_fallback_settings():
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
                "page_url": "https://www.facebook.com/0xSojalSec"
            },
        },
        "publishing": {
            "backend": "mixpost_ui",
            "mixpost": {
                "base_url": "https://mixpost.example.test",
                "storage_state_path": "/tmp/state.json",
                "headless": True,
            },
            "images": {
                "enabled": True,
                "provider": "useapi_google_flow",
                "fallback_provider": "zai_glm_image",
                "useapi_base_url": "https://api.useapi.net",
                "useapi_token_ref": "secret:useapi_token",
                "zai_api_key_ref": "secret:zai_api_key",
                "zai_model": "glm-image",
                "zai_quality": "standard",
                "require_image_for_publish": True,
                "overlay_mode": "none",
                "candidate_count": 4,
                "canvas": {
                    "width": 1080,
                    "height": 1350,
                    "theme": "ai5phut",
                },
            },
        },
    }
    validate("profile", valid)


def test_validate_profile_accepts_codex_imagen_fallback_settings():
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
                "page_url": "https://www.facebook.com/0xSojalSec"
            },
        },
        "publishing": {
            "backend": "mixpost_ui",
            "mixpost": {
                "base_url": "https://mixpost.example.test",
                "storage_state_path": "/tmp/state.json",
                "headless": True,
            },
            "images": {
                "enabled": True,
                "provider": "useapi_google_flow",
                "fallback_provider": "codex_imagen_oauth",
                "useapi_base_url": "https://api.useapi.net",
                "useapi_token_ref": "secret:useapi_token",
                "codex_imagen_script_path": "/tmp/codex-imagen/scripts/codex-imagen.mjs",
                "codex_auth_json_path": "~/.codex/auth.json",
                "codex_timeout_seconds": 300,
                "codex_model": "gpt-5.4",
                "require_image_for_publish": True,
                "overlay_mode": "none",
                "candidate_count": 4,
                "canvas": {
                    "width": 1080,
                    "height": 1350,
                    "theme": "ai5phut",
                },
            },
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


def test_validate_post_assets_accepts_valid_payload():
    validate("post_assets", {
        "page": "page_test",
        "provider": "mixed",
        "date": "2026-04-20",
        "assets": [
            {
                "time": "08:00",
                "type": "news",
                "status": "ok",
                "provider": "local_playwright_card",
                "image_prompt": "A clean editorial image about AI automation",
                "job_id": None,
                "raw_image_url": None,
                "raw_image_path": None,
                "final_image_path": "assets/08-00-selected.png",
                "selected_candidate_index": None,
                "candidates": [],
                "error": "fallback from primary provider",
            },
        ],
    })


def test_validate_post_assets_accepts_zai_provider():
    validate("post_assets", {
        "page": "page_test",
        "provider": "zai_glm_image",
        "date": "2026-04-20",
        "assets": [
            {
                "time": "08:00",
                "type": "news",
                "status": "ok",
                "provider": "zai_glm_image",
                "image_prompt": "A clean editorial image about AI automation",
                "job_id": None,
                "raw_image_url": "https://cdn.z.ai/out.png",
                "raw_image_path": "assets/08-00-raw-zai.png",
                "final_image_path": "assets/08-00-selected.png",
                "selected_candidate_index": None,
                "candidates": [],
                "error": "fallback from primary provider",
            },
        ],
    })


def test_validate_post_assets_accepts_codex_imagen_provider():
    validate("post_assets", {
        "page": "page_test",
        "provider": "codex_imagen_oauth",
        "date": "2026-04-20",
        "assets": [
            {
                "time": "08:00",
                "type": "news",
                "status": "ok",
                "provider": "codex_imagen_oauth",
                "image_prompt": "A clean editorial image about AI automation",
                "job_id": None,
                "raw_image_url": None,
                "raw_image_path": "assets/08-00-raw-codex.png",
                "final_image_path": "assets/08-00-selected.png",
                "selected_candidate_index": None,
                "candidates": [],
                "error": "fallback from primary provider",
            },
        ],
    })


def test_latest_source_post_schema_accepts_valid():
    validate("latest_source_post", {
        "source_page_url": "https://www.facebook.com/0xSojalSec",
        "source_post_id": "1234567890",
        "source_post_url": "https://www.facebook.com/0xSojalSec/posts/1234567890",
        "author": "0xSojalSec",
        "published_at": "2026-04-15T06:00:00+07:00",
        "published_at_resolved": "2026-04-15T06:00:00+07:00",
        "content_text": "Latest post text",
        "media_urls": ["https://example.com/image.jpg"],
        "backend": "browser_use_mcp",
        "fetched_at": "2026-04-15T06:05:00+07:00",
    })


def test_latest_source_post_schema_accepts_legacy_shape_without_published_at_resolved():
    validate("latest_source_post", {
        "source_page_url": "https://www.facebook.com/0xSojalSec",
        "source_post_id": "1234567890",
        "source_post_url": "https://www.facebook.com/0xSojalSec/posts/1234567890",
        "author": "0xSojalSec",
        "published_at": "2026-04-15T06:00:00+07:00",
        "content_text": "Latest post text",
        "media_urls": ["https://example.com/image.jpg"],
        "backend": "browser_use_mcp",
        "fetched_at": "2026-04-15T06:05:00+07:00",
    })


def test_latest_source_post_schema_rejects_missing_required_field():
    with pytest.raises(SchemaError):
        validate("latest_source_post", {
            "source_page_url": "https://www.facebook.com/0xSojalSec",
            "source_post_id": "1234567890",
            "source_post_url": "https://www.facebook.com/0xSojalSec/posts/1234567890",
            "author": "0xSojalSec",
            "published_at": "2026-04-15T06:00:00+07:00",
            "published_at_resolved": "2026-04-15T06:00:00+07:00",
            "media_urls": ["https://example.com/image.jpg"],
            "backend": "browser_use_mcp",
            "fetched_at": "2026-04-15T06:05:00+07:00",
        })


def test_repost_decision_schema_accepts_publish_with_selected_post():
    validate("repost_decision", {
        "action": "publish",
        "reason": "publish_today_newest",
        "selected_post": {
            "source_page_url": "https://www.facebook.com/0xSojalSec",
            "source_post_id": "1234567890",
            "source_post_url": "https://www.facebook.com/0xSojalSec/posts/1234567890",
            "author": "0xSojalSec",
            "published_at": "2026-04-15T06:00:00+07:00",
            "published_at_resolved": "2026-04-15T06:00:00+07:00",
            "content_text": "Latest post text",
            "media_urls": ["https://example.com/image.jpg"],
            "backend": "browser_use_mcp",
            "fetched_at": "2026-04-15T06:05:00+07:00",
        },
    })


def test_repost_decision_schema_accepts_skip_without_selected_post():
    validate("repost_decision", {
        "action": "skip",
        "reason": "skip_no_posts_fetched_after_full_search",
    })


def test_repost_decision_schema_accepts_error_without_selected_post():
    validate("repost_decision", {
        "action": "error",
        "reason": "error_partial_search_scope",
    })


def test_repost_decision_schema_rejects_publish_without_selected_post():
    with pytest.raises(SchemaError):
        validate("repost_decision", {
            "action": "publish",
            "reason": "publish_today_newest",
        })


def test_repost_decision_schema_rejects_unknown_action():
    with pytest.raises(SchemaError):
        validate("repost_decision", {
            "action": "repost",
            "reason": "Unknown action",
        })


def test_latest_reposted_source_schema_accepts_legacy_shape_without_published_at_resolved():
    validate("latest_reposted_source", {
        "source_post_id": "1234567890",
        "source_post_url": "https://www.facebook.com/0xSojalSec/posts/1234567890",
        "published_at": "2026-04-15T06:00:00+07:00",
        "reposted_at": "2026-04-15T06:10:00+07:00",
        "run_dir": "runs/2026-04-15/hourly-facebook-latest-repost",
    })


def test_latest_reposted_source_schema_rejects_missing_run_dir():
    with pytest.raises(SchemaError):
        validate("latest_reposted_source", {
            "source_post_id": "1234567890",
            "source_post_url": "https://www.facebook.com/0xSojalSec/posts/1234567890",
            "published_at": "2026-04-15T06:00:00+07:00",
            "published_at_resolved": "2026-04-15T06:00:00+07:00",
            "reposted_at": "2026-04-15T06:10:00+07:00",
        })


def test_source_posts_schema_accepts_full_search_complete_payload():
    validate("source_posts", {
        "source_page_url": "https://www.facebook.com/0xSojalSec",
        "backend": "browser_use_mcp",
        "fetched_at": "2026-04-25T03:05:00Z",
        "search_status": "full_search_complete",
        "end_of_feed_reached": True,
        "scan_stopped_reason": "end_of_feed",
        "posts_scanned": 8,
        "posts": [
            {
                "source_page_url": "https://www.facebook.com/0xSojalSec",
                "source_post_id": "1234567890",
                "source_post_url": "https://www.facebook.com/0xSojalSec/posts/1234567890",
                "author": "0xSojalSec",
                "published_at": "2026-04-25T02:40:00Z",
                "published_at_resolved": "2026-04-25T02:40:00Z",
                "content_text": "Latest post text",
                "media_urls": ["https://example.com/image.jpg"],
                "backend": "browser_use_mcp",
                "fetched_at": "2026-04-25T03:05:00Z",
            },
        ],
    })


def test_source_posts_schema_accepts_null_published_at_resolved():
    validate("source_posts", {
        "source_page_url": "https://www.facebook.com/0xSojalSec",
        "backend": "browser_use_mcp",
        "fetched_at": "2026-04-25T03:05:00Z",
        "search_status": "partial_search_scope",
        "end_of_feed_reached": False,
        "scan_stopped_reason": "time_window_exceeded",
        "posts_scanned": 8,
        "posts": [
            {
                "source_page_url": "https://www.facebook.com/0xSojalSec",
                "source_post_id": "1234567890",
                "source_post_url": "https://www.facebook.com/0xSojalSec/posts/1234567890",
                "author": "0xSojalSec",
                "published_at": "3 hours ago",
                "published_at_resolved": None,
                "content_text": "Latest post text",
                "media_urls": ["https://example.com/image.jpg"],
                "backend": "browser_use_mcp",
                "fetched_at": "2026-04-25T03:05:00Z",
            },
        ],
    })


def test_source_posts_schema_rejects_end_of_feed_reached_without_full_search_complete():
    with pytest.raises(SchemaError):
        validate("source_posts", {
            "source_page_url": "https://www.facebook.com/0xSojalSec",
            "backend": "browser_use_mcp",
            "fetched_at": "2026-04-25T03:05:00Z",
            "search_status": "partial_search_scope",
            "end_of_feed_reached": True,
            "scan_stopped_reason": "time_window_exceeded",
            "posts_scanned": 8,
            "posts": [
                {
                    "source_page_url": "https://www.facebook.com/0xSojalSec",
                    "source_post_id": "1234567890",
                    "source_post_url": "https://www.facebook.com/0xSojalSec/posts/1234567890",
                    "author": "0xSojalSec",
                    "published_at": "3 hours ago",
                    "published_at_resolved": None,
                    "content_text": "Latest post text",
                    "media_urls": ["https://example.com/image.jpg"],
                    "backend": "browser_use_mcp",
                    "fetched_at": "2026-04-25T03:05:00Z",
                },
            ],
        })


def test_source_posts_schema_rejects_empty_scan_stopped_reason():
    with pytest.raises(SchemaError):
        validate("source_posts", {
            "source_page_url": "https://www.facebook.com/0xSojalSec",
            "backend": "browser_use_mcp",
            "fetched_at": "2026-04-25T03:05:00Z",
            "search_status": "fetch_error",
            "end_of_feed_reached": False,
            "scan_stopped_reason": "",
            "posts_scanned": 0,
            "posts": [],
        })


def test_source_posts_schema_rejects_selection_ready_with_empty_posts():
    with pytest.raises(SchemaError):
        validate("source_posts", {
            "source_page_url": "https://www.facebook.com/0xSojalSec",
            "backend": "agent_browser",
            "fetched_at": "2026-04-25T03:05:00Z",
            "search_status": "selection_ready",
            "end_of_feed_reached": False,
            "scan_stopped_reason": "selection_limit_reached",
            "posts_scanned": 4,
            "posts": [],
        })


def test_reposted_source_posts_schema_accepts_history_items():
    validate("reposted_source_posts", {
        "items": [
            {
                "source_post_id": "1234567890",
                "source_post_url": "https://www.facebook.com/0xSojalSec/posts/1234567890",
                "published_at": "2026-04-25T02:40:00Z",
                "published_at_resolved": "2026-04-25T02:40:00Z",
                "reposted_at": "2026-04-25T03:10:00Z",
                "run_dir": "runs/2026-04-25/hourly-facebook-latest-repost",
            },
        ],
    })


def test_reposted_source_posts_schema_accepts_null_published_at_resolved():
    validate("reposted_source_posts", {
        "items": [
            {
                "source_post_id": "1234567890",
                "source_post_url": "https://www.facebook.com/0xSojalSec/posts/1234567890",
                "published_at": "3 hours ago",
                "published_at_resolved": None,
                "reposted_at": "2026-04-25T03:10:00Z",
                "run_dir": "runs/2026-04-25/hourly-facebook-latest-repost",
            },
        ],
    })
