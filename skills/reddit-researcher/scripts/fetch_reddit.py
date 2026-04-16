"""Reddit-researcher skill script."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

from autofanpage.errors import SourceFailedError
from autofanpage.http import get_json
from autofanpage.profile import load_profile
from autofanpage.schemas import validate
from autofanpage.secrets import get_secret
from autofanpage.sources.reddit import filter_and_rank, to_result
from autofanpage.sources.reddit_auth import get_app_token


def run(
    *,
    subreddits: list[str],
    min_score: int,
    time_filter: str,
    top_per_sub: int,
    client_id_ref: str,
    client_secret_ref: str,
    user_agent: str,
    out_path: str,
) -> dict:
    client_id = get_secret(client_id_ref)
    client_secret = get_secret(client_secret_ref)
    token = get_app_token(client_id, client_secret, user_agent=user_agent)

    all_items: list[dict] = []
    failed: list[str] = []

    for sub in subreddits:
        try:
            listing = get_json(
                f"https://oauth.reddit.com/r/{sub}/top",
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": user_agent,
                },
                params={"t": time_filter, "limit": max(top_per_sub * 3, 25)},
            )
        except SourceFailedError:
            failed.append(sub)
            continue
        kept = filter_and_rank(listing, min_score=min_score, top_n=top_per_sub)
        all_items.extend(to_result(p) for p in kept)

    if subreddits and len(failed) == len(subreddits):
        raise SourceFailedError(f"All subreddits failed: {failed}")

    doc = {
        "source": "reddit",
        "fetched_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "items": all_items,
    }
    validate("reddit_results", doc)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

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
            json.dumps({"source": "reddit",
                        "fetched_at": datetime.now(timezone.utc).astimezone().isoformat(),
                        "items": []}, ensure_ascii=False),
        )
        print(json.dumps({"status": "ok", "skipped": True, "count": 0}))
        return 0

    out_path = str(Path(args.run_dir) / "reddit_results.json")
    result = run(
        subreddits=cfg["subreddits"],
        min_score=cfg.get("min_score", 100),
        time_filter=cfg.get("time_filter", "week"),
        top_per_sub=cfg.get("top_per_sub", 5),
        client_id_ref="secret:reddit_client_id",
        client_secret_ref="secret:reddit_client_secret",
        user_agent=f"autofanpage/0.1 (profile={profile.name})",
        out_path=out_path,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
