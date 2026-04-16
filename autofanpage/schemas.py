"""JSON schema validation for all pipeline artifacts."""
from __future__ import annotations

from typing import Any

import jsonschema

from autofanpage.errors import SchemaError


PROFILE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "name", "page_id", "access_token_ref", "topic", "language",
        "post_times", "timezone", "min_posts_required",
        "max_sources_per_platform", "sources",
    ],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "page_id": {"type": "string", "minLength": 1},
        "access_token_ref": {"type": "string", "pattern": r"^secret:"},
        "topic": {"type": "string", "minLength": 1},
        "language": {"type": "string", "minLength": 2},
        "post_times": {
            "type": "array",
            "minItems": 4, "maxItems": 4,
            "items": {"type": "string", "pattern": r"^\d{2}:\d{2}$"},
        },
        "timezone": {"type": "string", "minLength": 1},
        "filters": {"type": "object"},
        "min_posts_required": {"type": "integer", "minimum": 0, "maximum": 4},
        "max_sources_per_platform": {"type": "integer", "minimum": 1},
        "sources": {
            "type": "object",
            "required": ["youtube", "perplexity", "twitter_via_perplexity",
                         "reddit", "hackernews"],
        },
    },
}


HACKERNEWS_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["title", "url", "points", "by", "descendants",
                 "created_at", "hn_url"],
    "properties": {
        "title": {"type": "string"},
        "url": {"type": "string"},
        "points": {"type": "integer"},
        "by": {"type": "string"},
        "descendants": {"type": "integer"},
        "created_at": {"type": "string"},
        "hn_url": {"type": "string"},
    },
}

HACKERNEWS_RESULTS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["source", "fetched_at", "items"],
    "properties": {
        "source": {"const": "hackernews"},
        "fetched_at": {"type": "string"},
        "items": {
            "type": "array",
            "items": HACKERNEWS_ITEM_SCHEMA,
        },
    },
}


LAST_SUCCESS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["date", "run_dir", "posts_scheduled", "completed_at"],
    "properties": {
        "date": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        "run_dir": {"type": "string"},
        "posts_scheduled": {"type": "integer", "minimum": 0},
        "completed_at": {"type": "string"},
    },
}


_SCHEMAS = {
    "profile": PROFILE_SCHEMA,
    "hackernews_results": HACKERNEWS_RESULTS_SCHEMA,
    "last_success": LAST_SUCCESS_SCHEMA,
}


def validate(name: str, data: Any) -> None:
    """Validate `data` against schema `name`. Raise SchemaError on failure."""
    if name not in _SCHEMAS:
        raise KeyError(f"unknown schema: {name}")
    validator = jsonschema.Draft7Validator(_SCHEMAS[name])
    errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
    if errors:
        violations = [
            f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in errors
        ]
        raise SchemaError(name, violations)
