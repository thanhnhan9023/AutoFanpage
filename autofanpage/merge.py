"""Combine per-source Phase-1 artifacts into one ``merged_sources.json``.

Produces the spec-mandated shape: ``{ urls, counts_per_platform }`` —
a deduplicated, per-platform-capped URL list ready for NotebookLM
(≤ max_per_platform × 4 platforms, staying under the 50-source limit).
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag

from autofanpage.schemas import validate


def _load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _canonical_url(url: str) -> str:
    return urldefrag(url)[0]


def _youtube_urls(doc: dict) -> list[dict]:
    return [{
        "url": it["url"],
        "title": it["title"],
        "platform": "youtube",
        "score_or_views": it["views"],
        "created_at": it.get("published_at", ""),
    } for it in doc.get("items", [])]


def _hackernews_urls(doc: dict) -> list[dict]:
    return [{
        "url": it["url"],
        "title": it["title"],
        "platform": "hackernews",
        "score_or_views": it["points"],
        "created_at": it.get("created_at", ""),
    } for it in doc.get("items", [])]


def _reddit_urls(doc: dict) -> list[dict]:
    return [{
        "url": it["url"],
        "title": it["title"],
        "platform": "reddit",
        "score_or_views": it["score"],
        "created_at": it.get("created_at", ""),
    } for it in doc.get("items", [])]


def _perplexity_urls(doc: dict) -> list[dict]:
    out: list[dict] = []
    for bucket in ("news", "reports", "twitter"):
        for it in doc.get(bucket, []):
            out.append({
                "url": it["url"],
                "title": it["title"],
                "platform": "perplexity",
                "score_or_views": 0,
                "created_at": "",
            })
    return out


_EXTRACTORS = {
    "youtube": _youtube_urls,
    "hackernews": _hackernews_urls,
    "reddit": _reddit_urls,
    "perplexity": _perplexity_urls,
}


def merge_sources(
    *,
    profile: str,
    topic: str,
    language: str,
    artifacts: dict[str, Path],
    failures: dict[str, str],
    max_per_platform: int = 12,
) -> dict[str, Any]:
    seen_urls: set[str] = set()
    urls: list[dict] = []
    counts: Counter[str] = Counter()
    succeeded: list[str] = []

    for source, path in artifacts.items():
        extractor = _EXTRACTORS.get(source)
        if not extractor:
            raise ValueError(f"Unknown source: {source}")
        raw = extractor(_load(path))
        raw.sort(key=lambda u: u["score_or_views"], reverse=True)
        platform = raw[0]["platform"] if raw else source
        added = 0
        for entry in raw:
            canon = _canonical_url(entry["url"])
            if canon in seen_urls:
                continue
            if added >= max_per_platform:
                break
            seen_urls.add(canon)
            urls.append(entry)
            added += 1
        counts[platform] += added
        succeeded.append(source)

    doc = {
        "profile": profile,
        "topic": topic,
        "language": language,
        "fetched_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "sources_succeeded": succeeded,
        "sources_failed": [
            {"source": s, "error": e} for s, e in failures.items()
        ],
        "counts_per_platform": dict(counts),
        "urls": urls,
    }
    validate("merged_sources", doc)
    return doc
