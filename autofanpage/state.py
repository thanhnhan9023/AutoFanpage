"""Idempotency marker for successful daily runs."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from autofanpage.schemas import validate


@dataclass(frozen=True)
class LastSuccess:
    base: Path
    page: str

    @property
    def path(self) -> Path:
        return Path(self.base) / "state" / self.page / "last_success.json"

    def ran_on(self, date: str) -> bool:
        if not self.path.exists():
            return False
        data = json.loads(self.path.read_text())
        return data.get("date") == date

    def read(self) -> dict:
        return json.loads(self.path.read_text())

    def mark(self, *, date: str, run_dir: str, posts_scheduled: int) -> None:
        payload = {
            "date": date,
            "run_dir": str(run_dir),
            "posts_scheduled": posts_scheduled,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        validate("last_success", payload)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2))
