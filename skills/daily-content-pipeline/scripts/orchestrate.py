"""Orchestrator entry point for the AutoFanpage daily pipeline.

Plan 2: calls every enabled Phase-1 researcher in parallel, merges their
artifacts, enforces ``min_posts_required``, then calls telegram-reporter.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

from autofanpage.dispatch import run_skill
from autofanpage.errors import (
    AutofanpageError, SkillInvocationError, SourceFailedError,
)
from autofanpage.merge import merge_sources
from autofanpage.profile import load_profile
from autofanpage.run_dir import RunDir
from autofanpage.state import LastSuccess


SOURCE_SKILLS = {
    "youtube": "youtube-researcher",
    "perplexity": "perplexity-researcher",
    "reddit": "reddit-researcher",
    "hackernews": "hackernews-researcher",
}

SOURCE_ARTIFACTS = {
    "youtube": "youtube_results.json",
    "perplexity": "perplexity_results.json",
    "reddit": "reddit_results.json",
    "hackernews": "hackernews_results.json",
}


def _report(run_dir: Path, *, status: str, page: str, details: dict) -> None:
    try:
        run_skill("telegram-reporter", {
            "run_dir": str(run_dir),
            "status": status,
            "page": page,
            "details": details,
        })
    except SkillInvocationError as e:
        sys.stderr.write(f"[orchestrate] telegram-reporter failed: {e}\n")


def _today(profile_tz: str) -> str:
    return datetime.now(tz=ZoneInfo(profile_tz)).strftime("%Y-%m-%d")


def _enabled_sources(profile) -> list[str]:
    return [
        key for key in SOURCE_SKILLS
        if profile.sources.get(key, {}).get("enabled", False)
    ]


def _invoke(
    key: str, skill_name: str, run_dir: Path, profile_path: str,
) -> tuple[str, str | None, dict | None]:
    try:
        result = run_skill(skill_name, {
            "run_dir": str(run_dir),
            "profile": profile_path,
        })
        return key, None, result
    except (SourceFailedError, SkillInvocationError) as e:
        return key, str(e), None


def _dispatch_phase1(
    run_dir: RunDir, profile, profile_path: str,
) -> tuple[dict[str, Path], dict[str, str]]:
    enabled = _enabled_sources(profile)
    run_dir.log(f"phase1 enabled sources: {enabled}")

    artifacts: dict[str, Path] = {}
    failures: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=len(enabled) or 1) as pool:
        futures = [
            pool.submit(_invoke, key, SOURCE_SKILLS[key], run_dir.path, profile_path)
            for key in enabled
        ]
        for fut in as_completed(futures):
            key, err, _result = fut.result()
            if err:
                run_dir.log(f"[source:{key}] FAILED: {err}")
                failures[key] = err
                continue
            artifact_path = run_dir.path / SOURCE_ARTIFACTS[key]
            if not artifact_path.exists():
                run_dir.log(
                    f"[source:{key}] skill reported ok but {SOURCE_ARTIFACTS[key]} missing"
                )
                failures[key] = f"artifact missing: {SOURCE_ARTIFACTS[key]}"
                continue
            run_dir.log(f"[source:{key}] ok artifact={artifact_path}")
            artifacts[key] = artifact_path
    return artifacts, failures


def _phase1_counts(merged: dict) -> dict[str, int]:
    return merged["counts_per_platform"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", required=True)
    parser.add_argument("--profile-path", required=True)
    parser.add_argument("--base-dir", required=True)
    parser.add_argument("--date", default=None)
    args = parser.parse_args(argv)

    base = Path(args.base_dir)
    profile = load_profile(args.profile_path)
    date = args.date or _today(profile.timezone)

    state = LastSuccess(base=base, page=args.page)
    if state.ran_on(date):
        run_dir = RunDir.create(base=base, page=args.page, date=date)
        _report(run_dir.path, status="info", page=args.page,
                details={"message": f"already ran on {date}"})
        return 0

    run_dir = RunDir.create(base=base, page=args.page, date=date)
    run_dir.log(f"orchestrator start page={args.page} date={date} topic={profile.topic}")
    started = time.monotonic()

    try:
        artifacts, failures = _dispatch_phase1(run_dir, profile, args.profile_path)

        if len(artifacts) < profile.min_posts_required:
            cause = (
                f"Only {len(artifacts)} source(s) succeeded "
                f"(need >= {profile.min_posts_required}). Failures: {failures}"
            )
            run_dir.log(f"ABORT: {cause}")
            log_tail = "\n".join(run_dir.log_path.read_text().splitlines()[-20:])
            _report(run_dir.path, status="error", page=args.page, details={
                "phase": "phase1-data-gathering",
                "cause": cause,
                "log_tail": log_tail,
            })
            return 1

        merged = merge_sources(
            profile=profile.name,
            topic=profile.topic,
            language=profile.language,
            artifacts=artifacts,
            failures=failures,
            max_per_platform=getattr(profile, "max_sources_per_platform", 12),
        )
        run_dir.write_json("merged_sources", merged)
        counts = _phase1_counts(merged)
        run_dir.log(f"merged counts={counts} failed={list(failures)}")

        total_urls = len(merged["urls"])
        if total_urls == 0:
            cause = (
                f"All {len(artifacts)} source(s) returned empty results. "
                f"merged urls=0. Failures: {failures}"
            )
            run_dir.log(f"ABORT: {cause}")
            log_tail = "\n".join(run_dir.log_path.read_text().splitlines()[-20:])
            _report(run_dir.path, status="error", page=args.page, details={
                "phase": "phase1-data-gathering",
                "cause": cause,
                "log_tail": log_tail,
            })
            return 1

        elapsed = int(time.monotonic() - started)
        posts_scheduled = 0
        state.mark(
            date=date, run_dir=str(run_dir.path),
            posts_scheduled=posts_scheduled,
        )
        _report(run_dir.path, status="success", page=args.page, details={
            "date": date,
            "posts_scheduled": posts_scheduled,
            "elapsed_sec": elapsed,
            "phase1_counts": counts,
            "phase1_failed_sources": list(failures),
        })
        return 0

    except AutofanpageError as e:
        run_dir.log(f"ERROR: {e}")
        log_tail = "\n".join(run_dir.log_path.read_text().splitlines()[-20:])
        _report(run_dir.path, status="error", page=args.page, details={
            "phase": "orchestrator",
            "cause": str(e),
            "log_tail": log_tail,
        })
        return 1
    except Exception as e:
        run_dir.log(f"UNEXPECTED: {type(e).__name__}: {e}")
        log_tail = "\n".join(run_dir.log_path.read_text().splitlines()[-20:])
        _report(run_dir.path, status="error", page=args.page, details={
            "phase": "orchestrator",
            "cause": f"{type(e).__name__}: {e}",
            "log_tail": log_tail,
        })
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
