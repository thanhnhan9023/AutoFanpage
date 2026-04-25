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
                "review_model": {"type": "string"},
                "review_api_key_ref": {"type": "string", "pattern": r"^secret:"},
                "review_max_rounds": {"type": "integer", "minimum": 1, "maximum": 5},
            },
        },
        "publishing": {
            "type": "object",
            "properties": {
                "backend": {
                    "type": "string",
                    "enum": ["facebook_graph", "mixpost_ui"],
                },
                "mixpost": {
                    "type": "object",
                    "properties": {
                        "base_url": {"type": "string", "minLength": 1},
                        "storage_state_path": {"type": "string", "minLength": 1},
                        "headless": {"type": "boolean"},
                    },
                    "required": ["base_url", "storage_state_path"],
                },
                "images": {
                    "type": "object",
                    "properties": {
                        "enabled": {"type": "boolean"},
                        "provider": {
                            "type": "string",
                            "enum": ["useapi_google_flow"],
                        },
                        "fallback_provider": {
                            "type": "string",
                            "enum": ["local_playwright_card", "zai_glm_image", "codex_imagen_oauth"],
                        },
                        "useapi_base_url": {"type": "string", "minLength": 1},
                        "useapi_token_ref": {"type": "string", "pattern": r"^secret:"},
                        "google_flow_account_ref": {"type": "string", "pattern": r"^secret:"},
                        "capsolver_api_key_ref": {"type": "string", "pattern": r"^secret:"},
                        "codex_imagen_script_path": {"type": "string", "minLength": 1},
                        "codex_auth_json_path": {"type": "string", "minLength": 1},
                        "codex_timeout_seconds": {"type": "integer", "minimum": 1},
                        "codex_model": {"type": "string", "minLength": 1},
                        "zai_base_url": {"type": "string", "minLength": 1},
                        "zai_api_key_ref": {"type": "string", "pattern": r"^secret:"},
                        "zai_model": {"type": "string", "minLength": 1},
                        "zai_quality": {"type": "string", "enum": ["standard", "hd"]},
                        "require_image_for_publish": {"type": "boolean"},
                        "overlay_mode": {"type": "string", "enum": ["none"]},
                        "candidate_count": {"type": "integer", "minimum": 1, "maximum": 8},
                        "canvas": {
                            "type": "object",
                            "properties": {
                                "width": {"type": "integer", "minimum": 1},
                                "height": {"type": "integer", "minimum": 1},
                                "theme": {"type": "string", "minLength": 1},
                            },
                            "required": ["width", "height", "theme"],
                        },
                    },
                    "required": [
                        "enabled",
                        "provider",
                        "useapi_base_url",
                        "useapi_token_ref",
                        "candidate_count",
                        "canvas",
                    ],
                },
            },
            "allOf": [
                {
                    "if": {
                        "properties": {"backend": {"const": "mixpost_ui"}},
                        "required": ["backend"],
                    },
                    "then": {"required": ["mixpost"]},
                }
            ],
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

SOURCE_POST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "source_page_url",
        "source_post_id",
        "source_post_url",
        "author",
        "published_at",
        "published_at_resolved",
        "content_text",
        "media_urls",
        "backend",
        "fetched_at",
    ],
    "properties": {
        "source_page_url": {"type": "string"},
        "source_post_id": {"type": ["string", "null"]},
        "source_post_url": {"type": "string"},
        "author": {"type": "string"},
        "published_at": {"type": "string"},
        "published_at_resolved": {"type": "string"},
        "content_text": {"type": "string", "minLength": 1},
        "media_urls": {"type": "array", "items": {"type": "string"}},
        "backend": {
            "type": "string",
            "enum": ["browser_use_mcp", "agent_browser"],
        },
        "fetched_at": {"type": "string"},
    },
}


LATEST_SOURCE_POST_SCHEMA: dict[str, Any] = SOURCE_POST_SCHEMA


SOURCE_POSTS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "source_page_url",
        "backend",
        "fetched_at",
        "search_status",
        "end_of_feed_reached",
        "scan_stopped_reason",
        "posts_scanned",
        "posts",
    ],
    "properties": {
        "source_page_url": {"type": "string"},
        "backend": {
            "type": "string",
            "enum": ["browser_use_mcp", "agent_browser"],
        },
        "fetched_at": {"type": "string"},
        "search_status": {
            "type": "string",
            "enum": [
                "full_search_complete",
                "selection_ready",
                "partial_search_scope",
                "fetch_error",
            ],
        },
        "end_of_feed_reached": {"type": "boolean"},
        "scan_stopped_reason": {"type": "string"},
        "posts_scanned": {"type": "integer", "minimum": 0},
        "posts": {
            "type": "array",
            "items": SOURCE_POST_SCHEMA,
        },
    },
    "allOf": [
        {
            "if": {
                "properties": {"search_status": {"const": "selection_ready"}},
                "required": ["search_status"],
            },
            "then": {
                "properties": {
                    "posts": {"minItems": 1},
                },
            },
        },
    ],
}


REPOSTED_SOURCE_POST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "source_post_id",
        "source_post_url",
        "published_at",
        "published_at_resolved",
        "reposted_at",
        "run_dir",
    ],
    "properties": {
        "source_post_id": {"type": ["string", "null"]},
        "source_post_url": {"type": "string"},
        "published_at": {"type": "string"},
        "published_at_resolved": {"type": "string"},
        "reposted_at": {"type": "string"},
        "run_dir": {"type": "string"},
    },
}


LATEST_REPOSTED_SOURCE_SCHEMA: dict[str, Any] = REPOSTED_SOURCE_POST_SCHEMA


REPOSTED_SOURCE_POSTS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["items"],
    "properties": {
        "items": {
            "type": "array",
            "items": REPOSTED_SOURCE_POST_SCHEMA,
        },
    },
}


REPOST_DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["action", "reason"],
    "properties": {
        "action": {"type": "string", "enum": ["publish", "skip_duplicate"]},
        "reason": {"type": "string"},
        "source_post_id": {"type": ["string", "null"]},
        "source_post_url": {"type": "string"},
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


_RELATIVE_PATH_SCHEMA = {
    "type": ["string", "null"],
    "pattern": r"^(?!/)(?!.*\.\.)[^\\]*$",
}

_IMAGE_CANDIDATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["index", "job_id", "raw_image_url", "raw_image_path"],
    "properties": {
        "index": {"type": "integer", "minimum": 1},
        "job_id": {"type": "string", "minLength": 1},
        "raw_image_url": {"type": "string", "minLength": 1},
        "raw_image_path": _RELATIVE_PATH_SCHEMA,
    },
}

POST_ASSETS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["page", "provider", "date", "assets"],
    "properties": {
        "page": {"type": "string", "minLength": 1},
        "provider": {
            "type": "string",
            "enum": ["useapi_google_flow", "codex_imagen_oauth", "zai_glm_image", "local_playwright_card", "mixed"],
        },
        "date": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        "assets": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "time",
                    "type",
                    "status",
                    "provider",
                    "image_prompt",
                    "job_id",
                    "raw_image_url",
                    "raw_image_path",
                    "final_image_path",
                    "selected_candidate_index",
                    "candidates",
                    "error",
                ],
                "properties": {
                    "time": {
                        "type": "string",
                        "pattern": r"^[0-2][0-9]:[0-5][0-9]$",
                    },
                    "type": {"type": "string", "enum": _POST_TYPES},
                    "status": {"type": "string", "enum": ["ok", "failed"]},
                    "provider": {
                        "type": "string",
                        "enum": ["useapi_google_flow", "codex_imagen_oauth", "zai_glm_image", "local_playwright_card"],
                    },
                    "image_prompt": {"type": "string", "minLength": 1},
                    "job_id": {"type": ["string", "null"]},
                    "raw_image_url": {"type": ["string", "null"]},
                    "raw_image_path": _RELATIVE_PATH_SCHEMA,
                    "final_image_path": _RELATIVE_PATH_SCHEMA,
                    "selected_candidate_index": {"type": ["integer", "null"], "minimum": 1},
                    "candidates": {"type": "array", "items": _IMAGE_CANDIDATE_SCHEMA},
                    "error": {"type": ["string", "null"]},
                },
            },
        },
    },
}


_SCHEMAS = {
    "profile": PROFILE_SCHEMA,
    "hackernews_results": HACKERNEWS_RESULTS_SCHEMA,
    "last_success": LAST_SUCCESS_SCHEMA,
    "latest_source_post": LATEST_SOURCE_POST_SCHEMA,
    "source_posts": SOURCE_POSTS_SCHEMA,
    "latest_reposted_source": LATEST_REPOSTED_SOURCE_SCHEMA,
    "reposted_source_posts": REPOSTED_SOURCE_POSTS_SCHEMA,
    "repost_decision": REPOST_DECISION_SCHEMA,
    "youtube_results": YOUTUBE_RESULTS_SCHEMA,
    "perplexity_results": PERPLEXITY_RESULTS_SCHEMA,
    "reddit_results": REDDIT_RESULTS_SCHEMA,
    "merged_sources": MERGED_SOURCES_SCHEMA,
    "insights":           INSIGHTS_SCHEMA,
    "reviewed_insights":  REVIEWED_INSIGHTS_SCHEMA,
    "posts":              POSTS_SCHEMA,
    "publish_results":    PUBLISH_RESULTS_SCHEMA,
    "post_assets":        POST_ASSETS_SCHEMA,
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
