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
    assert profile.min_posts_required == 2
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
