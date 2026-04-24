from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from autofanpage.agent_browser import run_agent_browser_extract
from autofanpage.browser_use import run_browser_use_task
from autofanpage.errors import SourceFailedError
from autofanpage.schemas import validate


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_post_id(raw: dict[str, Any]) -> str | None:
    source_post_id = raw.get("source_post_id")
    if source_post_id is not None:
        return str(source_post_id)

    post_url = str(raw.get("source_post_url") or "").strip()
    if not post_url:
        return None

    patterns = [
        r"/posts/[^/?#]+/(\d+)(?:/|$)",
        r"/posts/([^/?#]+)",
        r"[?&]story_fbid=([^&#]+)",
        r"/permalink/([^/?#]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, post_url)
        if match:
            return match.group(1)
    return None


def _require_non_empty(raw: dict[str, Any], field_name: str) -> str:
    value = str(raw.get(field_name) or "").strip()
    if not value:
        raise SourceFailedError(f"latest source post missing {field_name}")
    return value


def normalize_latest_post(raw: dict[str, Any], *, backend: str) -> dict[str, Any]:
    source_page_url = _require_non_empty(raw, "source_page_url")
    source_post_url = _require_non_empty(raw, "source_post_url")
    published_at = _require_non_empty(raw, "published_at")
    content_text = _require_non_empty(raw, "content_text")

    media_urls = raw.get("media_urls")
    if isinstance(media_urls, list):
        normalized_media_urls = [str(item) for item in media_urls]
    else:
        normalized_media_urls = []

    payload = {
        "source_page_url": source_page_url,
        "source_post_id": _extract_post_id(raw),
        "source_post_url": source_post_url,
        "author": str(raw.get("author") or "").strip(),
        "published_at": published_at,
        "content_text": content_text,
        "media_urls": normalized_media_urls,
        "backend": backend,
        "fetched_at": str(raw.get("fetched_at") or _utc_now_iso()),
    }
    validate("latest_source_post", payload)
    return payload


def fetch_latest_post_from_page(source_cfg: dict[str, Any]) -> dict[str, Any]:
    page_url = str(source_cfg.get("page_url") or "").strip()
    if not page_url:
        raise SourceFailedError("facebook_page_latest source missing page_url")

    backend = str(source_cfg.get("backend") or "browser_use_mcp")
    if backend == "browser_use_mcp":
        output_schema = {
            "type": "object",
            "required": [
                "source_page_url",
                "source_post_url",
                "published_at",
                "content_text",
            ],
            "properties": {
                "source_page_url": {"type": "string"},
                "source_post_id": {"type": "string"},
                "source_post_url": {"type": "string"},
                "author": {"type": "string"},
                "published_at": {"type": "string"},
                "content_text": {"type": "string"},
                "media_urls": {"type": "array", "items": {"type": "string"}},
                "fetched_at": {"type": "string"},
            },
            "additionalProperties": False,
        }
        raw = run_browser_use_task(
            task=(
                "Open the Facebook page at "
                f"{page_url} and return the newest top-level public post only. "
                "Extract the source page URL, source post URL, published timestamp, "
                "full content text, and when available the source post ID, author, "
                "media URLs, and fetched timestamp."
            ),
            output_schema=output_schema,
            profile_id=source_cfg.get("browser_use_profile_id"),
        )
        return normalize_latest_post(raw, backend=backend)

    if backend == "agent_browser":
        raw = run_agent_browser_extract(
            page_url=page_url,
            profile=source_cfg.get("agent_browser_profile"),
            session_name=source_cfg.get("agent_browser_session_name"),
            state_path=source_cfg.get("agent_browser_state_path"),
        )
        return normalize_latest_post(raw, backend=backend)

    raise SourceFailedError(f"Unsupported facebook_page_latest backend: {backend}")
