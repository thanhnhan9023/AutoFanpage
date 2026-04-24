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
from autofanpage.errors import AutofanpageError, SkillInvocationError
from autofanpage.hourly_run_dir import HourlyRunDir
from autofanpage.hourly_state import LatestRepostedSource
from autofanpage.profile import load_profile
from autofanpage.schemas import validate


def _report(run_dir: Path, *, status: str, page: str, details: dict) -> None:
    try:
        run_skill(
            "telegram-reporter",
            {
                "run_dir": str(run_dir),
                "status": status,
                "page": page,
                "details": details,
            },
        )
    except SkillInvocationError as e:
        sys.stderr.write(f"[orchestrate] telegram-reporter failed: {e}\n")
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[orchestrate] telegram-reporter failed: {type(e).__name__}: {e}\n")


def _log(log_path: Path, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"{message}\n")


def _log_tail(log_path: Path) -> str:
    if not log_path.exists():
        return "(no log)"
    return "\n".join(log_path.read_text(encoding="utf-8").splitlines()[-20:])


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
    log_path = run_dir.path / "orchestrate.log"
    date = args.date or datetime.now(tz=ZoneInfo(profile.timezone)).strftime("%Y-%m-%d")
    state = LatestRepostedSource(base=base, page=args.page)
    started = time.monotonic()
    _log(log_path, f"start page={args.page} date={date}")

    try:
        run_skill(
            "facebook-page-latest-researcher",
            {
                "run_dir": str(run_dir.path),
                "profile": args.profile_path,
            },
        )

        latest_post = json.loads(
            (run_dir.path / "latest_source_post.json").read_text(encoding="utf-8")
        )
        if state.matches(latest_post):
            repost_decision = {
                "action": "skip_duplicate",
                "reason": "latest source post already reposted",
                "source_post_id": latest_post.get("source_post_id"),
                "source_post_url": latest_post["source_post_url"],
            }
            validate("repost_decision", repost_decision)
            (run_dir.path / "repost_decision.json").write_text(
                json.dumps(repost_decision, indent=2),
                encoding="utf-8",
            )
            _log(log_path, f"skip duplicate source_post_url={latest_post['source_post_url']}")
            _report(
                run_dir.path,
                status="info",
                page=args.page,
                details={"message": f"Skip duplicate source post: {latest_post['source_post_url']}"},
            )
            return 0

        publish_time = _next_publish_time(profile.timezone)
        _log(log_path, f"publish_time={publish_time}")
        run_skill(
            "hourly-facebook-writer",
            {
                "run_dir": str(run_dir.path),
                "profile": args.profile_path,
                "date": date,
                "publish_time": publish_time,
            },
        )
        if profile.publishing.images.enabled:
            _log(
                log_path,
                "image_generation enabled provider="
                f"{profile.publishing.images.provider} candidates="
                f"{profile.publishing.images.candidate_count}",
            )
            run_skill(
                "hourly-facebook-image-generator",
                {
                    "run_dir": str(run_dir.path),
                    "profile": args.profile_path,
                    "date": date,
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

        publish_results = json.loads(
            (run_dir.path / "publish_results.json").read_text(encoding="utf-8")
        )
        posts_scheduled = sum(1 for post in publish_results["posts"] if post["status"] == 200)
        if posts_scheduled < 1:
            raise AutofanpageError(
                "hourly repost publish_results.json recorded no successful posts"
            )

        state.mark(
            source_post_id=latest_post.get("source_post_id"),
            source_post_url=latest_post["source_post_url"],
            published_at=latest_post["published_at"],
            run_dir=str(run_dir.path),
        )
        _log(log_path, f"success posts_scheduled={posts_scheduled}")

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
    except AutofanpageError as e:
        _log(log_path, f"ERROR: {e}")
        _report(
            run_dir.path,
            status="error",
            page=args.page,
            details={
                "phase": "orchestrator",
                "cause": str(e),
                "log_tail": _log_tail(log_path),
            },
        )
        return 1
    except Exception as e:
        _log(log_path, f"UNEXPECTED: {type(e).__name__}: {e}")
        _report(
            run_dir.path,
            status="error",
            page=args.page,
            details={
                "phase": "orchestrator",
                "cause": f"{type(e).__name__}: {e}",
                "log_tail": _log_tail(log_path),
            },
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
