import pytest

from autofanpage.errors import SourceFailedError
from autofanpage.sources.facebook_page_latest import (
    fetch_latest_post_from_page,
    normalize_latest_post,
)


def test_normalize_latest_post_prefers_source_post_id():
    payload = {
        "source_page_url": "https://www.facebook.com/0xSojalSec",
        "source_post_id": "123",
        "source_post_url": "https://www.facebook.com/0xSojalSec/posts/123",
        "author": "0xSojalSec",
        "published_at": "2026-04-23T09:15:00Z",
        "content_text": "A useful post",
        "media_urls": [],
        "backend": "browser_use_mcp",
        "fetched_at": "2026-04-23T10:00:00Z",
    }

    normalized = normalize_latest_post(payload, backend="browser_use_mcp")

    assert normalized["source_post_id"] == "123"


def test_normalize_latest_post_rejects_empty_content():
    payload = {
        "source_page_url": "https://www.facebook.com/0xSojalSec",
        "source_post_id": "123",
        "source_post_url": "https://www.facebook.com/0xSojalSec/posts/123",
        "author": "0xSojalSec",
        "published_at": "2026-04-23T09:15:00Z",
        "content_text": "   ",
        "media_urls": [],
        "backend": "browser_use_mcp",
        "fetched_at": "2026-04-23T10:00:00Z",
    }

    with pytest.raises(SourceFailedError, match="content_text"):
        normalize_latest_post(payload, backend="browser_use_mcp")


def test_fetch_latest_post_from_page_uses_strict_browser_use_schema(monkeypatch):
    seen: dict[str, object] = {}

    def fake_run_browser_use_task(*, task, output_schema, profile_id=None):
        seen["task"] = task
        seen["output_schema"] = output_schema
        seen["profile_id"] = profile_id
        return {
            "source_page_url": "https://www.facebook.com/0xSojalSec",
            "source_post_url": "https://www.facebook.com/0xSojalSec/posts/123",
            "published_at": "2026-04-23T09:15:00Z",
            "content_text": "A useful post",
        }

    monkeypatch.setattr(
        "autofanpage.sources.facebook_page_latest.run_browser_use_task",
        fake_run_browser_use_task,
    )

    fetch_latest_post_from_page(
        {
            "enabled": True,
            "page_url": "https://www.facebook.com/0xSojalSec",
            "backend": "browser_use_mcp",
        }
    )

    assert seen["output_schema"]["additionalProperties"] is False
