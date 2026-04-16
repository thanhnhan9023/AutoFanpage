import json
import sys
from pathlib import Path

import pytest
import responses

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "youtube-researcher" / "scripts"
sys.path.insert(0, str(SCRIPT))
import fetch_youtube  # noqa: E402


SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"


@responses.activate
def test_run_writes_filtered_results(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_youtube, "get_secret", lambda ref: "FAKE-KEY")

    responses.add(
        responses.GET, SEARCH_URL,
        json={"items": [
            {"id": {"videoId": "v1"},
             "snippet": {"title": "AI agents", "channelId": "c1",
                         "channelTitle": "Ch1",
                         "publishedAt": "2026-04-10T00:00:00Z"}},
            {"id": {"videoId": "v2"},
             "snippet": {"title": "Noise", "channelId": "c2",
                         "channelTitle": "Ch2",
                         "publishedAt": "2026-04-10T00:00:00Z"}},
        ]},
    )
    responses.add(
        responses.GET, VIDEOS_URL,
        json={"items": [
            {"id": "v1", "statistics": {"viewCount": "250000"}},
            {"id": "v2", "statistics": {"viewCount": "1000"}},
        ]},
    )
    responses.add(
        responses.GET, CHANNELS_URL,
        json={"items": [
            {"id": "c1", "statistics": {"subscriberCount": "50000"}},
            {"id": "c2", "statistics": {"subscriberCount": "100"}},
        ]},
    )

    out_path = tmp_path / "youtube_results.json"
    result = fetch_youtube.run(
        topic="AI automation",
        min_views=100000, min_subs=10000,
        api_key_ref="secret:youtube_api_key",
        limit=10,
        out_path=str(out_path),
    )
    assert result["status"] == "ok"
    data = json.loads(out_path.read_text())
    assert data["source"] == "youtube"
    assert len(data["items"]) == 1
    assert data["items"][0]["video_id"] == "v1"


@responses.activate
def test_run_returns_empty_when_search_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_youtube, "get_secret", lambda ref: "FAKE-KEY")
    responses.add(responses.GET, SEARCH_URL, json={"items": []})

    out_path = tmp_path / "youtube_results.json"
    result = fetch_youtube.run(
        topic="AI automation",
        min_views=100000, min_subs=10000,
        api_key_ref="secret:youtube_api_key",
        limit=10,
        out_path=str(out_path),
    )
    assert result["status"] == "ok"
    data = json.loads(out_path.read_text())
    assert data["items"] == []
