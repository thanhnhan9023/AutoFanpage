import json

import pytest

from autofanpage.hourly_state import LatestRepostedSource


def test_latest_reposted_source_round_trip(tmp_path):
    state = LatestRepostedSource(base=tmp_path, page="page_hourly_repost")

    assert state.read() is None

    state.mark(
        source_post_id="123",
        source_post_url="https://facebook.com/post/123",
        published_at="2026-04-23T09:15:00Z",
        run_dir="/tmp/run1",
    )

    payload = state.read()
    assert payload is not None
    assert payload["source_post_id"] == "123"
    assert payload["source_post_url"] == "https://facebook.com/post/123"
    assert payload["run_dir"] == "/tmp/run1"


def test_latest_reposted_source_matches_id_then_url(tmp_path):
    state = LatestRepostedSource(base=tmp_path, page="page_hourly_repost")
    state.mark(
        source_post_id="123",
        source_post_url="https://facebook.com/post/123",
        published_at="2026-04-23T09:15:00Z",
        run_dir="/tmp/run1",
    )

    assert state.matches(
        {
            "source_post_id": "123",
            "source_post_url": "https://facebook.com/post/other",
        }
    )
    assert state.matches(
        {
            "source_post_id": None,
            "source_post_url": "https://facebook.com/post/123",
        }
    )
    assert not state.matches(
        {
            "source_post_id": "456",
            "source_post_url": "https://facebook.com/post/456",
        }
    )


@pytest.mark.parametrize("page", ["/tmp/escape", "../escape", "nested/../escape"])
def test_latest_reposted_source_rejects_non_local_page_segments(tmp_path, page):
    with pytest.raises(ValueError):
        LatestRepostedSource(base=tmp_path, page=page).path


def test_latest_reposted_source_read_returns_none_for_malformed_json(tmp_path):
    state = LatestRepostedSource(base=tmp_path, page="page_hourly_repost")
    state.path.parent.mkdir(parents=True, exist_ok=True)
    state.path.write_text("{not valid json")

    assert state.read() is None


def test_latest_reposted_source_read_returns_none_for_invalid_schema(tmp_path):
    state = LatestRepostedSource(base=tmp_path, page="page_hourly_repost")
    state.path.parent.mkdir(parents=True, exist_ok=True)
    state.path.write_text(json.dumps({"source_post_url": "https://facebook.com/post/123"}))

    assert state.read() is None


def test_latest_reposted_source_matches_returns_false_for_corrupt_state(tmp_path):
    state = LatestRepostedSource(base=tmp_path, page="page_hourly_repost")
    state.path.parent.mkdir(parents=True, exist_ok=True)
    state.path.write_text("{not valid json")

    assert not state.matches(
        {
            "source_post_id": "123",
            "source_post_url": "https://facebook.com/post/123",
        }
    )
