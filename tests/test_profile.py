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
