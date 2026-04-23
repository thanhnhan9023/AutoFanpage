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
