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
        "writing": {
            "type": "object",
            "properties": {
                "model": {"type": "string"},
                "max_tokens": {"type": "integer", "minimum": 1},
                "temperature": {"type": "number"},
                "api_key_ref": {"type": "string", "pattern": r"^secret:"},
                "style": {"type": "string", "enum": ["ai5phut"]},
            },
        },
        "publishing": {
            "type": "object",
            "properties": {
                "backend": {
                    "type": "string",
                    "enum": ["facebook_graph", "mixpost_ui"],
                },
            },
        },
        "sources": {
            "type": "object",
            "required": ["youtube", "perplexity", "twitter_via_perplexity",
                         "reddit", "hackernews"],
            "properties": {
                "perplexity": {
                    "type": "object",
                    "properties": {
                        "backend": {
                            "type": "string",
                            "enum": ["tavily", "perplexity"],
                        },
                    },
                },
                "reddit": {
                    "type": "object",
                    "properties": {
                        "backend": {"type": "string", "enum": ["apify", "oauth"]},
                    },
                },
                "facebook_page_latest": {
                    "type": "object",
                    "required": ["enabled", "page_url"],
                    "properties": {
                        "enabled": {"type": "boolean"},
                        "backend": {
                            "type": "string",
                            "enum": ["browser_use_mcp", "agent_browser"],
                        },
                        "page_url": {"type": "string", "minLength": 1},
                        "browser_use_profile_id": {"type": "string"},
                        "agent_browser_profile": {"type": "string"},
                        "agent_browser_session_name": {"type": "string"},
                        "agent_browser_state_path": {"type": "string"},
                    },
                },
            },
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


YOUTUBE_RESULTS_SCHEMA = {
    "type": "object",
    "required": ["source", "fetched_at", "items"],
    "properties": {
        "source": {"const": "youtube"},
        "fetched_at": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["title", "url", "video_id", "channel",
                             "views", "published_at"],
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "video_id": {"type": "string"},
                    "channel": {"type": "string"},
                    "channel_id": {"type": "string"},
                    "views": {"type": "integer", "minimum": 0},
                    "subscribers": {"type": "integer", "minimum": 0},
                    "published_at": {"type": "string"},
                },
            },
        },
    },
}


_PERP_ITEM = {
    "type": "object",
    "required": ["title", "url", "summary", "source"],
    "properties": {
        "title": {"type": "string"},
        "url": {"type": "string"},
        "summary": {"type": "string"},
        "source": {"type": "string"},
    },
}

PERPLEXITY_RESULTS_SCHEMA = {
    "type": "object",
    "required": ["source", "fetched_at", "news", "reports", "twitter"],
    "properties": {
        "source": {"const": "perplexity"},
        "fetched_at": {"type": "string"},
        "news": {"type": "array", "items": _PERP_ITEM},
        "reports": {"type": "array", "items": _PERP_ITEM},
        "twitter": {"type": "array", "items": _PERP_ITEM},
    },
}


REDDIT_RESULTS_SCHEMA = {
    "type": "object",
    "required": ["source", "fetched_at", "items"],
    "properties": {
        "source": {"const": "reddit"},
        "fetched_at": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["title", "url", "subreddit", "score",
                             "num_comments", "author", "permalink",
                             "created_at", "is_self"],
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "subreddit": {"type": "string"},
                    "score": {"type": "integer"},
                    "num_comments": {"type": "integer"},
                    "author": {"type": "string"},
                    "permalink": {"type": "string"},
                    "created_at": {"type": "string"},
                    "is_self": {"type": "boolean"},
                    "external_url": {"type": "string"},
                },
            },
        },
    },
}


MERGED_SOURCES_SCHEMA = {
    "type": "object",
    "required": ["profile", "topic", "language", "fetched_at",
                 "sources_succeeded", "sources_failed",
                 "counts_per_platform", "urls"],
    "properties": {
        "profile": {"type": "string"},
        "topic": {"type": "string"},
        "language": {"type": "string"},
        "fetched_at": {"type": "string"},
        "sources_succeeded": {"type": "array", "items": {"type": "string"}},
        "sources_failed": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["source", "error"],
                "properties": {
                    "source": {"type": "string"},
                    "error": {"type": "string"},
                },
            },
        },
        "counts_per_platform": {
            "type": "object",
            "additionalProperties": {"type": "integer"},
        },
        "urls": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["url", "title", "platform", "score_or_views",
                             "created_at"],
                "properties": {
                    "url": {"type": "string"},
                    "title": {"type": "string"},
                    "platform": {"type": "string"},
                    "score_or_views": {"type": "integer"},
                    "created_at": {"type": "string"},
                },
            },
        },
    },
}


INSIGHTS_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "overview", "pain_points", "insights", "gap_topics",
        "source_urls", "language",
    ],
    "additionalProperties": True,
    "properties": {
        "overview": {"type": "string"},
        "pain_points": {"type": "array", "items": {"type": "string"}},
        "insights": {"type": "array", "items": {"type": "string"}},
        "gap_topics": {"type": "array", "items": {"type": "string"}},
        "source_urls": {
            "type": "array",
            "items": {"type": "string", "format": "uri"},
        },
        "language": {"type": "string"},
        "notebook_id": {"type": "string"},
    },
}


_POST_TYPES = ["news", "guide", "opinion", "case_study"]


REVIEWED_INSIGHTS_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["approved", "rejected"],
    "additionalProperties": True,
    "properties": {
        "approved": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "insight", "scores", "total",
                    "suggested_post_type", "hook_angle", "source_url",
                ],
                "additionalProperties": True,
                "properties": {
                    "insight": {"type": "string"},
                    "scores": {
                        "type": "object",
                        "required": ["relevance", "novelty", "viral", "actionable"],
                        "additionalProperties": False,
                        "properties": {
                            "relevance":  {"type": "integer", "minimum": 1, "maximum": 5},
                            "novelty":    {"type": "integer", "minimum": 1, "maximum": 5},
                            "viral":      {"type": "integer", "minimum": 1, "maximum": 5},
                            "actionable": {"type": "integer", "minimum": 1, "maximum": 5},
                        },
                    },
                    "total": {"type": "integer", "minimum": 4, "maximum": 20},
                    "suggested_post_type": {"type": "string", "enum": _POST_TYPES},
                    "hook_angle": {"type": "string"},
                    "source_url": {"type": "string"},
                },
            },
        },
        "rejected": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["insight", "total", "reason"],
                "additionalProperties": True,
                "properties": {
                    "insight": {"type": "string"},
                    "total": {"type": "integer", "minimum": 4, "maximum": 20},
                    "reason": {"type": "string"},
                },
            },
        },
    },
}


POSTS_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["posts", "language"],
    "additionalProperties": True,
    "properties": {
        "language": {"type": "string"},
        "posts": {
            "type": "array",
            "minItems": 4,
            "maxItems": 4,
            "items": {
                "type": "object",
                "required": ["time", "type", "content", "first_comment"],
                "additionalProperties": True,
                "properties": {
                    "time": {
                        "type": "string",
                        "pattern": "^[0-2][0-9]:[0-5][0-9]$",
                    },
                    "type": {"type": "string", "enum": _POST_TYPES},
                    "content": {"type": ["string", "null"]},
                    "first_comment": {"type": ["string", "null"]},
                },
            },
        },
    },
}


PUBLISH_RESULTS_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["page", "date", "posts"],
    "additionalProperties": True,
    "properties": {
        "page": {"type": "string"},
        "date": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        "posts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["time", "type", "post_id", "comment_id", "status"],
                "additionalProperties": True,
                "properties": {
                    "time": {
                        "type": "string",
                        "pattern": r"^[0-2][0-9]:[0-5][0-9]$",
                    },
                    "type": {"type": "string", "enum": _POST_TYPES},
                    "post_id": {"type": ["string", "null"]},
                    "comment_id": {"type": ["string", "null"]},
                    "status": {"type": "integer"},
                },
            },
        },
    },
}


_SCHEMAS = {
    "profile": PROFILE_SCHEMA,
    "hackernews_results": HACKERNEWS_RESULTS_SCHEMA,
    "last_success": LAST_SUCCESS_SCHEMA,
    "youtube_results": YOUTUBE_RESULTS_SCHEMA,
    "perplexity_results": PERPLEXITY_RESULTS_SCHEMA,
    "reddit_results": REDDIT_RESULTS_SCHEMA,
    "merged_sources": MERGED_SOURCES_SCHEMA,
    "insights":           INSIGHTS_SCHEMA,
    "reviewed_insights":  REVIEWED_INSIGHTS_SCHEMA,
    "posts":              POSTS_SCHEMA,
    "publish_results":    PUBLISH_RESULTS_SCHEMA,
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
