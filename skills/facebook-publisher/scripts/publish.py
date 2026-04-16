#!/usr/bin/env python3
"""facebook-publisher: schedule posts to Facebook Graph API."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from autofanpage.errors import AutofanpageError, SourceFailedError
from autofanpage.facebook import (
    add_first_comment,
    compute_publish_time,
    render_preview,
    schedule_post,
)
from autofanpage.profile import load_profile
from autofanpage.schemas import validate
from autofanpage.secrets import get_secret


def _load_existing_results(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "publish_results.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _already_published(existing: dict[str, Any] | None, slot_time: str) -> bool:
    if not existing:
        return False
    return any(
        entry["time"] == slot_time and entry["status"] == 200
        for entry in existing.get("posts", [])
    )


def _save_results(run_dir: Path, results: dict[str, Any]) -> None:
    validate("publish_results", results)
    (run_dir / "publish_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _status_code_from_error(error: SourceFailedError) -> int:
    match = re.search(r"HTTP (\d{3})", str(error))
    if match:
        return int(match.group(1))
    return 500


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir)
    posts_path = run_dir / "posts.json"
    if not posts_path.exists():
        raise AutofanpageError(f"missing input: {posts_path}")

    posts_data = json.loads(posts_path.read_text(encoding="utf-8"))
    validate("posts", posts_data)
    profile = load_profile(args.profile)

    if args.dry_run:
        preview = render_preview(posts_data, page=profile.name, date=args.date)
        (run_dir / "preview.md").write_text(preview, encoding="utf-8")
        print(json.dumps({"status": "ok", "artifact": "preview.md", "mode": "dry_run"}))
        return 0

    access_token = get_secret(profile.access_token_ref)
    existing = _load_existing_results(run_dir)
    results: dict[str, Any] = {
        "page": profile.name,
        "date": args.date,
        "posts": list(existing["posts"]) if existing else [],
    }
    had_failure = False

    for post in posts_data["posts"]:
        if post["content"] is None:
            continue
        if _already_published(existing, post["time"]):
            continue

        publish_time = compute_publish_time(
            post_time=post["time"],
            date=args.date,
            tz_name=profile.timezone,
        )

        post_id = None
        comment_id = None
        status = 200
        try:
            post_id = schedule_post(
                page_id=profile.page_id,
                access_token=access_token,
                message=post["content"],
                publish_time=publish_time,
            )
            if post["first_comment"]:
                comment_id = add_first_comment(
                    post_id=post_id,
                    access_token=access_token,
                    message=post["first_comment"],
                )
        except SourceFailedError as error:
            had_failure = True
            status = _status_code_from_error(error)

        results["posts"].append({
            "time": post["time"],
            "type": post["type"],
            "post_id": post_id,
            "comment_id": comment_id,
            "status": status,
        })
        _save_results(run_dir, results)

    published = sum(1 for post in results["posts"] if post["status"] == 200)
    print(json.dumps({
        "status": "ok" if not had_failure else "partial",
        "artifact": "publish_results.json",
        "posts_published": published,
    }))
    return 1 if had_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
