"""Idempotency marker for hourly reposted source posts."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autofanpage.errors import SchemaError
from autofanpage.schemas import validate


def _safe_segment(value: str) -> str:
    candidate = Path(value)
    if candidate.is_absolute() or len(candidate.parts) != 1:
        raise ValueError(f"invalid path segment: {value!r}")
    part = candidate.parts[0]
    if part in {"", ".", ".."}:
        raise ValueError(f"invalid path segment: {value!r}")
    return part


@dataclass(frozen=True)
class LatestRepostedSource:
    base: Path
    page: str

    @property
    def path(self) -> Path:
        return (
            Path(self.base)
            / "state"
            / _safe_segment(self.page)
            / "latest_reposted_source.json"
        )

    def read(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        try:
            payload = json.loads(self.path.read_text())
            validate("latest_reposted_source", payload)
        except (OSError, json.JSONDecodeError, SchemaError):
            return None
        return payload

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


def _matches_record(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_id = left.get("source_post_id")
    right_id = right.get("source_post_id")
    if left_id and right_id and left_id == right_id:
        return True

    left_url = left.get("source_post_url")
    right_url = right.get("source_post_url")
    return bool(left_url and right_url and left_url == right_url)


@dataclass(frozen=True)
class RepostedSourceHistory:
    base: Path
    page: str

    @property
    def path(self) -> Path:
        return (
            Path(self.base)
            / "state"
            / _safe_segment(self.page)
            / "reposted_source_posts.json"
        )

    def _empty(self) -> dict[str, list[dict[str, Any]]]:
        return {"items": []}

    def _read_valid(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text())
            validate("reposted_source_posts", payload)
        except (OSError, json.JSONDecodeError, SchemaError) as exc:
            raise ValueError(f"invalid repost history file: {self.path}") from exc
        return payload

    def _bootstrap_from_latest(self) -> dict[str, Any]:
        latest = LatestRepostedSource(base=self.base, page=self.page).read()
        if latest is None:
            return self._empty()

        payload = {
            "items": [
                {
                    "source_post_id": latest.get("source_post_id"),
                    "source_post_url": latest["source_post_url"],
                    "published_at": latest["published_at"],
                    "published_at_resolved": latest.get("published_at_resolved"),
                    "reposted_at": latest["reposted_at"],
                    "run_dir": latest["run_dir"],
                }
            ]
        }
        validate("reposted_source_posts", payload)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2))
        return payload

    def read_or_bootstrap(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._bootstrap_from_latest()

        try:
            return self._read_valid()
        except ValueError:
            bootstrapped = self._bootstrap_from_latest()
            if bootstrapped["items"]:
                return bootstrapped
            raise

    def contains(self, source_post: dict[str, Any]) -> bool:
        history = self.read_or_bootstrap()
        return any(_matches_record(item, source_post) for item in history["items"])

    def append(
        self,
        source_post: dict[str, Any],
        *,
        run_dir: str,
        reposted_at: str | None = None,
    ) -> None:
        history = self.read_or_bootstrap()
        payload = {
            "source_post_id": source_post.get("source_post_id"),
            "source_post_url": source_post["source_post_url"],
            "published_at": source_post["published_at"],
            "published_at_resolved": source_post.get("published_at_resolved"),
            "reposted_at": reposted_at or datetime.now(timezone.utc).isoformat(),
            "run_dir": str(run_dir),
        }

        items = list(history["items"])
        for index, item in enumerate(items):
            if _matches_record(item, payload):
                items[index] = payload
                break
        else:
            items.append(payload)

        updated = {"items": items}
        validate("reposted_source_posts", updated)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(updated, indent=2))
