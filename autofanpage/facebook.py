"""Facebook Graph API helpers used by the publishing skill."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from autofanpage.http import post_json


GRAPH_BASE = "https://graph.facebook.com/v19.0"
MIN_LEAD_MINUTES = 10
SHIFT_MINUTES = 15


def compute_publish_time(
    *,
    post_time: str,
    date: str,
    tz_name: str,
    wall_now: datetime | None = None,
) -> int:
    """Return the UTC unix timestamp for a scheduled Facebook post."""
    tz = ZoneInfo(tz_name)
    hour, minute = int(post_time[:2]), int(post_time[3:])
    year, month, day = int(date[:4]), int(date[5:7]), int(date[8:10])
    target = datetime(year, month, day, hour, minute, tzinfo=tz)

    if wall_now is None:
        wall_now = datetime.now(tz)

    delta_seconds = (target - wall_now).total_seconds()
    if delta_seconds < MIN_LEAD_MINUTES * 60:
        target += timedelta(minutes=SHIFT_MINUTES)

    return int(target.astimezone(timezone.utc).timestamp())


def schedule_post(
    *,
    page_id: str,
    access_token: str,
    message: str,
    publish_time: int,
    timeout: float = 60,
    max_retries: int = 3,
) -> str:
    """Create a scheduled post and return the Graph API post id."""
    response: dict[str, Any] = post_json(
        f"{GRAPH_BASE}/{page_id}/feed",
        json_body={
            "message": message,
            "scheduled_publish_time": publish_time,
            "published": False,
            "access_token": access_token,
        },
        timeout=timeout,
        max_retries=max_retries,
    )
    return response["id"]


def add_first_comment(
    *,
    post_id: str,
    access_token: str,
    message: str,
    timeout: float = 30,
    max_retries: int = 3,
) -> str:
    """Create a first comment on a published/scheduled post."""
    response: dict[str, Any] = post_json(
        f"{GRAPH_BASE}/{post_id}/comments",
        json_body={
            "message": message,
            "access_token": access_token,
        },
        timeout=timeout,
        max_retries=max_retries,
    )
    return response["id"]


def render_preview(posts_data: dict[str, Any], *, page: str, date: str) -> str:
    """Render posts.json content into a Markdown preview document."""
    lines = [f"# Preview: {page} — {date}", ""]

    for post in posts_data["posts"]:
        lines.extend([f"## {post['time']} — {post['type']}", ""])
        if post["content"]:
            lines.extend([post["content"], ""])
            if post["first_comment"]:
                lines.extend([f"> **First comment:** {post['first_comment']}", ""])
        else:
            lines.extend(["*(no content)*", ""])
        lines.extend(["---", ""])

    return "\n".join(lines)
