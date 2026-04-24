"""Orchestrator for the hourly Facebook repost pipeline."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

from autofanpage.dispatch import run_skill
from autofanpage.errors import AutofanpageError
from autofanpage.hourly_run_dir import HourlyRunDir
from autofanpage.hourly_state import LatestRepostedSource
from autofanpage.profile import load_profile


def _report(run_dir: Path, *, status: str, page: str, details: dict) -> None:
    run_skill(
        "telegram-reporter",
        {
            "run_dir": str(run_dir),
            "status": status,
            "page": page,
            "details": details,
        },
    )


def _next_publish_time(tz_name: str) -> str:
    now = datetime.now(tz=ZoneInfo(tz_name)) + timedelta(minutes=15)
    scheduled = now.replace(second=0, microsecond=0)
    return scheduled.strftime("%H:%M")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", required=True)
    parser.add_argument("--profile-path", required=True)
    parser.add_argument("--base-dir", required=True)
    parser.add_argument("--run-label", required=True)
    parser.add_argument("--date", default=None)
    args = parser.parse_args(argv)

    base = Path(args.base_dir)
    profile = load_profile(args.profile_path)

    run_dir = HourlyRunDir.create(base=base, page=args.page, run_label=args.run_label)
    if profile.publishing_backend not in (None, "facebook_graph"):
        _report(
            run_dir.path,
            status="error",
            page=args.page,
            details={
                "phase": "preflight",
                "cause": "hourly repost pipeline requires a Graph-compatible destination profile",
                "log_tail": "(preflight)",
            },
        )
        return 1

    date = args.date or datetime.now(tz=ZoneInfo(profile.timezone)).strftime("%Y-%m-%d")
    state = LatestRepostedSource(base=base, page=args.page)
    started = time.monotonic()

    run_skill(
        "facebook-page-latest-researcher",
        {
            "run_dir": str(run_dir.path),
            "profile": args.profile_path,
        },
    )

    latest_post = json.loads((run_dir.path / "latest_source_post.json").read_text(encoding="utf-8"))
    if state.matches(latest_post):
        repost_decision = {
            "action": "skip_duplicate",
            "reason": "latest source post already reposted",
            "source_post_id": latest_post.get("source_post_id"),
            "source_post_url": latest_post["source_post_url"],
        }
        (run_dir.path / "repost_decision.json").write_text(
            json.dumps(repost_decision, indent=2),
            encoding="utf-8",
        )
        _report(
            run_dir.path,
            status="info",
            page=args.page,
            details={"message": f"Skip duplicate source post: {latest_post['source_post_url']}"},
        )
        return 0

    publish_time = _next_publish_time(profile.timezone)
    run_skill(
        "hourly-facebook-writer",
        {
            "run_dir": str(run_dir.path),
            "profile": args.profile_path,
            "date": date,
            "publish_time": publish_time,
        },
    )
    run_skill(
        "facebook-publisher",
        {
            "run_dir": str(run_dir.path),
            "profile": args.profile_path,
            "date": date,
        },
    )

    publish_results = json.loads((run_dir.path / "publish_results.json").read_text(encoding="utf-8"))
    posts_scheduled = sum(1 for post in publish_results["posts"] if post["status"] == 200)
    if posts_scheduled < 1:
        raise AutofanpageError("hourly repost publish_results.json recorded no successful posts")

    state.mark(
        source_post_id=latest_post.get("source_post_id"),
        source_post_url=latest_post["source_post_url"],
        published_at=latest_post["published_at"],
        run_dir=str(run_dir.path),
    )

    _report(
        run_dir.path,
        status="success",
        page=args.page,
        details={
            "posts_scheduled": posts_scheduled,
            "date": date,
            "elapsed_sec": int(time.monotonic() - started),
            "posts_generated": 1,
            "source_page_url": latest_post["source_page_url"],
            "source_post_url": latest_post["source_post_url"],
            "source_published_at": latest_post["published_at"],
            "fetch_backend": latest_post["backend"],
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
