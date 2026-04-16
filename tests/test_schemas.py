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
