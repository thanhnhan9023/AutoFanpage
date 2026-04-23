"""Run-directory management for hourly repost runs."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def _safe_segment(value: str) -> str:
    candidate = Path(value)
    if candidate.is_absolute() or len(candidate.parts) != 1:
        raise ValueError(f"invalid path segment: {value!r}")
    part = candidate.parts[0]
    if part in {"", ".", ".."}:
        raise ValueError(f"invalid path segment: {value!r}")
    return part


@dataclass(frozen=True)
class HourlyRunDir:
    path: Path

    @classmethod
    def create(cls, base: Path, page: str, run_label: str) -> "HourlyRunDir":
        path = (
            Path(base)
            / "runs"
            / _safe_segment(page)
            / "hourly"
            / _safe_segment(run_label)
        )
        path.mkdir(parents=True, exist_ok=True)
        return cls(path=path)
