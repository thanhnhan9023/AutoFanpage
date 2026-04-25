from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from autofanpage.agent_browser import (
    run_agent_browser_extract,
    run_agent_browser_extract_posts,
)
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


def _normalize_page_url(page_url: str) -> str:
    parsed = urlsplit(page_url)
    if parsed.netloc != "web.facebook.com":
        return page_url
    return urlunsplit(parsed._replace(netloc="www.facebook.com"))


def _profile_zone(profile_timezone: str) -> timezone | ZoneInfo:
    try:
        return ZoneInfo(profile_timezone)
    except Exception:
        return timezone.utc


def _parse_timestamp(value: str, *, default_tz: timezone | ZoneInfo) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    candidate = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=default_tz)
    return parsed


def _relative_delta(value: str) -> timedelta | None:
    raw = value.strip().lower()
    short_match = re.fullmatch(r"(\d+)\s*([smhdw])", raw)
    if short_match:
        amount = int(short_match.group(1))
        unit = short_match.group(2)
    else:
        long_match = re.fullmatch(
            r"(\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?)\s*ago",
            raw,
        )
        if not long_match:
            return None
        amount = int(long_match.group(1))
        unit = long_match.group(2)[0]

    if unit == "s":
        return timedelta(seconds=amount)
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    if unit == "w":
        return timedelta(weeks=amount)
    return None


def _resolve_published_at(
    published_at: str,
    *,
    fetched_at: str,
    profile_timezone: str,
) -> str | None:
    raw = published_at.strip()
    if not raw:
        return None

    profile_zone = _profile_zone(profile_timezone)
    exact = _parse_timestamp(raw, default_tz=profile_zone)
    if exact is not None:
        if raw.endswith("Z") or re.search(r"[+-]\d{2}:\d{2}$", raw):
            return raw
        return exact.astimezone(profile_zone).isoformat()

    fetched_dt = _parse_timestamp(fetched_at, default_tz=timezone.utc)
    if fetched_dt is None:
        return None
    local_fetched = fetched_dt.astimezone(profile_zone)

    lowered = raw.lower()
    if lowered in {"just now", "today"}:
        return local_fetched.isoformat()
    if lowered == "yesterday":
        return (local_fetched - timedelta(days=1)).isoformat()

    delta = _relative_delta(raw)
    if delta is None:
        return None
    return (local_fetched - delta).isoformat()


def _normalize_media_urls(raw: dict[str, Any]) -> list[str]:
    media_urls = raw.get("media_urls")
    if isinstance(media_urls, list):
        return [str(item) for item in media_urls]
    return []


def _require_non_empty(raw: dict[str, Any], field_name: str) -> str:
    value = str(raw.get(field_name) or "").strip()
    if not value:
        raise SourceFailedError(f"latest source post missing {field_name}")
    return value


def normalize_latest_post(raw: dict[str, Any], *, backend: str) -> dict[str, Any]:
    payload = normalize_source_post(
        raw,
        backend=backend,
        fetched_at=str(raw.get("fetched_at") or _utc_now_iso()),
        profile_timezone="UTC",
    )
    validate("latest_source_post", payload)
    return payload


def normalize_source_post(
    raw: dict[str, Any],
    *,
    backend: str,
    fetched_at: str,
    profile_timezone: str,
) -> dict[str, Any]:
    source_page_url = _normalize_page_url(_require_non_empty(raw, "source_page_url"))
    source_post_url = _normalize_page_url(_require_non_empty(raw, "source_post_url"))
    published_at = _require_non_empty(raw, "published_at")
    content_text = _require_non_empty(raw, "content_text")

    payload = {
        "source_page_url": source_page_url,
        "source_post_id": _extract_post_id(raw),
        "source_post_url": source_post_url,
        "author": str(raw.get("author") or "").strip(),
        "published_at": published_at,
        "published_at_resolved": _resolve_published_at(
            published_at,
            fetched_at=fetched_at,
            profile_timezone=profile_timezone,
        ),
        "content_text": content_text,
        "media_urls": _normalize_media_urls(raw),
        "backend": backend,
        "fetched_at": fetched_at,
    }
    validate("latest_source_post", payload)
    return payload


def normalize_source_posts_artifact(
    raw: dict[str, Any],
    *,
    backend: str,
    profile_timezone: str,
) -> dict[str, Any]:
    source_page_url = _normalize_page_url(_require_non_empty(raw, "source_page_url"))
    fetched_at = str(raw.get("fetched_at") or _utc_now_iso())
    posts_raw = raw.get("posts")
    if not isinstance(posts_raw, list):
        raise SourceFailedError("source_posts artifact missing posts")

    normalized_posts = []
    for item in posts_raw:
        if not isinstance(item, dict):
            raise SourceFailedError("source_posts artifact post must be an object")
        post_raw = dict(item)
        post_raw.setdefault("source_page_url", source_page_url)
        normalized_posts.append(
            normalize_source_post(
                post_raw,
                backend=backend,
                fetched_at=fetched_at,
                profile_timezone=profile_timezone,
            )
        )

    raw_posts_scanned = raw.get("posts_scanned")
    if raw_posts_scanned is None:
        posts_scanned = len(normalized_posts)
    else:
        posts_scanned = int(raw_posts_scanned)

    end_of_feed_reached = raw.get("end_of_feed_reached")
    payload = {
        "source_page_url": source_page_url,
        "backend": backend,
        "fetched_at": fetched_at,
        "search_status": str(raw.get("search_status") or "").strip(),
        "end_of_feed_reached": end_of_feed_reached if isinstance(end_of_feed_reached, bool) else False,
        "scan_stopped_reason": str(raw.get("scan_stopped_reason") or "").strip(),
        "posts_scanned": posts_scanned,
        "posts": normalized_posts,
    }
    validate("source_posts", payload)
    return payload


def fetch_source_posts_from_page(
    source_cfg: dict[str, Any],
    *,
    profile_timezone: str,
) -> dict[str, Any]:
    page_url = str(source_cfg.get("page_url") or "").strip()
    if not page_url:
        raise SourceFailedError("facebook_page_latest source missing page_url")
    page_url = _normalize_page_url(page_url)

    backend = str(source_cfg.get("backend") or "browser_use_mcp")
    if backend == "browser_use_mcp":
        output_schema = {
            "type": "object",
            "required": [
                "source_page_url",
                "search_status",
                "end_of_feed_reached",
                "scan_stopped_reason",
                "posts_scanned",
                "posts",
            ],
            "properties": {
                "source_page_url": {"type": "string"},
                "fetched_at": {"type": "string"},
                "search_status": {"type": "string"},
                "end_of_feed_reached": {"type": "boolean"},
                "scan_stopped_reason": {"type": "string"},
                "posts_scanned": {"type": "integer"},
                "posts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": [
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
                        },
                        "additionalProperties": False,
                    },
                },
            },
            "additionalProperties": False,
        }
        raw = run_browser_use_task(
            task=(
                "Open the Facebook page at "
                f"{page_url} and return recent top-level public posts. "
                "Extract the source page URL, fetched timestamp, search_status, "
                "end_of_feed_reached, scan_stopped_reason, posts_scanned, and a posts list. "
                "Each post must include the source post URL, published timestamp, full content text, "
                "and when available the source page URL, source post ID, author, and media URLs. "
                "Use selection_ready when there is at least one recent post ready for downstream selection."
            ),
            output_schema=output_schema,
            profile_id=source_cfg.get("browser_use_profile_id"),
        )
        return normalize_source_posts_artifact(
            raw,
            backend=backend,
            profile_timezone=profile_timezone,
        )

    if backend == "agent_browser":
        raw = run_agent_browser_extract_posts(
            page_url=page_url,
            profile=source_cfg.get("agent_browser_profile"),
            session_name=source_cfg.get("agent_browser_session_name"),
            state_path=source_cfg.get("agent_browser_state_path"),
        )
        return normalize_source_posts_artifact(
            raw,
            backend=backend,
            profile_timezone=profile_timezone,
        )

    raise SourceFailedError(f"Unsupported facebook_page_latest backend: {backend}")


def fetch_latest_post_from_page(source_cfg: dict[str, Any]) -> dict[str, Any]:
    page_url = str(source_cfg.get("page_url") or "").strip()
    if not page_url:
        raise SourceFailedError("facebook_page_latest source missing page_url")
    page_url = _normalize_page_url(page_url)

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
