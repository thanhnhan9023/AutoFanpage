import json
from pathlib import Path
import sys

import pytest
import responses

# Import by path since skills/ is not a package
SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "hackernews-researcher" / "scripts"
sys.path.insert(0, str(SCRIPT))
import fetch_hn  # noqa: E402


@responses.activate
def test_fetch_returns_filtered_results(tmp_path):
    responses.add(
        responses.GET,
        "https://hacker-news.firebaseio.com/v0/topstories.json",
        json=[1, 2, 3],
    )
    responses.add(
        responses.GET,
        "https://hacker-news.firebaseio.com/v0/item/1.json",
        json={"id": 1, "type": "story", "title": "AI breakthrough",
              "url": "https://x.com/a", "score": 200, "by": "u1",
              "descendants": 30, "time": 1744156800},
    )
    responses.add(
        responses.GET,
        "https://hacker-news.firebaseio.com/v0/item/2.json",
        json={"id": 2, "type": "story", "title": "Not relevant",
              "url": "https://x.com/b", "score": 300, "by": "u2",
              "descendants": 10, "time": 1744156800},
    )
    responses.add(
        responses.GET,
        "https://hacker-news.firebaseio.com/v0/item/3.json",
        json={"id": 3, "type": "story", "title": "AI automation wins",
              "url": "https://x.com/c", "score": 500, "by": "u3",
              "descendants": 80, "time": 1744156800},
    )

    results = fetch_hn.run(
        topic="AI automation",
        min_points=100,
        limit=10,
        top_n=3,
    )

    titles = [r["title"] for r in results]
    assert "AI automation wins" in titles
    assert "AI breakthrough" in titles
    assert "Not relevant" not in titles
    assert results[0]["points"] >= results[-1]["points"]


@responses.activate
def test_main_writes_wrapped_hackernews_artifact(tmp_path, fixtures_dir):
    responses.add(
        responses.GET,
        "https://hacker-news.firebaseio.com/v0/topstories.json",
        json=[1, 2],
    )
    responses.add(
        responses.GET,
        "https://hacker-news.firebaseio.com/v0/item/1.json",
        json={"id": 1, "type": "story", "title": "AI automation launch",
              "url": "https://example.com/a", "score": 200, "by": "u1",
              "descendants": 30, "time": 1744156800},
    )
    responses.add(
        responses.GET,
        "https://hacker-news.firebaseio.com/v0/item/2.json",
        json={"id": 2, "type": "story", "title": "Another AI automation win",
              "url": "https://example.com/b", "score": 180, "by": "u2",
              "descendants": 20, "time": 1744156800},
    )

    exit_code = fetch_hn.main([
        "--run-dir", str(tmp_path),
        "--profile", str(fixtures_dir / "page_test.json"),
    ])

    assert exit_code == 0
    data = json.loads((tmp_path / "hackernews_results.json").read_text())
    assert data["source"] == "hackernews"
    assert isinstance(data["fetched_at"], str)
    assert len(data["items"]) == 2
    assert data["items"][0]["points"] >= data["items"][1]["points"]
