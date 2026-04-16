# AutoFanpage — Plan 2: Phase 1 Data Gathering (YouTube + Perplexity + Reddit + Merge)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the vertical slice from Plan 1 to gather news from all four Phase-1 sources (YouTube Data API v3, Perplexity Sonar, Reddit, Hacker News), merge them into a single normalized artifact (`merged_sources.json`), and report counts to Telegram. After Plan 2, the pipeline proves that parallel multi-source data gathering works end-to-end on OpenClaw — still without NotebookLM, writing, or publishing (those are Plan 3/4).

**Architecture:** Each new source (`youtube-researcher`, `perplexity-researcher`, `reddit-researcher`) follows the same two-file pattern already established by `hackernews-researcher` in Plan 1:
1. A **pure-logic module** in `autofanpage/sources/<name>.py` containing filter/rank/shape functions that are network-free and unit-testable.
2. A **skill script** in `skills/<name>-researcher/scripts/fetch_<name>.py` that performs network calls via the shared `autofanpage.http` client, delegates filtering to the pure module, writes the result artifact, and returns `{"status": "ok", "artifact": "..."}` to stdout as JSON.

A new shared HTTP helper (`autofanpage/http.py`) centralizes retries, timeouts, and error-to-exception mapping so each fetcher stays small. A new `autofanpage/merge.py` combines the four per-source JSON artifacts into one `merged_sources.json` with a uniform schema. The orchestrator is upgraded to dispatch the four researchers in parallel via a `ThreadPoolExecutor`, tolerate partial failures using the `min_posts_required` rule, and pass the merged artifact to the Telegram reporter.

**Tech Stack:** Python 3.11+, `requests`, `responses` (HTTP mock in tests), `concurrent.futures.ThreadPoolExecutor` for parallel dispatch. No new runtime dependencies beyond what Plan 1 installed.

**Spec reference:** `docs/superpowers/specs/2026-04-15-autofanpage-openclaw-design.md` (EN) / `.vi.md` (VN). This plan implements §3.2 (youtube-researcher), §3.3 (perplexity-researcher, including Twitter via `site:x.com`), §3.4 (reddit-researcher), §3.1 orchestrator parallel dispatch + merge, and the `merged_sources.json` artifact in §4. NotebookLM, review, writing, publishing, and health-check skills remain Plan 3/4.

---

## File Structure

**New shared libraries under `autofanpage/`:**
- `autofanpage/http.py` — `get_json(url, *, headers, params, timeout, max_retries) -> dict | list`; `post_json(url, *, headers, json_body, timeout, max_retries) -> dict`. Raises `autofanpage.errors.SourceFailedError` after retries exhausted.
- `autofanpage/sources/youtube.py` — pure filter/shape logic (views ≥ min_views, subs ≥ min_subs, published_after window, shape to common schema).
- `autofanpage/sources/perplexity.py` — pure logic for extracting `{title, url, summary, source}` tuples from a Perplexity chat completion response (parses citations).
- `autofanpage/sources/reddit.py` — pure logic (filter by score, filter by stickied/nsfw, shape post → common schema).
- `autofanpage/merge.py` — `merge_sources(artifacts: dict[str, Path], ..., max_per_platform: int) -> dict` where key is source name and value is path to per-source artifact. Returns a `{ urls, counts_per_platform, ... }` document matching the spec contract: deduplicated by canonical URL, capped at `max_per_platform` per source (default 12, so ≤48 total — under NotebookLM's 50-source limit).
- `autofanpage/schemas.py` — extend with schemas: `YOUTUBE_RESULTS_SCHEMA`, `PERPLEXITY_RESULTS_SCHEMA`, `REDDIT_RESULTS_SCHEMA`, `MERGED_SOURCES_SCHEMA`.

**New skill folders under `skills/`:**
- `skills/youtube-researcher/SKILL.md` + `scripts/__init__.py` + `scripts/fetch_youtube.py`
- `skills/perplexity-researcher/SKILL.md` + `scripts/__init__.py` + `scripts/fetch_perplexity.py`
- `skills/reddit-researcher/SKILL.md` + `scripts/__init__.py` + `scripts/fetch_reddit.py`

**Modified:**
- `skills/daily-content-pipeline/scripts/orchestrate.py` — parallel dispatch, merge call.
- `autofanpage/schemas.py` — new schemas, existing `HACKERNEWS_RESULTS_SCHEMA` unchanged.
- `scripts/install-skills.sh` — copy new skill folders.

**New tests under `tests/`:**
- `tests/test_http.py`
- `tests/sources/test_youtube.py`, `tests/sources/test_perplexity.py`, `tests/sources/test_reddit.py`
- `tests/test_merge.py`
- `tests/skills/test_youtube_fetch.py`, `tests/skills/test_perplexity_fetch.py`, `tests/skills/test_reddit_fetch.py`
- `tests/skills/test_orchestrator_plan2.py` (covers parallel dispatch + merge + partial-failure rule)

---

### Task 1: Shared HTTP client with retry + timeout

**Files:**
- Create: `autofanpage/http.py`
- Test: `tests/test_http.py`

- [ ] **Step 1: Write failing test `tests/test_http.py`**

```python
import pytest
import responses

from autofanpage.http import get_json, post_json
from autofanpage.errors import SourceFailedError


@responses.activate
def test_get_json_returns_parsed_body():
    responses.add(
        responses.GET, "https://api.example/x",
        json={"ok": True}, status=200,
    )
    assert get_json("https://api.example/x") == {"ok": True}


@responses.activate
def test_get_json_retries_on_5xx_then_succeeds():
    responses.add(responses.GET, "https://api.example/x", status=503)
    responses.add(responses.GET, "https://api.example/x", status=502)
    responses.add(
        responses.GET, "https://api.example/x",
        json={"ok": True}, status=200,
    )
    assert get_json("https://api.example/x", max_retries=3, backoff=0) == {"ok": True}
    assert len(responses.calls) == 3


@responses.activate
def test_get_json_raises_after_exhausted_retries():
    for _ in range(4):
        responses.add(responses.GET, "https://api.example/x", status=500)
    with pytest.raises(SourceFailedError) as exc:
        get_json("https://api.example/x", max_retries=3, backoff=0)
    assert "https://api.example/x" in str(exc.value)


@responses.activate
def test_get_json_does_not_retry_4xx():
    responses.add(responses.GET, "https://api.example/x", status=404)
    with pytest.raises(SourceFailedError):
        get_json("https://api.example/x", max_retries=3, backoff=0)
    assert len(responses.calls) == 1


@responses.activate
def test_get_json_retries_on_429_then_succeeds():
    responses.add(responses.GET, "https://api.example/x", status=429,
                  headers={"Retry-After": "1"})
    responses.add(responses.GET, "https://api.example/x",
                  json={"ok": True}, status=200)
    assert get_json("https://api.example/x", max_retries=3, backoff=0) == {"ok": True}
    assert len(responses.calls) == 2


@responses.activate
def test_get_json_raises_after_exhausted_429_retries():
    for _ in range(4):
        responses.add(responses.GET, "https://api.example/x", status=429)
    with pytest.raises(SourceFailedError):
        get_json("https://api.example/x", max_retries=3, backoff=0)
    assert len(responses.calls) == 4


@responses.activate
def test_post_json_sends_body_and_headers():
    def check(request):
        assert request.headers["Authorization"] == "Bearer tok"
        assert request.headers["Content-Type"] == "application/json"
        body = request.body
        if isinstance(body, (bytes, bytearray)):
            body = body.decode()
        assert '"q": "hi"' in body
        return (200, {}, '{"result": 1}')

    responses.add_callback(
        responses.POST, "https://api.example/chat",
        callback=check, content_type="application/json",
    )
    out = post_json(
        "https://api.example/chat",
        headers={"Authorization": "Bearer tok"},
        json_body={"q": "hi"},
    )
    assert out == {"result": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_http.py -v`
Expected: `ModuleNotFoundError: No module named 'autofanpage.http'`.

- [ ] **Step 3: Write `autofanpage/http.py`**

```python
"""Shared HTTP client with retry + timeout for all source fetchers.

Retries on 5xx and connection errors up to ``max_retries`` times with
exponential backoff. 4xx responses fail immediately (caller bug or auth
problem). All failure paths raise ``SourceFailedError`` with the URL
and final status in the message so orchestrator logs are useful.
"""
from __future__ import annotations

import time
from typing import Any

import requests

from autofanpage.errors import SourceFailedError

DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF = 1.0


def _request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None,
    params: dict[str, Any] | None,
    json_body: dict[str, Any] | None,
    timeout: float,
    max_retries: int,
    backoff: float,
) -> Any:
    last_err: str | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.request(
                method, url,
                headers=headers, params=params, json=json_body,
                timeout=timeout,
            )
        except requests.RequestException as e:
            last_err = f"{type(e).__name__}: {e}"
            if attempt >= max_retries:
                break
            time.sleep(backoff * (2 ** attempt))
            continue

        if 200 <= resp.status_code < 300:
            return resp.json()
        if resp.status_code == 429:
            # Rate-limited — treat as transient, honour Retry-After if present.
            retry_after = resp.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else backoff * (2 ** attempt)
            last_err = f"HTTP 429 (rate limited)"
            if attempt >= max_retries:
                break
            time.sleep(wait)
            continue
        if 400 <= resp.status_code < 500:
            # Don't retry other client errors.
            raise SourceFailedError(
                f"{method} {url} -> HTTP {resp.status_code}: {resp.text[:200]}"
            )
        # 5xx: retry
        last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
        if attempt >= max_retries:
            break
        time.sleep(backoff * (2 ** attempt))
    raise SourceFailedError(f"{method} {url} failed after {max_retries} retries: {last_err}")


def get_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
) -> Any:
    return _request_json(
        "GET", url,
        headers=headers, params=params, json_body=None,
        timeout=timeout, max_retries=max_retries, backoff=backoff,
    )


def post_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
) -> Any:
    merged_headers = {"Content-Type": "application/json"}
    if headers:
        merged_headers.update(headers)
    return _request_json(
        "POST", url,
        headers=merged_headers, params=None, json_body=json_body,
        timeout=timeout, max_retries=max_retries, backoff=backoff,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_http.py -v`
Expected: `7 passed`.

- [ ] **Step 5: Commit**

```bash
git add autofanpage/http.py tests/test_http.py
git commit -m "feat(http): shared HTTP client with retry+timeout"
```

---

### Task 2: Extend schemas for Phase 1 artifacts

**Files:**
- Modify: `autofanpage/schemas.py`
- Modify: `tests/test_schemas.py`

- [ ] **Step 1: Add failing schema tests**

Append to `tests/test_schemas.py`:

```python
from autofanpage.schemas import (
    YOUTUBE_RESULTS_SCHEMA,
    PERPLEXITY_RESULTS_SCHEMA,
    REDDIT_RESULTS_SCHEMA,
    MERGED_SOURCES_SCHEMA,
)


def test_youtube_schema_accepts_valid():
    validate("youtube_results", {
        "source": "youtube",
        "fetched_at": "2026-04-15T06:00:00+07:00",
        "items": [{
            "title": "t", "url": "https://youtu.be/x",
            "video_id": "x", "channel": "c",
            "views": 150000, "subscribers": 50000,
            "published_at": "2026-04-10T00:00:00Z",
        }],
    })


def test_youtube_schema_rejects_missing_views():
    with pytest.raises(SchemaError):
        validate("youtube_results", {
            "source": "youtube",
            "fetched_at": "2026-04-15T06:00:00+07:00",
            "items": [{"title": "t", "url": "u", "video_id": "x",
                       "channel": "c", "published_at": "..."}],
        })


def test_perplexity_schema_accepts_valid():
    validate("perplexity_results", {
        "source": "perplexity",
        "fetched_at": "2026-04-15T06:00:00+07:00",
        "news": [{"title": "t", "url": "https://a", "summary": "s", "source": "a.com"}],
        "reports": [{"title": "t", "url": "https://b", "summary": "s", "source": "b.com"}],
        "twitter": [{"title": "t", "url": "https://x.com/u/status/1",
                     "summary": "s", "source": "x.com"}],
    })


def test_reddit_schema_accepts_valid():
    validate("reddit_results", {
        "source": "reddit",
        "fetched_at": "2026-04-15T06:00:00+07:00",
        "items": [{
            "title": "t", "url": "https://reddit.com/r/x/comments/1",
            "subreddit": "ChatGPT", "score": 500,
            "num_comments": 120, "author": "u",
            "permalink": "/r/ChatGPT/comments/1",
            "created_at": "2026-04-12T10:00:00Z",
            "is_self": False, "external_url": "https://ext.com/a",
        }],
    })


def test_merged_sources_schema_accepts_valid():
    validate("merged_sources", {
        "profile": "page_vn_ai",
        "topic": "AI automation business",
        "language": "vi",
        "fetched_at": "2026-04-15T06:00:00+07:00",
        "sources_succeeded": ["youtube", "hackernews"],
        "sources_failed": [{"source": "reddit", "error": "..."}],
        "counts_per_platform": {"youtube": 1, "hackernews": 1},
        "urls": [{
            "url": "https://u", "title": "t", "platform": "youtube",
            "score_or_views": 150000, "created_at": "2026-04-10T00:00:00Z",
        }],
    })
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_schemas.py -v`
Expected: `ImportError` — new schema constants don't exist.

- [ ] **Step 3: Append schemas to `autofanpage/schemas.py`**

Add after existing schemas:

```python
YOUTUBE_RESULTS_SCHEMA = {
    "type": "object",
    "required": ["source", "fetched_at", "items"],
    "properties": {
        "source": {"const": "youtube"},
        "fetched_at": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["title", "url", "video_id", "channel",
                             "views", "published_at"],
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "video_id": {"type": "string"},
                    "channel": {"type": "string"},
                    "channel_id": {"type": "string"},
                    "views": {"type": "integer", "minimum": 0},
                    "subscribers": {"type": "integer", "minimum": 0},
                    "published_at": {"type": "string"},
                },
            },
        },
    },
}


_PERP_ITEM = {
    "type": "object",
    "required": ["title", "url", "summary", "source"],
    "properties": {
        "title": {"type": "string"},
        "url": {"type": "string"},
        "summary": {"type": "string"},
        "source": {"type": "string"},
    },
}

PERPLEXITY_RESULTS_SCHEMA = {
    "type": "object",
    "required": ["source", "fetched_at", "news", "reports", "twitter"],
    "properties": {
        "source": {"const": "perplexity"},
        "fetched_at": {"type": "string"},
        "news": {"type": "array", "items": _PERP_ITEM},
        "reports": {"type": "array", "items": _PERP_ITEM},
        "twitter": {"type": "array", "items": _PERP_ITEM},
    },
}


REDDIT_RESULTS_SCHEMA = {
    "type": "object",
    "required": ["source", "fetched_at", "items"],
    "properties": {
        "source": {"const": "reddit"},
        "fetched_at": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["title", "url", "subreddit", "score",
                             "num_comments", "author", "permalink",
                             "created_at", "is_self"],
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "subreddit": {"type": "string"},
                    "score": {"type": "integer"},
                    "num_comments": {"type": "integer"},
                    "author": {"type": "string"},
                    "permalink": {"type": "string"},
                    "created_at": {"type": "string"},
                    "is_self": {"type": "boolean"},
                    "external_url": {"type": "string"},
                },
            },
        },
    },
}


MERGED_SOURCES_SCHEMA = {
    "type": "object",
    "required": ["profile", "topic", "language", "fetched_at",
                 "sources_succeeded", "sources_failed",
                 "counts_per_platform", "urls"],
    "properties": {
        "profile": {"type": "string"},
        "topic": {"type": "string"},
        "language": {"type": "string"},
        "fetched_at": {"type": "string"},
        "sources_succeeded": {"type": "array", "items": {"type": "string"}},
        "sources_failed": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["source", "error"],
                "properties": {
                    "source": {"type": "string"},
                    "error": {"type": "string"},
                },
            },
        },
        "counts_per_platform": {
            "type": "object",
            "additionalProperties": {"type": "integer"},
        },
        "urls": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["url", "title", "platform", "score_or_views",
                             "created_at"],
                "properties": {
                    "url": {"type": "string"},
                    "title": {"type": "string"},
                    "platform": {"type": "string"},
                    "score_or_views": {"type": "integer"},
                    "created_at": {"type": "string"},
                },
            },
        },
    },
}
```

Extend the `_SCHEMAS` mapping (Plan 1 uses keys **without** `.json` suffix — keep the same convention):

```python
_SCHEMAS = {
    "profile": PROFILE_SCHEMA,
    "hackernews_results": HACKERNEWS_RESULTS_SCHEMA,
    "last_success": LAST_SUCCESS_SCHEMA,
    "youtube_results": YOUTUBE_RESULTS_SCHEMA,
    "perplexity_results": PERPLEXITY_RESULTS_SCHEMA,
    "reddit_results": REDDIT_RESULTS_SCHEMA,
    "merged_sources": MERGED_SOURCES_SCHEMA,
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_schemas.py -v`
Expected: all existing tests still pass + 5 new ones pass.

- [ ] **Step 5: Commit**

```bash
git add autofanpage/schemas.py tests/test_schemas.py
git commit -m "feat(schemas): add YouTube/Perplexity/Reddit/merged schemas"
```

---

### Task 3: YouTube source pure logic

**Files:**
- Create: `autofanpage/sources/youtube.py`
- Test: `tests/sources/test_youtube.py`
- Fixture: `tests/fixtures/youtube_search.json`, `tests/fixtures/youtube_videos.json`, `tests/fixtures/youtube_channels.json`

- [ ] **Step 1: Create fixtures**

`tests/fixtures/youtube_search.json` — simulates `search.list` response (snippet only, no stats):

```json
{
  "items": [
    {"id": {"videoId": "v1"},
     "snippet": {"title": "AI agents revolution",
                 "channelId": "c1", "channelTitle": "Ch1",
                 "publishedAt": "2026-04-10T00:00:00Z"}},
    {"id": {"videoId": "v2"},
     "snippet": {"title": "Cute cats",
                 "channelId": "c2", "channelTitle": "Ch2",
                 "publishedAt": "2026-04-11T00:00:00Z"}},
    {"id": {"videoId": "v3"},
     "snippet": {"title": "AI automation for business",
                 "channelId": "c3", "channelTitle": "Ch3",
                 "publishedAt": "2026-04-12T00:00:00Z"}}
  ]
}
```

`tests/fixtures/youtube_videos.json` — simulates `videos.list(part=statistics)`:

```json
{
  "items": [
    {"id": "v1", "statistics": {"viewCount": "250000"}},
    {"id": "v2", "statistics": {"viewCount": "5000"}},
    {"id": "v3", "statistics": {"viewCount": "150000"}}
  ]
}
```

`tests/fixtures/youtube_channels.json` — simulates `channels.list(part=statistics)`:

```json
{
  "items": [
    {"id": "c1", "statistics": {"subscriberCount": "50000"}},
    {"id": "c2", "statistics": {"subscriberCount": "500"}},
    {"id": "c3", "statistics": {"subscriberCount": "20000"}}
  ]
}
```

- [ ] **Step 2: Write failing test `tests/sources/test_youtube.py`**

```python
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
    assert "v2" not in ids  # 5000 < 100000


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
```

- [ ] **Step 3: Run to verify it fails**

Run: `pytest tests/sources/test_youtube.py -v`
Expected: `ModuleNotFoundError: No module named 'autofanpage.sources.youtube'`.

- [ ] **Step 4: Write `autofanpage/sources/youtube.py`**

```python
"""Pure filter/shape logic for YouTube Data API v3 results.

Network calls (search.list, videos.list, channels.list) live in
``skills/youtube-researcher/scripts/fetch_youtube.py``. This module
takes the already-fetched JSON payloads and produces the pipeline's
``youtube_results.json`` items.
"""
from __future__ import annotations

from typing import Any


def merge_stats(
    search: dict[str, Any],
    videos: dict[str, Any],
    channels: dict[str, Any],
) -> list[dict[str, Any]]:
    """Join search items with video stats (views) and channel stats (subs)."""
    view_by_id = {
        v["id"]: int(v["statistics"].get("viewCount", "0"))
        for v in videos.get("items", [])
    }
    sub_by_id = {
        c["id"]: int(c["statistics"].get("subscriberCount", "0"))
        for c in channels.get("items", [])
    }
    merged: list[dict[str, Any]] = []
    for item in search.get("items", []):
        vid = item["id"]["videoId"]
        snip = item["snippet"]
        merged.append({
            "video_id": vid,
            "title": snip["title"],
            "channel": snip["channelTitle"],
            "channel_id": snip["channelId"],
            "views": view_by_id.get(vid, 0),
            "subscribers": sub_by_id.get(snip["channelId"], 0),
            "published_at": snip["publishedAt"],
        })
    return merged


def filter_and_rank(
    items: list[dict[str, Any]],
    *,
    min_views: int,
    min_subs: int,
    limit: int,
) -> list[dict[str, Any]]:
    keep = [
        i for i in items
        if i["views"] >= min_views and i["subscribers"] >= min_subs
    ]
    keep.sort(key=lambda i: i["views"], reverse=True)
    return keep[:limit]


def to_result(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": item["title"],
        "url": f"https://youtu.be/{item['video_id']}",
        "video_id": item["video_id"],
        "channel": item["channel"],
        "channel_id": item["channel_id"],
        "views": item["views"],
        "subscribers": item["subscribers"],
        "published_at": item["published_at"],
    }
```

- [ ] **Step 5: Run to verify it passes**

Run: `pytest tests/sources/test_youtube.py -v`
Expected: `6 passed`.

- [ ] **Step 6: Commit**

```bash
git add autofanpage/sources/youtube.py tests/sources/test_youtube.py tests/fixtures/youtube_*.json
git commit -m "feat(sources): add youtube filter/rank/shape logic"
```

---

### Task 4: YouTube fetcher skill script

**Files:**
- Create: `skills/youtube-researcher/SKILL.md`
- Create: `skills/youtube-researcher/scripts/__init__.py`
- Create: `skills/youtube-researcher/scripts/fetch_youtube.py`
- Test: `tests/skills/test_youtube_fetch.py`

- [ ] **Step 1: Write failing test `tests/skills/test_youtube_fetch.py`**

```python
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
    # monkeypatch secret lookup
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/skills/test_youtube_fetch.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `skills/youtube-researcher/SKILL.md`**

```markdown
---
name: youtube-researcher
description: Fetch top AI-automation YouTube videos matching a topic, filtered by views and channel subscribers. Use when daily-content-pipeline dispatches Phase-1 data gathering for a profile.
---

# youtube-researcher

## Inputs

Invoke with a JSON payload:

```json
{
  "topic": "AI automation business",
  "min_views": 100000,
  "min_subs": 10000,
  "api_key_ref": "secret:youtube_api_key",
  "limit": 10,
  "out_path": "/path/to/run_dir/youtube_results.json"
}
```

## Output

Writes `youtube_results.json` matching `YOUTUBE_RESULTS_SCHEMA`; returns `{"status": "ok", "artifact": "<out_path>", "count": N}` on stdout.

## Failure modes

- Missing/invalid API key → `SourceFailedError` (HTTP 400/403 from Google).
- Quota exhausted → `SourceFailedError` with HTTP 403 `quotaExceeded`.
- Any 5xx is retried up to 3× via `autofanpage.http`.
```

- [ ] **Step 4: Write `skills/youtube-researcher/scripts/__init__.py`** — empty file.

- [ ] **Step 5: Write `skills/youtube-researcher/scripts/fetch_youtube.py`**

Two-layer design matches Plan 1's `hackernews-researcher`:
- `run(...)` takes fine-grained kwargs so unit tests don't need a full profile on disk.
- `main(argv)` is the OpenClaw entry point: parses `--run-dir --profile`, loads profile, calls `run()`, writes the artifact using `RunDir.write_json`.

```python
"""YouTube-researcher skill script.

Fetches candidate videos from the YouTube Data API v3 (search.list →
videos.list → channels.list), joins view/subscriber stats, applies the
profile filters, and writes ``youtube_results.json`` into the run dir.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

from autofanpage.http import get_json  # noqa: E402
from autofanpage.profile import load_profile  # noqa: E402
from autofanpage.run_dir import RunDir  # noqa: E402
from autofanpage.schemas import validate  # noqa: E402
from autofanpage.secrets import get_secret  # noqa: E402
from autofanpage.sources.youtube import (  # noqa: E402
    merge_stats, filter_and_rank, to_result,
)

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"


def _published_after(days: int = 7) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(
    *,
    topic: str,
    min_views: int,
    min_subs: int,
    api_key_ref: str,
    limit: int,
    out_path: str,
) -> dict:
    api_key = get_secret(api_key_ref)

    search = get_json(SEARCH_URL, params={
        "part": "snippet",
        "q": topic,
        "order": "viewCount",
        "publishedAfter": _published_after(7),
        "type": "video",
        "maxResults": 25,
        "key": api_key,
    })

    video_ids = [it["id"]["videoId"] for it in search.get("items", [])]
    channel_ids = list({it["snippet"]["channelId"] for it in search.get("items", [])})

    videos = (
        get_json(VIDEOS_URL, params={
            "part": "statistics", "id": ",".join(video_ids), "key": api_key,
        })
        if video_ids else {"items": []}
    )
    channels = (
        get_json(CHANNELS_URL, params={
            "part": "statistics", "id": ",".join(channel_ids), "key": api_key,
        })
        if channel_ids else {"items": []}
    )

    merged = merge_stats(search, videos, channels)
    kept = filter_and_rank(
        merged, min_views=min_views, min_subs=min_subs, limit=limit,
    )
    doc = {
        "source": "youtube",
        "fetched_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "items": [to_result(m) for m in kept],
    }
    validate("youtube_results", doc)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    return {"status": "ok", "artifact": out_path, "count": len(doc["items"])}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--profile", required=True)
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    cfg = profile.sources.get("youtube", {})
    if not cfg.get("enabled", False):
        Path(args.run_dir, "youtube_results.json").write_text(
            json.dumps({"source": "youtube",
                        "fetched_at": datetime.now(timezone.utc).astimezone().isoformat(),
                        "items": []}, ensure_ascii=False),
        )
        print(json.dumps({"status": "ok", "skipped": True, "count": 0}))
        return 0

    out_path = str(Path(args.run_dir) / "youtube_results.json")
    result = run(
        topic=profile.topic,
        min_views=profile.filters["youtube_min_views"],
        min_subs=profile.filters["youtube_min_subs"],
        api_key_ref="secret:youtube_api_key",
        limit=10,
        out_path=out_path,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run to verify it passes**

Run: `pytest tests/skills/test_youtube_fetch.py -v`
Expected: `2 passed`.

- [ ] **Step 7: Commit**

```bash
git add skills/youtube-researcher/ tests/skills/test_youtube_fetch.py
git commit -m "feat(skills): youtube-researcher fetch + filter"
```

---

### Task 5: Perplexity source pure logic

**Files:**
- Create: `autofanpage/sources/perplexity.py`
- Test: `tests/sources/test_perplexity.py`
- Fixture: `tests/fixtures/perplexity_response.json`

- [ ] **Step 1: Create fixture `tests/fixtures/perplexity_response.json`**

Mimics the OpenAI-compatible shape returned by Sonar (one assistant message, citations list):

```json
{
  "id": "cmpl-123",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "1. GPT-5 launch redefines enterprise AI [1]\nAnthropic released Claude 4 with agentic capabilities [2]\n3. New AI automation startups raise $500M [3]"
    }
  }],
  "citations": [
    "https://openai.com/blog/gpt5",
    "https://anthropic.com/claude4",
    "https://techcrunch.com/ai-funding"
  ]
}
```

- [ ] **Step 2: Write failing test `tests/sources/test_perplexity.py`**

```python
import json
import pytest

from autofanpage.sources.perplexity import parse_completion, shape_items


@pytest.fixture
def resp(fixtures_dir):
    return json.loads((fixtures_dir / "perplexity_response.json").read_text())


def test_parse_completion_splits_numbered_lines(resp):
    items = parse_completion(resp)
    assert len(items) == 3
    assert "GPT-5" in items[0]["title"]
    assert items[0]["url"] == "https://openai.com/blog/gpt5"
    assert items[1]["url"] == "https://anthropic.com/claude4"
    assert items[2]["url"] == "https://techcrunch.com/ai-funding"


def test_parse_completion_uses_hostname_as_source(resp):
    items = parse_completion(resp)
    assert items[0]["source"] == "openai.com"
    assert items[1]["source"] == "anthropic.com"
    assert items[2]["source"] == "techcrunch.com"


def test_parse_completion_handles_missing_citations():
    out = parse_completion({
        "choices": [{"message": {"content": "1. foo\n2. bar"}}],
    })
    assert out == []


def test_shape_items_dedupes_by_url():
    raw = [
        {"title": "a", "url": "https://x/1", "summary": "", "source": "x"},
        {"title": "b", "url": "https://x/1", "summary": "", "source": "x"},
        {"title": "c", "url": "https://x/2", "summary": "", "source": "x"},
    ]
    out = shape_items(raw, limit=10)
    urls = [i["url"] for i in out]
    assert urls == ["https://x/1", "https://x/2"]


def test_shape_items_respects_limit():
    raw = [
        {"title": str(i), "url": f"https://x/{i}", "summary": "", "source": "x"}
        for i in range(5)
    ]
    assert len(shape_items(raw, limit=3)) == 3
```

- [ ] **Step 3: Run to verify it fails**

Run: `pytest tests/sources/test_perplexity.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Write `autofanpage/sources/perplexity.py`**

```python
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
    """Extract ``{title, url, summary, source}`` tuples from a Sonar response.

    Lines of the assistant message are zipped with ``resp["citations"]`` in
    order. Lines without a matching citation are dropped. Leading numbering
    like ``"1. "`` is stripped from titles.
    """
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
        # strip leading "1. " / "1) " numbering
        title = re.sub(r"^\d+[\.\)]\s*", "", line)
        # strip trailing citation markers like "[1]"
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
    """Dedupe by URL, preserve order, truncate to ``limit``."""
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
```

- [ ] **Step 5: Run to verify it passes**

Run: `pytest tests/sources/test_perplexity.py -v`
Expected: `5 passed`.

- [ ] **Step 6: Commit**

```bash
git add autofanpage/sources/perplexity.py tests/sources/test_perplexity.py tests/fixtures/perplexity_response.json
git commit -m "feat(sources): add perplexity parse/shape logic"
```

---

### Task 6: Perplexity fetcher skill script

**Files:**
- Create: `skills/perplexity-researcher/SKILL.md`
- Create: `skills/perplexity-researcher/scripts/__init__.py`
- Create: `skills/perplexity-researcher/scripts/fetch_perplexity.py`
- Test: `tests/skills/test_perplexity_fetch.py`

- [ ] **Step 1: Write failing test `tests/skills/test_perplexity_fetch.py`**

```python
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

    # 3 separate POST calls — responses matches in FIFO order.
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
    # exactly 2 POSTs, not 3
    assert len(responses.calls) == 2
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/skills/test_perplexity_fetch.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `skills/perplexity-researcher/SKILL.md`**

```markdown
---
name: perplexity-researcher
description: Query Perplexity Sonar for today's AI automation news, recent research reports, and Twitter/X posts about a topic. Outputs three parallel lists.
---

# perplexity-researcher

## Inputs

```json
{
  "topic": "AI automation business",
  "api_key_ref": "secret:perplexity_api_key",
  "news_limit": 5,
  "reports_limit": 3,
  "twitter_limit": 5,
  "twitter_enabled": true,
  "out_path": "/path/to/run_dir/perplexity_results.json"
}
```

## Output

Writes `perplexity_results.json` matching `PERPLEXITY_RESULTS_SCHEMA` (keys: `news`, `reports`, `twitter`). When `twitter_enabled=false`, `twitter` is an empty list and no call is made.

## Failure modes

- Missing/invalid API key → `SourceFailedError` (HTTP 401).
- Rate limited → HTTP 429 treated as transient; retries via `autofanpage.http`.
- Malformed completion (no citations) → source produces empty list, does not fail.
```

- [ ] **Step 4: Write `skills/perplexity-researcher/scripts/__init__.py`** — empty.

- [ ] **Step 5: Write `skills/perplexity-researcher/scripts/fetch_perplexity.py`**

```python
"""Perplexity-researcher skill script.

Issues up to three Sonar chat completions: news (sonar-pro), reports
(sonar academic), and Twitter/X (sonar-pro with site:x.com). Writes a
combined ``perplexity_results.json`` into the run dir.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

from autofanpage.http import post_json  # noqa: E402
from autofanpage.profile import load_profile  # noqa: E402
from autofanpage.schemas import validate  # noqa: E402
from autofanpage.secrets import get_secret  # noqa: E402
from autofanpage.sources.perplexity import parse_completion, shape_items  # noqa: E402

CHAT_URL = "https://api.perplexity.ai/chat/completions"


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


def run(
    *,
    topic: str,
    api_key_ref: str,
    news_limit: int,
    reports_limit: int,
    twitter_limit: int,
    twitter_enabled: bool,
    out_path: str,
) -> dict:
    api_key = get_secret(api_key_ref)

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
        twitter = [
            i for i in shape_items(parse_completion(tw_resp), limit=twitter_limit)
            if "x.com" in i["source"] or "twitter.com" in i["source"]
        ]
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
    out_path = str(Path(args.run_dir) / "perplexity_results.json")
    result = run(
        topic=profile.topic,
        api_key_ref="secret:perplexity_api_key",
        news_limit=5, reports_limit=3, twitter_limit=5,
        twitter_enabled=twitter_enabled,
        out_path=out_path,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run to verify it passes**

Run: `pytest tests/skills/test_perplexity_fetch.py -v`
Expected: `2 passed`.

- [ ] **Step 7: Commit**

```bash
git add skills/perplexity-researcher/ tests/skills/test_perplexity_fetch.py
git commit -m "feat(skills): perplexity-researcher with news+reports+twitter"
```

---

### Task 7: Reddit source pure logic

**Files:**
- Create: `autofanpage/sources/reddit.py`
- Test: `tests/sources/test_reddit.py`
- Fixture: `tests/fixtures/reddit_listing.json`

- [ ] **Step 1: Create fixture `tests/fixtures/reddit_listing.json`**

```json
{
  "data": {
    "children": [
      {"data": {
        "title": "OpenAI drops GPT-5",
        "subreddit": "ChatGPT",
        "score": 1500,
        "num_comments": 320,
        "author": "u1",
        "permalink": "/r/ChatGPT/comments/aaa/openai_drops_gpt5/",
        "url": "https://openai.com/gpt5",
        "created_utc": 1744156800,
        "is_self": false,
        "stickied": false,
        "over_18": false
      }},
      {"data": {
        "title": "Meta: please read the rules",
        "subreddit": "ChatGPT",
        "score": 50, "num_comments": 0, "author": "mod",
        "permalink": "/r/ChatGPT/comments/bbb/meta/",
        "url": "https://reddit.com/r/ChatGPT/comments/bbb/meta/",
        "created_utc": 1744156800, "is_self": true,
        "stickied": true, "over_18": false
      }},
      {"data": {
        "title": "NSFW low-effort",
        "subreddit": "ChatGPT",
        "score": 200, "num_comments": 10, "author": "u3",
        "permalink": "/r/ChatGPT/comments/ccc/nsfw/",
        "url": "https://x.com/nsfw",
        "created_utc": 1744156800, "is_self": false,
        "stickied": false, "over_18": true
      }},
      {"data": {
        "title": "AI agents beat humans at coding",
        "subreddit": "ChatGPT",
        "score": 80, "num_comments": 5, "author": "u4",
        "permalink": "/r/ChatGPT/comments/ddd/ai_agents/",
        "url": "https://arxiv.org/abs/xxx",
        "created_utc": 1744156800, "is_self": false,
        "stickied": false, "over_18": false
      }}
    ]
  }
}
```

- [ ] **Step 2: Write failing test `tests/sources/test_reddit.py`**

```python
import json
import pytest

from autofanpage.sources.reddit import filter_and_rank, to_result


@pytest.fixture
def listing(fixtures_dir):
    return json.loads((fixtures_dir / "reddit_listing.json").read_text())


def test_filter_rejects_stickied(listing):
    out = filter_and_rank(listing, min_score=0, top_n=10)
    assert all(not (p.get("stickied")) for p in out)


def test_filter_rejects_nsfw(listing):
    out = filter_and_rank(listing, min_score=0, top_n=10)
    assert all(not p.get("over_18") for p in out)


def test_filter_rejects_below_min_score(listing):
    out = filter_and_rank(listing, min_score=100, top_n=10)
    titles = [p["title"] for p in out]
    assert "AI agents beat humans at coding" not in titles  # score 80


def test_filter_sorts_by_score_desc(listing):
    out = filter_and_rank(listing, min_score=0, top_n=10)
    scores = [p["score"] for p in out]
    assert scores == sorted(scores, reverse=True)


def test_filter_respects_top_n(listing):
    out = filter_and_rank(listing, min_score=0, top_n=1)
    assert len(out) == 1


def test_to_result_shape():
    post = {
        "title": "t", "subreddit": "ChatGPT",
        "score": 500, "num_comments": 120, "author": "u",
        "permalink": "/r/ChatGPT/comments/1/t/",
        "url": "https://ext.com/a",
        "created_utc": 1744156800, "is_self": False,
    }
    r = to_result(post)
    assert r["title"] == "t"
    assert r["url"] == "https://reddit.com/r/ChatGPT/comments/1/t/"
    assert r["external_url"] == "https://ext.com/a"
    assert r["subreddit"] == "ChatGPT"
    assert r["score"] == 500
    assert r["is_self"] is False
    assert r["created_at"].startswith("202")
```

- [ ] **Step 3: Run to verify it fails**

Run: `pytest tests/sources/test_reddit.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Write `autofanpage/sources/reddit.py`**

```python
"""Pure filter/shape logic for Reddit listing JSON.

``skills/reddit-researcher/scripts/fetch_reddit.py`` handles OAuth and
network; this module decides which posts pass and how to reshape them.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def filter_and_rank(
    listing: dict[str, Any],
    *,
    min_score: int,
    top_n: int,
) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for child in listing.get("data", {}).get("children", []):
        p = child.get("data", {})
        if p.get("stickied"):
            continue
        if p.get("over_18"):
            continue
        if p.get("score", 0) < min_score:
            continue
        kept.append(p)
    kept.sort(key=lambda p: p.get("score", 0), reverse=True)
    return kept[:top_n]


def to_result(post: dict[str, Any]) -> dict[str, Any]:
    created = datetime.fromtimestamp(
        post["created_utc"], tz=timezone.utc,
    ).isoformat()
    return {
        "title": post["title"],
        "url": f"https://reddit.com{post['permalink']}",
        "subreddit": post["subreddit"],
        "score": post["score"],
        "num_comments": post.get("num_comments", 0),
        "author": post.get("author", ""),
        "permalink": post["permalink"],
        "created_at": created,
        "is_self": bool(post.get("is_self")),
        "external_url": post.get("url", ""),
    }
```

- [ ] **Step 5: Run to verify it passes**

Run: `pytest tests/sources/test_reddit.py -v`
Expected: `6 passed`.

- [ ] **Step 6: Commit**

```bash
git add autofanpage/sources/reddit.py tests/sources/test_reddit.py tests/fixtures/reddit_listing.json
git commit -m "feat(sources): add reddit filter/shape logic"
```

---

### Task 8: Reddit OAuth token helper

**Files:**
- Create: `autofanpage/sources/reddit_auth.py`
- Test: `tests/sources/test_reddit_auth.py`

The Reddit app-only OAuth flow needs its own small helper because it uses HTTP Basic auth (client_id:client_secret) and `grant_type=client_credentials` — not the same shape as the JSON endpoints. Keeping it separate keeps `fetch_reddit.py` simple and gives us a focused unit test.

- [ ] **Step 1: Write failing test `tests/sources/test_reddit_auth.py`**

```python
import base64
import pytest
import responses

from autofanpage.sources.reddit_auth import get_app_token
from autofanpage.errors import SourceFailedError

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"


@responses.activate
def test_get_token_sends_basic_auth_and_form():
    def check(request):
        # Basic auth with client_id:client_secret
        expected = base64.b64encode(b"cid:csec").decode()
        assert request.headers["Authorization"] == f"Basic {expected}"
        assert request.headers["User-Agent"].startswith("autofanpage")
        body = request.body
        if isinstance(body, (bytes, bytearray)):
            body = body.decode()
        assert "grant_type=client_credentials" in body
        return (200, {}, '{"access_token": "tkn", "token_type": "bearer", "expires_in": 3600}')

    responses.add_callback(
        responses.POST, TOKEN_URL,
        callback=check, content_type="application/json",
    )
    token = get_app_token("cid", "csec", user_agent="autofanpage/0.1")
    assert token == "tkn"


@responses.activate
def test_get_token_raises_on_401():
    responses.add(responses.POST, TOKEN_URL, status=401, json={"error": "invalid_grant"})
    with pytest.raises(SourceFailedError):
        get_app_token("cid", "csec", user_agent="autofanpage/0.1")
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/sources/test_reddit_auth.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `autofanpage/sources/reddit_auth.py`**

```python
"""Reddit app-only OAuth (client_credentials) token fetcher."""
from __future__ import annotations

import requests

from autofanpage.errors import SourceFailedError

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"


def get_app_token(client_id: str, client_secret: str, *, user_agent: str) -> str:
    resp = requests.post(
        TOKEN_URL,
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials"},
        headers={"User-Agent": user_agent},
        timeout=30,
    )
    if resp.status_code != 200:
        raise SourceFailedError(
            f"Reddit token fetch failed: HTTP {resp.status_code}: {resp.text[:200]}"
        )
    body = resp.json()
    token = body.get("access_token")
    if not token:
        raise SourceFailedError(f"Reddit token response missing access_token: {body}")
    return token
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/sources/test_reddit_auth.py -v`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add autofanpage/sources/reddit_auth.py tests/sources/test_reddit_auth.py
git commit -m "feat(sources): reddit OAuth client_credentials helper"
```

---

### Task 9: Reddit fetcher skill script (multi-subreddit)

**Files:**
- Create: `skills/reddit-researcher/SKILL.md`
- Create: `skills/reddit-researcher/scripts/__init__.py`
- Create: `skills/reddit-researcher/scripts/fetch_reddit.py`
- Test: `tests/skills/test_reddit_fetch.py`

- [ ] **Step 1: Write failing test `tests/skills/test_reddit_fetch.py`**

```python
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
    # Two subreddits -> two listing calls
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
    assert "two" not in titles  # below min_score


@responses.activate
def test_run_continues_if_one_subreddit_fails(tmp_path, monkeypatch):
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
        json=_listing([_post(title="good", score=500)]),
    )
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
    assert res["status"] == "ok"  # partial success
    data = json.loads(out.read_text())
    titles = [i["title"] for i in data["items"]]
    assert "good" in titles
    assert res["failed_subreddits"] == ["BadSub"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/skills/test_reddit_fetch.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `skills/reddit-researcher/SKILL.md`**

```markdown
---
name: reddit-researcher
description: Fetch top posts from configured AI-focused subreddits for a topic, filter by score, and combine into a single result set. Uses Reddit app-only OAuth.
---

# reddit-researcher

## Inputs

```json
{
  "subreddits": ["ChatGPT", "OpenAI", "LocalLLaMA"],
  "min_score": 100,
  "time_filter": "week",
  "top_per_sub": 5,
  "client_id_ref": "secret:reddit_client_id",
  "client_secret_ref": "secret:reddit_client_secret",
  "user_agent": "autofanpage/0.1 (by /u/yourname)",
  "out_path": "/path/to/run_dir/reddit_results.json"
}
```

## Output

Writes `reddit_results.json` matching `REDDIT_RESULTS_SCHEMA`. Items from all subreddits are flattened into one `items` list (sorted by score descending per subreddit, concatenated).

On subreddit-level failure (HTTP 5xx after retries, 403 private sub, 404 banned) the skill continues with the remaining subreddits and reports `failed_subreddits` in its return value. The source as a whole only fails if the OAuth token fetch fails or every subreddit fails.

## Failure modes

- OAuth 401 → `SourceFailedError` (bad credentials).
- Single subreddit 403/404/5xx → logged, skipped, others continue.
- All subreddits fail → `SourceFailedError`.
```

- [ ] **Step 4: Write `skills/reddit-researcher/scripts/__init__.py`** — empty.

- [ ] **Step 5: Write `skills/reddit-researcher/scripts/fetch_reddit.py`**

```python
"""Reddit-researcher skill script.

Authenticates with Reddit app-only OAuth, fetches top posts of the
configured time window from each requested subreddit, filters by score
and post quality, and writes ``reddit_results.json``. Continues on
single-subreddit failures (the list is still useful with 7/8 working).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

from autofanpage.errors import SourceFailedError  # noqa: E402
from autofanpage.http import get_json  # noqa: E402
from autofanpage.profile import load_profile  # noqa: E402
from autofanpage.schemas import validate  # noqa: E402
from autofanpage.secrets import get_secret  # noqa: E402
from autofanpage.sources.reddit import filter_and_rank, to_result  # noqa: E402
from autofanpage.sources.reddit_auth import get_app_token  # noqa: E402


def run(
    *,
    subreddits: list[str],
    min_score: int,
    time_filter: str,
    top_per_sub: int,
    client_id_ref: str,
    client_secret_ref: str,
    user_agent: str,
    out_path: str,
) -> dict:
    client_id = get_secret(client_id_ref)
    client_secret = get_secret(client_secret_ref)
    token = get_app_token(client_id, client_secret, user_agent=user_agent)

    all_items: list[dict] = []
    failed: list[str] = []

    for sub in subreddits:
        try:
            listing = get_json(
                f"https://oauth.reddit.com/r/{sub}/top",
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": user_agent,
                },
                params={"t": time_filter, "limit": max(top_per_sub * 3, 25)},
            )
        except SourceFailedError:
            failed.append(sub)
            continue
        kept = filter_and_rank(listing, min_score=min_score, top_n=top_per_sub)
        all_items.extend(to_result(p) for p in kept)

    if subreddits and len(failed) == len(subreddits):
        raise SourceFailedError(f"All subreddits failed: {failed}")

    doc = {
        "source": "reddit",
        "fetched_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "items": all_items,
    }
    validate("reddit_results", doc)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    return {
        "status": "ok",
        "artifact": out_path,
        "count": len(all_items),
        "failed_subreddits": failed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--profile", required=True)
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    cfg = profile.sources.get("reddit", {})
    if not cfg.get("enabled", False):
        Path(args.run_dir, "reddit_results.json").write_text(
            json.dumps({"source": "reddit",
                        "fetched_at": datetime.now(timezone.utc).astimezone().isoformat(),
                        "items": []}, ensure_ascii=False),
        )
        print(json.dumps({"status": "ok", "skipped": True, "count": 0}))
        return 0

    out_path = str(Path(args.run_dir) / "reddit_results.json")
    result = run(
        subreddits=cfg["subreddits"],
        min_score=cfg.get("min_score", 100),
        time_filter=cfg.get("time_filter", "week"),
        top_per_sub=cfg.get("top_per_sub", 5),
        client_id_ref="secret:reddit_client_id",
        client_secret_ref="secret:reddit_client_secret",
        user_agent=f"autofanpage/0.1 (profile={profile.name})",
        out_path=out_path,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run to verify it passes**

Run: `pytest tests/skills/test_reddit_fetch.py -v`
Expected: `2 passed`.

- [ ] **Step 7: Commit**

```bash
git add skills/reddit-researcher/ tests/skills/test_reddit_fetch.py
git commit -m "feat(skills): reddit-researcher multi-subreddit fetch"
```

---

### Task 10: Merge sources pure function

**Files:**
- Create: `autofanpage/merge.py`
- Test: `tests/test_merge.py`

The merger pulls each per-source JSON artifact off disk, extracts URLs into the spec-mandated shape (`url`, `title`, `platform`, `score_or_views`, `created_at`), deduplicates by canonical URL, caps at `max_per_platform` per source (default 12, so ≤48 total — under NotebookLM's 50-source limit), and emits `merged_sources.json` with `{ urls, counts_per_platform }`. This artifact is what Phase 2 (NotebookLM) and the Telegram reporter consume.

- [ ] **Step 1: Write failing test `tests/test_merge.py`**

```python
import json
import pytest

from autofanpage.merge import merge_sources


@pytest.fixture
def run_dir(tmp_path):
    # synthesize per-source artifacts
    (tmp_path / "youtube_results.json").write_text(json.dumps({
        "source": "youtube",
        "fetched_at": "2026-04-15T06:00:00+07:00",
        "items": [{
            "title": "yt1", "url": "https://youtu.be/1", "video_id": "1",
            "channel": "c", "views": 150000, "subscribers": 20000,
            "published_at": "2026-04-10T00:00:00Z",
        }],
    }))
    (tmp_path / "hackernews_results.json").write_text(json.dumps({
        "source": "hackernews",
        "fetched_at": "2026-04-15T06:00:00+07:00",
        "items": [{
            "title": "hn1", "url": "https://hn1",
            "points": 300, "by": "u", "descendants": 40,
            "created_at": "2026-04-14T00:00:00Z",
            "hn_url": "https://news.ycombinator.com/item?id=1",
        }],
    }))
    (tmp_path / "perplexity_results.json").write_text(json.dumps({
        "source": "perplexity",
        "fetched_at": "2026-04-15T06:00:00+07:00",
        "news": [{"title": "n1", "url": "https://n1", "summary": "", "source": "n.com"}],
        "reports": [{"title": "r1", "url": "https://r1", "summary": "", "source": "r.com"}],
        "twitter": [{"title": "t1", "url": "https://x.com/u/1", "summary": "", "source": "x.com"}],
    }))
    (tmp_path / "reddit_results.json").write_text(json.dumps({
        "source": "reddit",
        "fetched_at": "2026-04-15T06:00:00+07:00",
        "items": [{
            "title": "rd1", "url": "https://reddit.com/r/x/comments/1",
            "subreddit": "ChatGPT", "score": 800, "num_comments": 50,
            "author": "u", "permalink": "/r/x/1", "created_at": "2026-04-14T00:00:00Z",
            "is_self": False, "external_url": "",
        }],
    }))
    return tmp_path


def test_merge_combines_all_sources(run_dir):
    out = merge_sources(
        profile="page_vn_ai", topic="AI", language="vi",
        artifacts={
            "youtube": run_dir / "youtube_results.json",
            "hackernews": run_dir / "hackernews_results.json",
            "perplexity": run_dir / "perplexity_results.json",
            "reddit": run_dir / "reddit_results.json",
        },
        failures={},
        max_per_platform=12,
    )
    platforms_in_urls = {u["platform"] for u in out["urls"]}
    assert "youtube" in platforms_in_urls
    assert "hackernews" in platforms_in_urls
    assert "reddit" in platforms_in_urls
    assert "perplexity" in platforms_in_urls
    assert out["sources_succeeded"] == [
        "youtube", "hackernews", "perplexity", "reddit",
    ]
    assert out["sources_failed"] == []
    assert out["counts_per_platform"] == {
        "youtube": 1, "hackernews": 1, "perplexity": 3, "reddit": 1,
    }
    assert len(out["urls"]) == 6  # 1+1+3+1


def test_merge_records_failures(run_dir):
    out = merge_sources(
        profile="p", topic="T", language="vi",
        artifacts={"youtube": run_dir / "youtube_results.json"},
        failures={"reddit": "timeout after 3 retries"},
        max_per_platform=12,
    )
    assert out["sources_succeeded"] == ["youtube"]
    assert out["sources_failed"] == [{"source": "reddit", "error": "timeout after 3 retries"}]


def test_merge_uses_score_field_uniformly(run_dir):
    out = merge_sources(
        profile="p", topic="T", language="vi",
        artifacts={
            "youtube": run_dir / "youtube_results.json",
            "hackernews": run_dir / "hackernews_results.json",
            "reddit": run_dir / "reddit_results.json",
        },
        failures={},
        max_per_platform=12,
    )
    by_plat = {u["platform"]: u for u in out["urls"]}
    assert by_plat["youtube"]["score_or_views"] == 150000   # views
    assert by_plat["hackernews"]["score_or_views"] == 300   # points
    assert by_plat["reddit"]["score_or_views"] == 800       # upvotes


def test_merge_deduplicates_by_url(run_dir):
    """Same URL appearing in two sources should only appear once."""
    (run_dir / "hackernews_results.json").write_text(json.dumps({
        "source": "hackernews",
        "fetched_at": "2026-04-15T06:00:00+07:00",
        "items": [{
            "title": "same as yt1", "url": "https://youtu.be/1",
            "points": 500, "by": "u", "descendants": 10,
            "created_at": "2026-04-14T00:00:00Z",
            "hn_url": "https://news.ycombinator.com/item?id=2",
        }],
    }))
    out = merge_sources(
        profile="p", topic="T", language="vi",
        artifacts={
            "youtube": run_dir / "youtube_results.json",
            "hackernews": run_dir / "hackernews_results.json",
        },
        failures={},
        max_per_platform=12,
    )
    urls = [u["url"] for u in out["urls"]]
    assert urls.count("https://youtu.be/1") == 1  # deduplicated


def test_merge_caps_per_platform(run_dir):
    """With max_per_platform=1, only 1 URL per platform survives."""
    (run_dir / "youtube_results.json").write_text(json.dumps({
        "source": "youtube",
        "fetched_at": "2026-04-15T06:00:00+07:00",
        "items": [
            {"title": f"yt{i}", "url": f"https://youtu.be/{i}", "video_id": str(i),
             "channel": "c", "views": 200000 - i * 1000, "subscribers": 10000,
             "published_at": "2026-04-10T00:00:00Z"}
            for i in range(5)
        ],
    }))
    out = merge_sources(
        profile="p", topic="T", language="vi",
        artifacts={"youtube": run_dir / "youtube_results.json"},
        failures={},
        max_per_platform=1,
    )
    assert out["counts_per_platform"]["youtube"] == 1
    assert len(out["urls"]) == 1
    assert out["urls"][0]["score_or_views"] == 200000  # highest score kept
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_merge.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `autofanpage/merge.py`**

```python
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
    """Strip fragment for dedup comparison."""
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
    """Merge per-source artifacts into a deduplicated, capped URL list."""
    seen_urls: set[str] = set()
    urls: list[dict] = []
    counts: Counter[str] = Counter()
    succeeded: list[str] = []

    for source, path in artifacts.items():
        extractor = _EXTRACTORS.get(source)
        if not extractor:
            raise ValueError(f"Unknown source: {source}")
        raw = extractor(_load(path))
        # Sort by score descending so cap keeps top items
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_merge.py -v`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add autofanpage/merge.py tests/test_merge.py
git commit -m "feat(merge): combine per-source artifacts into merged_sources.json"
```

---

### Task 11: Orchestrator — parallel dispatch + merge

**Files:**
- Modify: `skills/daily-content-pipeline/scripts/orchestrate.py`
- Modify: `skills/daily-content-pipeline/SKILL.md` (append a "Plan 2" section)

The Plan 1 orchestrator called one source (Hacker News) then the Telegram reporter. Plan 2 upgrades it to dispatch all four enabled researchers in parallel via `ThreadPoolExecutor`, collect results and failures, merge them via `autofanpage.merge`, apply the `min_posts_required` rule, and include source counts in the success/error Telegram payload. **CLI surface (`--page --profile-path --base-dir --date`), `_report` helper, and `LastSuccess` / `RunDir` constructor signatures stay identical to Plan 1.**

- [ ] **Step 1: Read current orchestrator**

Run: `cat skills/daily-content-pipeline/scripts/orchestrate.py`

Confirm Plan 1's layout: argparse → profile load → date resolve → idempotency (`info` report + return 0 if already ran) → `RunDir.create` → call `hackernews-researcher` → `state.mark` → `_report(status="success", ...)` → error branches. Our edits add a new `_dispatch_phase1` step between "create run_dir" and "mark success", and adjust the success/error payload details to include `counts` and `failed_sources`.

- [ ] **Step 2: Replace `orchestrate.py` content (full file)**

```python
"""Orchestrator entry point for the AutoFanpage daily pipeline.

Plan 2: calls every enabled Phase-1 researcher in parallel, merges their
artifacts, enforces ``min_posts_required``, then calls telegram-reporter.
Plans 3/4 will add NotebookLM, writing, and publishing.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

from autofanpage.dispatch import run_skill  # noqa: E402
from autofanpage.errors import (  # noqa: E402
    AutofanpageError, SkillInvocationError, SourceFailedError,
)
from autofanpage.merge import merge_sources  # noqa: E402
from autofanpage.profile import load_profile  # noqa: E402
from autofanpage.run_dir import RunDir  # noqa: E402
from autofanpage.state import LastSuccess  # noqa: E402


# Profile source-key -> skill-name. Order defines orchestrator log order.
SOURCE_SKILLS = {
    "youtube": "youtube-researcher",
    "perplexity": "perplexity-researcher",
    "reddit": "reddit-researcher",
    "hackernews": "hackernews-researcher",
}

# Profile source-key -> artifact file name (read by merge step).
SOURCE_ARTIFACTS = {
    "youtube": "youtube_results.json",
    "perplexity": "perplexity_results.json",
    "reddit": "reddit_results.json",
    "hackernews": "hackernews_results.json",
}


def _report(run_dir: Path, *, status: str, page: str, details: dict) -> None:
    """Fire-and-forget call to telegram-reporter (same contract as Plan 1)."""
    try:
        run_skill("telegram-reporter", {
            "run_dir": str(run_dir),
            "status": status,
            "page": page,
            "details": details,
        })
    except SkillInvocationError as e:
        sys.stderr.write(f"[orchestrate] telegram-reporter failed: {e}\n")


def _today(profile_tz: str) -> str:
    return datetime.now(tz=ZoneInfo(profile_tz)).strftime("%Y-%m-%d")


def _enabled_sources(profile) -> list[str]:
    return [
        key for key in SOURCE_SKILLS
        if profile.sources.get(key, {}).get("enabled", False)
    ]


def _invoke(
    key: str, skill_name: str, run_dir: Path, profile_path: str,
) -> tuple[str, str | None, dict | None]:
    try:
        result = run_skill(skill_name, {
            "run_dir": str(run_dir),
            "profile": profile_path,
        })
        return key, None, result
    except (SourceFailedError, SkillInvocationError) as e:
        return key, str(e), None


def _dispatch_phase1(
    run_dir: RunDir, profile, profile_path: str,
) -> tuple[dict[str, Path], dict[str, str]]:
    """Run enabled sources in parallel. Returns (artifacts, failures)."""
    enabled = _enabled_sources(profile)
    run_dir.log(f"phase1 enabled sources: {enabled}")

    artifacts: dict[str, Path] = {}
    failures: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=len(enabled) or 1) as pool:
        futures = [
            pool.submit(_invoke, key, SOURCE_SKILLS[key], run_dir.path, profile_path)
            for key in enabled
        ]
        for fut in as_completed(futures):
            key, err, _result = fut.result()
            if err:
                run_dir.log(f"[source:{key}] FAILED: {err}")
                failures[key] = err
                continue
            artifact_path = run_dir.path / SOURCE_ARTIFACTS[key]
            if not artifact_path.exists():
                run_dir.log(
                    f"[source:{key}] skill reported ok but {SOURCE_ARTIFACTS[key]} missing"
                )
                failures[key] = f"artifact missing: {SOURCE_ARTIFACTS[key]}"
                continue
            run_dir.log(f"[source:{key}] ok artifact={artifact_path}")
            artifacts[key] = artifact_path
    return artifacts, failures


def _phase1_counts(merged: dict) -> dict[str, int]:
    return merged["counts_per_platform"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", required=True)
    parser.add_argument("--profile-path", required=True)
    parser.add_argument("--base-dir", required=True)
    parser.add_argument("--date", default=None)
    args = parser.parse_args(argv)

    base = Path(args.base_dir)
    profile = load_profile(args.profile_path)
    date = args.date or _today(profile.timezone)

    state = LastSuccess(base=base, page=args.page)
    if state.ran_on(date):
        run_dir = RunDir.create(base=base, page=args.page, date=date)
        _report(run_dir.path, status="info", page=args.page,
                details={"message": f"already ran on {date}"})
        return 0

    run_dir = RunDir.create(base=base, page=args.page, date=date)
    run_dir.log(f"orchestrator start page={args.page} date={date} topic={profile.topic}")
    started = time.monotonic()

    try:
        artifacts, failures = _dispatch_phase1(run_dir, profile, args.profile_path)

        if len(artifacts) < profile.min_posts_required:
            cause = (
                f"Only {len(artifacts)} source(s) succeeded "
                f"(need >= {profile.min_posts_required}). Failures: {failures}"
            )
            run_dir.log(f"ABORT: {cause}")
            log_tail = "\n".join(run_dir.log_path.read_text().splitlines()[-20:])
            _report(run_dir.path, status="error", page=args.page, details={
                "phase": "phase1-data-gathering",
                "cause": cause,
                "log_tail": log_tail,
            })
            return 1

        merged = merge_sources(
            profile=profile.name,
            topic=profile.topic,
            language=profile.language,
            artifacts=artifacts,
            failures=failures,
            max_per_platform=getattr(profile, "max_sources_per_platform", 12),
        )
        run_dir.write_json("merged_sources", merged)
        counts = _phase1_counts(merged)
        run_dir.log(f"merged counts={counts} failed={list(failures)}")

        # Guard: refuse to mark success when the merged URL set is empty.
        # Sources can return status=ok with items=[] (e.g. YouTube empty
        # search, Perplexity malformed completion), so artifact count alone
        # is not enough — we must verify actual content after merge.
        total_urls = len(merged["urls"])
        if total_urls == 0:
            cause = (
                f"All {len(artifacts)} source(s) returned empty results. "
                f"merged urls=0. Failures: {failures}"
            )
            run_dir.log(f"ABORT: {cause}")
            log_tail = "\n".join(run_dir.log_path.read_text().splitlines()[-20:])
            _report(run_dir.path, status="error", page=args.page, details={
                "phase": "phase1-data-gathering",
                "cause": cause,
                "log_tail": log_tail,
            })
            return 1

        elapsed = int(time.monotonic() - started)
        posts_scheduled = 0  # still no publishing in Plan 2
        state.mark(
            date=date, run_dir=str(run_dir.path),
            posts_scheduled=posts_scheduled,
        )
        _report(run_dir.path, status="success", page=args.page, details={
            "date": date,
            "posts_scheduled": posts_scheduled,
            "elapsed_sec": elapsed,
            "phase1_counts": counts,
            "phase1_failed_sources": list(failures),
        })
        return 0

    except AutofanpageError as e:
        run_dir.log(f"ERROR: {e}")
        log_tail = "\n".join(run_dir.log_path.read_text().splitlines()[-20:])
        _report(run_dir.path, status="error", page=args.page, details={
            "phase": "orchestrator",
            "cause": str(e),
            "log_tail": log_tail,
        })
        return 1
    except Exception as e:  # noqa: BLE001
        run_dir.log(f"UNEXPECTED: {type(e).__name__}: {e}")
        log_tail = "\n".join(run_dir.log_path.read_text().splitlines()[-20:])
        _report(run_dir.path, status="error", page=args.page, details={
            "phase": "orchestrator",
            "cause": f"{type(e).__name__}: {e}",
            "log_tail": log_tail,
        })
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Update the `telegram-reporter` success template to render new keys**

Open `autofanpage/telegram.py`. The existing `status == "success"` branch renders `posts_scheduled`, `date`, `elapsed_sec`. Extend it to render `phase1_counts` and `phase1_failed_sources` when present (Plan 2 emits them; Plan 1 did not). Both are optional in the template — if the caller omits them (Plan 1 style), the output is unchanged.

Replace the `if status == "success":` block with:

```python
    if status == "success":
        lines = [
            header,
            f"📝 {details['posts_scheduled']} posts scheduled",
            f"📅 {details['date']}",
            f"⏱ {details['elapsed_sec']}s",
        ]
        counts = details.get("phase1_counts")
        if counts:
            parts = ", ".join(f"{k}={v}" for k, v in counts.items())
            lines.append(f"🔎 sources: {parts}")
        failed = details.get("phase1_failed_sources") or []
        if failed:
            lines.append(f"⚠️ failed: {', '.join(failed)}")
```

Add a failing test in `tests/test_telegram.py`:

```python
def test_success_template_includes_phase1_counts():
    msg = format_message(
        status="success", page="p",
        details={
            "date": "2026-04-15", "posts_scheduled": 0, "elapsed_sec": 12,
            "phase1_counts": {"youtube": 3, "hackernews": 5},
            "phase1_failed_sources": ["reddit"],
        },
    )
    assert "sources: youtube=3, hackernews=5" in msg
    assert "failed: reddit" in msg


def test_success_template_without_phase1_keys_is_backward_compatible():
    msg = format_message(
        status="success", page="p",
        details={"date": "2026-04-15", "posts_scheduled": 4, "elapsed_sec": 12},
    )
    assert "sources:" not in msg
    assert "failed:" not in msg
```

Run `pytest tests/test_telegram.py -v`. Expected: existing tests still pass + 2 new ones pass.

- [ ] **Step 4: Append a "Plan 2" section to `skills/daily-content-pipeline/SKILL.md`**

```markdown
## Flow (Plan 2 additions)

After the Plan 1 "load profile / check idempotency / create run_dir" steps,
the orchestrator now:

1. Computes `enabled = [k for k in SOURCE_SKILLS if profile.sources[k].enabled]`.
2. Dispatches every enabled skill in parallel via
   `ThreadPoolExecutor(max_workers=len(enabled))`, each with
   `{"run_dir": <path>, "profile": <profile path>}`.
3. Collects per-source successes (artifact file on disk) and failures
   (exception message).
4. If `len(artifacts) < profile.min_posts_required`, emits a
   `telegram-reporter` call with `status="error"` and returns exit code 1
   **without** marking `last_success.json` — so a retry that same day
   is possible.
5. Otherwise merges artifacts into `<run_dir>/merged_sources.json` via
   `autofanpage.merge.merge_sources` — the merge deduplicates by URL and
   caps at `max_sources_per_platform` per platform (default 12, ≤48 total).
6. If the merged URL list is empty (all sources returned ok but with no
   items), aborts with `status="error"` **without** marking
   `last_success.json` — same-day retry stays possible.
7. Marks success, then emits `status="success"` to telegram-reporter
   with new fields `phase1_counts` and `phase1_failed_sources`.

`merged_sources.json` is the artifact consumed by Phase 2 (NotebookLM)
in Plan 3. Its shape follows the spec: `{ urls, counts_per_platform }`.
```

- [ ] **Step 5: Commit**

```bash
git add skills/daily-content-pipeline/ autofanpage/telegram.py tests/test_telegram.py
git commit -m "feat(orchestrator): parallel dispatch + merge for 4 sources"
```

---

### Task 12: Orchestrator integration test (parallel dispatch + merge + partial failure)

**Files:**
- Create: `tests/skills/test_orchestrator_plan2.py`
- Fixture: `tests/fixtures/profile_plan2.json`

- [ ] **Step 1: Create fixture `tests/fixtures/profile_plan2.json`**

```json
{
  "name": "page_test",
  "page_id": "123",
  "access_token_ref": "secret:fb_page_test",
  "topic": "AI automation",
  "language": "vi",
  "post_times": ["08:00", "12:00", "16:00", "20:00"],
  "timezone": "Asia/Ho_Chi_Minh",
  "filters": {"youtube_min_views": 100000, "youtube_min_subs": 10000},
  "min_posts_required": 2,
  "max_sources_per_platform": 12,
  "sources": {
    "youtube":    {"enabled": true},
    "perplexity": {"enabled": true},
    "twitter_via_perplexity": {"enabled": false},
    "reddit":     {"enabled": true, "subreddits": ["ChatGPT"],
                   "min_score": 100, "time_filter": "week", "top_per_sub": 5},
    "hackernews": {"enabled": true, "min_points": 50}
  }
}
```

- [ ] **Step 2: Write failing integration test**

The tests drive the same CLI entry point the OpenClaw runtime uses: `orchestrate.main(argv)` with `--page --profile-path --base-dir --date`. We stub `run_skill` to (a) write the correct per-source artifact to disk when called with a researcher name, (b) record the call when called with `telegram-reporter`. This matches the Plan 1 integration-test shape (`tests/skills/test_orchestrator.py`).

`tests/skills/test_orchestrator_plan2.py`:

```python
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "daily-content-pipeline" / "scripts"
sys.path.insert(0, str(SCRIPT))
import orchestrate  # noqa: E402


@pytest.fixture
def env(tmp_path, fixtures_dir):
    return {
        "base": tmp_path,
        "profile": fixtures_dir / "profile_plan2.json",
        "page": "page_test",
    }


def _fake_factory(failing: set[str]):
    """Return a fake ``run_skill`` plus a call recorder.

    When called as a researcher it writes a minimal-valid artifact into
    ``args['run_dir']``; when called as telegram-reporter it just records.
    """
    calls: list[tuple[str, dict]] = []

    artifacts: dict[str, dict] = {
        "youtube": {
            "source": "youtube",
            "fetched_at": "2026-04-15T06:00:00+07:00",
            "items": [{"title": "yt", "url": "https://y/1", "video_id": "1",
                       "channel": "c", "views": 200000, "subscribers": 30000,
                       "published_at": "2026-04-10T00:00:00Z"}],
        },
        "perplexity": {
            "source": "perplexity",
            "fetched_at": "2026-04-15T06:00:00+07:00",
            "news": [{"title": "n", "url": "https://n/1", "summary": "",
                      "source": "n.com"}],
            "reports": [], "twitter": [],
        },
        "reddit": {
            "source": "reddit",
            "fetched_at": "2026-04-15T06:00:00+07:00",
            "items": [{"title": "r", "url": "https://r/1",
                       "subreddit": "ChatGPT", "score": 500,
                       "num_comments": 30, "author": "u",
                       "permalink": "/r/1",
                       "created_at": "2026-04-14T00:00:00Z",
                       "is_self": False, "external_url": ""}],
        },
        "hackernews": {
            "source": "hackernews",
            "fetched_at": "2026-04-15T06:00:00+07:00",
            "items": [{"title": "hn", "url": "https://h/1",
                       "points": 300, "by": "u", "descendants": 10,
                       "created_at": "2026-04-14T00:00:00Z",
                       "hn_url": "https://news.ycombinator.com/item?id=1"}],
        },
    }

    def fake(name: str, args: dict):
        calls.append((name, args))
        if name == "telegram-reporter":
            return {"status": "ok", "sent": True}
        # researcher skill
        key = name.replace("-researcher", "")
        if key in failing:
            from autofanpage.errors import SourceFailedError
            raise SourceFailedError(f"fake fail for {key}")
        run_dir = Path(args["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)
        artifact_name = orchestrate.SOURCE_ARTIFACTS[key]
        (run_dir / artifact_name).write_text(
            json.dumps(artifacts[key]), encoding="utf-8",
        )
        return {"status": "ok", "artifact": str(run_dir / artifact_name)}

    return fake, calls


def _run(env, argv_date="2026-04-15"):
    return orchestrate.main([
        "--page", env["page"],
        "--profile-path", str(env["profile"]),
        "--base-dir", str(env["base"]),
        "--date", argv_date,
    ])


def test_happy_path_dispatches_all_4_sources(env, mocker):
    fake, calls = _fake_factory(failing=set())
    mocker.patch("orchestrate.run_skill", side_effect=fake)

    exit_code = _run(env)
    assert exit_code == 0

    names = [c[0] for c in calls]
    for expected in ("youtube-researcher", "perplexity-researcher",
                     "reddit-researcher", "hackernews-researcher"):
        assert expected in names
    assert names.count("telegram-reporter") == 1

    # success report payload includes phase1_counts and empty failed list
    tg = next(c for c in calls if c[0] == "telegram-reporter")
    assert tg[1]["status"] == "success"
    details = tg[1]["details"]
    assert details["phase1_counts"]["youtube"] == 1
    assert details["phase1_counts"]["hackernews"] == 1
    assert details["phase1_failed_sources"] == []

    # last_success recorded
    from autofanpage.state import LastSuccess
    assert LastSuccess(base=env["base"], page=env["page"]).ran_on("2026-04-15")

    # merged_sources.json written with spec-mandated shape
    merged_path = env["base"] / "runs" / env["page"] / "2026-04-15" / "merged_sources.json"
    merged = json.loads(merged_path.read_text())
    assert set(merged["sources_succeeded"]) == {"youtube", "perplexity", "reddit", "hackernews"}
    assert merged["sources_failed"] == []
    assert "urls" in merged and "counts_per_platform" in merged
    assert len(merged["urls"]) == sum(merged["counts_per_platform"].values())


def test_partial_failure_still_succeeds(env, mocker):
    # reddit fails, 3 others ok. min_posts_required=2 → proceed.
    fake, calls = _fake_factory(failing={"reddit"})
    mocker.patch("orchestrate.run_skill", side_effect=fake)

    exit_code = _run(env)
    assert exit_code == 0

    tg = next(c for c in calls if c[0] == "telegram-reporter")
    assert tg[1]["status"] == "success"
    assert tg[1]["details"]["phase1_failed_sources"] == ["reddit"]

    merged_path = env["base"] / "runs" / env["page"] / "2026-04-15" / "merged_sources.json"
    merged = json.loads(merged_path.read_text())
    assert "reddit" not in merged["sources_succeeded"]
    assert any(f["source"] == "reddit" for f in merged["sources_failed"])


def test_below_min_required_reports_error_and_does_not_mark(env, mocker):
    # 3 of 4 fail → only 1 ok, below min=2
    fake, calls = _fake_factory(
        failing={"youtube", "perplexity", "reddit"},
    )
    mocker.patch("orchestrate.run_skill", side_effect=fake)

    exit_code = _run(env)
    assert exit_code == 1

    # telegram-reporter called once with status=error
    err_calls = [c for c in calls if c[0] == "telegram-reporter"]
    assert len(err_calls) == 1
    assert err_calls[0][1]["status"] == "error"
    assert err_calls[0][1]["details"]["phase"] == "phase1-data-gathering"

    # last_success NOT written — tomorrow the next retry can proceed.
    from autofanpage.state import LastSuccess
    assert not LastSuccess(base=env["base"], page=env["page"]).ran_on("2026-04-15")


def test_idempotent_second_run_emits_info(env, mocker):
    fake, calls = _fake_factory(failing=set())
    mocker.patch("orchestrate.run_skill", side_effect=fake)

    assert _run(env) == 0
    calls.clear()
    assert _run(env) == 0

    # Only a single info Telegram message on the second run.
    assert len(calls) == 1
    assert calls[0][0] == "telegram-reporter"
    assert calls[0][1]["status"] == "info"


def test_empty_items_aborts_and_does_not_mark(env, mocker):
    """All sources return ok but with empty items — must NOT mark success."""
    calls: list[tuple[str, dict]] = []
    empty_artifacts: dict[str, dict] = {
        "youtube": {
            "source": "youtube",
            "fetched_at": "2026-04-15T06:00:00+07:00",
            "items": [],
        },
        "perplexity": {
            "source": "perplexity",
            "fetched_at": "2026-04-15T06:00:00+07:00",
            "news": [], "reports": [], "twitter": [],
        },
        "reddit": {
            "source": "reddit",
            "fetched_at": "2026-04-15T06:00:00+07:00",
            "items": [],
        },
        "hackernews": {
            "source": "hackernews",
            "fetched_at": "2026-04-15T06:00:00+07:00",
            "items": [],
        },
    }

    def fake(skill_name, args):
        calls.append((skill_name, args))
        if skill_name == "telegram-reporter":
            return {"status": "ok"}
        source = skill_name.replace("-researcher", "")
        art_path = args["run_dir"] / f"{source}_results.json"
        import json as _json
        art_path.write_text(_json.dumps(empty_artifacts[source]))
        return {"status": "ok", "artifact": str(art_path)}

    mocker.patch("orchestrate.run_skill", side_effect=fake)

    exit_code = _run(env)
    assert exit_code == 1

    # Error reported to Telegram
    err_calls = [c for c in calls if c[0] == "telegram-reporter"]
    assert len(err_calls) == 1
    assert err_calls[0][1]["status"] == "error"
    assert "urls=0" in err_calls[0][1]["details"]["cause"]

    # last_success NOT written — same-day retry stays possible
    from autofanpage.state import LastSuccess
    assert not LastSuccess(base=env["base"], page=env["page"]).ran_on("2026-04-15")
```

- [ ] **Step 3: Run to verify it fails / pass**

Run: `pytest tests/skills/test_orchestrator_plan2.py -v`
Expected after Task 11 commit: `5 passed`. If any test fails, investigate:
- Import error on `orchestrate` → ensure Task 11 committed the new file.
- `ThreadPoolExecutor(max_workers=0)` when `enabled == []` → the `or 1` guard handles it; if still failing, check that the fixture has at least one source enabled.
- Test ordering leaking state → each test uses a fresh `tmp_path`, so `LastSuccess(base=tmp_path, ...)` reads from a clean directory.

- [ ] **Step 4: Commit**

```bash
git add tests/skills/test_orchestrator_plan2.py tests/fixtures/profile_plan2.json
git commit -m "test(orchestrator): parallel dispatch + merge + partial failure"
```

---

### Task 13: Update install script

**Files:**
- Modify: `scripts/install-skills.sh`

- [ ] **Step 1: Read current script**

Run: `cat scripts/install-skills.sh` — confirm it iterates `skills/*` already. If yes, the script works for the new skills unchanged because they're new directories under `skills/`. If not (e.g., it lists skill names explicitly), edit it.

- [ ] **Step 2: Ensure glob-based copy**

Expected body (rewrite if different):

```bash
#!/usr/bin/env bash
set -euo pipefail
DEST="${HOME}/.openclaw/skills/autofanpage"
mkdir -p "$DEST"
for d in skills/*/; do
    name=$(basename "$d")
    rm -rf "$DEST/$name"
    cp -R "$d" "$DEST/$name"
    echo "installed: $name"
done
```

- [ ] **Step 3: Dry-run (list expected output)**

Run: `bash scripts/install-skills.sh`
Expected stdout lines: `installed: daily-content-pipeline`, `installed: hackernews-researcher`, `installed: perplexity-researcher`, `installed: reddit-researcher`, `installed: telegram-reporter`, `installed: youtube-researcher`.

- [ ] **Step 4: Commit (if changed)**

```bash
git add scripts/install-skills.sh
git commit -m "chore(install): ensure glob install picks up new source skills"
```

---

### Task 14: Manual smoke test documentation

**Files:**
- Modify: `README.md` (append a Plan 2 smoke-test section)

- [ ] **Step 1: Append to `README.md`**

```markdown
## Smoke test — Plan 2 (Phase 1 data gathering)

After `pip install -e ".[dev]"` and `bash scripts/install-skills.sh`:

### 1. Configure secrets in OpenClaw

```bash
openclaw secrets set youtube_api_key              # Google Cloud API key
openclaw secrets set perplexity_api_key           # pplx-...
openclaw secrets set reddit_client_id             # Reddit app id
openclaw secrets set reddit_client_secret         # Reddit app secret
openclaw secrets set telegram_bot_token           # already set in Plan 1
openclaw secrets set telegram_chat_id             # already set in Plan 1
```

### 2. Create a test profile

Save as `profiles/page_smoketest.json`:

```json
{
  "name": "page_smoketest",
  "page_id": "0",
  "access_token_ref": "secret:fb_page_smoketest",
  "topic": "AI automation business",
  "language": "vi",
  "post_times": ["08:00", "12:00", "16:00", "20:00"],
  "timezone": "Asia/Ho_Chi_Minh",
  "filters": {"youtube_min_views": 50000, "youtube_min_subs": 5000},
  "min_posts_required": 2,
  "max_sources_per_platform": 12,
  "sources": {
    "youtube":    {"enabled": true},
    "perplexity": {"enabled": true},
    "twitter_via_perplexity": {"enabled": true},
    "reddit":     {"enabled": true,
                   "subreddits": ["ChatGPT","ArtificialIntelligence","OpenAI","LocalLLaMA"],
                   "min_score": 100, "time_filter": "week", "top_per_sub": 5},
    "hackernews": {"enabled": true, "min_points": 50}
  }
}
```

### 3. Run orchestrator directly

```bash
openclaw skills run daily-content-pipeline -- \
    --page page_smoketest \
    --profile-path ./profiles/page_smoketest.json \
    --base-dir ~/.openclaw/autofanpage \
    --date "$(date +%F)"
```

Expected:
- Exit code 0.
- Under `~/.openclaw/autofanpage/runs/page_smoketest/<date>/`:
  - `youtube_results.json`, `perplexity_results.json`, `reddit_results.json`, `hackernews_results.json`, `merged_sources.json`, `run.log`, `telegram_sent.log`.
- Telegram channel: one `✅ AutoFanpage [page_smoketest]` message including
  `🔎 sources: youtube=N, perplexity_news=N, reddit=N, hackernews=N` and (if any failed) `⚠️ failed: ...`.

### 4. Failure-mode check — force `min_posts_required` abort

Flip 3 of the 4 `enabled: true` to `false` in the profile so only 1 source runs; re-run.

Expected:
- Exit code 1.
- `last_success.json` for `page_smoketest` is NOT updated (same-day retry stays possible).
- Telegram channel: one `🚨 AutoFanpage [page_smoketest]` message with
  `Phase: phase1-data-gathering` and `Cause: Only 1 source(s) succeeded (need >= 2). Failures: {...}`.

Reset the profile after.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: Plan 2 smoke test instructions"
```

---

### Task 15: Full test suite green + coverage floor

**Files:**
- None new. Just verify the suite.

- [ ] **Step 1: Run the full suite**

Run: `pytest -v`
Expected: all Plan 1 tests still pass + all Plan 2 tests pass. Count: roughly 35–40 tests total.

- [ ] **Step 2: Check coverage of new modules**

Run: `pytest --cov=autofanpage --cov-report=term-missing`
Expected: coverage for `autofanpage/http.py`, `autofanpage/sources/youtube.py`, `autofanpage/sources/perplexity.py`, `autofanpage/sources/reddit.py`, `autofanpage/sources/reddit_auth.py`, `autofanpage/merge.py` each at ≥ 85%. `skills/*/scripts/fetch_*.py` are exercised by the integration tests but may not be reflected in the `autofanpage` package coverage — that is expected.

- [ ] **Step 3: Fix any gaps**

If a module is below 85%, add a focused unit test for the uncovered branch. Do NOT paper over by adding `# pragma: no cover` unless the branch is demonstrably unreachable (e.g., the `if __name__ == "__main__"` guard, which is covered by the integration tests implicitly but not counted).

- [ ] **Step 4: Final commit**

```bash
git add -u
git commit --allow-empty -m "chore: Plan 2 complete — phase 1 data gathering green"
```

---

## Self-review

(Completed inline after writing — leaving this section so future readers see the checks that were run.)

**Spec coverage:**
- §3.2 youtube-researcher → Tasks 3–4 ✓
- §3.3 perplexity-researcher (incl. Twitter via site:x.com) → Tasks 5–6 ✓
- §3.4 reddit-researcher (8-subreddit list, OAuth, partial-failure tolerance) → Tasks 7–9 ✓
- §3.1 orchestrator parallel dispatch + merge + `min_posts_required` rule → Task 11 ✓
- `merged_sources.json` artifact schema → Tasks 2, 10 ✓
- Phase-1 Telegram summary message → Task 11 (integrated) ✓
- NotebookLM, review, writing, publishing → intentionally deferred to Plans 3/4.

**Placeholder scan:**
- No TBD, TODO, "add appropriate error handling", or similar. Every step has concrete code and expected output.

**Type / API consistency with Plan 1:**
- `run_skill(name, args)` signature and `SubprocessBackend` JSON-args convention: unchanged (Plan 1 Task 8).
- `RunDir.create(base=Path, page=str, date=str)` and `RunDir.write_json(name_without_json_suffix, data)`: matches Plan 1 Task 5. Plan 2 orchestrator calls `run_dir.write_json("merged_sources", merged)` (no `.json` suffix).
- `LastSuccess(base=Path, page=str)` constructor plus `state.mark(date=..., run_dir=..., posts_scheduled=...)` keyword-only signature: matches Plan 1 Task 6. Plan 2 passes `posts_scheduled=0` (still no publishing).
- `get_secret(ref)` signature: matches Plan 1 Task 7.
- Orchestrator CLI flags `--page --profile-path --base-dir --date`: matches Plan 1 Task 12.
- `_report(run_dir, status=, page=, details=)` helper and `success`/`error`/`info`/`partial` template keys: reused from Plan 1 Task 11. Plan 2 extends only the `success` template with two new optional keys (`phase1_counts`, `phase1_failed_sources`) with a backward-compat test.
- Skill entrypoint convention `main(argv)` using `argparse` with `--run-dir --profile` (skill reads its own slice of the profile): matches Plan 1 HN skill.
- Profile attribute access (`profile.name`, `profile.topic`, `profile.language`, `profile.timezone`, `profile.filters`, `profile.sources`, `profile.min_posts_required`): matches Plan 1 profile loader.

**Edge cases verified in tests:**
- HTTP: retry on 5xx succeeds on 3rd try; exhausted retries raise; 4xx (non-429) fails fast; **429 retried with Retry-After honour** (Task 1); headers/body round-trip correctly.
- YouTube: empty search → empty items (Task 4 test 2); low-view rejection, low-subs rejection, sort by views desc (Task 3).
- Perplexity: missing citations → empty list; `twitter_enabled=False` → zero Twitter HTTP calls (Task 6 test 2); dedup by URL.
- Reddit: stickied, NSFW, below-min-score rejected; single subreddit fails → others continue (Task 9 test 2); all subreddits fail → raise.
- Merge: **spec-mandated `{ urls, counts_per_platform }` shape**; URL dedup by canonical URL; per-platform cap at `max_sources_per_platform`; `score_or_views` populated uniformly; failure list propagated.
- Orchestrator happy path — all 4 sources, Telegram `success` with `phase1_counts`; partial-failure path — 3/4 ok, still success; below-min path — error report + `last_success` NOT written; **empty-items path — all sources ok but zero URLs after merge → error + `last_success` NOT written**; idempotent rerun → `info` Telegram, no researcher calls.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-15-autofanpage-plan2-data-gathering.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
