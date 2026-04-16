"""YouTube-researcher skill script."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

from autofanpage.http import get_json
from autofanpage.profile import load_profile
from autofanpage.run_dir import RunDir
from autofanpage.schemas import validate
from autofanpage.secrets import get_secret
from autofanpage.sources.youtube import (
    merge_stats, filter_and_rank, to_result,
)

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"


def _published_after(days: int = 7) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(
    *,
    topic: str,
    min_views: int,
    min_subs: int,
    api_key_ref: str,
    limit: int,
    out_path: str,
) -> dict:
    api_key = get_secret(api_key_ref)

    search = get_json(SEARCH_URL, params={
        "part": "snippet",
        "q": topic,
        "order": "viewCount",
        "publishedAfter": _published_after(7),
        "type": "video",
        "maxResults": 25,
        "key": api_key,
    })

    video_ids = [it["id"]["videoId"] for it in search.get("items", [])]
    channel_ids = list({it["snippet"]["channelId"] for it in search.get("items", [])})

    videos = (
        get_json(VIDEOS_URL, params={
            "part": "statistics", "id": ",".join(video_ids), "key": api_key,
        })
        if video_ids else {"items": []}
    )
    channels = (
        get_json(CHANNELS_URL, params={
            "part": "statistics", "id": ",".join(channel_ids), "key": api_key,
        })
        if channel_ids else {"items": []}
    )

    merged = merge_stats(search, videos, channels)
    kept = filter_and_rank(
        merged, min_views=min_views, min_subs=min_subs, limit=limit,
    )
    doc = {
        "source": "youtube",
        "fetched_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "items": [to_result(m) for m in kept],
    }
    validate("youtube_results", doc)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    return {"status": "ok", "artifact": out_path, "count": len(doc["items"])}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--profile", required=True)
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    cfg = profile.sources.get("youtube", {})
    if not cfg.get("enabled", False):
        Path(args.run_dir, "youtube_results.json").write_text(
            json.dumps({"source": "youtube",
                        "fetched_at": datetime.now(timezone.utc).astimezone().isoformat(),
                        "items": []}, ensure_ascii=False),
        )
        print(json.dumps({"status": "ok", "skipped": True, "count": 0}))
        return 0

    out_path = str(Path(args.run_dir) / "youtube_results.json")
    result = run(
        topic=profile.topic,
        min_views=profile.filters["youtube_min_views"],
        min_subs=profile.filters["youtube_min_subs"],
        api_key_ref="secret:youtube_api_key",
        limit=10,
        out_path=out_path,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
