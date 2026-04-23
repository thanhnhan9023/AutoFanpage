import pytest

from autofanpage.errors import SourceFailedError
from autofanpage.sources.facebook_page_latest import normalize_latest_post


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
