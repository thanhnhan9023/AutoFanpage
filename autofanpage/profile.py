"""Per-page profile loader."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autofanpage.errors import ProfileError, SchemaError
from autofanpage.schemas import validate


@dataclass(frozen=True)
class WritingConfig:
    model: str = "claude-opus-4-6"
    max_tokens: int = 900
    temperature: float = 0.7
    api_key_ref: str = "secret:anthropic_api_key"
    style: str | None = None
    review_model: str | None = None
    review_api_key_ref: str | None = None
    review_max_rounds: int = 3


@dataclass(frozen=True)
class MixpostPublishingConfig:
    base_url: str = ""
    storage_state_path: str = ""
    headless: bool = True


@dataclass(frozen=True)
class ImageCanvasConfig:
    width: int = 1080
    height: int = 1350
    theme: str = "ai5phut"


@dataclass(frozen=True)
class ImagePublishingConfig:
    enabled: bool = False
    provider: str = "useapi_google_flow"
    fallback_provider: str | None = None
    useapi_base_url: str = "https://api.useapi.net"
    useapi_token_ref: str = "secret:useapi_token"
    google_flow_account_ref: str | None = None
    capsolver_api_key_ref: str | None = None
    codex_imagen_script_path: str = "/tmp/codex-imagen/scripts/codex-imagen.mjs"
    codex_auth_json_path: str = "~/.codex/auth.json"
    codex_timeout_seconds: int = 300
    codex_model: str = "gpt-5.4"
    zai_base_url: str = "https://api.z.ai/api/paas/v4"
    zai_api_key_ref: str = "secret:zai_api_key"
    zai_model: str = "glm-image"
    zai_quality: str = "standard"
    require_image_for_publish: bool = True
    overlay_mode: str = "none"
    candidate_count: int = 4
    canvas: ImageCanvasConfig = field(default_factory=ImageCanvasConfig)


@dataclass(frozen=True)
class PublishingConfig:
    backend: str | None = None
    mixpost: MixpostPublishingConfig = field(default_factory=MixpostPublishingConfig)
    images: ImagePublishingConfig = field(default_factory=ImagePublishingConfig)


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
    writing: WritingConfig = field(default_factory=WritingConfig)
    publishing: PublishingConfig = field(default_factory=PublishingConfig)
    publishing_backend: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        writing_data = data.get("writing", {})
        writing = WritingConfig(**writing_data) if writing_data else WritingConfig()
        sources = dict(data["sources"])
        reddit = dict(sources.get("reddit", {}))
        if reddit:
            reddit.setdefault("backend", "apify")
            sources["reddit"] = reddit
        if "perplexity" in sources:
            perplexity = dict(sources.get("perplexity", {}))
            perplexity.setdefault("backend", "tavily")
            sources["perplexity"] = perplexity
        fb_latest = dict(sources.get("facebook_page_latest", {}))
        if fb_latest:
            fb_latest.setdefault("backend", "browser_use_mcp")
            sources["facebook_page_latest"] = fb_latest
        publishing_data = data.get("publishing", {})
        publishing = publishing_data if isinstance(publishing_data, dict) else {}
        mixpost_data = publishing.get("mixpost", {})
        images_data = publishing.get("images", {})
        canvas_data = images_data.get("canvas", {}) if isinstance(images_data, dict) else {}
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
            sources=sources,
            filters=data.get("filters", {}),
            writing=writing,
            publishing=PublishingConfig(
                backend=publishing.get("backend"),
                mixpost=MixpostPublishingConfig(
                    base_url=mixpost_data.get("base_url", ""),
                    storage_state_path=mixpost_data.get("storage_state_path", ""),
                    headless=mixpost_data.get("headless", True),
                ),
                images=ImagePublishingConfig(
                    enabled=images_data.get("enabled", False),
                    provider=images_data.get("provider", "useapi_google_flow"),
                    fallback_provider=images_data.get("fallback_provider"),
                    useapi_base_url=images_data.get(
                        "useapi_base_url", "https://api.useapi.net"
                    ),
                    useapi_token_ref=images_data.get(
                        "useapi_token_ref", "secret:useapi_token"
                    ),
                    google_flow_account_ref=images_data.get("google_flow_account_ref"),
                    capsolver_api_key_ref=images_data.get("capsolver_api_key_ref"),
                    codex_imagen_script_path=images_data.get(
                        "codex_imagen_script_path",
                        "/tmp/codex-imagen/scripts/codex-imagen.mjs",
                    ),
                    codex_auth_json_path=images_data.get(
                        "codex_auth_json_path",
                        "~/.codex/auth.json",
                    ),
                    codex_timeout_seconds=images_data.get("codex_timeout_seconds", 300),
                    codex_model=images_data.get("codex_model", "gpt-5.4"),
                    zai_base_url=images_data.get(
                        "zai_base_url", "https://api.z.ai/api/paas/v4"
                    ),
                    zai_api_key_ref=images_data.get(
                        "zai_api_key_ref", "secret:zai_api_key"
                    ),
                    zai_model=images_data.get("zai_model", "glm-image"),
                    zai_quality=images_data.get("zai_quality", "standard"),
                    require_image_for_publish=images_data.get(
                        "require_image_for_publish", True
                    ),
                    overlay_mode=images_data.get("overlay_mode", "none"),
                    candidate_count=images_data.get("candidate_count", 4),
                    canvas=ImageCanvasConfig(
                        width=canvas_data.get("width", 1080),
                        height=canvas_data.get("height", 1350),
                        theme=canvas_data.get("theme", "ai5phut"),
                    ),
                ),
            ),
            publishing_backend=publishing.get("backend"),
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
