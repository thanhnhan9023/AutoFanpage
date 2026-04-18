"""Pure parsing/shaping for Perplexity Sonar chat completion responses."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


def _hostname(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return ""
    return host[4:] if host.startswith("www.") else host


def parse_completion(resp: dict[str, Any]) -> list[dict[str, str]]:
    try:
        content = resp["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        return []
    citations = resp.get("citations") or []
    if not citations:
        return []

    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
    items: list[dict[str, str]] = []
    for line, url in zip(lines, citations):
        title = re.sub(r"^\d+[\.\)]\s*", "", line)
        title = re.sub(r"\s*\[\d+\]\s*$", "", title).strip()
        if not title:
            continue
        items.append({
            "title": title,
            "url": url,
            "summary": "",
            "source": _hostname(url),
        })
    return items


def shape_items(
    items: list[dict[str, str]],
    *,
    limit: int,
) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for it in items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        out.append(it)
        if len(out) >= limit:
            break
    return out


def shape_tavily_results(resp: dict[str, Any], *, limit: int) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for item in resp.get("results", []):
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        if not title or not url or url in seen:
            continue
        seen.add(url)
        out.append({
            "title": title,
            "url": url,
            "summary": str(item.get("content") or "").strip(),
            "source": _hostname(url),
        })
        if len(out) >= limit:
            break
    return out


def filter_twitter_urls(items: list[dict[str, str]]) -> list[dict[str, str]]:
    return [item for item in items if item.get("source") in {"x.com", "twitter.com"}]
