"""Run-directory management: artifact files + run.log for one day/page."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunDir:
    path: Path

    @property
    def log_path(self) -> Path:
        return self.path / "run.log"

    @classmethod
    def create(cls, base: Path, page: str, date: str) -> "RunDir":
        p = Path(base) / "runs" / page / date
        p.mkdir(parents=True, exist_ok=True)
        return cls(path=p)

    def write_json(self, name: str, data: Any) -> None:
        target = self.path / f"{name}.json"
        target.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def read_json(self, name: str) -> Any:
        return json.loads((self.path / f"{name}.json").read_text())

    def has_artifact(self, name: str) -> bool:
        return (self.path / f"{name}.json").exists()

    def log(self, message: str) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        with self.log_path.open("a") as fh:
            fh.write(f"[{ts}] {message}\n")
