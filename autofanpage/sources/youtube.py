"""Pure filter/shape logic for YouTube Data API v3 results."""
from __future__ import annotations

from typing import Any


def merge_stats(
    search: dict[str, Any],
    videos: dict[str, Any],
    channels: dict[str, Any],
) -> list[dict[str, Any]]:
    view_by_id = {
        v["id"]: int(v["statistics"].get("viewCount", "0"))
        for v in videos.get("items", [])
    }
    sub_by_id = {
        c["id"]: int(c["statistics"].get("subscriberCount", "0"))
        for c in channels.get("items", [])
    }
    merged: list[dict[str, Any]] = []
    for item in search.get("items", []):
        vid = item["id"]["videoId"]
        snip = item["snippet"]
        merged.append({
            "video_id": vid,
            "title": snip["title"],
            "channel": snip["channelTitle"],
            "channel_id": snip["channelId"],
            "views": view_by_id.get(vid, 0),
            "subscribers": sub_by_id.get(snip["channelId"], 0),
            "published_at": snip["publishedAt"],
        })
    return merged


def filter_and_rank(
    items: list[dict[str, Any]],
    *,
    min_views: int,
    min_subs: int,
    limit: int,
) -> list[dict[str, Any]]:
    keep = [
        i for i in items
        if i["views"] >= min_views and i["subscribers"] >= min_subs
    ]
    keep.sort(key=lambda i: i["views"], reverse=True)
    return keep[:limit]


def to_result(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": item["title"],
        "url": f"https://youtu.be/{item['video_id']}",
        "video_id": item["video_id"],
        "channel": item["channel"],
        "channel_id": item["channel_id"],
        "views": item["views"],
        "subscribers": item["subscribers"],
        "published_at": item["published_at"],
    }
