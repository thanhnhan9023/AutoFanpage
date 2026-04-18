"""Reddit-researcher skill script backed by Apify."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

from autofanpage.errors import SourceFailedError
from autofanpage.http import post_json
from autofanpage.profile import load_profile
from autofanpage.schemas import validate
from autofanpage.secrets import get_secret


DEFAULT_ACTOR_ID = "automation-lab/reddit-scraper"


def _actor_url(actor_id: str, token: str) -> str:
    actor_ref = actor_id.replace("/", "~")
    return (
        f"https://api.apify.com/v2/acts/{quote(actor_ref, safe='~')}"
        f"/run-sync-get-dataset-items?token={token}"
    )


def _actor_input(subreddit: str, time_filter: str, top_per_sub: int) -> dict[str, Any]:
    return {
        "urls": [f"https://www.reddit.com/r/{subreddit}/top/?t={time_filter}"],
        "sort": "top",
        "timeFilter": time_filter,
        "maxPostsPerSource": max(top_per_sub * 3, 15),
        "includeComments": False,
    }


def _parse_created(value: Any) -> str:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    if isinstance(value, str) and value:
        return value
    return datetime.now(timezone.utc).isoformat()


def _normalize_item(item: dict[str, Any], subreddit: str) -> dict[str, Any]:
    permalink = item.get("permalink") or item.get("url") or ""
    if permalink.startswith("http"):
        url = permalink
        permalink = item.get("permalink") or ""
    else:
        url = f"https://reddit.com{permalink}" if permalink else item.get("url", "")
    external_url = (
        item.get("externalUrl")
        or item.get("outboundUrl")
        or item.get("link")
        or item.get("url", "")
    )
    return {
        "title": item.get("title") or item.get("postTitle") or "",
        "url": url,
        "subreddit": item.get("subreddit") or subreddit,
        "score": int(item.get("score") or item.get("ups") or item.get("upvotes") or 0),
        "num_comments": int(item.get("numComments") or item.get("commentCount") or item.get("commentsCount") or 0),
        "author": item.get("author") or item.get("username") or "",
        "permalink": permalink,
        "created_at": _parse_created(item.get("createdUtc") or item.get("createdAt")),
        "is_self": bool(item.get("isSelf") or item.get("is_self")),
        "external_url": external_url,
    }


def run(
    *,
    actor_id: str,
    subreddits: list[str],
    min_score: int,
    time_filter: str,
    top_per_sub: int,
    api_token_ref: str,
    out_path: str,
) -> dict[str, Any]:
    token = get_secret(api_token_ref)
    all_items: list[dict[str, Any]] = []
    failed: list[str] = []

    for sub in subreddits:
        try:
            items = post_json(
                _actor_url(actor_id, token),
                json_body=_actor_input(sub, time_filter, top_per_sub),
            )
        except SourceFailedError:
            failed.append(sub)
            continue
        normalized = [
            _normalize_item(item, sub)
            for item in items
            if int(item.get("score") or item.get("ups") or item.get("upvotes") or 0) >= min_score
        ]
        normalized.sort(key=lambda post: post["score"], reverse=True)
        all_items.extend(normalized[:top_per_sub])

    if subreddits and len(failed) == len(subreddits):
        raise SourceFailedError(f"All subreddits failed: {failed}")

    doc = {
        "source": "reddit",
        "fetched_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "items": all_items,
    }
    validate("reddit_results", doc)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)

    return {
        "status": "ok",
        "artifact": out_path,
        "count": len(all_items),
        "failed_subreddits": failed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--profile", required=True)
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    cfg = profile.sources.get("reddit", {})
    if not cfg.get("enabled", False):
        Path(args.run_dir, "reddit_results.json").write_text(
            json.dumps({
                "source": "reddit",
                "fetched_at": datetime.now(timezone.utc).astimezone().isoformat(),
                "items": [],
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        print(json.dumps({"status": "ok", "skipped": True, "count": 0}))
        return 0

    result = run(
        actor_id=cfg.get("actor_id", DEFAULT_ACTOR_ID),
        subreddits=cfg["subreddits"],
        min_score=cfg.get("min_score", 100),
        time_filter=cfg.get("time_filter", "week"),
        top_per_sub=cfg.get("top_per_sub", 5),
        api_token_ref=cfg.get("api_token_ref", "secret:apify_api_token"),
        out_path=str(Path(args.run_dir) / "reddit_results.json"),
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
