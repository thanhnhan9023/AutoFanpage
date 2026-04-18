import json
import sys
from pathlib import Path

import pytest
import responses

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "perplexity-researcher" / "scripts"
sys.path.insert(0, str(SCRIPT))
import fetch_perplexity  # noqa: E402

CHAT_URL = "https://api.perplexity.ai/chat/completions"


def _fake_resp(titles, urls):
    lines = [f"{i+1}. {t} [{i+1}]" for i, t in enumerate(titles)]
    return {
        "choices": [{"message": {"content": "\n".join(lines)}}],
        "citations": urls,
    }


@responses.activate
def test_run_writes_news_reports_twitter(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_perplexity, "get_secret", lambda ref: "pplx-XXX")

    responses.add(responses.POST, CHAT_URL, json=_fake_resp(
        ["GPT-5 launches", "Claude 4 released"],
        ["https://openai.com/x", "https://anthropic.com/y"],
    ))
    responses.add(responses.POST, CHAT_URL, json=_fake_resp(
        ["AI Index 2026"], ["https://stanford.edu/ai-index"],
    ))
    responses.add(responses.POST, CHAT_URL, json=_fake_resp(
        ["Sam Altman posts"], ["https://x.com/sama/status/1"],
    ))

    out = tmp_path / "perplexity_results.json"
    result = fetch_perplexity.run(
        topic="AI automation business",
        api_key_ref="secret:perplexity_api_key",
        news_limit=5, reports_limit=3, twitter_limit=5,
        twitter_enabled=True,
        out_path=str(out),
    )
    assert result["status"] == "ok"
    data = json.loads(out.read_text())
    assert data["source"] == "perplexity"
    assert len(data["news"]) == 2
    assert len(data["reports"]) == 1
    assert len(data["twitter"]) == 1
    assert data["twitter"][0]["url"].startswith("https://x.com/")


@responses.activate
def test_run_skips_twitter_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_perplexity, "get_secret", lambda ref: "pplx-XXX")
    responses.add(responses.POST, CHAT_URL, json=_fake_resp(
        ["n1"], ["https://a.com/1"]))
    responses.add(responses.POST, CHAT_URL, json=_fake_resp(
        ["r1"], ["https://b.com/1"]))

    out = tmp_path / "perplexity_results.json"
    fetch_perplexity.run(
        topic="AI",
        api_key_ref="secret:perplexity_api_key",
        news_limit=5, reports_limit=3, twitter_limit=5,
        twitter_enabled=False,
        out_path=str(out),
    )
    data = json.loads(out.read_text())
    assert data["twitter"] == []
    assert len(responses.calls) == 2


@responses.activate
def test_run_excludes_non_twitter_hosts_from_twitter_results(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_perplexity, "get_secret", lambda ref: "pplx-XXX")

    responses.add(responses.POST, CHAT_URL, json=_fake_resp(
        ["n1"], ["https://a.com/1"],
    ))
    responses.add(responses.POST, CHAT_URL, json=_fake_resp(
        ["r1"], ["https://b.com/1"],
    ))
    responses.add(responses.POST, CHAT_URL, json=_fake_resp(
        ["real post", "fake post"],
        ["https://x.com/sama/status/1", "https://notx.com/post/2"],
    ))

    out = tmp_path / "perplexity_results.json"
    fetch_perplexity.run(
        topic="AI",
        api_key_ref="secret:perplexity_api_key",
        news_limit=5, reports_limit=3, twitter_limit=5,
        twitter_enabled=True,
        out_path=str(out),
    )

    data = json.loads(out.read_text())
    assert data["twitter"] == [
        {
            "title": "real post",
            "url": "https://x.com/sama/status/1",
            "summary": "",
            "source": "x.com",
        },
    ]


def test_shape_tavily_results_deduplicates_and_limits():
    items = fetch_perplexity.shape_tavily_results(
        {
            "results": [
                {
                    "title": "Launch recap",
                    "url": "https://openai.com/blog/launch",
                    "content": "Key release notes",
                },
                {
                    "title": "Launch recap duplicate",
                    "url": "https://openai.com/blog/launch",
                    "content": "Should be skipped by URL dedupe",
                },
            ],
        },
        limit=1,
    )

    assert items == [
        {
            "title": "Launch recap",
            "url": "https://openai.com/blog/launch",
            "summary": "Key release notes",
            "source": "openai.com",
        },
    ]


def test_filter_twitter_urls_keeps_only_x_hosts():
    items = [
        {
            "title": "x",
            "url": "https://x.com/sama/status/1",
            "summary": "",
            "source": "x.com",
        },
        {
            "title": "twitter",
            "url": "https://twitter.com/openai/status/2",
            "summary": "",
            "source": "twitter.com",
        },
        {
            "title": "other",
            "url": "https://example.com/post",
            "summary": "",
            "source": "example.com",
        },
    ]

    assert fetch_perplexity.filter_twitter_urls(items) == items[:2]
