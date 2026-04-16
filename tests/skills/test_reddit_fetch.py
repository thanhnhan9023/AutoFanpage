import json
import sys
from pathlib import Path

import pytest
import responses

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "reddit-researcher" / "scripts"
sys.path.insert(0, str(SCRIPT))
import fetch_reddit  # noqa: E402


TOKEN_URL = "https://www.reddit.com/api/v1/access_token"


def _listing(posts):
    return {"data": {"children": [{"data": p} for p in posts]}}


def _post(**overrides):
    base = {
        "title": "t", "subreddit": "ChatGPT",
        "score": 500, "num_comments": 10, "author": "u",
        "permalink": "/r/x/comments/1/t/",
        "url": "https://ext.com/a",
        "created_utc": 1744156800,
        "is_self": False, "stickied": False, "over_18": False,
    }
    base.update(overrides)
    return base


@responses.activate
def test_run_fetches_multiple_subreddits(tmp_path, monkeypatch):
    monkeypatch.setattr(
        fetch_reddit, "get_secret",
        lambda ref: "cid" if "client_id" in ref else "csec",
    )
    responses.add(
        responses.POST, TOKEN_URL,
        json={"access_token": "tkn", "token_type": "bearer", "expires_in": 3600},
    )
    responses.add(
        responses.GET,
        "https://oauth.reddit.com/r/ChatGPT/top",
        json=_listing([_post(title="one", score=900),
                       _post(title="two", score=50)]),
    )
    responses.add(
        responses.GET,
        "https://oauth.reddit.com/r/OpenAI/top",
        json=_listing([_post(title="three", subreddit="OpenAI", score=700)]),
    )

    out = tmp_path / "reddit_results.json"
    res = fetch_reddit.run(
        subreddits=["ChatGPT", "OpenAI"],
        min_score=100, time_filter="week", top_per_sub=5,
        client_id_ref="secret:reddit_client_id",
        client_secret_ref="secret:reddit_client_secret",
        user_agent="autofanpage/0.1",
        out_path=str(out),
    )
    assert res["status"] == "ok"
    data = json.loads(out.read_text())
    titles = [i["title"] for i in data["items"]]
    assert "one" in titles
    assert "three" in titles
    assert "two" not in titles


@responses.activate
def test_run_continues_if_one_subreddit_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(
        fetch_reddit, "get_secret",
        lambda ref: "cid" if "client_id" in ref else "csec",
    )
    # Monkeypatch get_json to use backoff=0 to avoid slow retries in tests
    import autofanpage.http as _http
    _orig_get_json = fetch_reddit.get_json

    def _fast_get_json(url, **kwargs):
        kwargs["backoff"] = 0
        return _orig_get_json(url, **kwargs)

    monkeypatch.setattr(fetch_reddit, "get_json", _fast_get_json)

    responses.add(
        responses.POST, TOKEN_URL,
        json={"access_token": "tkn", "token_type": "bearer", "expires_in": 3600},
    )
    responses.add(
        responses.GET,
        "https://oauth.reddit.com/r/ChatGPT/top",
        json=_listing([_post(title="good", score=500)]),
    )
    # max_retries=3 means 4 total attempts for 5xx
    for _ in range(4):
        responses.add(
            responses.GET,
            "https://oauth.reddit.com/r/BadSub/top",
            status=500,
        )

    out = tmp_path / "reddit_results.json"
    res = fetch_reddit.run(
        subreddits=["ChatGPT", "BadSub"],
        min_score=100, time_filter="week", top_per_sub=5,
        client_id_ref="secret:reddit_client_id",
        client_secret_ref="secret:reddit_client_secret",
        user_agent="autofanpage/0.1",
        out_path=str(out),
    )
    assert res["status"] == "ok"
    data = json.loads(out.read_text())
    titles = [i["title"] for i in data["items"]]
    assert "good" in titles
    assert res["failed_subreddits"] == ["BadSub"]
