"""Orchestrator entry point for the AutoFanpage daily pipeline.

Plan 1 vertical slice: calls hackernews-researcher then telegram-reporter.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

from autofanpage.dispatch import run_skill  # noqa: E402
from autofanpage.errors import AutofanpageError, SkillInvocationError  # noqa: E402
from autofanpage.profile import load_profile  # noqa: E402
from autofanpage.run_dir import RunDir  # noqa: E402
from autofanpage.state import LastSuccess  # noqa: E402


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
    run_dir.log(f"orchestrator start page={args.page} date={date}")
    started = time.monotonic()

    try:
        result = run_skill("hackernews-researcher", {
            "run_dir": str(run_dir.path),
            "profile": str(args.profile_path),
        })
        run_dir.log(f"hackernews-researcher -> {json.dumps(result)}")

        elapsed = int(time.monotonic() - started)
        posts_scheduled = 0
        state.mark(date=date, run_dir=str(run_dir.path),
                   posts_scheduled=posts_scheduled)
        _report(run_dir.path, status="success", page=args.page, details={
            "date": date,
            "posts_scheduled": posts_scheduled,
            "elapsed_sec": elapsed,
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
    except Exception as e:  # noqa: BLE001
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
