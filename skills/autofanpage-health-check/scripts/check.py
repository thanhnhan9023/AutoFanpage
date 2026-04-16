#!/usr/bin/env python3
"""autofanpage-health-check: detect stale pages and prune old runs."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from autofanpage.dispatch import run_skill
from autofanpage.health import find_stale_pages, prune_old_runs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", required=True)
    parser.add_argument("--date", default=None)
    parser.add_argument("--tz", default="Asia/Ho_Chi_Minh")
    parser.add_argument("--max-age-days", type=int, default=30)
    args = parser.parse_args(argv)

    base = Path(args.base_dir)
    today = args.date or datetime.now(tz=ZoneInfo(args.tz)).strftime("%Y-%m-%d")

    stale_pages = find_stale_pages(base, today=today)
    if stale_pages:
        message = f"Stale pages ({today}): {', '.join(stale_pages)}"
        run_skill("telegram-reporter", {
            "run_dir": str(base),
            "status": "error",
            "page": "health-check",
            "details": {
                "phase": "health-check",
                "cause": message,
                "message": message,
                "log_tail": "",
            },
        })

    removed = prune_old_runs(base, max_age_days=args.max_age_days, today=today)
    if removed:
        print(json.dumps({"pruned": removed}))

    print(json.dumps({
        "status": "ok",
        "stale_pages": stale_pages,
        "pruned_runs": len(removed),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
