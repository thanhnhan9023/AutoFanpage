from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo


def _profile_zone(profile_timezone: str) -> timezone | ZoneInfo:
    try:
        return ZoneInfo(profile_timezone)
    except Exception:
        return timezone.utc


def _parse_timestamp(value: str | None, *, default_tz: timezone | ZoneInfo) -> datetime | None:
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


def _history_contains(repost_history: dict[str, Any], source_post: dict[str, Any]) -> bool:
    source_post_id = source_post.get("source_post_id")
    source_post_url = source_post.get("source_post_url")

    for item in repost_history.get("items", []):
        history_id = item.get("source_post_id")
        if history_id and source_post_id and history_id == source_post_id:
            return True

        history_url = item.get("source_post_url")
        if history_url and source_post_url and history_url == source_post_url:
            return True

    return False


def _partition_by_profile_day(
    ranked_posts: list[tuple[datetime, dict[str, Any]]],
    *,
    profile_timezone: str,
    now_iso: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    profile_zone = _profile_zone(profile_timezone)
    now = _parse_timestamp(now_iso, default_tz=profile_zone) or datetime.now(timezone.utc)
    local_today = now.astimezone(profile_zone).date()
    ranked = sorted(ranked_posts, key=lambda item: item[0], reverse=True)

    today_posts: list[dict[str, Any]] = []
    backlog_posts: list[dict[str, Any]] = []
    for resolved, post in ranked:
        local_date = resolved.astimezone(profile_zone).date()
        if local_date == local_today:
            today_posts.append(post)
        else:
            backlog_posts.append(post)
    return today_posts, backlog_posts


def select_source_post(
    *,
    source_posts: dict[str, Any],
    repost_history: dict[str, Any],
    profile_timezone: str,
    now_iso: str | None = None,
) -> dict[str, Any]:
    search_status = source_posts["search_status"]
    posts = list(source_posts["posts"])

    if not posts and search_status == "full_search_complete":
        return {"action": "skip", "reason": "skip_no_posts_fetched_after_full_search"}
    if not posts and search_status in {"fetch_error", "selection_ready"}:
        return {"action": "error", "reason": "error_source_fetch_failed"}
    if not posts:
        return {"action": "error", "reason": "error_partial_search_scope"}

    unreposted = [
        post for post in posts if not _history_contains(repost_history, post)
    ]
    profile_zone = _profile_zone(profile_timezone)
    ranked_eligible: list[tuple[datetime, dict[str, Any]]] = []
    unresolved = []
    for post in unreposted:
        resolved = _parse_timestamp(
            post.get("published_at_resolved"),
            default_tz=profile_zone,
        )
        if resolved is None:
            unresolved.append(post)
            continue
        ranked_eligible.append((resolved, post))

    if not ranked_eligible and unresolved:
        return {"action": "error", "reason": "error_unresolved_candidate_timestamps"}

    today_posts, backlog_posts = _partition_by_profile_day(
        ranked_eligible,
        profile_timezone=profile_timezone,
        now_iso=now_iso,
    )
    if today_posts:
        return {
            "action": "publish",
            "reason": "publish_today_newest",
            "selected_post": today_posts[0],
        }
    if backlog_posts:
        return {
            "action": "publish",
            "reason": "publish_backlog_newest",
            "selected_post": backlog_posts[0],
        }
    if search_status == "full_search_complete":
        return {"action": "skip", "reason": "skip_no_eligible_post_after_full_search"}
    return {"action": "error", "reason": "error_partial_search_scope"}
