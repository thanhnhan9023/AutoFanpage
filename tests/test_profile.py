from pathlib import Path

import pytest
from autofanpage.profile import Profile, load_profile
from autofanpage.errors import ProfileError


def test_load_profile_returns_typed_object(fixtures_dir):
    profile = load_profile(fixtures_dir / "page_test.json")
    assert isinstance(profile, Profile)
    assert profile.name == "page_test"
    assert profile.page_id == "000000000000000"
    assert profile.topic == "AI automation business"
    assert profile.language == "en"
    assert profile.post_times == ["08:00", "12:00", "16:00", "20:00"]
    assert profile.timezone == "UTC"
    assert profile.min_posts_required == 1
    assert profile.sources["hackernews"]["enabled"] is True


def test_load_profile_raises_on_missing_file(tmp_path):
    with pytest.raises(ProfileError, match="not found"):
        load_profile(tmp_path / "missing.json")


def test_load_profile_raises_on_invalid_schema(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"name": "x"}')
    with pytest.raises(ProfileError, match="page_id"):
        load_profile(path)


def test_load_profile_raises_on_malformed_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json")
    with pytest.raises(ProfileError, match="parse"):
        load_profile(path)


def test_profile_loads_writing_block(fixtures_dir):
    p = load_profile(fixtures_dir / "profile_plan3.json")
    assert p.writing.model == "claude-opus-4-6"
    assert p.writing.max_tokens == 900


def test_profile_without_writing_block_uses_defaults(tmp_path, fixtures_dir):
    import json
    src = json.loads((fixtures_dir / "profile_plan2.json").read_text())
    p_path = tmp_path / "p.json"
    p_path.write_text(json.dumps(src))
    p = load_profile(str(p_path))
    assert p.writing.model == "claude-opus-4-6"
    assert p.writing.temperature == 0.7


def test_profile_defaults_reddit_backend_to_apify(tmp_path, fixtures_dir):
    import json
    src = json.loads((fixtures_dir / "profile_plan2.json").read_text())
    src["sources"]["reddit"].pop("backend", None)
    p_path = tmp_path / "p.json"
    p_path.write_text(json.dumps(src))

    p = load_profile(str(p_path))

    assert p.sources["reddit"]["backend"] == "apify"


def test_profile_defaults_perplexity_backend_to_tavily(tmp_path, fixtures_dir):
    import json
    src = json.loads((fixtures_dir / "profile_plan2.json").read_text())
    src["sources"]["perplexity"].pop("backend", None)
    p_path = tmp_path / "p.json"
    p_path.write_text(json.dumps(src))

    p = load_profile(str(p_path))

    assert p.sources["perplexity"]["backend"] == "tavily"


def test_profile_preserves_explicit_perplexity_backend(tmp_path, fixtures_dir):
    import json
    src = json.loads((fixtures_dir / "profile_plan2.json").read_text())
    src["sources"]["perplexity"]["backend"] = "perplexity"
    p_path = tmp_path / "p.json"
    p_path.write_text(json.dumps(src))

    p = load_profile(str(p_path))

    assert p.sources["perplexity"]["backend"] == "perplexity"


def test_profile_defaults_empty_perplexity_config_to_tavily(tmp_path, fixtures_dir):
    import json
    src = json.loads((fixtures_dir / "profile_plan2.json").read_text())
    src["sources"]["perplexity"] = {}
    p_path = tmp_path / "p.json"
    p_path.write_text(json.dumps(src))

    p = load_profile(str(p_path))

    assert p.sources["perplexity"]["backend"] == "tavily"


def test_profile_keeps_empty_reddit_config_unset_while_defaulting_perplexity(
    tmp_path, fixtures_dir
):
    import json
    src = json.loads((fixtures_dir / "profile_plan2.json").read_text())
    src["sources"]["reddit"] = {}
    src["sources"]["perplexity"] = {}
    p_path = tmp_path / "p.json"
    p_path.write_text(json.dumps(src))

    p = load_profile(str(p_path))

    assert "backend" not in p.sources["reddit"]
    assert p.sources["perplexity"]["backend"] == "tavily"


def test_profile_loads_hourly_writing_style(fixtures_dir):
    p = load_profile(fixtures_dir / "profile_hourly_facebook_repost.json")
    assert p.writing.style == "ai5phut"
    assert p.writing.review_model == "minimax/MiniMax-M2.7"
    assert p.writing.review_api_key_ref == "secret:writer_gateway_key"
    assert p.writing.review_max_rounds == 3


def test_profile_defaults_facebook_page_latest_backend_to_browser_use_mcp(fixtures_dir):
    p = load_profile(fixtures_dir / "profile_hourly_facebook_repost.json")
    assert p.sources["facebook_page_latest"]["backend"] == "browser_use_mcp"


def test_profile_exposes_optional_publishing_backend_for_preflight(fixtures_dir):
    p = load_profile(fixtures_dir / "profile_hourly_facebook_repost.json")
    assert p.publishing_backend == "facebook_graph"


def test_profile_loads_mixpost_publishing_settings(tmp_path, fixtures_dir):
    import json

    src = json.loads((fixtures_dir / "profile_plan3.json").read_text())
    src["publishing"] = {
        "backend": "mixpost_ui",
        "mixpost": {
            "base_url": "https://mixpost.example.test",
            "storage_state_path": str(tmp_path / "state.json"),
            "headless": False,
        },
    }
    path = tmp_path / "mixpost.json"
    path.write_text(json.dumps(src))

    p = load_profile(path)

    assert p.publishing_backend == "mixpost_ui"
    assert p.publishing.mixpost.base_url == "https://mixpost.example.test"
    assert p.publishing.mixpost.storage_state_path == str(tmp_path / "state.json")
    assert p.publishing.mixpost.headless is False


def test_profile_loads_mixpost_image_generation_settings(tmp_path, fixtures_dir):
    import json

    src = json.loads((fixtures_dir / "profile_plan3.json").read_text())
    src["publishing"] = {
        "backend": "mixpost_ui",
        "mixpost": {
            "base_url": "https://mixpost.example.test",
            "storage_state_path": str(tmp_path / "state.json"),
            "headless": True,
        },
        "images": {
            "enabled": True,
            "provider": "useapi_google_flow",
            "fallback_provider": "local_playwright_card",
            "useapi_base_url": "https://api.useapi.net",
            "useapi_token_ref": "secret:useapi_token",
            "google_flow_account_ref": "secret:useapi_google_flow_account",
            "candidate_count": 4,
            "overlay_mode": "none",
            "require_image_for_publish": True,
            "canvas": {
                "width": 1080,
                "height": 1350,
                "theme": "ai5phut",
            },
        },
    }
    path = tmp_path / "mixpost-images.json"
    path.write_text(json.dumps(src), encoding="utf-8")

    p = load_profile(path)

    assert p.publishing.images.enabled is True
    assert p.publishing.images.provider == "useapi_google_flow"
    assert p.publishing.images.fallback_provider == "local_playwright_card"
    assert p.publishing.images.useapi_base_url == "https://api.useapi.net"
    assert p.publishing.images.useapi_token_ref == "secret:useapi_token"
    assert p.publishing.images.google_flow_account_ref == "secret:useapi_google_flow_account"
    assert p.publishing.images.candidate_count == 4
    assert p.publishing.images.overlay_mode == "none"
    assert p.publishing.images.require_image_for_publish is True
    assert p.publishing.images.canvas.width == 1080
    assert p.publishing.images.canvas.height == 1350
    assert p.publishing.images.canvas.theme == "ai5phut"


def test_profile_loads_zai_fallback_image_generation_settings(tmp_path, fixtures_dir):
    import json

    src = json.loads((fixtures_dir / "profile_plan3.json").read_text())
    src["publishing"] = {
        "backend": "mixpost_ui",
        "mixpost": {
            "base_url": "https://mixpost.example.test",
            "storage_state_path": str(tmp_path / "state.json"),
            "headless": True,
        },
        "images": {
            "enabled": True,
            "provider": "useapi_google_flow",
            "fallback_provider": "zai_glm_image",
            "useapi_base_url": "https://api.useapi.net",
            "useapi_token_ref": "secret:useapi_token",
            "zai_api_key_ref": "secret:zai_api_key",
            "zai_model": "glm-image",
            "zai_quality": "standard",
            "candidate_count": 4,
            "overlay_mode": "none",
            "require_image_for_publish": True,
            "canvas": {
                "width": 1080,
                "height": 1350,
                "theme": "ai5phut",
            },
        },
    }
    path = tmp_path / "mixpost-images-zai.json"
    path.write_text(json.dumps(src), encoding="utf-8")

    p = load_profile(path)

    assert p.publishing.images.fallback_provider == "zai_glm_image"
    assert p.publishing.images.zai_api_key_ref == "secret:zai_api_key"
    assert p.publishing.images.zai_model == "glm-image"
    assert p.publishing.images.zai_quality == "standard"


def test_profile_loads_codex_imagen_fallback_settings(tmp_path, fixtures_dir):
    import json

    src = json.loads((fixtures_dir / "profile_plan3.json").read_text())
    src["publishing"] = {
        "backend": "mixpost_ui",
        "mixpost": {
            "base_url": "https://mixpost.example.test",
            "storage_state_path": str(tmp_path / "state.json"),
            "headless": True,
        },
        "images": {
            "enabled": True,
            "provider": "useapi_google_flow",
            "fallback_provider": "codex_imagen_oauth",
            "useapi_base_url": "https://api.useapi.net",
            "useapi_token_ref": "secret:useapi_token",
            "codex_imagen_script_path": "/tmp/codex-imagen/scripts/codex-imagen.mjs",
            "codex_auth_json_path": "~/.codex/auth.json",
            "codex_timeout_seconds": 300,
            "codex_model": "gpt-5.4",
            "candidate_count": 4,
            "overlay_mode": "none",
            "require_image_for_publish": True,
            "canvas": {
                "width": 1080,
                "height": 1350,
                "theme": "ai5phut",
            },
        },
    }
    path = tmp_path / "mixpost-images-codex-imagen.json"
    path.write_text(json.dumps(src), encoding="utf-8")

    p = load_profile(path)

    assert p.publishing.images.fallback_provider == "codex_imagen_oauth"
    assert p.publishing.images.codex_imagen_script_path == "/tmp/codex-imagen/scripts/codex-imagen.mjs"
    assert p.publishing.images.codex_auth_json_path == "~/.codex/auth.json"
    assert p.publishing.images.codex_timeout_seconds == 300
    assert p.publishing.images.codex_model == "gpt-5.4"


def test_profile_ignores_non_mapping_publishing_when_building_from_dict():
    profile = Profile.from_dict(
        {
            "name": "page_hourly_repost",
            "page_id": "123",
            "access_token_ref": "secret:fb_test",
            "topic": "AI",
            "language": "vi",
            "post_times": ["08:00", "12:00", "16:00", "20:00"],
            "timezone": "Asia/Ho_Chi_Minh",
            "min_posts_required": 1,
            "max_sources_per_platform": 12,
            "sources": {
                "youtube": {"enabled": False},
                "perplexity": {"enabled": False},
                "twitter_via_perplexity": {"enabled": False},
                "reddit": {
                    "enabled": False,
                    "subreddits": [],
                    "min_score": 0,
                    "time_filter": "week",
                    "top_per_sub": 0,
                },
                "hackernews": {"enabled": False, "min_points": 0},
            },
            "publishing": "facebook_graph",
        }
    )

    assert profile.publishing_backend is None
    assert profile.publishing.backend is None
