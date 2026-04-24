#!/usr/bin/env python3
"""facebook-publisher: schedule posts to Facebook Graph API."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

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
from autofanpage.mixpost import schedule_slot_via_mixpost
from autofanpage.profile import load_profile
from autofanpage.schemas import validate
from autofanpage.secrets import get_secret


def _load_existing_results(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "publish_results.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_post_assets(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "post_assets.json"
    if not path.exists():
        raise AutofanpageError(f"missing input: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate("post_assets", payload)
    return payload


def _find_asset_by_slot_time(assets_payload: dict[str, Any], slot_time: str) -> dict[str, Any] | None:
    for asset in assets_payload.get("assets", []):
        if asset.get("time") == slot_time:
            return asset
    return None


def _mixpost_image_path_for_slot(
    *,
    run_dir: Path,
    assets_payload: dict[str, Any],
    slot_time: str,
) -> str:
    asset = _find_asset_by_slot_time(assets_payload, slot_time)
    final_image_path = asset.get("final_image_path") if asset else None
    if asset is None or asset.get("status") != "ok" or not isinstance(final_image_path, str):
        raise AutofanpageError(f"missing valid Mixpost image asset for filled slot {slot_time}")
    resolved_path = (run_dir / final_image_path).resolve()
    if not resolved_path.is_file():
        raise AutofanpageError(f"missing Mixpost image file for filled slot {slot_time}")
    return str(resolved_path)


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


def _publish_via_graph(*, profile: Any, post: dict[str, Any], date: str) -> dict[str, Any]:
    access_token = get_secret(profile.access_token_ref)
    publish_time = compute_publish_time(
        post_time=post["time"],
        date=date,
        tz_name=profile.timezone,
    )
    post_id = schedule_post(
        page_id=profile.page_id,
        access_token=access_token,
        message=post["content"],
        publish_time=publish_time,
    )
    comment_id = None
    if post["first_comment"]:
        comment_id = add_first_comment(
            post_id=post_id,
            access_token=access_token,
            message=post["first_comment"],
        )
    return {"post_id": post_id, "comment_id": comment_id, "status": 200}


def _compute_mixpost_publish_slot(
    *,
    date: str,
    post_time: str,
    timezone_name: str,
    wall_now: datetime | None = None,
) -> tuple[str, str]:
    tz = ZoneInfo(timezone_name)
    if wall_now is None:
        wall_now = datetime.now(tz)
    year, month, day = int(date[:4]), int(date[5:7]), int(date[8:10])
    hour, minute = int(post_time[:2]), int(post_time[3:])
    target = datetime(year, month, day, hour, minute, tzinfo=tz)
    if (target - wall_now).total_seconds() < 10 * 60:
        target = wall_now + timedelta(minutes=15)
    return target.strftime("%Y-%m-%d"), target.strftime("%H:%M")


def _publish_via_mixpost(
    *,
    profile: Any,
    post: dict[str, Any],
    date: str,
    image_path: str | None = None,
) -> dict[str, Any]:
    publish_date, publish_time = _compute_mixpost_publish_slot(
        date=date,
        post_time=post["time"],
        timezone_name=profile.timezone,
    )
    return schedule_slot_via_mixpost(
        base_url=profile.publishing.mixpost.base_url,
        storage_state_path=profile.publishing.mixpost.storage_state_path,
        headless=profile.publishing.mixpost.headless,
        page_name=profile.name,
        content=post["content"],
        publish_date=publish_date,
        publish_time=publish_time,
        timezone=profile.timezone,
        image_path=image_path,
    )


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
    assets_payload = None

    if args.dry_run:
        preview = render_preview(posts_data, page=profile.name, date=args.date)
        (run_dir / "preview.md").write_text(preview, encoding="utf-8")
        print(json.dumps({"status": "ok", "artifact": "preview.md", "mode": "dry_run"}))
        return 0

    if profile.publishing_backend == "mixpost_ui" and profile.publishing.images.enabled:
        assets_payload = _load_post_assets(run_dir)

    existing = _load_existing_results(run_dir)
    results: dict[str, Any] = {
        "page": profile.name,
        "backend": profile.publishing_backend,
        "date": args.date,
        "posts": list(existing["posts"]) if existing else [],
    }
    had_failure = False

    for post in posts_data["posts"]:
        if post["content"] is None:
            continue
        if _already_published(existing, post["time"]):
            continue

        post_id = None
        comment_id = None
        status = 200
        try:
            if profile.publishing_backend == "mixpost_ui":
                outcome = _publish_via_mixpost(
                    profile=profile,
                    post=post,
                    date=args.date,
                    image_path=(
                        _mixpost_image_path_for_slot(
                            run_dir=run_dir,
                            assets_payload=assets_payload,
                            slot_time=post["time"],
                        )
                        if assets_payload is not None
                        else None
                    ),
                )
            else:
                outcome = _publish_via_graph(profile=profile, post=post, date=args.date)
            post_id = outcome["post_id"]
            comment_id = outcome["comment_id"]
            status = outcome["status"]
        except SourceFailedError as error:
            had_failure = True
            status = _status_code_from_error(error)
        except AutofanpageError:
            had_failure = True
            status = 500

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
