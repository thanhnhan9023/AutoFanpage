import json

import pytest

from autofanpage.sources.youtube import (
    merge_stats, filter_and_rank, to_result,
)


@pytest.fixture
def search(fixtures_dir):
    return json.loads((fixtures_dir / "youtube_search.json").read_text())


@pytest.fixture
def videos(fixtures_dir):
    return json.loads((fixtures_dir / "youtube_videos.json").read_text())


@pytest.fixture
def channels(fixtures_dir):
    return json.loads((fixtures_dir / "youtube_channels.json").read_text())


def test_merge_stats_attaches_views_and_subs(search, videos, channels):
    merged = merge_stats(search, videos, channels)
    by_id = {m["video_id"]: m for m in merged}
    assert by_id["v1"]["views"] == 250000
    assert by_id["v1"]["subscribers"] == 50000
    assert by_id["v3"]["views"] == 150000


def test_filter_enforces_min_views(search, videos, channels):
    merged = merge_stats(search, videos, channels)
    out = filter_and_rank(merged, min_views=100000, min_subs=0, limit=10)
    ids = [m["video_id"] for m in out]
    assert "v2" not in ids


def test_filter_enforces_min_subs(search, videos, channels):
    merged = merge_stats(search, videos, channels)
    out = filter_and_rank(merged, min_views=0, min_subs=10000, limit=10)
    ids = [m["video_id"] for m in out]
    assert "c2" not in [m["channel_id"] for m in out]


def test_filter_sorts_by_views_desc(search, videos, channels):
    merged = merge_stats(search, videos, channels)
    out = filter_and_rank(merged, min_views=0, min_subs=0, limit=10)
    views = [m["views"] for m in out]
    assert views == sorted(views, reverse=True)


def test_filter_respects_limit(search, videos, channels):
    merged = merge_stats(search, videos, channels)
    out = filter_and_rank(merged, min_views=0, min_subs=0, limit=1)
    assert len(out) == 1


def test_to_result_shape():
    m = {
        "video_id": "vX", "title": "t", "channel": "Ch", "channel_id": "cX",
        "views": 100, "subscribers": 50, "published_at": "2026-04-10T00:00:00Z",
    }
    r = to_result(m)
    assert r["url"] == "https://youtu.be/vX"
    assert r["title"] == "t"
    assert r["views"] == 100
    assert r["subscribers"] == 50
    assert r["channel"] == "Ch"
    assert r["published_at"] == "2026-04-10T00:00:00Z"
