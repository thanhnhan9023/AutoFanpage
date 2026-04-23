import subprocess

import pytest

from autofanpage.agent_browser import run_agent_browser_extract
from autofanpage.browser_use import run_browser_use_task
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


@pytest.mark.parametrize(
    ("field_name", "message"),
    [
        ("source_page_url", "source_page_url"),
        ("source_post_url", "source_post_url"),
        ("published_at", "published_at"),
    ],
)
def test_normalize_latest_post_rejects_empty_required_fields(field_name, message):
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
    payload[field_name] = "   "

    with pytest.raises(SourceFailedError, match=message):
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


def test_fetch_latest_post_from_page_uses_agent_browser_backend(monkeypatch):
    seen: dict[str, object] = {}

    def fake_run_agent_browser_extract(
        *,
        page_url,
        profile=None,
        session_name=None,
        state_path=None,
    ):
        seen["page_url"] = page_url
        seen["profile"] = profile
        seen["session_name"] = session_name
        seen["state_path"] = state_path
        return {
            "source_page_url": "https://www.facebook.com/0xSojalSec",
            "source_post_id": "123",
            "source_post_url": "https://www.facebook.com/0xSojalSec/posts/123",
            "author": "0xSojalSec",
            "published_at": "2026-04-23T09:15:00Z",
            "content_text": "A useful post",
            "media_urls": [],
            "fetched_at": "2026-04-23T10:00:00Z",
        }

    monkeypatch.setattr(
        "autofanpage.sources.facebook_page_latest.run_agent_browser_extract",
        fake_run_agent_browser_extract,
    )

    result = fetch_latest_post_from_page(
        {
            "enabled": True,
            "page_url": "https://www.facebook.com/0xSojalSec",
            "backend": "agent_browser",
            "agent_browser_profile": "facebook-profile",
            "agent_browser_session_name": "session-1",
            "agent_browser_state_path": "/tmp/state.json",
        }
    )

    assert seen == {
        "page_url": "https://www.facebook.com/0xSojalSec",
        "profile": "facebook-profile",
        "session_name": "session-1",
        "state_path": "/tmp/state.json",
    }
    assert result["backend"] == "agent_browser"
    assert result["source_post_id"] == "123"


def test_run_browser_use_task_maps_subprocess_timeout(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=kwargs.get("args", args[0]), timeout=kwargs["timeout"])

    monkeypatch.setattr("subprocess.run", fake_run)

    with pytest.raises(SourceFailedError, match="timed out"):
        run_browser_use_task(
            task="fetch latest post",
            output_schema={"type": "object", "properties": {}, "additionalProperties": False},
        )


def test_run_agent_browser_extract_maps_subprocess_timeout(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=kwargs.get("args", args[0]), timeout=kwargs["timeout"])

    monkeypatch.setattr("subprocess.run", fake_run)

    with pytest.raises(SourceFailedError, match="timed out"):
        run_agent_browser_extract(page_url="https://www.facebook.com/0xSojalSec")
