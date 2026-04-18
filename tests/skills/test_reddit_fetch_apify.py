import json
import sys
from pathlib import Path

import responses

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "reddit-researcher-apify" / "scripts"
sys.path.insert(0, str(SCRIPT))
import fetch_reddit_apify  # noqa: E402


ACTOR_ID = "automation-lab/reddit-scraper"
RUN_URL = "https://api.apify.com/v2/acts/automation-lab~reddit-scraper/run-sync-get-dataset-items"


def _item(**overrides):
    base = {
        "title": "Reddit title",
        "subreddit": "ChatGPT",
        "score": 500,
        "numComments": 33,
        "author": "openclaw",
        "permalink": "/r/ChatGPT/comments/abc/title/",
        "createdAt": "2026-04-18T12:14:24.499Z",
        "isSelf": False,
        "url": "https://www.reddit.com/r/ChatGPT/comments/abc/title/",
        "link": "https://example.com/post",
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
        match=[
            responses.matchers.query_param_matcher({"token": "apify-token"}),
            responses.matchers.json_params_matcher({
                "urls": ["https://www.reddit.com/r/ChatGPT/top/?t=week"],
                "sort": "top",
                "timeFilter": "week",
                "maxPostsPerSource": 15,
                "includeComments": False,
            }),
        ],
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
    assert payload["items"][0]["url"] == "https://reddit.com/r/ChatGPT/comments/abc/title/"
    assert payload["items"][0]["external_url"] == "https://example.com/post"


@responses.activate
def test_run_prefers_substantive_posts_over_higher_score_media(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_reddit_apify, "get_secret", lambda ref: "apify-token")
    responses.add(
        responses.POST,
        RUN_URL,
        json=[
            _item(title="lol", score=9000, numComments=40, url="https://www.reddit.com/r/ChatGPT/comments/m1/lol/", link="https://v.redd.it/meme1"),
            _item(title="7 years ago", score=8500, numComments=60, url="https://www.reddit.com/r/ChatGPT/comments/m2/7_years_ago/", link="https://i.redd.it/meme2.jpeg"),
            _item(title="Why do ChatGPT agent demos fail in production so often?", score=6200, numComments=480, url="https://www.reddit.com/r/ChatGPT/comments/d1/fail_in_production/", link="https://www.reddit.com/r/ChatGPT/comments/d1/fail_in_production/"),
            _item(title="How are teams using ChatGPT memory in real support workflows?", score=5900, numComments=420, url="https://www.reddit.com/r/ChatGPT/comments/d2/support_workflows/", link="https://www.reddit.com/r/ChatGPT/comments/d2/support_workflows/"),
        ],
        match=[
            responses.matchers.query_param_matcher({"token": "apify-token"}),
            responses.matchers.json_params_matcher({
                "urls": ["https://www.reddit.com/r/ChatGPT/top/?t=week"],
                "sort": "top",
                "timeFilter": "week",
                "maxPostsPerSource": 15,
                "includeComments": False,
            }),
        ],
    )

    out = tmp_path / "reddit_results.json"
    result = fetch_reddit_apify.run(
        actor_id=ACTOR_ID,
        subreddits=["ChatGPT"],
        min_score=100,
        time_filter="week",
        top_per_sub=2,
        api_token_ref="secret:apify_api_token",
        out_path=str(out),
    )

    assert result["status"] == "ok"
    payload = json.loads(out.read_text())
    assert [item["title"] for item in payload["items"]] == [
        "Why do ChatGPT agent demos fail in production so often?",
        "How are teams using ChatGPT memory in real support workflows?",
    ]


@responses.activate
def test_run_caps_media_heavy_posts_per_subreddit(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_reddit_apify, "get_secret", lambda ref: "apify-token")
    responses.add(
        responses.POST,
        RUN_URL,
        json=[
            _item(title="Deep dive into prompt caching failures", score=5000, numComments=350, url="https://www.reddit.com/r/ChatGPT/comments/d1/deep_dive/", link="https://www.reddit.com/r/ChatGPT/comments/d1/deep_dive/"),
            _item(title="Strong media one", score=9100, numComments=500, url="https://www.reddit.com/r/ChatGPT/comments/m1/one/", link="https://v.redd.it/one"),
            _item(title="Strong media two", score=8900, numComments=490, url="https://www.reddit.com/r/ChatGPT/comments/m2/two/", link="https://i.redd.it/two.jpeg"),
            _item(title="Strong media three", score=8800, numComments=480, url="https://www.reddit.com/r/ChatGPT/comments/m3/three/", link="https://www.reddit.com/gallery/m3"),
        ],
        match=[
            responses.matchers.query_param_matcher({"token": "apify-token"}),
            responses.matchers.json_params_matcher({
                "urls": ["https://www.reddit.com/r/ChatGPT/top/?t=week"],
                "sort": "top",
                "timeFilter": "week",
                "maxPostsPerSource": 15,
                "includeComments": False,
            }),
        ],
    )

    out = tmp_path / "reddit_results.json"
    fetch_reddit_apify.run(
        actor_id=ACTOR_ID,
        subreddits=["ChatGPT"],
        min_score=100,
        time_filter="week",
        top_per_sub=4,
        api_token_ref="secret:apify_api_token",
        out_path=str(out),
    )

    payload = json.loads(out.read_text())
    media_urls = {item["external_url"] for item in payload["items"]}
    assert len(payload["items"]) == 3
    assert "https://v.redd.it/one" in media_urls
    assert "https://i.redd.it/two.jpeg" in media_urls
    assert "https://www.reddit.com/gallery/m3" not in media_urls


@responses.activate
def test_run_still_keeps_best_available_media_when_substantive_pool_is_small(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_reddit_apify, "get_secret", lambda ref: "apify-token")
    responses.add(
        responses.POST,
        RUN_URL,
        json=[
            _item(title="Useful discussion about prompt ops", score=4200, numComments=260, url="https://www.reddit.com/r/ChatGPT/comments/d1/prompt_ops/", link="https://www.reddit.com/r/ChatGPT/comments/d1/prompt_ops/"),
            _item(title="Funny outage meme", score=8300, numComments=320, url="https://www.reddit.com/r/ChatGPT/comments/m1/outage_meme/", link="https://v.redd.it/outage1"),
            _item(title="Dashboard meme recap", score=7900, numComments=280, url="https://www.reddit.com/r/ChatGPT/comments/m2/dashboard/", link="https://i.redd.it/outage2.jpeg"),
        ],
        match=[
            responses.matchers.query_param_matcher({"token": "apify-token"}),
            responses.matchers.json_params_matcher({
                "urls": ["https://www.reddit.com/r/ChatGPT/top/?t=week"],
                "sort": "top",
                "timeFilter": "week",
                "maxPostsPerSource": 15,
                "includeComments": False,
            }),
        ],
    )

    out = tmp_path / "reddit_results.json"
    fetch_reddit_apify.run(
        actor_id=ACTOR_ID,
        subreddits=["ChatGPT"],
        min_score=100,
        time_filter="week",
        top_per_sub=3,
        api_token_ref="secret:apify_api_token",
        out_path=str(out),
    )

    payload = json.loads(out.read_text())
    assert [item["title"] for item in payload["items"]] == [
        "Useful discussion about prompt ops",
        "Funny outage meme",
        "Dashboard meme recap",
    ]
