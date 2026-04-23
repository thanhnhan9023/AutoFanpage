"""Run-directory management for hourly repost runs."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HourlyRunDir:
    path: Path

    @classmethod
    def create(cls, base: Path, page: str, run_label: str) -> "HourlyRunDir":
        path = Path(base) / "runs" / page / "hourly" / run_label
        path.mkdir(parents=True, exist_ok=True)
        return cls(path=path)
