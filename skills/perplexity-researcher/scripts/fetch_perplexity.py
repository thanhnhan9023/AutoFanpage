"""Perplexity-researcher skill script."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

from autofanpage.http import post_json
from autofanpage.profile import load_profile
from autofanpage.schemas import validate
from autofanpage.secrets import get_secret
from autofanpage.sources.perplexity import (
    filter_twitter_urls,
    parse_completion,
    shape_items,
    shape_tavily_results,
)

CHAT_URL = "https://api.perplexity.ai/chat/completions"
TAVILY_URL = "https://api.tavily.com/search"


def _query(api_key: str, *, model: str, system: str, user: str) -> dict:
    return post_json(
        CHAT_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json_body={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
    )


def _tavily_query(api_key: str, *, query: str) -> dict:
    return post_json(
        TAVILY_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json_body={
            "query": query,
            "search_depth": "basic",
            "max_results": 10,
            "include_answer": False,
            "include_raw_content": False,
        },
    )


def run(
    *,
    topic: str,
    backend: str,
    api_key_ref: str,
    news_limit: int,
    reports_limit: int,
    twitter_limit: int,
    twitter_enabled: bool,
    out_path: str,
) -> dict:
    api_key = get_secret(api_key_ref)

    if backend == "tavily":
        news = shape_tavily_results(
            _tavily_query(api_key, query=f"Top news stories today about: {topic}"),
            limit=news_limit,
        )
        reports = shape_tavily_results(
            _tavily_query(
                api_key,
                query=(
                    f"Recent (2025-2026) research reports or white papers on: {topic}"
                ),
            ),
            limit=reports_limit,
        )
        if twitter_enabled:
            twitter = filter_twitter_urls(
                shape_tavily_results(
                    _tavily_query(
                        api_key,
                        query=(
                            f"Top notable X/Twitter posts this week about: {topic} "
                            "site:x.com OR site:twitter.com"
                        ),
                    ),
                    limit=twitter_limit,
                )
            )
        else:
            twitter = []
    else:
        news_resp = _query(
            api_key, model="sonar-pro",
            system="You are a news analyst. Respond with a numbered list of the most important articles, one per line, no prose.",
            user=f"Top {news_limit} news stories today about: {topic}. Cite each.",
        )
        reports_resp = _query(
            api_key, model="sonar",
            system="You are an academic researcher. Respond with a numbered list of reports, one per line, no prose.",
            user=f"Recent (2025-2026) research reports or white papers on: {topic}. "
                 f"List up to {reports_limit}. Cite each.",
        )
        news = shape_items(parse_completion(news_resp), limit=news_limit)
        reports = shape_items(parse_completion(reports_resp), limit=reports_limit)

        if twitter_enabled:
            tw_resp = _query(
                api_key, model="sonar-pro",
                system="You report notable Twitter/X posts. Respond with a numbered list, one post per line. Only cite URLs under site:x.com or site:twitter.com.",
                user=f"Top {twitter_limit} notable X/Twitter posts this week about: {topic}. "
                     f"Only cite URLs on x.com or twitter.com.",
            )
            twitter = filter_twitter_urls(
                shape_items(parse_completion(tw_resp), limit=twitter_limit)
            )
        else:
            twitter = []

    doc = {
        "source": "perplexity",
        "fetched_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "news": news,
        "reports": reports,
        "twitter": twitter,
    }
    validate("perplexity_results", doc)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    return {
        "status": "ok", "artifact": out_path,
        "count_news": len(news), "count_reports": len(reports),
        "count_twitter": len(twitter),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--profile", required=True)
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    cfg = profile.sources.get("perplexity", {})
    if not cfg.get("enabled", False):
        Path(args.run_dir, "perplexity_results.json").write_text(
            json.dumps({"source": "perplexity",
                        "fetched_at": datetime.now(timezone.utc).astimezone().isoformat(),
                        "news": [], "reports": [], "twitter": []}, ensure_ascii=False),
        )
        print(json.dumps({"status": "ok", "skipped": True}))
        return 0

    twitter_enabled = (
        profile.sources.get("twitter_via_perplexity", {}).get("enabled", False)
    )
    backend = cfg.get("backend", "tavily")
    api_key_ref = (
        "secret:tavily_api_key"
        if backend == "tavily"
        else "secret:perplexity_api_key"
    )
    out_path = str(Path(args.run_dir) / "perplexity_results.json")
    result = run(
        topic=profile.topic,
        backend=backend,
        api_key_ref=api_key_ref,
        news_limit=5, reports_limit=3, twitter_limit=5,
        twitter_enabled=twitter_enabled,
        out_path=out_path,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
