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
    "hackernews": "hackernews-researcher",
}

SOURCE_ARTIFACTS = {
    "youtube": "youtube_results.json",
    "perplexity": "perplexity_results.json",
    "reddit": "reddit_results.json",
    "hackernews": "hackernews_results.json",
}

PHASE2_SKILL = "notebooklm-analyzer"
PHASE3A_SKILL = "review-agent"
PHASE3B_SKILL = "writing-agent"
PHASE4_SKILL = "facebook-publisher"

NOTEBOOKLM_RETRIES = 1


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
    ] + (
        ["reddit"] if profile.sources.get("reddit", {}).get("enabled", False) else []
    )


def _source_skill_name(profile, key: str) -> str:
    if key != "reddit":
        return SOURCE_SKILLS[key]
    backend = profile.sources.get("reddit", {}).get("backend", "apify")
    return "reddit-researcher-apify" if backend == "apify" else "reddit-researcher"


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
            pool.submit(_invoke, key, _source_skill_name(profile, key), run_dir.path, profile_path)
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


def _run_with_retry(name: str, args: dict, retries: int, run_dir: RunDir) -> None:
    last = None
    for attempt in range(retries + 1):
        try:
            run_skill(name, args)
            return
        except Exception as e:  # noqa: BLE001
            last = e
            run_dir.log(f"[{name}] attempt {attempt + 1} failed: {e}")
            if attempt < retries:
                time.sleep(30)
    raise last  # type: ignore[misc]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", required=True)
    parser.add_argument("--profile-path", required=True)
    parser.add_argument("--base-dir", required=True)
    parser.add_argument("--date", default=None)
    parser.add_argument("--dry-run", action="store_true", default=False)
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

        # ----- Phase 2: NotebookLM (mandatory) -----
        run_dir.log("phase2 notebooklm-analyzer start")
        try:
            _run_with_retry(
                PHASE2_SKILL,
                {"run_dir": str(run_dir.path),
                 "profile": args.profile_path,
                 "language": profile.language},
                retries=NOTEBOOKLM_RETRIES,
                run_dir=run_dir,
            )
        except Exception as e:  # noqa: BLE001
            run_dir.log(f"PHASE2 FAIL: {e}")
            log_tail = "\n".join(run_dir.log_path.read_text().splitlines()[-20:])
            cause = str(e)
            if "cookies" in cause.lower():
                cause = (cause + "\nRun `nlm login` to refresh NotebookLM cookies.")
            _report(run_dir.path, status="error", page=args.page, details={
                "phase": "phase2-notebooklm", "cause": cause,
                "log_tail": log_tail,
            })
            return 1

        # ----- Phase 3a: Review -----
        run_dir.log("phase3a review-agent start")
        run_skill(PHASE3A_SKILL, {
            "run_dir": str(run_dir.path),
            "profile": args.profile_path,
        })
        reviewed = json.loads(
            (run_dir.path / "reviewed_insights.json").read_text(encoding="utf-8")
        )
        approved_count = len(reviewed["approved"])
        run_dir.log(f"review approved={approved_count}")

        if approved_count < profile.min_posts_required:
            elapsed = int(time.monotonic() - started)
            state.mark(date=date, run_dir=str(run_dir.path), posts_scheduled=0)
            _report(run_dir.path, status="partial", page=args.page, details={
                "date": date,
                "phase": "review",
                "approved_count": approved_count,
                "posts_generated": 0,
                "elapsed_sec": elapsed,
                "phase1_counts": counts,
                "phase1_failed_sources": list(failures),
            })
            return 0  # soft-success

        # ----- Phase 3b: Writing -----
        run_dir.log("phase3b writing-agent start")
        run_skill(PHASE3B_SKILL, {
            "run_dir": str(run_dir.path),
            "profile": args.profile_path,
        })
        posts = json.loads(
            (run_dir.path / "posts.json").read_text(encoding="utf-8")
        )
        posts_generated = sum(1 for p in posts["posts"] if p["content"])
        run_dir.log(f"writing generated={posts_generated}")

        # ----- Phase 4: Publish / Dry-run -----
        run_dir.log(f"phase4 facebook-publisher start dry_run={args.dry_run}")
        run_skill(PHASE4_SKILL, {
            "run_dir": str(run_dir.path),
            "profile": args.profile_path,
            "date": date,
            "dry_run": args.dry_run,
        })

        if args.dry_run:
            preview_path = run_dir.path / "preview.md"
            preview = preview_path.read_text(encoding="utf-8") if preview_path.exists() else "(empty)"
            _report(run_dir.path, status="info", page=args.page, details={
                "message": f"Dry-run preview:\n\n{preview}",
            })
            return 0

        pub_results = json.loads(
            (run_dir.path / "publish_results.json").read_text(encoding="utf-8")
        )
        posts_scheduled = sum(
            1 for post in pub_results["posts"] if post["status"] == 200
        )
        run_dir.log(f"publish scheduled={posts_scheduled}")

        elapsed = int(time.monotonic() - started)
        state.mark(date=date, run_dir=str(run_dir.path),
                   posts_scheduled=posts_scheduled)
        _report(run_dir.path, status="success", page=args.page, details={
            "date": date,
            "posts_scheduled": posts_scheduled,
            "posts_generated": posts_generated,
            "approved_count": approved_count,
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
