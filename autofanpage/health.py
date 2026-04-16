"""Health check helpers: stale-page detection and run-directory pruning."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path


def find_stale_pages(base: Path, *, today: str) -> list[str]:
    """Return page names whose last_success.json is missing or not for today."""
    state_dir = Path(base) / "state"
    if not state_dir.exists():
        return []

    stale = []
    for page_dir in sorted(state_dir.iterdir()):
        if not page_dir.is_dir():
            continue
        success_path = page_dir / "last_success.json"
        if not success_path.exists():
            stale.append(page_dir.name)
            continue
        try:
            payload = json.loads(success_path.read_text())
        except json.JSONDecodeError:
            stale.append(page_dir.name)
            continue
        if payload.get("date") != today:
            stale.append(page_dir.name)
    return stale


def prune_old_runs(base: Path, *, max_age_days: int = 30, today: str) -> list[str]:
    """Delete run directories older than the retention window."""
    runs_dir = Path(base) / "runs"
    if not runs_dir.exists():
        return []

    today_dt = datetime.strptime(today, "%Y-%m-%d")
    cutoff = today_dt - timedelta(days=max_age_days)
    removed = []

    for page_dir in runs_dir.iterdir():
        if not page_dir.is_dir():
            continue
        for date_dir in sorted(page_dir.iterdir()):
            if not date_dir.is_dir():
                continue
            try:
                run_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
            except ValueError:
                continue
            if run_date < cutoff:
                shutil.rmtree(date_dir)
                removed.append(date_dir.name)

    return removed
