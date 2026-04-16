"""Pure filter/shape logic for Reddit listing JSON."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def filter_and_rank(
    listing: dict[str, Any],
    *,
    min_score: int,
    top_n: int,
) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for child in listing.get("data", {}).get("children", []):
        p = child.get("data", {})
        if p.get("stickied"):
            continue
        if p.get("over_18"):
            continue
        if p.get("score", 0) < min_score:
            continue
        kept.append(p)
    kept.sort(key=lambda p: p.get("score", 0), reverse=True)
    return kept[:top_n]


def to_result(post: dict[str, Any]) -> dict[str, Any]:
    created = datetime.fromtimestamp(
        post["created_utc"], tz=timezone.utc,
    ).isoformat()
    return {
        "title": post["title"],
        "url": f"https://reddit.com{post['permalink']}",
        "subreddit": post["subreddit"],
        "score": post["score"],
        "num_comments": post.get("num_comments", 0),
        "author": post.get("author", ""),
        "permalink": post["permalink"],
        "created_at": created,
        "is_self": bool(post.get("is_self")),
        "external_url": post.get("url", ""),
    }
