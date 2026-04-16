"""Per-page profile loader."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autofanpage.errors import ProfileError, SchemaError
from autofanpage.schemas import validate


@dataclass(frozen=True)
class Profile:
    name: str
    page_id: str
    access_token_ref: str
    topic: str
    language: str
    post_times: list[str]
    timezone: str
    min_posts_required: int
    max_sources_per_platform: int
    sources: dict[str, Any]
    filters: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        return cls(
            name=data["name"],
            page_id=data["page_id"],
            access_token_ref=data["access_token_ref"],
            topic=data["topic"],
            language=data["language"],
            post_times=list(data["post_times"]),
            timezone=data["timezone"],
            min_posts_required=data["min_posts_required"],
            max_sources_per_platform=data["max_sources_per_platform"],
            sources=data["sources"],
            filters=data.get("filters", {}),
        )


def load_profile(path: str | Path) -> Profile:
    p = Path(path)
    if not p.exists():
        raise ProfileError(f"profile file not found: {p}")
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        raise ProfileError(f"failed to parse profile {p}: {e}") from e
    try:
        validate("profile", data)
    except SchemaError as e:
        raise ProfileError(str(e)) from e
    return Profile.from_dict(data)
