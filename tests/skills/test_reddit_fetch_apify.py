import json
import sys
from pathlib import Path

import responses

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "reddit-researcher-apify" / "scripts"
sys.path.insert(0, str(SCRIPT))
import fetch_reddit_apify  # noqa: E402


ACTOR_ID = "good-apis/reddit-scraper"
RUN_URL = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"


def _item(**overrides):
    base = {
        "title": "Reddit title",
        "subreddit": "ChatGPT",
        "score": 500,
        "numComments": 33,
        "author": "openclaw",
        "permalink": "/r/ChatGPT/comments/abc/title/",
        "createdUtc": 1744156800,
        "isSelf": False,
        "url": "https://example.com/post",
    }
    base.update(overrides)
    return base


@responses.activate
def test_run_fetches_via_apify_actor(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_reddit_apify, "get_secret", lambda ref: "apify-token")
    responses.add(
        responses.POST,
        RUN_URL,
        json=[_item(title="one"), _item(title="two", score=50)],
        match=[responses.matchers.query_param_matcher({"token": "apify-token"})],
    )

    out = tmp_path / "reddit_results.json"
    result = fetch_reddit_apify.run(
        actor_id=ACTOR_ID,
        subreddits=["ChatGPT"],
        min_score=100,
        time_filter="week",
        top_per_sub=5,
        api_token_ref="secret:apify_api_token",
        out_path=str(out),
    )

    assert result["status"] == "ok"
    payload = json.loads(out.read_text())
    assert [item["title"] for item in payload["items"]] == ["one"]
