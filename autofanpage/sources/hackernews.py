"""Pure logic for Hacker News source filtering and shaping.

Network calls live in `skills/hackernews-researcher/scripts/fetch_hn.py`;
this module is network-free so it can be unit tested deterministically.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

# Common English suffixes for lightweight stemming (ordered longest first)
_SUFFIXES = ("ation", "ion", "ated", "ate", "ing", "ed", "ly", "er", "est", "s")


def _stem(word: str) -> str:
    """Strip a common English suffix to get an approximate stem.

    Only strips when the remaining stem is longer than 3 characters so that
    short words like "wins" or "ai" are left intact.
    """
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) > len(suffix) + 3:
            return word[: -len(suffix)]
    return word


def matches_topic(title: str, topic: str) -> bool:
    """True if any word of topic is a case-insensitive substring of title,
    or if any topic word shares a stem with any title word."""
    title_l = title.lower()
    title_words = title_l.split()
    title_stems = [_stem(w) for w in title_words]

    for word in topic.lower().split():
        if not word:
            continue
        # Direct substring match (fast path)
        if word in title_l:
            return True
        # Stem-based word match
        word_stem = _stem(word)
        if any(word_stem == ts for ts in title_stems):
            return True
    return False


def filter_and_rank(
    items: Iterable[dict[str, Any]],
    *,
    topic: str,
    min_points: int,
    limit: int,
) -> list[dict[str, Any]]:
    keep: list[dict[str, Any]] = []
    for item in items:
        if item.get("type") != "story":
            continue
        if item.get("score", 0) < min_points:
            continue
        if not matches_topic(item.get("title", ""), topic):
            continue
        keep.append(item)
    keep.sort(key=lambda i: i.get("score", 0), reverse=True)
    return keep[:limit]


def to_result(item: dict[str, Any]) -> dict[str, Any]:
    hn_url = f"https://news.ycombinator.com/item?id={item['id']}"
    created_at = datetime.fromtimestamp(
        item["time"], tz=timezone.utc
    ).isoformat()
    return {
        "title": item["title"],
        "url": item["url"] or hn_url,
        "points": item["score"],
        "by": item["by"],
        "descendants": item.get("descendants", 0),
        "created_at": created_at,
        "hn_url": hn_url,
    }
