"""Idempotency marker for hourly reposted source posts."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autofanpage.schemas import validate


@dataclass(frozen=True)
class LatestRepostedSource:
    base: Path
    page: str

    @property
    def path(self) -> Path:
        return Path(self.base) / "state" / self.page / "latest_reposted_source.json"

    def read(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        return json.loads(self.path.read_text())

    def mark(
        self,
        *,
        source_post_id: str | None,
        source_post_url: str,
        published_at: str,
        run_dir: str,
        reposted_at: str | None = None,
    ) -> None:
        payload = {
            "source_post_id": source_post_id,
            "source_post_url": source_post_url,
            "published_at": published_at,
            "reposted_at": reposted_at or datetime.now(timezone.utc).isoformat(),
            "run_dir": str(run_dir),
        }
        validate("latest_reposted_source", payload)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2))

    def matches(self, source_post: dict[str, Any]) -> bool:
        current = self.read()
        if current is None:
            return False

        current_id = current.get("source_post_id")
        source_id = source_post.get("source_post_id")
        if current_id and source_id:
            return current_id == source_id

        return current.get("source_post_url") == source_post.get("source_post_url")
