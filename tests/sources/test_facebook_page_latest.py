import subprocess
from types import SimpleNamespace

import pytest

from autofanpage.agent_browser import run_agent_browser_extract
from autofanpage.browser_use import run_browser_use_task
from autofanpage.errors import SourceFailedError
from autofanpage.sources.facebook_page_latest import (
    fetch_source_posts_from_page,
    fetch_latest_post_from_page,
    normalize_source_posts_artifact,
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


def test_normalize_latest_post_extracts_numeric_id_from_slugged_posts_url():
    payload = {
        "source_page_url": "https://www.facebook.com/0xSojalSec",
        "source_post_url": (
            "https://www.facebook.com/0xSojalSec/posts/"
            "in-1964-a-soon-to-be-nobel-laureate/1499861465001585/"
        ),
        "author": "0xSojalSec",
        "published_at": "8h",
        "content_text": "A useful post",
        "media_urls": [],
        "backend": "agent_browser",
        "fetched_at": "2026-04-24T10:00:00Z",
    }

    normalized = normalize_latest_post(payload, backend="agent_browser")

    assert normalized["source_post_id"] == "1499861465001585"


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


def test_fetch_latest_post_from_page_normalizes_web_facebook_url_for_agent_browser(monkeypatch):
    seen: dict[str, object] = {}

    def fake_run_agent_browser_extract(
        *,
        page_url,
        profile=None,
        session_name=None,
        state_path=None,
    ):
        seen["page_url"] = page_url
        return {
            "source_page_url": page_url,
            "source_post_id": "123",
            "source_post_url": f"{page_url}/posts/123",
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

    fetch_latest_post_from_page(
        {
            "enabled": True,
            "page_url": "https://web.facebook.com/0xSojalSec",
            "backend": "agent_browser",
        }
    )

    assert seen["page_url"] == "https://www.facebook.com/0xSojalSec"


def test_normalize_source_posts_artifact_accepts_status_fields_and_resolves_published_at():
    artifact = normalize_source_posts_artifact(
        {
            "source_page_url": "https://www.facebook.com/0xSojalSec",
            "fetched_at": "2026-04-25T03:05:00Z",
            "search_status": "selection_ready",
            "end_of_feed_reached": False,
            "scan_stopped_reason": "selection_limit_reached",
            "posts_scanned": 4,
            "posts": [
                {
                    "source_page_url": "https://www.facebook.com/0xSojalSec",
                    "source_post_url": "https://www.facebook.com/0xSojalSec/posts/123",
                    "author": "0xSojalSec",
                    "published_at": "8h",
                    "content_text": "A useful post",
                    "media_urls": [],
                }
            ],
        },
        backend="browser_use_mcp",
        profile_timezone="Asia/Ho_Chi_Minh",
    )

    assert artifact["search_status"] == "selection_ready"
    assert artifact["posts_scanned"] == 4
    assert artifact["posts"][0]["source_post_id"] == "123"
    assert artifact["posts"][0]["published_at_resolved"] == "2026-04-25T02:05:00+07:00"


def test_fetch_source_posts_from_page_uses_agent_browser_backend_and_resolves_timestamps(monkeypatch):
    seen: dict[str, object] = {}

    def fake_run_agent_browser_extract_posts(
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
            "source_page_url": page_url,
            "fetched_at": "2026-04-25T03:05:00Z",
            "search_status": "selection_ready",
            "end_of_feed_reached": False,
            "scan_stopped_reason": "selection_limit_reached",
            "posts_scanned": 3,
            "posts": [
                {
                    "source_page_url": page_url,
                    "source_post_url": f"{page_url}/posts/123",
                    "author": "0xSojalSec",
                    "published_at": "8h",
                    "content_text": "A useful post",
                    "media_urls": [],
                }
            ],
        }

    monkeypatch.setattr(
        "autofanpage.sources.facebook_page_latest.run_agent_browser_extract_posts",
        fake_run_agent_browser_extract_posts,
    )

    result = fetch_source_posts_from_page(
        {
            "enabled": True,
            "page_url": "https://web.facebook.com/0xSojalSec",
            "backend": "agent_browser",
            "agent_browser_profile": "facebook-profile",
            "agent_browser_session_name": "session-1",
            "agent_browser_state_path": "/tmp/state.json",
        },
        profile_timezone="Asia/Ho_Chi_Minh",
    )

    assert seen == {
        "page_url": "https://www.facebook.com/0xSojalSec",
        "profile": "facebook-profile",
        "session_name": "session-1",
        "state_path": "/tmp/state.json",
    }
    assert result["backend"] == "agent_browser"
    assert result["search_status"] == "selection_ready"
    assert result["posts"][0]["published_at_resolved"] == "2026-04-25T02:05:00+07:00"


def test_run_browser_use_task_uses_mcporter_args_flag(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[4] == "browser-use.run_session":
            return SimpleNamespace(
                returncode=0,
                stdout='{"session_id":"sess-1"}',
                stderr="",
            )
        return SimpleNamespace(
            returncode=0,
            stdout='{"status":"idle","output":{"source_page_url":"https://www.facebook.com/0xSojalSec","source_post_url":"https://www.facebook.com/0xSojalSec/posts/123","published_at":"2026-04-23T09:15:00Z","content_text":"A useful post"}}',
            stderr="",
        )

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr("time.sleep", lambda _: None)

    result = run_browser_use_task(
        task="fetch latest post",
        output_schema={"type": "object", "properties": {}, "additionalProperties": False},
    )

    assert result["content_text"] == "A useful post"
    assert len(calls) == 2
    assert calls[0][:6] == [
        "mcporter",
        "--config",
        "/home/thanhnhan9023/config/mcporter.json",
        "call",
        "browser-use.run_session",
        "--args",
    ]
    assert calls[1][:6] == [
        "mcporter",
        "--config",
        "/home/thanhnhan9023/config/mcporter.json",
        "call",
        "browser-use.get_session",
        "--args",
    ]


def test_run_agent_browser_extract_uses_two_stage_open_wait_eval_flow(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if "eval" in cmd:
            if len(calls) == 3:
                return SimpleNamespace(
                    returncode=0,
                    stdout='"https://www.facebook.com/0xSojalSec/posts/123"',
                    stderr="",
                )
            return SimpleNamespace(
                returncode=0,
                stdout='{"source_page_url":"https://www.facebook.com/0xSojalSec","source_post_url":"https://www.facebook.com/0xSojalSec/posts/123","published_at":"2026-04-23T09:15:00Z","content_text":"A useful post from the post detail page","author":"0xSojalSec","media_urls":[]}',
                stderr="",
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    result = run_agent_browser_extract(
        page_url="https://www.facebook.com/0xSojalSec",
        profile="facebook-profile",
        session_name="session-1",
        state_path="/tmp/state.json",
    )

    assert result["source_post_url"] == "https://www.facebook.com/0xSojalSec/posts/123"
    assert result["content_text"] == "A useful post from the post detail page"
    assert len(calls) == 6
    assert calls[0] == [
        "agent-browser",
        "--profile",
        "facebook-profile",
        "--session-name",
        "session-1",
        "--state",
        "/tmp/state.json",
        "open",
        "https://www.facebook.com/0xSojalSec",
    ]
    assert calls[1] == [
        "agent-browser",
        "--profile",
        "facebook-profile",
        "--session-name",
        "session-1",
        "--state",
        "/tmp/state.json",
        "wait",
        "--load",
        "networkidle",
    ]
    assert calls[2][:8] == [
        "agent-browser",
        "--profile",
        "facebook-profile",
        "--session-name",
        "session-1",
        "--state",
        "/tmp/state.json",
        "eval",
    ]
    assert calls[3] == [
        "agent-browser",
        "--profile",
        "facebook-profile",
        "--session-name",
        "session-1",
        "--state",
        "/tmp/state.json",
        "open",
        "https://www.facebook.com/0xSojalSec/posts/123",
    ]
    assert calls[4] == [
        "agent-browser",
        "--profile",
        "facebook-profile",
        "--session-name",
        "session-1",
        "--state",
        "/tmp/state.json",
        "wait",
        "--load",
        "networkidle",
    ]
    assert calls[5][:8] == [
        "agent-browser",
        "--profile",
        "facebook-profile",
        "--session-name",
        "session-1",
        "--state",
        "/tmp/state.json",
        "eval",
    ]
    assert "--json" not in calls[0]
    assert "--json" not in calls[1]


def test_run_agent_browser_extract_unwraps_json_envelope_and_backfills_fields(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if "eval" in cmd:
            if len(calls) == 3:
                return SimpleNamespace(
                    returncode=0,
                    stdout=(
                        '{"success":true,"data":{"origin":"https://www.facebook.com/0xSojalSec",'
                        '"result":"https://www.facebook.com/0xSojalSec/posts/pfbid123"},"error":null}'
                    ),
                    stderr="",
                )
            return SimpleNamespace(
                returncode=0,
                stdout=(
                    '{"success":true,"data":{"origin":"https://www.facebook.com/0xSojalSec/posts/pfbid123",'
                    '"result":{"source_page_url":"https://www.facebook.com/0xSojalSec/posts/pfbid123",'
                    '"source_post_url":"https://www.facebook.com/0xSojalSec/posts/pfbid123",'
                    '"published_at":"","relative_published_at":"8h","content_text":"A useful post",'
                    '"author":"","media_urls":[]}},"error":null}'
                ),
                stderr="",
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    result = run_agent_browser_extract(
        page_url="https://www.facebook.com/0xSojalSec",
        profile="facebook-profile",
        session_name="session-1",
        state_path="/tmp/state.json",
    )

    assert result["source_page_url"] == "https://www.facebook.com/0xSojalSec"
    assert result["source_post_url"] == "https://www.facebook.com/0xSojalSec/posts/pfbid123"
    assert result["published_at"] == "8h"


def test_run_agent_browser_extract_fails_when_latest_post_url_not_found(monkeypatch):
    def fake_run(cmd, **kwargs):
        if "eval" in cmd:
            return SimpleNamespace(returncode=0, stdout='""', stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    with pytest.raises(SourceFailedError, match="latest post URL"):
        run_agent_browser_extract(page_url="https://www.facebook.com/0xSojalSec")


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
