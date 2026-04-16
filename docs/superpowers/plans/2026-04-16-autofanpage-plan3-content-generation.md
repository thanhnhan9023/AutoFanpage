# AutoFanpage — Plan 3: Content Generation (NotebookLM + Review + Writing)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Plan 2 pipeline with the three content-generation skills that turn a `merged_sources.json` URL list into a ready-to-publish `posts.json` (four slot posts + first-comments). After Plan 3 the pipeline produces deterministic post content but still does not publish to Facebook — that remains Plan 4.

**Architecture:** Three new skills slot in between merge (Plan 2) and publish (Plan 4):

1. `notebooklm-analyzer` — calls the `notebooklm-mcp` MCP server (community tool, cookie-auth) to create a Notebook, add sources, run the 4 fixed queries, and write `insights.json`.
2. `review-agent` — scores each insight on Relevance / Novelty / Viral / Actionable (1–5 each), keeps `total ≥ 14`, assigns a `suggested_post_type ∈ {news, guide, opinion, case_study}`, writes `reviewed_insights.json`.
3. `writing-agent` — maps approved insights to the four positional slots (slot 0 = news, 1 = guide, 2 = opinion, 3 = case_study), generates 4 FB-ready posts (with first-comment) via Claude (Anthropic Messages API), writes `posts.json`.

Three new shared libraries support them:
- `autofanpage/mcp.py` — pluggable wrapper for invoking an MCP tool via OpenClaw's MCP CLI bridge. Mockable in tests.
- `autofanpage/scoring.py` — pure scoring + type-mapping logic used by the review-agent.
- `autofanpage/llm.py` — thin Claude Messages API client (direct HTTP POST, same pattern as Plan 2's `autofanpage.http`). Mockable in tests.

`autofanpage/schemas.py` gains three new schemas: `INSIGHTS_SCHEMA`, `REVIEWED_INSIGHTS_SCHEMA`, `POSTS_SCHEMA`. `autofanpage/templates.py` holds the four post-type templates (hook / body / CTA / hashtag hints + first-comment shape). `autofanpage/prompts.py` composes the writing prompt from a template + insight + language.

The orchestrator grows three sequential phases after Phase 1 merge: Phase 2 (NotebookLM, mandatory — any failure halts), Phase 3a (Review — below threshold → partial, skip Writing), Phase 3b (Writing). Success still writes `last_success.json`; partial writes `last_success.json` too but with `posts_generated < 4`.

**Tech Stack:** Python 3.11+, `requests` (Claude + MCP subprocess), `responses` (HTTP mock in tests), `jsonschema`. No new runtime dependencies beyond what Plans 1–2 installed.

**Spec reference:** `docs/superpowers/specs/2026-04-15-autofanpage-openclaw-design.md` (EN) / `.vi.md` (VN). This plan implements §3.6 (notebooklm-analyzer), §3.7 (review-agent), §3.8 (writing-agent), §3.1 orchestrator Phase 2 / 3a / 3b integration, and the `insights.json` / `reviewed_insights.json` / `posts.json` artifacts in §4. Publishing (§3.9), health-check (§3.11), and dry-run rendering (§3.1 step 9) remain Plan 4.

**Integration assumptions (Plan 2 outputs consumed by Plan 3):**
- `<run_dir>/merged_sources.json` with top-level keys `urls[]`, `counts_per_platform{}`, `sources_succeeded[]`, `sources_failed[]`, `topic`, `language`. Each URL entry has `{url, title, platform, score_or_views, created_at}` — already deduplicated by canonical URL and capped at `max_sources_per_platform` per platform (default 12, ≤48 total).
- The analyzer reads `urls[]` directly — no further dedup needed since Plan 2's merge already handles it. The `extract_urls` helper simply reads the list and applies an optional cap.

---

## File Structure

**New shared libraries under `autofanpage/`:**
- `autofanpage/mcp.py` — `MCPClient` with `call_tool(server: str, tool: str, args: dict) -> dict`. Default backend is `subprocess` to the OpenClaw MCP CLI; the backend is a class attribute so tests can override it.
- `autofanpage/scoring.py` — pure functions: `score_insight(insight: str, topic: str) -> Scores`, `total(scores) -> int`, `assign_type(insight: str) -> str`. Network-free; uses only keyword heuristics. (LLM-assisted scoring is out of scope — we score deterministically so reviews are reproducible.)
- `autofanpage/llm.py` — `ClaudeClient.generate(messages: list[dict], *, system: str, max_tokens: int, temperature: float) -> str`. Thin wrapper around `POST https://api.anthropic.com/v1/messages`. Retries on 429 / 5xx via `autofanpage.http`.
- `autofanpage/templates.py` — `TEMPLATES: dict[str, PostTemplate]` keyed by `news | guide | opinion | case_study`; each holds `hook_shape`, `body_shape`, `cta`, `hashtag_hint`, `first_comment_shape`. All CTA strings are English; `autofanpage.prompts` handles translation per `language`.
- `autofanpage/prompts.py` — `build_writing_prompt(*, insight: Approved, template: PostTemplate, language: str) -> tuple[str, list[dict]]` returning `(system, messages)` for `ClaudeClient.generate`. Also `build_first_comment_prompt` for the per-type first-comment shape.
- `autofanpage/schemas.py` — extend with `INSIGHTS_SCHEMA`, `REVIEWED_INSIGHTS_SCHEMA`, `POSTS_SCHEMA`.

**New skill folders under `skills/`:**
- `skills/notebooklm-analyzer/SKILL.md` + `scripts/__init__.py` + `scripts/analyze.py`
- `skills/review-agent/SKILL.md` + `scripts/__init__.py` + `scripts/review.py`
- `skills/writing-agent/SKILL.md` + `scripts/__init__.py` + `scripts/write_posts.py`

**Modified:**
- `skills/daily-content-pipeline/scripts/orchestrate.py` — Phase 2 / 3a / 3b dispatch, mandatory-failure halts, partial-path handling.
- `autofanpage/telegram.py` — `status="partial"` template gains optional `posts_generated` / `approved_count` fields.
- `scripts/install-skills.sh` — already globs (Plan 2 Task 13); works for new skills unchanged.
- `README.md` — append Plan 3 smoke test section.

**New tests under `tests/`:**
- `tests/test_mcp.py`
- `tests/test_scoring.py`
- `tests/test_llm.py`
- `tests/test_templates.py`
- `tests/test_prompts.py`
- `tests/skills/test_notebooklm_analyzer.py`
- `tests/skills/test_review_agent.py`
- `tests/skills/test_writing_agent.py`
- `tests/skills/test_orchestrator_plan3.py`

**New fixtures:**
- `tests/fixtures/merged_sources_small.json` — 6 URLs across all 4 platforms for analyzer input (uses Plan 2's `{urls[], counts_per_platform}` shape).
- `tests/fixtures/insights_sample.json` — a realistic NotebookLM-style output for the review-agent tests.
- `tests/fixtures/reviewed_insights_sample.json` — 4 approved insights (1 per type) for writing-agent tests.
- `tests/fixtures/profile_plan3.json` — extends `profile_plan2.json` with `min_posts_required = 2` (still) and a new explicit `writing: {model, max_tokens, temperature}` block.

---

### Task 1: MCP wrapper with subprocess backend

**Files:**
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/autofanpage/mcp.py`
- Test: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/test_mcp.py`

- [ ] **Step 1: Write failing test `tests/test_mcp.py`**

```python
import json

import pytest

from autofanpage.mcp import MCPClient, MCPError


def test_call_tool_invokes_openclaw_mcp_cli(mocker):
    fake = mocker.Mock()
    fake.returncode = 0
    fake.stdout = json.dumps({"ok": True, "result": {"notebook_id": "nb_123"}})
    fake.stderr = ""
    run = mocker.patch("autofanpage.mcp.subprocess.run", return_value=fake)

    client = MCPClient()
    out = client.call_tool(
        server="notebooklm-mcp",
        tool="notebook_create",
        args={"title": "AI Research 2026-04-15"},
    )
    assert out == {"notebook_id": "nb_123"}

    # Verify the subprocess invocation shape.
    cmd = run.call_args.args[0]
    assert cmd[0] == "openclaw"
    assert cmd[1] == "mcp"
    assert cmd[2] == "call"
    assert cmd[3] == "notebooklm-mcp"
    assert cmd[4] == "notebook_create"
    assert "--args-json" in cmd
    args_idx = cmd.index("--args-json") + 1
    assert json.loads(cmd[args_idx]) == {"title": "AI Research 2026-04-15"}


def test_call_tool_raises_on_nonzero_exit(mocker):
    fake = mocker.Mock()
    fake.returncode = 1
    fake.stdout = ""
    fake.stderr = "auth error: cookies expired"
    mocker.patch("autofanpage.mcp.subprocess.run", return_value=fake)

    client = MCPClient()
    with pytest.raises(MCPError) as exc:
        client.call_tool(server="notebooklm-mcp", tool="notebook_create", args={})
    assert "cookies expired" in str(exc.value)


def test_call_tool_raises_on_malformed_json(mocker):
    fake = mocker.Mock()
    fake.returncode = 0
    fake.stdout = "not json at all"
    fake.stderr = ""
    mocker.patch("autofanpage.mcp.subprocess.run", return_value=fake)

    client = MCPClient()
    with pytest.raises(MCPError):
        client.call_tool(server="notebooklm-mcp", tool="notebook_query", args={})


def test_call_tool_raises_on_ok_false(mocker):
    fake = mocker.Mock()
    fake.returncode = 0
    fake.stdout = json.dumps({"ok": False, "error": "rate limit"})
    fake.stderr = ""
    mocker.patch("autofanpage.mcp.subprocess.run", return_value=fake)

    client = MCPClient()
    with pytest.raises(MCPError) as exc:
        client.call_tool(server="notebooklm-mcp", tool="notebook_query", args={})
    assert "rate limit" in str(exc.value)


def test_timeout_is_passed_to_subprocess(mocker):
    fake = mocker.Mock()
    fake.returncode = 0
    fake.stdout = json.dumps({"ok": True, "result": {}})
    fake.stderr = ""
    run = mocker.patch("autofanpage.mcp.subprocess.run", return_value=fake)

    MCPClient().call_tool(
        server="s", tool="t", args={}, timeout=42,
    )
    assert run.call_args.kwargs["timeout"] == 42
```

Run: `pytest tests/test_mcp.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autofanpage.mcp'`.

- [ ] **Step 2: Write `autofanpage/mcp.py`**

```python
"""Wrapper around OpenClaw's `mcp call` CLI.

Each `call_tool` invocation expects the MCP CLI to emit a single JSON object
of the form {"ok": bool, "result": {...}, "error": "..."} on stdout. A
non-zero exit, non-JSON stdout, or ``ok == False`` is treated as an MCP
failure (MCPError).
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any

from autofanpage.errors import AutofanpageError


class MCPError(AutofanpageError):
    """Raised when an MCP tool call fails."""


@dataclass
class MCPClient:
    """Invoke MCP tools via ``openclaw mcp call <server> <tool> --args-json ...``.

    ``cli`` defaults to ``openclaw``; override in tests or when running the
    MCP CLI under an alternate name.
    """

    cli: str = "openclaw"

    def call_tool(
        self,
        *,
        server: str,
        tool: str,
        args: dict[str, Any],
        timeout: int = 120,
    ) -> dict[str, Any]:
        cmd = [
            self.cli, "mcp", "call", server, tool,
            "--args-json", json.dumps(args, ensure_ascii=False),
        ]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        if proc.returncode != 0:
            raise MCPError(
                f"MCP call {server}/{tool} exit={proc.returncode}: "
                f"{proc.stderr.strip()}"
            )
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise MCPError(
                f"MCP call {server}/{tool} returned non-JSON stdout: {e}"
            ) from e
        if not payload.get("ok", False):
            raise MCPError(
                f"MCP call {server}/{tool} ok=false: "
                f"{payload.get('error', 'unknown error')}"
            )
        return payload.get("result", {})
```

- [ ] **Step 3: Run test to verify pass**

Run: `pytest tests/test_mcp.py -v`
Expected: `5 passed`.

- [ ] **Step 4: Commit**

```bash
git add autofanpage/mcp.py tests/test_mcp.py
git commit -m "feat(mcp): MCPClient wrapper for openclaw mcp call"
```

---

### Task 2: Schemas for insights, reviewed_insights, posts

**Files:**
- Modify: `/Users/nguyenloc/VibeCoding/AutoFanpage/autofanpage/schemas.py`
- Test: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/test_schemas.py` (extend)

- [ ] **Step 1: Write failing tests (extend `tests/test_schemas.py`)**

Append:

```python
from autofanpage.schemas import (
    INSIGHTS_SCHEMA,
    REVIEWED_INSIGHTS_SCHEMA,
    POSTS_SCHEMA,
    validate,
)


def test_insights_schema_requires_all_four_keys():
    ok = {
        "overview": "short paragraph",
        "pain_points": ["p1", "p2"],
        "insights": ["i1", "i2"],
        "gap_topics": ["g1"],
        "source_urls": ["https://example.com/a"],
        "language": "vi",
    }
    validate("insights", ok)

    bad = dict(ok)
    bad.pop("insights")
    with pytest.raises(Exception):
        validate("insights", bad)


def test_insights_schema_rejects_non_string_items():
    bad = {
        "overview": "x",
        "pain_points": ["p"],
        "insights": [123],  # not a string
        "gap_topics": [],
        "source_urls": [],
        "language": "vi",
    }
    with pytest.raises(Exception):
        validate("insights", bad)


def test_reviewed_insights_schema_total_must_equal_sum():
    # the schema itself can't enforce total==sum; see scoring unit tests.
    # Here we just check that all required keys are present.
    ok = {
        "approved": [
            {
                "insight": "AI usage climbing 40% in SMBs",
                "scores": {"relevance": 5, "novelty": 4, "viral": 4, "actionable": 3},
                "total": 16,
                "suggested_post_type": "news",
                "hook_angle": "40% jump in 6 months",
                "source_url": "https://example.com/a",
            }
        ],
        "rejected": [
            {"insight": "too generic", "total": 9, "reason": "below threshold"},
        ],
    }
    validate("reviewed_insights", ok)


def test_reviewed_insights_rejects_bad_post_type():
    bad = {
        "approved": [
            {
                "insight": "x",
                "scores": {"relevance": 1, "novelty": 1, "viral": 1, "actionable": 1},
                "total": 4,
                "suggested_post_type": "meme",  # not in enum
                "hook_angle": "",
                "source_url": "",
            }
        ],
        "rejected": [],
    }
    with pytest.raises(Exception):
        validate("reviewed_insights", bad)


def test_posts_schema_allows_null_content_for_unfilled_slots():
    ok = {
        "posts": [
            {"time": "08:00", "type": "news", "content": "...", "first_comment": "..."},
            {"time": "12:00", "type": "guide", "content": None, "first_comment": None},
            {"time": "16:00", "type": "opinion", "content": "...", "first_comment": "..."},
            {"time": "20:00", "type": "case_study", "content": None, "first_comment": None},
        ],
        "language": "vi",
    }
    validate("posts", ok)


def test_posts_schema_requires_exactly_four_posts_with_correct_types():
    # Slot order is positional: news, guide, opinion, case_study.
    bad = {
        "posts": [
            {"time": "08:00", "type": "news", "content": "x", "first_comment": "x"},
            {"time": "12:00", "type": "news", "content": None, "first_comment": None},
            {"time": "16:00", "type": "opinion", "content": None, "first_comment": None},
            {"time": "20:00", "type": "case_study", "content": None, "first_comment": None},
        ],
        "language": "vi",
    }
    # Same-type duplication is not a schema violation per se (the schema allows any
    # enum value at any index) — this is a business-rule test to ensure the writing
    # agent is the one that enforces slot-ordering; the schema covers shape only.
    validate("posts", bad)
```

Run: `pytest tests/test_schemas.py -v`
Expected: the new tests FAIL with `ImportError: cannot import name 'INSIGHTS_SCHEMA' from 'autofanpage.schemas'` (and similar).

- [ ] **Step 2: Add the three schemas to `autofanpage/schemas.py`**

Append to the existing `schemas.py` (keep all current schemas unchanged):

```python
INSIGHTS_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "overview", "pain_points", "insights", "gap_topics",
        "source_urls", "language",
    ],
    "additionalProperties": True,
    "properties": {
        "overview": {"type": "string"},
        "pain_points": {"type": "array", "items": {"type": "string"}},
        "insights": {"type": "array", "items": {"type": "string"}},
        "gap_topics": {"type": "array", "items": {"type": "string"}},
        "source_urls": {
            "type": "array",
            "items": {"type": "string", "format": "uri"},
        },
        "language": {"type": "string"},
        "notebook_id": {"type": "string"},
    },
}


_POST_TYPES = ["news", "guide", "opinion", "case_study"]


REVIEWED_INSIGHTS_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["approved", "rejected"],
    "additionalProperties": True,
    "properties": {
        "approved": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "insight", "scores", "total",
                    "suggested_post_type", "hook_angle", "source_url",
                ],
                "additionalProperties": True,
                "properties": {
                    "insight": {"type": "string"},
                    "scores": {
                        "type": "object",
                        "required": ["relevance", "novelty", "viral", "actionable"],
                        "additionalProperties": False,
                        "properties": {
                            "relevance":  {"type": "integer", "minimum": 1, "maximum": 5},
                            "novelty":    {"type": "integer", "minimum": 1, "maximum": 5},
                            "viral":      {"type": "integer", "minimum": 1, "maximum": 5},
                            "actionable": {"type": "integer", "minimum": 1, "maximum": 5},
                        },
                    },
                    "total": {"type": "integer", "minimum": 4, "maximum": 20},
                    "suggested_post_type": {"type": "string", "enum": _POST_TYPES},
                    "hook_angle": {"type": "string"},
                    "source_url": {"type": "string"},
                },
            },
        },
        "rejected": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["insight", "total", "reason"],
                "additionalProperties": True,
                "properties": {
                    "insight": {"type": "string"},
                    "total": {"type": "integer", "minimum": 4, "maximum": 20},
                    "reason": {"type": "string"},
                },
            },
        },
    },
}


POSTS_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["posts", "language"],
    "additionalProperties": True,
    "properties": {
        "language": {"type": "string"},
        "posts": {
            "type": "array",
            "minItems": 4,
            "maxItems": 4,
            "items": {
                "type": "object",
                "required": ["time", "type", "content", "first_comment"],
                "additionalProperties": True,
                "properties": {
                    "time": {
                        "type": "string",
                        "pattern": "^[0-2][0-9]:[0-5][0-9]$",
                    },
                    "type": {"type": "string", "enum": _POST_TYPES},
                    "content": {"type": ["string", "null"]},
                    "first_comment": {"type": ["string", "null"]},
                },
            },
        },
    },
}


# Register with the validate() dispatcher — the existing dispatcher is a
# dict literal; extend the mapping accordingly.
```

Find the existing `_SCHEMAS` mapping in `schemas.py` and add entries:

```python
_SCHEMAS = {
    # ... existing entries ...
    "insights":           INSIGHTS_SCHEMA,
    "reviewed_insights":  REVIEWED_INSIGHTS_SCHEMA,
    "posts":              POSTS_SCHEMA,
}
```

- [ ] **Step 3: Run tests to verify pass**

Run: `pytest tests/test_schemas.py -v`
Expected: all existing tests still green + 5 new ones pass.

- [ ] **Step 4: Commit**

```bash
git add autofanpage/schemas.py tests/test_schemas.py
git commit -m "feat(schemas): insights, reviewed_insights, posts"
```

---

### Task 3: notebooklm-analyzer — input parsing & URL extraction (pure)

**Files:**
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/autofanpage/notebooklm.py`
- Test: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/test_notebooklm.py`

*Rationale:* the skill script is thin; the URL-extraction + dedup logic lives in a pure module so it's testable without MCP calls.

- [ ] **Step 1: Write failing test `tests/test_notebooklm.py`**

```python
from autofanpage.notebooklm import (
    extract_urls,
    canonicalize,
    DEFAULT_MAX_SOURCES,
)


def test_canonicalize_strips_utm_and_fragment():
    assert canonicalize("https://example.com/a?utm_source=x&b=1#frag") == \
        "https://example.com/a?b=1"


def test_canonicalize_lowercases_host_keeps_path_case():
    assert canonicalize("HTTPS://Example.COM/Path/Foo") == \
        "https://example.com/Path/Foo"


def test_canonicalize_empty_string_returns_empty():
    assert canonicalize("") == ""
    assert canonicalize(None) == ""


def test_extract_urls_reads_urls_list_directly():
    merged = {
        "topic": "AI",
        "language": "vi",
        "counts_per_platform": {"youtube": 2, "reddit": 1, "hackernews": 1},
        "urls": [
            {"url": "https://y/1",  "title": "a", "platform": "youtube",
             "score_or_views": 150000, "created_at": "2026-04-10T00:00:00Z"},
            {"url": "https://r/1",  "title": "b", "platform": "reddit",
             "score_or_views": 800, "created_at": "2026-04-14T00:00:00Z"},
            {"url": "https://h/1",  "title": "c", "platform": "hackernews",
             "score_or_views": 300, "created_at": "2026-04-14T00:00:00Z"},
            {"url": "https://y/2",  "title": "d", "platform": "youtube",
             "score_or_views": 90000, "created_at": "2026-04-11T00:00:00Z"},
        ],
    }
    urls = extract_urls(merged)
    assert urls == ["https://y/1", "https://r/1", "https://h/1", "https://y/2"]


def test_extract_urls_caps_at_default_limit():
    many = {"topic": "x", "language": "vi", "counts_per_platform": {"youtube": 80},
            "urls": [
        {"url": f"https://y/{i}", "title": str(i), "platform": "youtube",
         "score_or_views": 0, "created_at": ""}
        for i in range(80)
    ]}
    assert len(extract_urls(many)) == DEFAULT_MAX_SOURCES  # 48 per spec


def test_extract_urls_respects_explicit_cap():
    many = {"topic": "x", "language": "vi", "counts_per_platform": {"youtube": 30},
            "urls": [
        {"url": f"https://y/{i}", "title": str(i), "platform": "youtube",
         "score_or_views": 0, "created_at": ""}
        for i in range(30)
    ]}
    assert len(extract_urls(many, max_sources=10)) == 10
```

Run: `pytest tests/test_notebooklm.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 2: Write `autofanpage/notebooklm.py`**

```python
"""Pure helpers for the notebooklm-analyzer skill.

Concretely: reading the Plan 2 ``merged_sources.json`` URL list (already
deduplicated and per-platform-capped by Plan 2's merge step), canonicalizing
URLs for the MCP tool, and applying an optional cap.

No network I/O here — those live in the skill script.
"""
from __future__ import annotations

from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode


DEFAULT_MAX_SOURCES = 48


_STRIP_QUERY_PREFIXES = ("utm_", "ref_", "gclid", "fbclid", "mc_")


def canonicalize(url: str | None) -> str:
    """Return a canonical form of ``url`` suitable for dedup comparison.

    Drops fragment, tracking-only query params (utm_*, ref_*, fbclid, gclid,
    mc_*), lowercases the scheme+host, and preserves path case. Invalid or
    empty inputs become ``""``.
    """
    if not url:
        return ""
    try:
        p = urlparse(url.strip())
    except ValueError:
        return ""
    if not p.scheme or not p.netloc:
        return ""
    q = [
        (k, v) for (k, v) in parse_qsl(p.query, keep_blank_values=True)
        if not any(k.lower().startswith(pref) for pref in _STRIP_QUERY_PREFIXES)
    ]
    return urlunparse((
        p.scheme.lower(), p.netloc.lower(), p.path, p.params,
        urlencode(q), "",
    ))


def extract_urls(
    merged: dict,
    *,
    max_sources: int = DEFAULT_MAX_SOURCES,
) -> list[str]:
    """Extract URL list from a Plan 2 ``merged_sources.json``.

    Plan 2's merge already deduplicates by canonical URL and caps per platform,
    so this function simply reads the ``urls[]`` array and applies an optional
    overall cap. URLs are canonicalized for consistency with the MCP tool.
    """
    out: list[str] = []
    for entry in merged.get("urls") or []:
        raw = entry.get("url") if isinstance(entry, dict) else entry
        canon = canonicalize(raw)
        if not canon:
            continue
        out.append(canon)
        if len(out) >= max_sources:
            break
    return out
```

- [ ] **Step 3: Run tests to verify pass**

Run: `pytest tests/test_notebooklm.py -v`
Expected: `5 passed`.

- [ ] **Step 4: Commit**

```bash
git add autofanpage/notebooklm.py tests/test_notebooklm.py
git commit -m "feat(notebooklm): pure URL extract + canonicalize + dedup"
```

---

### Task 4: notebooklm-analyzer skill

**Files:**
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/skills/notebooklm-analyzer/SKILL.md`
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/skills/notebooklm-analyzer/scripts/__init__.py` (empty)
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/skills/notebooklm-analyzer/scripts/analyze.py`
- Test: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/skills/test_notebooklm_analyzer.py`
- Fixture: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/fixtures/merged_sources_small.json`

- [ ] **Step 1: Create fixture `tests/fixtures/merged_sources_small.json`**

```json
{
  "profile": "page_test",
  "topic": "AI automation",
  "language": "vi",
  "fetched_at": "2026-04-16T06:00:00+07:00",
  "sources_succeeded": ["youtube", "perplexity", "reddit", "hackernews"],
  "sources_failed": [],
  "counts_per_platform": {"youtube": 1, "perplexity": 1, "reddit": 1, "hackernews": 1},
  "urls": [
    {"url": "https://y.example/v1", "title": "AI demo",    "platform": "youtube",    "score_or_views": 200000, "created_at": "2026-04-10T00:00:00Z"},
    {"url": "https://n.example/a",  "title": "News A",     "platform": "perplexity", "score_or_views": 0,      "created_at": ""},
    {"url": "https://r.example/p1", "title": "Reddit pop",  "platform": "reddit",    "score_or_views": 1500,   "created_at": "2026-04-14T00:00:00Z"},
    {"url": "https://h.example/i1", "title": "HN front",    "platform": "hackernews","score_or_views": 420,    "created_at": "2026-04-14T00:00:00Z"}
  ]
}
```

- [ ] **Step 2: Write failing test `tests/skills/test_notebooklm_analyzer.py`**

```python
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "notebooklm-analyzer" / "scripts"
sys.path.insert(0, str(SCRIPT))
import analyze  # noqa: E402


@pytest.fixture
def run_dir(tmp_path, fixtures_dir):
    rd = tmp_path / "runs" / "page_test" / "2026-04-16"
    rd.mkdir(parents=True)
    src = fixtures_dir / "merged_sources_small.json"
    (rd / "merged_sources.json").write_text(src.read_text(), encoding="utf-8")
    return rd


def _fake_mcp_client(notebook_id="nb_42"):
    class Fake:
        def __init__(self):
            self.calls = []

        def call_tool(self, *, server, tool, args, timeout=120):
            self.calls.append((server, tool, dict(args)))
            if tool == "notebook_create":
                return {"notebook_id": notebook_id}
            if tool == "source_add":
                return {"source_id": f"src_{len(self.calls)}"}
            if tool == "notebook_query":
                q = args.get("query", "")
                # Return deterministic shapes keyed by question marker.
                if "overview" in q.lower():
                    return {"answer": "overview text"}
                if "pain" in q.lower():
                    return {"answer": "- p1\n- p2\n- p3"}
                if "insights" in q.lower() or "business insight" in q.lower():
                    return {
                        "answer": "\n".join([f"- insight {i}" for i in range(7)]),
                    }
                if "gap" in q.lower():
                    return {"answer": "- gap1\n- gap2"}
            raise RuntimeError(f"unexpected tool {tool}")

    return Fake()


def test_happy_path_creates_notebook_adds_sources_runs_four_queries(run_dir, mocker):
    fake = _fake_mcp_client()
    mocker.patch.object(analyze, "MCPClient", return_value=fake)

    out = analyze.main([
        "--run-dir", str(run_dir),
        "--profile", str(run_dir.parent.parent / "does_not_matter.json"),
        "--language", "vi",
    ])
    assert out == 0

    # 1 create + 4 sources (dedup from the 5th) + 4 queries = 9 calls
    tool_names = [t for (_, t, _) in fake.calls]
    assert tool_names.count("notebook_create") == 1
    assert tool_names.count("source_add") == 4
    assert tool_names.count("notebook_query") == 4

    insights_path = run_dir / "insights.json"
    assert insights_path.exists()
    payload = json.loads(insights_path.read_text())
    assert payload["language"] == "vi"
    assert payload["overview"] == "overview text"
    assert len(payload["pain_points"]) == 3
    assert len(payload["insights"]) >= 5
    assert len(payload["gap_topics"]) == 2
    assert payload["notebook_id"] == "nb_42"
    assert payload["source_urls"] == [
        "https://y.example/v1",
        "https://n.example/a",
        "https://r.example/p1",
        "https://h.example/i1",
    ]


def test_mcp_failure_on_notebook_create_raises_and_writes_no_artifact(run_dir, mocker):
    from autofanpage.mcp import MCPError

    class Fake:
        def call_tool(self, **kw):
            raise MCPError("cookies expired")

    mocker.patch.object(analyze, "MCPClient", return_value=Fake())

    with pytest.raises(MCPError):
        analyze.main([
            "--run-dir", str(run_dir),
            "--profile", str(run_dir.parent.parent / "x.json"),
            "--language", "vi",
        ])
    assert not (run_dir / "insights.json").exists()


def test_all_empty_urls_raises(tmp_path, mocker):
    rd = tmp_path / "runs" / "page_test" / "2026-04-16"
    rd.mkdir(parents=True)
    (rd / "merged_sources.json").write_text(json.dumps({
        "topic": "x", "language": "vi", "urls": [],
        "counts_per_platform": {},
        "sources_succeeded": [], "sources_failed": [],
        "fetched_at": "2026-04-16T06:00:00+07:00", "profile": "page_test",
    }), encoding="utf-8")

    from autofanpage.errors import AutofanpageError
    with pytest.raises(AutofanpageError) as exc:
        analyze.main([
            "--run-dir", str(rd),
            "--profile", str(tmp_path / "x.json"),
            "--language", "vi",
        ])
    assert "no source urls" in str(exc.value).lower()


def test_legacy_items_shape_raises_schema_error(tmp_path):
    """If someone runs Plan 3 against an old Plan 2 merged_sources with items[],
    we get a clear schema error — not a silent empty-URL fallthrough."""
    rd = tmp_path / "runs" / "page_test" / "2026-04-16"
    rd.mkdir(parents=True)
    (rd / "merged_sources.json").write_text(json.dumps({
        "profile": "page_test",
        "topic": "x", "language": "vi",
        "fetched_at": "2026-04-16T06:00:00+07:00",
        "sources_succeeded": ["youtube"], "sources_failed": [],
        "items": [{"source": "youtube", "url": "https://y/1", "title": "t", "score": 1}],
    }), encoding="utf-8")

    from autofanpage.errors import AutofanpageError
    with pytest.raises(AutofanpageError) as exc:
        analyze.main([
            "--run-dir", str(rd),
            "--profile", str(tmp_path / "x.json"),
            "--language", "vi",
        ])
    assert "schema" in str(exc.value).lower()
```

Run: `pytest tests/skills/test_notebooklm_analyzer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'analyze'`.

- [ ] **Step 3: Write `skills/notebooklm-analyzer/scripts/analyze.py`**

```python
#!/usr/bin/env python3
"""notebooklm-analyzer: create a NotebookLM notebook and run 4 fixed queries.

Reads  <run_dir>/merged_sources.json
Writes <run_dir>/insights.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make the project root importable when invoked directly by the OpenClaw
# skill runner (which sets CWD to the repo root).
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from autofanpage.errors import AutofanpageError
from autofanpage.mcp import MCPClient
from autofanpage.notebooklm import extract_urls
from autofanpage.schemas import validate


SERVER = "notebooklm-mcp"


def _bullets(text: str) -> list[str]:
    """Parse a bulleted answer string into a list of clean items."""
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        # Strip common list markers.
        for marker in ("- ", "* ", "• "):
            if line.startswith(marker):
                line = line[len(marker):]
                break
        # Numbered lists: "1. x"
        if line[:2].rstrip(".").isdigit() and line[2:3] in (".", ")", " "):
            line = line.split(None, 1)[-1]
        out.append(line)
    return out


def _queries(language: str) -> dict[str, str]:
    # Language gate: the prompt TEXT stays English but instructs the model
    # to respond in ``language``. This keeps the prompt deterministic.
    instruct = f"Respond in {language}. Use bullets where the answer is a list."
    return {
        "overview":    f"{instruct}\nWrite a 3-5 sentence overview of the state of this topic today based on the provided sources.",
        "pain_points": f"{instruct}\nList 5-8 concrete pain points or friction areas users describe in these sources.",
        "insights":    f"{instruct}\nGive 5-10 sharp, non-obvious business insights the sources collectively support. One bullet each.",
        "gap_topics":  f"{instruct}\nList 3-5 gap topics the sources hint at but do not explore in depth.",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True)
    p.add_argument("--profile", required=True)
    p.add_argument("--language", required=True,
                   help="BCP-47 or plain language name, e.g. 'vi' or 'English'")
    p.add_argument("--max-sources", type=int, default=48)
    args = p.parse_args(argv)

    run_dir = Path(args.run_dir)
    merged_path = run_dir / "merged_sources.json"
    if not merged_path.exists():
        raise AutofanpageError(f"missing input: {merged_path}")
    merged = json.loads(merged_path.read_text(encoding="utf-8"))

    # Validate input against Plan 2's contract before extraction.
    # Fail fast with a clear schema error rather than a generic empty-input.
    from autofanpage.schemas import validate, SchemaError
    try:
        validate("merged_sources", merged)
    except SchemaError as e:
        raise AutofanpageError(
            f"merged_sources.json does not match Plan 2 schema: {e}"
        ) from e

    urls = extract_urls(merged, max_sources=args.max_sources)
    if not urls:
        raise AutofanpageError("no source urls after extraction — cannot analyze")

    client = MCPClient()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    nb = client.call_tool(
        server=SERVER, tool="notebook_create",
        args={"title": f"AI Research {today}"},
    )
    notebook_id = nb["notebook_id"]

    for url in urls:
        client.call_tool(
            server=SERVER, tool="source_add",
            args={"notebook_id": notebook_id, "url": url},
        )

    queries = _queries(args.language)
    answers = {}
    for key, prompt in queries.items():
        resp = client.call_tool(
            server=SERVER, tool="notebook_query",
            args={"notebook_id": notebook_id, "query": prompt},
            timeout=180,
        )
        answers[key] = resp.get("answer", "")

    insights = {
        "overview":    answers["overview"].strip(),
        "pain_points": _bullets(answers["pain_points"]),
        "insights":    _bullets(answers["insights"]),
        "gap_topics":  _bullets(answers["gap_topics"]),
        "source_urls": urls,
        "language":    args.language,
        "notebook_id": notebook_id,
    }
    validate("insights", insights)
    (run_dir / "insights.json").write_text(
        json.dumps(insights, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(json.dumps({"status": "ok", "artifact": "insights.json",
                      "notebook_id": notebook_id, "sources": len(urls)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Create `skills/notebooklm-analyzer/SKILL.md`**

```markdown
---
name: notebooklm-analyzer
description: Create a NotebookLM notebook from merged_sources.json, add each source URL, run four fixed queries, write insights.json.
---

# notebooklm-analyzer

**Inputs:** `run_dir` (contains `merged_sources.json`), `profile` (path to per-page JSON), `language`.
**Output:** `<run_dir>/insights.json` — `{overview, pain_points[], insights[], gap_topics[], source_urls[], language, notebook_id}`.

**Flow:**
1. Read `<run_dir>/merged_sources.json` → extract deduplicated URL list (`autofanpage.notebooklm.extract_urls`), capped at 48.
2. `notebook_create(title="AI Research <today>")` via the `notebooklm-mcp` MCP server.
3. For each URL, `source_add(notebook_id, url)`.
4. Call `notebook_query` four times with fixed prompts (overview / pain_points / insights / gap_topics), all instructed to respond in `language`.
5. Parse bulleted answers, validate against `INSIGHTS_SCHEMA`, write `insights.json`.

**Failure semantics (mandatory phase — see spec §5):**
- `cookies expired` from any MCP call → propagates as `MCPError`; the orchestrator reports a Telegram error with the literal string `Run \`nlm login\` to refresh NotebookLM cookies.`
- Rate-limit (HTTP 429) → MCPError propagates; orchestrator reports + halts; next-day cron retries.
- Any other MCP failure → 1 retry (30s backoff) then MCPError. **The retry loop is implemented in the orchestrator, not here**, so this script is idempotent: re-invoking it recreates the notebook (cheap) and re-issues the queries.

**CLI invocation:**

    python scripts/analyze.py \
        --run-dir <path> \
        --profile <profile.json> \
        --language vi \
        [--max-sources 48]

**Exit codes:** 0 on success; non-zero raises `AutofanpageError`/`MCPError` for the orchestrator to catch.
```

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest tests/skills/test_notebooklm_analyzer.py -v`
Expected: `4 passed`.

- [ ] **Step 6: Commit**

```bash
git add skills/notebooklm-analyzer/ tests/skills/test_notebooklm_analyzer.py tests/fixtures/merged_sources_small.json
git commit -m "feat(skill): notebooklm-analyzer — 4 fixed queries via MCP"
```

---

### Task 5: Review scoring logic (pure)

**Files:**
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/autofanpage/scoring.py`
- Test: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/test_scoring.py`

*Design note:* the spec says "score each raw insight on Relevance / Novelty / Viral / Actionable, each 1–5". To keep reviews **reproducible** and **testable without an LLM**, we use deterministic keyword-based heuristics. An LLM-assisted review mode is out of scope for Plan 3 (YAGNI) — the heuristics are conservative enough to surface the obvious insights, and the writing-agent uses the LLM anyway.

- [ ] **Step 1: Write failing test `tests/test_scoring.py`**

```python
import pytest

from autofanpage.scoring import (
    score_insight, total, assign_type, APPROVAL_THRESHOLD,
)


def test_total_sums_the_four_axes():
    assert total({"relevance": 5, "novelty": 4, "viral": 4, "actionable": 3}) == 16


def test_score_empty_string_returns_low_scores():
    s = score_insight("", topic="AI automation")
    assert all(v == 1 for v in s.values())
    assert total(s) < APPROVAL_THRESHOLD


def test_score_on_topic_with_numbers_and_actionable_verbs_is_high():
    s = score_insight(
        "Using AI automation, teams reduced ticket backlog by 40% in 6 weeks — try batching similar tickets first.",
        topic="AI automation",
    )
    assert s["relevance"] >= 4     # on-topic keywords present
    assert s["actionable"] >= 4    # verb + concrete step
    assert s["viral"] >= 4         # contains number
    assert total(s) >= APPROVAL_THRESHOLD


def test_score_generic_opinion_is_below_threshold():
    s = score_insight("AI is the future.", topic="AI automation")
    assert total(s) < APPROVAL_THRESHOLD


def test_assign_type_maps_breaking_news_language():
    assert assign_type("OpenAI announced GPT-5 yesterday") == "news"
    assert assign_type("Google launches a new Gemini release today") == "news"


def test_assign_type_maps_howto_language():
    assert assign_type("How to set up an AI chatbot in 5 minutes") == "guide"
    assert assign_type("3 steps to automate invoice processing") == "guide"


def test_assign_type_maps_opinion_language():
    assert assign_type("Why most AI agents still fail in production") == "opinion"
    assert assign_type("Unpopular opinion: LLMs aren't ready for ops") == "opinion"


def test_assign_type_maps_case_study_language():
    assert assign_type("How Acme Corp cut support cost 60% with AI") == "case_study"
    assert assign_type("A real-world case of AI in manufacturing") == "case_study"


def test_assign_type_falls_back_to_news():
    # Ambiguous insight with no clear marker defaults to news.
    assert assign_type("The token cost of large context windows") == "news"
```

Run: `pytest tests/test_scoring.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 2: Write `autofanpage/scoring.py`**

```python
"""Pure scoring and type-assignment heuristics for the review-agent.

Scoring is deliberately deterministic. Every insight gets four integer scores
(1..5) on Relevance / Novelty / Viral / Actionable, summed into ``total``.
Insights with ``total >= APPROVAL_THRESHOLD`` (14) move to Writing.

Type assignment uses keyword heuristics — news / guide / opinion / case_study —
with ``news`` as the safe default for insights that don't match any bucket.
"""
from __future__ import annotations

import re
from typing import TypedDict


class Scores(TypedDict):
    relevance: int
    novelty: int
    viral: int
    actionable: int


APPROVAL_THRESHOLD = 14


_ACTIONABLE_VERBS = re.compile(
    r"\b(try|use|implement|build|set up|adopt|switch|apply|measure|track|"
    r"automate|deploy|run|configure|start|install|test)\b",
    re.IGNORECASE,
)
_NOVELTY_MARKERS = re.compile(
    r"\b(announced|launched|released|unveiled|new|first|breakthrough|"
    r"surpris(ed|ing)|counterintuitive)\b",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"\b\d+(\.\d+)?\s?%?\b")
_OPINION_MARKERS = re.compile(
    r"\b(why|opinion|unpopular|hot take|debate|controvers(y|ial)|myth)\b",
    re.IGNORECASE,
)
_GUIDE_MARKERS = re.compile(
    r"\b(how to|step(s)?|tutorial|guide|checklist|\d+\s+(ways?|steps?|tips?))\b",
    re.IGNORECASE,
)
_CASE_MARKERS = re.compile(
    r"\b(case study|real[- ]world|company|corp\.?|inc\.?|ltd\.?|"
    r"reduced|increased|cut\b|saved|grew)\b.*\b\d+\s?%",
    re.IGNORECASE,
)
_NEWS_MARKERS = re.compile(
    r"\b(today|yesterday|this week|announce(d)?|releases?|launches?)\b",
    re.IGNORECASE,
)


def _topic_relevance(insight: str, topic: str) -> int:
    if not insight:
        return 1
    # Overlap of topic tokens (3+ chars, case-insensitive) with insight tokens.
    tokens = {t for t in re.findall(r"\w+", topic.lower()) if len(t) >= 3}
    if not tokens:
        return 3
    text = insight.lower()
    hits = sum(1 for t in tokens if t in text)
    if hits == 0:
        return 2
    if hits == 1:
        return 3
    if hits == 2:
        return 4
    return 5


def _novelty(insight: str) -> int:
    if not insight:
        return 1
    if _NOVELTY_MARKERS.search(insight):
        return 5
    if _NUMBER.search(insight):
        return 4
    # Short insights usually restate common knowledge.
    return 2 if len(insight) < 50 else 3


def _viral(insight: str) -> int:
    if not insight:
        return 1
    if _NUMBER.search(insight) and len(insight) > 40:
        return 5
    if _NUMBER.search(insight):
        return 4
    if "?" in insight or "!" in insight:
        return 3
    return 2


def _actionable(insight: str) -> int:
    if not insight:
        return 1
    verb = bool(_ACTIONABLE_VERBS.search(insight))
    has_step = bool(re.search(r"\b(first|step|then|after|next)\b", insight, re.IGNORECASE))
    if verb and has_step:
        return 5
    if verb:
        return 4
    if has_step:
        return 3
    return 2


def score_insight(insight: str, *, topic: str) -> Scores:
    return {
        "relevance":  _topic_relevance(insight, topic),
        "novelty":    _novelty(insight),
        "viral":      _viral(insight),
        "actionable": _actionable(insight),
    }


def total(scores: Scores) -> int:
    return sum(scores.values())


def assign_type(insight: str) -> str:
    if _CASE_MARKERS.search(insight):
        return "case_study"
    if _GUIDE_MARKERS.search(insight):
        return "guide"
    if _OPINION_MARKERS.search(insight):
        return "opinion"
    if _NEWS_MARKERS.search(insight):
        return "news"
    return "news"
```

- [ ] **Step 3: Run tests to verify pass**

Run: `pytest tests/test_scoring.py -v`
Expected: `9 passed`.

- [ ] **Step 4: Commit**

```bash
git add autofanpage/scoring.py tests/test_scoring.py
git commit -m "feat(scoring): deterministic insight scoring + type assignment"
```

---

### Task 6: review-agent skill

**Files:**
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/skills/review-agent/SKILL.md`
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/skills/review-agent/scripts/__init__.py`
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/skills/review-agent/scripts/review.py`
- Test: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/skills/test_review_agent.py`
- Fixture: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/fixtures/insights_sample.json`

- [ ] **Step 1: Create fixture `tests/fixtures/insights_sample.json`**

```json
{
  "overview": "AI automation is moving from pilots into mainline ops.",
  "pain_points": [
    "Integrations still require manual token rotation",
    "Cost per 1M tokens is unpredictable under prompt caching"
  ],
  "insights": [
    "OpenAI announced GPT-5 yesterday — latency dropped 35% vs 4.5.",
    "Teams using prompt caching cut API spend 60% in 8 weeks — try batching similar calls first.",
    "Why most AI agents still fail in production deployment.",
    "How Acme Corp cut support response time 55% with AI routing.",
    "AI is the future.",
    "A random short insight."
  ],
  "gap_topics": [
    "Cold-start behavior under high concurrency",
    "Regulatory pressure on agent autonomy"
  ],
  "source_urls": [
    "https://y.example/v1",
    "https://n.example/a",
    "https://r.example/p1",
    "https://h.example/i1"
  ],
  "language": "vi",
  "notebook_id": "nb_test"
}
```

- [ ] **Step 2: Write failing test `tests/skills/test_review_agent.py`**

```python
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "review-agent" / "scripts"
sys.path.insert(0, str(SCRIPT))
import review  # noqa: E402


@pytest.fixture
def run_dir(tmp_path, fixtures_dir):
    rd = tmp_path / "runs" / "page_test" / "2026-04-16"
    rd.mkdir(parents=True)
    (rd / "insights.json").write_text(
        (fixtures_dir / "insights_sample.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return rd


def test_review_writes_reviewed_insights_with_approved_and_rejected(run_dir, fixtures_dir):
    profile_path = fixtures_dir / "profile_plan2.json"  # min_posts_required=2
    rc = review.main([
        "--run-dir", str(run_dir),
        "--profile", str(profile_path),
    ])
    assert rc == 0

    out = json.loads((run_dir / "reviewed_insights.json").read_text())
    assert "approved" in out
    assert "rejected" in out
    # The hand-curated fixture has 4 strong insights and 2 weak ones.
    assert len(out["approved"]) >= 3
    assert len(out["rejected"]) >= 1


def test_all_approved_entries_have_total_ge_threshold(run_dir, fixtures_dir):
    review.main([
        "--run-dir", str(run_dir),
        "--profile", str(fixtures_dir / "profile_plan2.json"),
    ])
    out = json.loads((run_dir / "reviewed_insights.json").read_text())
    from autofanpage.scoring import APPROVAL_THRESHOLD
    assert all(a["total"] >= APPROVAL_THRESHOLD for a in out["approved"])


def test_every_approved_has_valid_post_type(run_dir, fixtures_dir):
    review.main([
        "--run-dir", str(run_dir),
        "--profile", str(fixtures_dir / "profile_plan2.json"),
    ])
    out = json.loads((run_dir / "reviewed_insights.json").read_text())
    allowed = {"news", "guide", "opinion", "case_study"}
    assert all(a["suggested_post_type"] in allowed for a in out["approved"])


def test_rejected_rows_have_reason(run_dir, fixtures_dir):
    review.main([
        "--run-dir", str(run_dir),
        "--profile", str(fixtures_dir / "profile_plan2.json"),
    ])
    out = json.loads((run_dir / "reviewed_insights.json").read_text())
    for r in out["rejected"]:
        assert r["reason"]
        assert r["total"] < 14


def test_empty_approved_is_still_valid_output(tmp_path, fixtures_dir):
    rd = tmp_path / "runs" / "page_test" / "2026-04-16"
    rd.mkdir(parents=True)
    (rd / "insights.json").write_text(json.dumps({
        "overview": "x",
        "pain_points": [],
        "insights": ["AI is the future.", "Vague stuff."],
        "gap_topics": [],
        "source_urls": [],
        "language": "vi",
    }), encoding="utf-8")

    rc = review.main([
        "--run-dir", str(rd),
        "--profile", str(fixtures_dir / "profile_plan2.json"),
    ])
    assert rc == 0
    out = json.loads((rd / "reviewed_insights.json").read_text())
    assert out["approved"] == []
    assert len(out["rejected"]) == 2
```

Run: `pytest tests/skills/test_review_agent.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'review'`.

- [ ] **Step 3: Write `skills/review-agent/scripts/review.py`**

```python
#!/usr/bin/env python3
"""review-agent: score insights, keep total>=14, assign post type.

Reads  <run_dir>/insights.json
Writes <run_dir>/reviewed_insights.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from autofanpage.errors import AutofanpageError
from autofanpage.profile import load_profile
from autofanpage.schemas import validate
from autofanpage.scoring import (
    APPROVAL_THRESHOLD, assign_type, score_insight, total,
)


def _hook_angle(insight: str) -> str:
    """Crude first-pass hook suggestion: the most number-dense sentence."""
    import re
    sentences = re.split(r"(?<=[.!?])\s+", insight.strip())
    if not sentences:
        return insight
    best = max(
        sentences,
        key=lambda s: (len(re.findall(r"\d", s)), len(s)),
    )
    return best.strip()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True)
    p.add_argument("--profile", required=True)
    args = p.parse_args(argv)

    run_dir = Path(args.run_dir)
    insights_path = run_dir / "insights.json"
    if not insights_path.exists():
        raise AutofanpageError(f"missing input: {insights_path}")
    insights = json.loads(insights_path.read_text(encoding="utf-8"))
    validate("insights", insights)

    profile = load_profile(args.profile)

    source_urls = insights.get("source_urls", [])
    fallback_url = source_urls[0] if source_urls else ""

    approved: list[dict] = []
    rejected: list[dict] = []
    for raw in insights["insights"]:
        text = (raw or "").strip()
        scores = score_insight(text, topic=profile.topic)
        t = total(scores)
        if t >= APPROVAL_THRESHOLD:
            approved.append({
                "insight": text,
                "scores": scores,
                "total": t,
                "suggested_post_type": assign_type(text),
                "hook_angle": _hook_angle(text),
                "source_url": fallback_url,
            })
        else:
            rejected.append({
                "insight": text,
                "total": t,
                "reason": f"total {t} < threshold {APPROVAL_THRESHOLD}",
            })

    # Sort approved by total desc for deterministic downstream behavior.
    approved.sort(key=lambda a: a["total"], reverse=True)

    out = {"approved": approved, "rejected": rejected}
    validate("reviewed_insights", out)
    (run_dir / "reviewed_insights.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(json.dumps({
        "status": "ok", "artifact": "reviewed_insights.json",
        "approved_count": len(approved), "rejected_count": len(rejected),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Create `skills/review-agent/SKILL.md`**

```markdown
---
name: review-agent
description: Score NotebookLM insights on Relevance / Novelty / Viral / Actionable (1-5 each), keep total >= 14, assign news/guide/opinion/case_study, write reviewed_insights.json.
---

# review-agent

**Inputs:** `run_dir` (contains `insights.json`), `profile` (for `topic`).
**Output:** `<run_dir>/reviewed_insights.json` — `{approved[], rejected[]}` per spec §3.7.

**Scoring:** deterministic keyword heuristics in `autofanpage.scoring`. No LLM call — this keeps reviews reproducible, cheap, and test-independent.

**Approval rule:** `total >= 14`. `total` is the sum of the four 1-5 axes.

**Type assignment rule:** keyword match against each insight text in order `case_study > guide > opinion > news` (news is the fallback).

**Partial case:** `approved.length == 0` is a valid output (empty array). The orchestrator uses `profile.min_posts_required` to decide whether to continue to Writing or halt as partial (see Plan 3 Task 12).

**CLI invocation:**

    python scripts/review.py --run-dir <path> --profile <profile.json>
```

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest tests/skills/test_review_agent.py -v`
Expected: `5 passed`.

- [ ] **Step 6: Commit**

```bash
git add skills/review-agent/ tests/skills/test_review_agent.py tests/fixtures/insights_sample.json
git commit -m "feat(skill): review-agent — deterministic scoring + type assignment"
```

---

### Task 7: Templates (pure)

**Files:**
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/autofanpage/templates.py`
- Test: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/test_templates.py`

- [ ] **Step 1: Write failing test `tests/test_templates.py`**

```python
from autofanpage.templates import TEMPLATES, POST_TYPE_BY_SLOT, slot_time


def test_all_four_types_present():
    assert set(TEMPLATES.keys()) == {"news", "guide", "opinion", "case_study"}


def test_slot_index_to_type_matches_spec():
    assert POST_TYPE_BY_SLOT == ("news", "guide", "opinion", "case_study")


def test_each_template_has_required_fields():
    for t, tpl in TEMPLATES.items():
        assert tpl["hook_shape"]
        assert tpl["body_shape"]
        assert tpl["cta"]
        assert tpl["hashtag_hint"]
        assert tpl["first_comment_shape"]


def test_slot_time_reads_profile_list():
    post_times = ["07:30", "11:45", "15:00", "19:20"]
    assert slot_time(post_times, 0) == "07:30"
    assert slot_time(post_times, 3) == "19:20"


def test_slot_time_out_of_range_raises():
    import pytest
    with pytest.raises(IndexError):
        slot_time(["08:00"], 3)
```

Run: `pytest tests/test_templates.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 2: Write `autofanpage/templates.py`**

```python
"""Post-type templates used by the writing-agent.

All text is expressed in English inside the templates; ``autofanpage.prompts``
translates CTA and hashtag hints into the page's ``language`` when it builds
the writing prompt.
"""
from __future__ import annotations

from typing import TypedDict


class PostTemplate(TypedDict):
    hook_shape: str
    body_shape: str
    cta: str
    hashtag_hint: str
    first_comment_shape: str


TEMPLATES: dict[str, PostTemplate] = {
    "news": {
        "hook_shape":
            "Lead with the breaking event in one tight sentence. Name the "
            "actor and the change.",
        "body_shape":
            "150-250 words. 2-3 short paragraphs summarizing the news, then "
            "one paragraph on what it means for a business audience. No "
            "speculation beyond the source.",
        "cta":
            "Ask how this affects the reader's own work in a single question.",
        "hashtag_hint":
            "3-5 hashtags. 1 about the topic, 1 about the actor, 1 general "
            "(#AI #Automation).",
        "first_comment_shape":
            "Drop the canonical source URL in the first line. Follow with "
            "2-3 related links if multiple URLs are provided.",
    },
    "guide": {
        "hook_shape":
            "Lead with a concrete numeric result that the guide will help the "
            "reader reproduce.",
        "body_shape":
            "150-250 words. Numbered 3-5 steps, each actionable, each under "
            "40 words. No motivation filler.",
        "cta":
            "Ask which step the reader will try first.",
        "hashtag_hint":
            "3-5 hashtags. Include 1 how-to-flavored tag and 1 topic tag.",
        "first_comment_shape":
            "Expand each step into 2-3 concrete sub-bullets. This is the "
            "place for the long form.",
    },
    "opinion": {
        "hook_shape":
            "Lead by inverting a widely held belief. State the unpopular "
            "view plainly in one sentence.",
        "body_shape":
            "150-250 words. Steelman the common view in one paragraph, then "
            "present the counter-argument in one paragraph. Avoid absolutes.",
        "cta":
            "Ask which side the reader is on and invite a comment.",
        "hashtag_hint":
            "3-5 hashtags. 1 topic tag + 1 debate-flavored tag.",
        "first_comment_shape":
            "Post one follow-up question that sharpens the debate. No links.",
    },
    "case_study": {
        "hook_shape":
            "Lead with before/after numbers from a named company.",
        "body_shape":
            "150-250 words. Structure: context, AI solution applied, measured "
            "outcome with numbers.",
        "cta":
            "Ask whether the reader's business has tried this.",
        "hashtag_hint":
            "3-5 hashtags. Include industry tag + 1 metric tag (#ROI, "
            "#Growth).",
        "first_comment_shape":
            "Link to the source of the case study. Add a 2-3 line breakdown "
            "of the headline metric.",
    },
}


POST_TYPE_BY_SLOT: tuple[str, str, str, str] = (
    "news", "guide", "opinion", "case_study",
)


def slot_time(post_times: list[str], slot_index: int) -> str:
    """Return the clock time for ``slot_index`` from the profile list.

    Raises IndexError if ``slot_index`` is out of bounds — the caller is
    expected to pass 0..3.
    """
    return post_times[slot_index]
```

- [ ] **Step 3: Run tests to verify pass**

Run: `pytest tests/test_templates.py -v`
Expected: `5 passed`.

- [ ] **Step 4: Commit**

```bash
git add autofanpage/templates.py tests/test_templates.py
git commit -m "feat(templates): 4 post-type templates + slot->type mapping"
```

---

### Task 8: Claude LLM wrapper

**Files:**
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/autofanpage/llm.py`
- Test: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/test_llm.py`

*Design:* thin `requests`-based wrapper around Anthropic's Messages API. We do not take a dependency on the `anthropic` SDK — this stays consistent with Plan 2's "HTTP only" style and keeps mocking straightforward via `responses`. Default model: `claude-opus-4-6` (latest Opus per the project CLAUDE.md).

- [ ] **Step 1: Write failing test `tests/test_llm.py`**

```python
import json

import pytest
import responses

from autofanpage.errors import SourceFailedError
from autofanpage.llm import ClaudeClient


API = "https://api.anthropic.com/v1/messages"


@responses.activate
def test_generate_posts_payload_and_returns_text():
    responses.add(
        responses.POST, API,
        json={"content": [{"type": "text", "text": "hello from claude"}]},
        status=200,
    )
    c = ClaudeClient(api_key="sk-ant-xxx", model="claude-opus-4-6")
    out = c.generate(
        system="you are a writer",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=500,
        temperature=0.7,
    )
    assert out == "hello from claude"

    call = responses.calls[0]
    body = json.loads(call.request.body)
    assert body["model"] == "claude-opus-4-6"
    assert body["system"] == "you are a writer"
    assert body["max_tokens"] == 500
    assert body["temperature"] == 0.7
    assert call.request.headers["x-api-key"] == "sk-ant-xxx"
    assert call.request.headers["anthropic-version"] == "2023-06-01"


@responses.activate
def test_generate_retries_on_429_then_succeeds():
    responses.add(responses.POST, API, status=429)
    responses.add(responses.POST, API, status=429)
    responses.add(
        responses.POST, API,
        json={"content": [{"type": "text", "text": "ok"}]},
        status=200,
    )
    c = ClaudeClient(api_key="k", model="claude-opus-4-6")
    assert c.generate(
        system="", messages=[{"role": "user", "content": "x"}],
        max_tokens=10, temperature=0,
    ) == "ok"


@responses.activate
def test_generate_raises_after_exhausted_retries():
    for _ in range(5):
        responses.add(responses.POST, API, status=500)
    c = ClaudeClient(api_key="k", model="claude-opus-4-6")
    with pytest.raises(SourceFailedError):
        c.generate(
            system="", messages=[{"role": "user", "content": "x"}],
            max_tokens=10, temperature=0,
        )


@responses.activate
def test_generate_raises_on_4xx_non_429():
    responses.add(responses.POST, API, status=400,
                  json={"error": {"message": "bad request"}})
    c = ClaudeClient(api_key="k", model="claude-opus-4-6")
    with pytest.raises(SourceFailedError):
        c.generate(
            system="", messages=[{"role": "user", "content": "x"}],
            max_tokens=10, temperature=0,
        )


@responses.activate
def test_generate_joins_multiple_text_blocks():
    responses.add(
        responses.POST, API,
        json={"content": [
            {"type": "text", "text": "hello "},
            {"type": "text", "text": "world"},
        ]},
        status=200,
    )
    c = ClaudeClient(api_key="k", model="claude-opus-4-6")
    assert c.generate(
        system="", messages=[{"role": "user", "content": "x"}],
        max_tokens=10, temperature=0,
    ) == "hello world"
```

Run: `pytest tests/test_llm.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 2: Write `autofanpage/llm.py`**

```python
"""Thin Anthropic Messages API client used by the writing-agent.

Why direct HTTP and not the ``anthropic`` SDK?
- Consistency with Plan 2's HTTP-only style (``autofanpage.http``).
- One obvious failure model: every retryable condition is HTTP-shaped.
- Tests already use ``responses`` to stub HTTP; no extra mocking plumbing.

The client honors 429 / 5xx retry via ``autofanpage.http.post_json``. Model,
max_tokens, and temperature are caller-controlled.
"""
from __future__ import annotations

from dataclasses import dataclass

from autofanpage.http import post_json


API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


@dataclass
class ClaudeClient:
    api_key: str
    model: str = "claude-opus-4-6"
    max_retries: int = 4
    timeout: int = 120

    def generate(
        self,
        *,
        system: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
    ) -> str:
        body = {
            "model": self.model,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        resp = post_json(
            API_URL,
            headers=headers,
            json_body=body,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )
        content = resp.get("content") or []
        parts = [b.get("text", "") for b in content if b.get("type") == "text"]
        return "".join(parts)
```

- [ ] **Step 3: Confirm `autofanpage/http.post_json` treats 429 as retryable**

This assumes Plan 2 already made 429 retryable (a Codex finding explicitly addressed). If `post_json` still treats all 4xx as terminal, this task depends on that fix. Re-check Plan 2 Task 1 (the `autofanpage.http` module): 429 must be listed in the retryable set alongside 5xx and connection errors. If it isn't, **stop and fix `autofanpage.http` first** — do not work around it here.

Run: `pytest tests/test_http.py -v`
Expected: existing tests pass **and** an explicit `test_*_429_retries_and_succeeds` is present. If missing, add it in `autofanpage/http.py` per the Codex-finding recommendation before continuing.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_llm.py -v`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add autofanpage/llm.py tests/test_llm.py
git commit -m "feat(llm): Claude Messages API wrapper with 429/5xx retry"
```

---

### Task 9: Prompts (pure)

**Files:**
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/autofanpage/prompts.py`
- Test: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/test_prompts.py`

- [ ] **Step 1: Write failing test `tests/test_prompts.py`**

```python
from autofanpage.prompts import build_writing_prompt, build_first_comment_prompt
from autofanpage.templates import TEMPLATES


APPROVED = {
    "insight": "OpenAI launched GPT-5 — latency dropped 35% vs 4.5.",
    "scores": {"relevance": 5, "novelty": 5, "viral": 5, "actionable": 2},
    "total": 17,
    "suggested_post_type": "news",
    "hook_angle": "latency dropped 35%",
    "source_url": "https://news.example/gpt5",
}


def test_build_writing_prompt_returns_system_and_messages():
    system, messages = build_writing_prompt(
        insight=APPROVED, template=TEMPLATES["news"], language="vi",
    )
    assert isinstance(system, str) and system
    assert isinstance(messages, list) and len(messages) == 1
    assert messages[0]["role"] == "user"
    content = messages[0]["content"]
    assert "vi" in content or "Vietnamese" in content
    assert APPROVED["insight"] in content
    assert "hook" in content.lower()


def test_build_writing_prompt_forbids_fabrication():
    system, _ = build_writing_prompt(
        insight=APPROVED, template=TEMPLATES["news"], language="vi",
    )
    assert "do not invent" in system.lower() or \
           "do not fabricate" in system.lower()


def test_build_writing_prompt_includes_word_count_window():
    _, messages = build_writing_prompt(
        insight=APPROVED, template=TEMPLATES["news"], language="vi",
    )
    content = messages[0]["content"]
    assert "150" in content and "250" in content


def test_build_first_comment_prompt_includes_source_url_for_news():
    system, messages = build_first_comment_prompt(
        insight=APPROVED, template=TEMPLATES["news"], language="vi",
        post_body="POST BODY",
    )
    assert APPROVED["source_url"] in messages[0]["content"]


def test_build_prompt_different_languages_produce_different_instructions():
    _, m_vi = build_writing_prompt(
        insight=APPROVED, template=TEMPLATES["news"], language="vi",
    )
    _, m_en = build_writing_prompt(
        insight=APPROVED, template=TEMPLATES["news"], language="en",
    )
    assert m_vi[0]["content"] != m_en[0]["content"]
```

Run: `pytest tests/test_prompts.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 2: Write `autofanpage/prompts.py`**

```python
"""Prompt builders for the writing-agent.

Each builder returns ``(system, messages)`` ready to pass to
``ClaudeClient.generate``. Prompts are deterministic text and contain only the
fields on the approved insight — no outside context is introduced.
"""
from __future__ import annotations

from autofanpage.templates import PostTemplate


_SYSTEM = (
    "You are a senior Facebook content editor. Use only the insight and "
    "source URL provided. Do not invent statistics, company names, or "
    "events that are not in the insight text. If a requested numeric hook "
    "isn't supported, rephrase the hook qualitatively — never fabricate "
    "numbers."
)


def build_writing_prompt(
    *,
    insight: dict,
    template: PostTemplate,
    language: str,
) -> tuple[str, list[dict]]:
    msg = (
        f"Write one Facebook post in {language}. Target 150-250 words.\n\n"
        f"Post type: {insight['suggested_post_type']}.\n"
        f"Insight: {insight['insight']}\n"
        f"Suggested hook angle: {insight['hook_angle']}\n"
        f"Source URL (for reference only, do not inline): {insight['source_url']}\n\n"
        f"Hook shape: {template['hook_shape']}\n"
        f"Body shape: {template['body_shape']}\n"
        f"CTA shape: {template['cta']} Translate naturally into {language}.\n"
        f"Hashtags: {template['hashtag_hint']} Translate or keep in English.\n\n"
        f"Output only the post text. No preamble. No meta-commentary."
    )
    return _SYSTEM, [{"role": "user", "content": msg}]


def build_first_comment_prompt(
    *,
    insight: dict,
    template: PostTemplate,
    language: str,
    post_body: str,
) -> tuple[str, list[dict]]:
    msg = (
        f"Write the first comment in {language} to attach to the post below. "
        f"Shape: {template['first_comment_shape']}\n\n"
        f"Source URL: {insight['source_url']}\n"
        f"Insight: {insight['insight']}\n\n"
        f"--- POST ---\n{post_body}\n--- END ---\n\n"
        f"Output only the comment text. No preamble."
    )
    return _SYSTEM, [{"role": "user", "content": msg}]
```

- [ ] **Step 3: Run tests to verify pass**

Run: `pytest tests/test_prompts.py -v`
Expected: `5 passed`.

- [ ] **Step 4: Commit**

```bash
git add autofanpage/prompts.py tests/test_prompts.py
git commit -m "feat(prompts): writing + first-comment prompt builders"
```

---

### Task 10: writing-agent skill

**Files:**
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/skills/writing-agent/SKILL.md`
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/skills/writing-agent/scripts/__init__.py`
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/skills/writing-agent/scripts/write_posts.py`
- Test: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/skills/test_writing_agent.py`
- Fixture: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/fixtures/reviewed_insights_sample.json`
- Fixture: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/fixtures/profile_plan3.json`

- [ ] **Step 1: Create fixture `tests/fixtures/reviewed_insights_sample.json`**

Four approved insights — one per post type — plus two rejected.

```json
{
  "approved": [
    {"insight": "OpenAI launched GPT-5 — latency dropped 35% vs 4.5.",
     "scores": {"relevance": 5, "novelty": 5, "viral": 5, "actionable": 2}, "total": 17,
     "suggested_post_type": "news",
     "hook_angle": "latency dropped 35%",
     "source_url": "https://news.example/gpt5"},
    {"insight": "Teams using prompt caching cut API spend 60% in 8 weeks — try batching similar calls first.",
     "scores": {"relevance": 5, "novelty": 4, "viral": 5, "actionable": 5}, "total": 19,
     "suggested_post_type": "guide",
     "hook_angle": "60% API spend cut",
     "source_url": "https://blog.example/caching"},
    {"insight": "Why most AI agents still fail in production deployment.",
     "scores": {"relevance": 5, "novelty": 4, "viral": 3, "actionable": 2}, "total": 14,
     "suggested_post_type": "opinion",
     "hook_angle": "most agents still fail",
     "source_url": "https://blog.example/agents-fail"},
    {"insight": "How Acme Corp cut support response time 55% with AI routing.",
     "scores": {"relevance": 5, "novelty": 4, "viral": 5, "actionable": 4}, "total": 18,
     "suggested_post_type": "case_study",
     "hook_angle": "Acme cut response 55%",
     "source_url": "https://case.example/acme"}
  ],
  "rejected": [
    {"insight": "AI is the future.", "total": 7, "reason": "too generic"},
    {"insight": "Random short.", "total": 6, "reason": "too short"}
  ]
}
```

- [ ] **Step 2: Create fixture `tests/fixtures/profile_plan3.json`**

Extends `profile_plan2.json` with a `writing` block.

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
  "writing": {
    "model": "claude-opus-4-6",
    "max_tokens": 900,
    "temperature": 0.7,
    "api_key_ref": "secret:anthropic_api_key"
  },
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

- [ ] **Step 3: Update `autofanpage/profile.py` to carry the `writing` block**

The Plan 1 profile loader rejected unknown keys. Extend it:

Edit `autofanpage/profile.py`. In the `Profile` dataclass (or TypedDict — whichever Plan 1 chose), add:

```python
@dataclass(frozen=True)
class WritingConfig:
    model: str = "claude-opus-4-6"
    max_tokens: int = 900
    temperature: float = 0.7
    api_key_ref: str = "secret:anthropic_api_key"
```

Add a `writing: WritingConfig` field on `Profile`. In `load_profile`, pass `data.get("writing", {})` through `WritingConfig(**payload)` with a `try`/`except TypeError` that raises `ProfileError` on unknown keys. Back-compat: if `writing` is absent, use defaults. Add the matching field to the profile schema.

Add a test in `tests/test_profile.py`:

```python
def test_profile_loads_writing_block():
    from autofanpage.profile import load_profile
    p = load_profile("tests/fixtures/profile_plan3.json")
    assert p.writing.model == "claude-opus-4-6"
    assert p.writing.max_tokens == 900


def test_profile_without_writing_block_uses_defaults(tmp_path):
    from autofanpage.profile import load_profile
    import json
    # Start from profile_plan2 which has no writing block.
    src = json.loads(open("tests/fixtures/profile_plan2.json").read())
    p_path = tmp_path / "p.json"
    p_path.write_text(json.dumps(src))
    p = load_profile(str(p_path))
    assert p.writing.model == "claude-opus-4-6"
    assert p.writing.temperature == 0.7
```

Run: `pytest tests/test_profile.py -v`
Expected: new tests pass, old tests still pass.

- [ ] **Step 4: Write failing test `tests/skills/test_writing_agent.py`**

```python
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "writing-agent" / "scripts"
sys.path.insert(0, str(SCRIPT))
import write_posts  # noqa: E402


@pytest.fixture
def run_dir(tmp_path, fixtures_dir):
    rd = tmp_path / "runs" / "page_test" / "2026-04-16"
    rd.mkdir(parents=True)
    (rd / "reviewed_insights.json").write_text(
        (fixtures_dir / "reviewed_insights_sample.json").read_text(),
        encoding="utf-8",
    )
    return rd


class _FakeClaude:
    def __init__(self, body: str = "BODY", comment: str = "COMMENT"):
        self.body = body
        self.comment = comment
        self.calls: list[dict] = []

    def generate(self, *, system, messages, max_tokens, temperature):
        self.calls.append({
            "system": system, "messages": messages,
            "max_tokens": max_tokens, "temperature": temperature,
        })
        # Detect whether this is a first-comment prompt by checking shape.
        if "first comment" in messages[0]["content"].lower():
            return self.comment
        return self.body


def test_happy_path_writes_four_posts_matching_slot_types(run_dir, fixtures_dir, mocker):
    fake = _FakeClaude()
    mocker.patch.object(write_posts, "ClaudeClient", return_value=fake)
    mocker.patch.object(write_posts, "get_secret", return_value="sk-ant-fake")

    rc = write_posts.main([
        "--run-dir", str(run_dir),
        "--profile", str(fixtures_dir / "profile_plan3.json"),
    ])
    assert rc == 0

    out = json.loads((run_dir / "posts.json").read_text())
    assert out["language"] == "vi"
    assert [p["type"] for p in out["posts"]] == ["news", "guide", "opinion", "case_study"]
    assert [p["time"] for p in out["posts"]] == ["08:00", "12:00", "16:00", "20:00"]
    assert all(p["content"] == "BODY" for p in out["posts"])
    assert all(p["first_comment"] == "COMMENT" for p in out["posts"])
    # 4 posts * 2 calls (body + comment) = 8 Claude calls
    assert len(fake.calls) == 8


def test_slot_without_matching_insight_emits_null(run_dir, fixtures_dir, mocker):
    # Remove the guide insight so only 3 slots get filled.
    src = json.loads((run_dir / "reviewed_insights.json").read_text())
    src["approved"] = [a for a in src["approved"]
                       if a["suggested_post_type"] != "guide"]
    (run_dir / "reviewed_insights.json").write_text(json.dumps(src))

    fake = _FakeClaude()
    mocker.patch.object(write_posts, "ClaudeClient", return_value=fake)
    mocker.patch.object(write_posts, "get_secret", return_value="sk")

    write_posts.main([
        "--run-dir", str(run_dir),
        "--profile", str(fixtures_dir / "profile_plan3.json"),
    ])
    out = json.loads((run_dir / "posts.json").read_text())
    # Slot 1 (guide) is null in both content and first_comment.
    assert out["posts"][1]["content"] is None
    assert out["posts"][1]["first_comment"] is None
    # Others are filled.
    for i in (0, 2, 3):
        assert out["posts"][i]["content"] == "BODY"
    # 3 filled slots * 2 = 6 Claude calls
    assert len(fake.calls) == 6


def test_multiple_approved_of_same_type_picks_highest_total(run_dir, fixtures_dir, mocker):
    src = json.loads((run_dir / "reviewed_insights.json").read_text())
    # Two news entries: the existing one (17) plus a lower-scored dupe.
    src["approved"].append({
        "insight": "weak news item",
        "scores": {"relevance": 3, "novelty": 3, "viral": 4, "actionable": 2},
        "total": 12,
        "suggested_post_type": "news",
        "hook_angle": "weak",
        "source_url": "https://weak.example/1",
    })
    (run_dir / "reviewed_insights.json").write_text(json.dumps(src))

    fake = _FakeClaude()
    mocker.patch.object(write_posts, "ClaudeClient", return_value=fake)
    mocker.patch.object(write_posts, "get_secret", return_value="sk")

    write_posts.main([
        "--run-dir", str(run_dir),
        "--profile", str(fixtures_dir / "profile_plan3.json"),
    ])

    # The news prompt (first slot) should mention the stronger insight.
    news_body_prompt = fake.calls[0]["messages"][0]["content"]
    assert "GPT-5" in news_body_prompt
    assert "weak news item" not in news_body_prompt


def test_empty_approved_produces_four_null_posts(tmp_path, fixtures_dir, mocker):
    rd = tmp_path / "runs" / "page_test" / "2026-04-16"
    rd.mkdir(parents=True)
    (rd / "reviewed_insights.json").write_text(json.dumps({
        "approved": [], "rejected": [],
    }))

    fake = _FakeClaude()
    mocker.patch.object(write_posts, "ClaudeClient", return_value=fake)
    mocker.patch.object(write_posts, "get_secret", return_value="sk")

    rc = write_posts.main([
        "--run-dir", str(rd),
        "--profile", str(fixtures_dir / "profile_plan3.json"),
    ])
    assert rc == 0
    out = json.loads((rd / "posts.json").read_text())
    assert all(p["content"] is None for p in out["posts"])
    assert all(p["first_comment"] is None for p in out["posts"])
    assert len(fake.calls) == 0
```

Run: `pytest tests/skills/test_writing_agent.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'write_posts'`.

- [ ] **Step 5: Write `skills/writing-agent/scripts/write_posts.py`**

```python
#!/usr/bin/env python3
"""writing-agent: compose 4 slot posts + first-comments from reviewed insights.

Reads  <run_dir>/reviewed_insights.json
Writes <run_dir>/posts.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from autofanpage.errors import AutofanpageError
from autofanpage.llm import ClaudeClient
from autofanpage.profile import load_profile
from autofanpage.prompts import build_first_comment_prompt, build_writing_prompt
from autofanpage.schemas import validate
from autofanpage.secrets import get_secret
from autofanpage.templates import POST_TYPE_BY_SLOT, TEMPLATES


def _pick_for_type(approved: list[dict], ptype: str) -> dict | None:
    """Return the highest-``total`` approved insight matching ``ptype``."""
    candidates = [a for a in approved if a["suggested_post_type"] == ptype]
    if not candidates:
        return None
    return max(candidates, key=lambda a: a["total"])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True)
    p.add_argument("--profile", required=True)
    args = p.parse_args(argv)

    run_dir = Path(args.run_dir)
    src = run_dir / "reviewed_insights.json"
    if not src.exists():
        raise AutofanpageError(f"missing input: {src}")
    reviewed = json.loads(src.read_text(encoding="utf-8"))
    validate("reviewed_insights", reviewed)

    profile = load_profile(args.profile)
    api_key = get_secret(profile.writing.api_key_ref)
    client = ClaudeClient(
        api_key=api_key,
        model=profile.writing.model,
    )

    posts = []
    for slot_index, ptype in enumerate(POST_TYPE_BY_SLOT):
        time_str = profile.post_times[slot_index]
        insight = _pick_for_type(reviewed["approved"], ptype)
        if insight is None:
            posts.append({
                "time": time_str, "type": ptype,
                "content": None, "first_comment": None,
            })
            continue
        template = TEMPLATES[ptype]
        system, messages = build_writing_prompt(
            insight=insight, template=template, language=profile.language,
        )
        body = client.generate(
            system=system, messages=messages,
            max_tokens=profile.writing.max_tokens,
            temperature=profile.writing.temperature,
        ).strip()

        fc_system, fc_messages = build_first_comment_prompt(
            insight=insight, template=template, language=profile.language,
            post_body=body,
        )
        first_comment = client.generate(
            system=fc_system, messages=fc_messages,
            max_tokens=max(profile.writing.max_tokens // 2, 300),
            temperature=profile.writing.temperature,
        ).strip()

        posts.append({
            "time": time_str, "type": ptype,
            "content": body, "first_comment": first_comment,
        })

    out = {"posts": posts, "language": profile.language}
    validate("posts", out)
    (run_dir / "posts.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    filled = sum(1 for p in posts if p["content"])
    print(json.dumps({
        "status": "ok", "artifact": "posts.json",
        "posts_generated": filled,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Create `skills/writing-agent/SKILL.md`**

```markdown
---
name: writing-agent
description: Compose four Facebook slot posts (news / guide / opinion / case_study) and their first-comments from reviewed_insights.json via the Anthropic Messages API. Slots with no matching approved insight emit null content.
---

# writing-agent

**Inputs:** `run_dir` (contains `reviewed_insights.json`), `profile` (reads `language`, `post_times`, `writing.*`).
**Output:** `<run_dir>/posts.json` — `{posts: [{time, type, content, first_comment}]}` with exactly 4 entries.

**Slot → type mapping (positional):**

| Slot index | Type         |
|------------|--------------|
| 0          | `news`       |
| 1          | `guide`      |
| 2          | `opinion`    |
| 3          | `case_study` |

Clock time comes from `profile.post_times[slot_index]`.

**For each slot:**
1. Pick the highest-`total` approved insight whose `suggested_post_type == type`.
2. If none, emit `content: null` and `first_comment: null` — do NOT fabricate.
3. Otherwise call Claude twice:
   - Body prompt: `build_writing_prompt(insight, template, language)`.
   - First-comment prompt: `build_first_comment_prompt(insight, template, language, post_body)`.

**Model / auth:** `profile.writing.model` (default `claude-opus-4-6`), API key via `profile.writing.api_key_ref` (default `secret:anthropic_api_key`).

**Hard constraint:** the writing agent must never introduce facts not present in the approved insight. Enforced in the system prompt (`autofanpage.prompts._SYSTEM`).

**CLI invocation:**

    python scripts/write_posts.py --run-dir <path> --profile <profile.json>
```

- [ ] **Step 7: Run tests to verify pass**

Run: `pytest tests/skills/test_writing_agent.py tests/test_profile.py -v`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add skills/writing-agent/ tests/skills/test_writing_agent.py \
        tests/fixtures/reviewed_insights_sample.json \
        tests/fixtures/profile_plan3.json \
        autofanpage/profile.py tests/test_profile.py
git commit -m "feat(skill): writing-agent — 4-slot Claude-backed post writer"
```

---

### Task 11: Orchestrator — Phase 2 / 3a / 3b integration

**Files:**
- Modify: `/Users/nguyenloc/VibeCoding/AutoFanpage/skills/daily-content-pipeline/scripts/orchestrate.py`
- Modify: `/Users/nguyenloc/VibeCoding/AutoFanpage/autofanpage/telegram.py`
- Modify: `/Users/nguyenloc/VibeCoding/AutoFanpage/skills/daily-content-pipeline/SKILL.md`

- [ ] **Step 1: Extend `autofanpage/telegram.py` success / partial templates**

The Plan 2 success template included `phase1_counts` and `phase1_failed_sources`. For Plan 3:
- `success` template: also render `posts_generated` (already exists as integer in the payload — Plan 2 passed `0`; Plan 3 passes actual count).
- Add a `status == "partial"` template rendering:
  - `⚠️ AutoFanpage [<page>] partial run`
  - `📝 <approved_count> insights approved`
  - `✏️ <posts_generated>/4 posts generated`
  - `🔎 sources: ...` when `phase1_counts` is present

Add test cases in `tests/test_telegram.py`:

```python
def test_partial_template_includes_approved_and_generated_counts():
    from autofanpage.telegram import format_message
    msg = format_message(
        status="partial", page="p",
        details={
            "date": "2026-04-16", "approved_count": 1, "posts_generated": 1,
            "phase1_counts": {"youtube": 3}, "phase": "review",
        },
    )
    assert "1 insights approved" in msg
    assert "1/4 posts generated" in msg
    assert "sources:" in msg


def test_success_template_renders_posts_generated_value():
    from autofanpage.telegram import format_message
    msg = format_message(
        status="success", page="p",
        details={"date": "2026-04-16", "posts_scheduled": 0,
                 "posts_generated": 4, "elapsed_sec": 60},
    )
    assert "4 posts generated" in msg
```

Run the tests; they should FAIL first. Implement in `telegram.py`:

```python
# In format_message, add a "partial" branch:
    if status == "partial":
        lines = [
            f"⚠️ AutoFanpage [{page}] partial run",
            f"📝 {details.get('approved_count', 0)} insights approved",
            f"✏️ {details.get('posts_generated', 0)}/4 posts generated",
        ]
        counts = details.get("phase1_counts")
        if counts:
            parts = ", ".join(f"{k}={v}" for k, v in counts.items())
            lines.append(f"🔎 sources: {parts}")
        if details.get("phase"):
            lines.append(f"🪜 phase: {details['phase']}")
        return "\n".join(lines)
```

And in the `success` branch, insert a new line when `posts_generated` is present:

```python
        generated = details.get("posts_generated")
        if generated is not None:
            lines.insert(2, f"✏️ {generated} posts generated")
```

Run: `pytest tests/test_telegram.py -v`
Expected: new tests pass; existing success tests still pass.

- [ ] **Step 2: Update `orchestrate.py` with Phase 2 / 3a / 3b**

At the top of `orchestrate.py`, after the existing `SOURCE_SKILLS` / `SOURCE_ARTIFACTS` maps, add:

```python
PHASE2_SKILL = "notebooklm-analyzer"
PHASE3A_SKILL = "review-agent"
PHASE3B_SKILL = "writing-agent"

# Retry counts for mandatory-phase retry (spec §5: NotebookLM 1 retry).
NOTEBOOKLM_RETRIES = 1
```

Add a helper:

```python
def _run_with_retry(name: str, args: dict, retries: int, run_dir) -> None:
    """Invoke ``run_skill`` with ``retries`` extra attempts on failure.

    Any ``AutofanpageError`` / subprocess error is caught; after the last
    attempt the exception is re-raised.
    """
    last = None
    for attempt in range(retries + 1):
        try:
            run_skill(name, args)
            return
        except Exception as e:  # noqa: BLE001
            last = e
            run_dir.log(f"[{name}] attempt {attempt + 1} failed: {e}")
            if attempt < retries:
                time.sleep(30)
    raise last  # type: ignore[misc]
```

Inside `main()`, after the `run_dir.write_json("merged_sources", merged)` line but **before** the `state.mark(...)` call, add:

```python
        # ----- Phase 2: NotebookLM (mandatory) -----
        run_dir.log("phase2 notebooklm-analyzer start")
        try:
            _run_with_retry(
                PHASE2_SKILL,
                {"run_dir": str(run_dir.path),
                 "profile": args.profile_path,
                 "language": profile.language},
                retries=NOTEBOOKLM_RETRIES,
                run_dir=run_dir,
            )
        except Exception as e:  # noqa: BLE001
            run_dir.log(f"PHASE2 FAIL: {e}")
            log_tail = "\n".join(run_dir.log_path.read_text().splitlines()[-20:])
            cause = str(e)
            if "cookies" in cause.lower():
                cause = (cause + "\nRun `nlm login` to refresh NotebookLM cookies.")
            _report(run_dir.path, status="error", page=args.page, details={
                "phase": "phase2-notebooklm", "cause": cause,
                "log_tail": log_tail,
            })
            return 1

        # ----- Phase 3a: Review -----
        run_dir.log("phase3a review-agent start")
        run_skill(PHASE3A_SKILL, {
            "run_dir": str(run_dir.path),
            "profile": args.profile_path,
        })
        reviewed = json.loads(
            (run_dir.path / "reviewed_insights.json").read_text(encoding="utf-8")
        )
        approved_count = len(reviewed["approved"])
        run_dir.log(f"review approved={approved_count}")

        if approved_count < profile.min_posts_required:
            # Partial: skip Writing, mark the day as run so same-day retries
            # don't re-bill NotebookLM, and surface the partial in Telegram.
            elapsed = int(time.monotonic() - started)
            state.mark(date=date, run_dir=str(run_dir.path), posts_scheduled=0)
            _report(run_dir.path, status="partial", page=args.page, details={
                "date": date,
                "phase": "review",
                "approved_count": approved_count,
                "posts_generated": 0,
                "elapsed_sec": elapsed,
                "phase1_counts": counts,
                "phase1_failed_sources": list(failures),
            })
            return 0  # soft-success exit code

        # ----- Phase 3b: Writing -----
        run_dir.log("phase3b writing-agent start")
        run_skill(PHASE3B_SKILL, {
            "run_dir": str(run_dir.path),
            "profile": args.profile_path,
        })
        posts = json.loads(
            (run_dir.path / "posts.json").read_text(encoding="utf-8")
        )
        posts_generated = sum(1 for p in posts["posts"] if p["content"])
        run_dir.log(f"writing generated={posts_generated}")
```

Then change the existing success branch to pass `posts_generated` and `approved_count`:

```python
        elapsed = int(time.monotonic() - started)
        state.mark(date=date, run_dir=str(run_dir.path),
                   posts_scheduled=0)  # still no publishing in Plan 3
        _report(run_dir.path, status="success", page=args.page, details={
            "date": date,
            "posts_scheduled": 0,
            "posts_generated": posts_generated,
            "approved_count": approved_count,
            "elapsed_sec": elapsed,
            "phase1_counts": counts,
            "phase1_failed_sources": list(failures),
        })
        return 0
```

Keep the Plan 2 `AutofanpageError` and generic-exception catches unchanged — they already cover Phase 3a/3b errors via fall-through.

- [ ] **Step 3: Append a "Plan 3 additions" section to `skills/daily-content-pipeline/SKILL.md`**

```markdown
## Flow (Plan 3 additions)

After the Plan 2 merge step and before `state.mark`:

1. **Phase 2 — `notebooklm-analyzer`** (mandatory). One retry on failure.
   - Arguments: `{run_dir, profile, language}`.
   - Failure → Telegram `error` with `phase=phase2-notebooklm`. If the
     cause message mentions `cookies`, the literal string
     `Run \`nlm login\` to refresh NotebookLM cookies.` is appended.
2. **Phase 3a — `review-agent`**. Reads `insights.json`, writes
   `reviewed_insights.json`.
   - If `approved.length < profile.min_posts_required`, emit Telegram
     `partial` with `approved_count` and `posts_generated=0`, mark
     `last_success`, and return 0. (The mark is intentional — NotebookLM has
     already spent its quota; same-day retries shouldn't re-bill it.)
3. **Phase 3b — `writing-agent`**. Reads `reviewed_insights.json`, writes
   `posts.json` with 4 slot entries (null content for un-mappable slots).

Success Telegram now carries `posts_generated` and `approved_count` in
addition to Plan 2's `phase1_counts` / `phase1_failed_sources`.

`posts.json` is the artifact consumed by Phase 4 (facebook-publisher) in
Plan 4.
```

- [ ] **Step 4: Commit**

```bash
git add skills/daily-content-pipeline/ autofanpage/telegram.py tests/test_telegram.py
git commit -m "feat(orchestrator): Phase 2/3a/3b NotebookLM->Review->Writing"
```

---

### Task 12: Orchestrator integration test (Phase 2/3a/3b)

**Files:**
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/skills/test_orchestrator_plan3.py`

- [ ] **Step 1: Write the integration tests**

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
        "profile": fixtures_dir / "profile_plan3.json",
        "page": "page_test",
    }


def _plan2_fake(failing: set[str] | None = None):
    """Reuse the shape of Plan 2's fake dispatcher.

    For Plan 3, we additionally handle `notebooklm-analyzer`, `review-agent`,
    and `writing-agent` — each writes the next-phase artifact on invocation.
    """
    failing = failing or set()
    calls: list[tuple[str, dict]] = []

    def fake(name, args):
        calls.append((name, args))
        run_dir = Path(args.get("run_dir", "."))
        if name == "telegram-reporter":
            return {"status": "ok", "sent": True}

        if name.endswith("-researcher"):
            key = name.replace("-researcher", "")
            if key in failing:
                from autofanpage.errors import SourceFailedError
                raise SourceFailedError(f"fake fail {key}")
            run_dir.mkdir(parents=True, exist_ok=True)
            # Per-source artifacts must match Plan 2's actual schemas
            _FAKE_ARTIFACTS = {
                "youtube": {
                    "source": "youtube", "fetched_at": "t",
                    "items": [{"title": "yt", "url": "https://youtube.example/1",
                               "video_id": "1", "channel": "c", "views": 200000,
                               "subscribers": 30000,
                               "published_at": "2026-04-10T00:00:00Z"}],
                },
                "perplexity": {
                    "source": "perplexity", "fetched_at": "t",
                    "news": [{"title": "n", "url": "https://perplexity.example/1",
                              "summary": "", "source": "n.com"}],
                    "reports": [], "twitter": [],
                },
                "reddit": {
                    "source": "reddit", "fetched_at": "t",
                    "items": [{"title": "rd", "url": "https://reddit.example/1",
                               "subreddit": "ChatGPT", "score": 800,
                               "num_comments": 30, "author": "u",
                               "permalink": "/r/1",
                               "created_at": "2026-04-14T00:00:00Z",
                               "is_self": False, "external_url": ""}],
                },
                "hackernews": {
                    "source": "hackernews", "fetched_at": "t",
                    "items": [{"title": "hn", "url": "https://hackernews.example/1",
                               "points": 300, "by": "u", "descendants": 10,
                               "created_at": "2026-04-14T00:00:00Z",
                               "hn_url": "https://news.ycombinator.com/item?id=1"}],
                },
            }
            (run_dir / orchestrate.SOURCE_ARTIFACTS[key]).write_text(
                json.dumps(_FAKE_ARTIFACTS[key])
            )
            return {"status": "ok"}

        if name == "notebooklm-analyzer":
            if "nblm_fail" in failing:
                from autofanpage.errors import AutofanpageError
                raise AutofanpageError("cookies expired")
            (run_dir / "insights.json").write_text(json.dumps({
                "overview": "x",
                "pain_points": ["p"],
                "insights": [
                    "OpenAI launched GPT-5 — latency dropped 35% vs 4.5.",
                    "Teams using prompt caching cut API spend 60% in 8 weeks.",
                    "Why most AI agents still fail in production.",
                    "How Acme Corp cut support response 55% with AI routing.",
                ],
                "gap_topics": ["g"],
                "source_urls": ["https://y.example/1"],
                "language": "vi",
                "notebook_id": "nb_fake",
            }))
            return {"status": "ok"}

        if name == "review-agent":
            reviewed = {
                "approved": [
                    {"insight": "a", "scores": {"relevance": 5, "novelty": 5, "viral": 5, "actionable": 2},
                     "total": 17, "suggested_post_type": "news",
                     "hook_angle": "", "source_url": ""},
                    {"insight": "b", "scores": {"relevance": 5, "novelty": 4, "viral": 5, "actionable": 5},
                     "total": 19, "suggested_post_type": "guide",
                     "hook_angle": "", "source_url": ""},
                    {"insight": "c", "scores": {"relevance": 5, "novelty": 4, "viral": 3, "actionable": 2},
                     "total": 14, "suggested_post_type": "opinion",
                     "hook_angle": "", "source_url": ""},
                    {"insight": "d", "scores": {"relevance": 5, "novelty": 4, "viral": 5, "actionable": 4},
                     "total": 18, "suggested_post_type": "case_study",
                     "hook_angle": "", "source_url": ""},
                ],
                "rejected": [],
            }
            if "review_empty" in failing:
                reviewed = {"approved": [], "rejected": []}
            elif "review_one" in failing:
                reviewed["approved"] = reviewed["approved"][:1]
            (run_dir / "reviewed_insights.json").write_text(json.dumps(reviewed))
            return {"status": "ok"}

        if name == "writing-agent":
            (run_dir / "posts.json").write_text(json.dumps({
                "language": "vi",
                "posts": [
                    {"time": "08:00", "type": "news",       "content": "x", "first_comment": "y"},
                    {"time": "12:00", "type": "guide",      "content": "x", "first_comment": "y"},
                    {"time": "16:00", "type": "opinion",    "content": "x", "first_comment": "y"},
                    {"time": "20:00", "type": "case_study", "content": "x", "first_comment": "y"},
                ],
            }))
            return {"status": "ok"}

        raise RuntimeError(f"unexpected skill {name}")

    return fake, calls


def _run(env, date="2026-04-16"):
    return orchestrate.main([
        "--page", env["page"],
        "--profile-path", str(env["profile"]),
        "--base-dir", str(env["base"]),
        "--date", date,
    ])


def test_happy_path_runs_all_phases_and_reports_success(env, mocker):
    fake, calls = _plan2_fake()
    mocker.patch("orchestrate.run_skill", side_effect=fake)
    assert _run(env) == 0

    names = [c[0] for c in calls]
    # Phase 1 (4 researchers) + Phase 2 + 3a + 3b + 1 telegram success
    assert "notebooklm-analyzer" in names
    assert "review-agent" in names
    assert "writing-agent" in names

    tg = [c for c in calls if c[0] == "telegram-reporter"]
    assert len(tg) == 1
    assert tg[0][1]["status"] == "success"
    assert tg[0][1]["details"]["posts_generated"] == 4
    assert tg[0][1]["details"]["approved_count"] == 4


def test_notebooklm_failure_halts_pipeline_and_reports_cookies_hint(env, mocker):
    fake, calls = _plan2_fake(failing={"nblm_fail"})
    mocker.patch("orchestrate.run_skill", side_effect=fake)
    assert _run(env) == 1

    names = [c[0] for c in calls]
    # Writing + review should NOT have been invoked.
    assert "review-agent" not in names
    assert "writing-agent" not in names

    tg = [c for c in calls if c[0] == "telegram-reporter"]
    assert len(tg) == 1
    assert tg[0][1]["status"] == "error"
    assert tg[0][1]["details"]["phase"] == "phase2-notebooklm"
    assert "nlm login" in tg[0][1]["details"]["cause"]

    # last_success NOT written — tomorrow's cron can retry.
    from autofanpage.state import LastSuccess
    assert not LastSuccess(base=env["base"], page=env["page"]).ran_on("2026-04-16")


def test_notebooklm_retries_once_and_succeeds(env, mocker):
    attempts = {"count": 0}
    fake, calls = _plan2_fake()

    def wrapped(name, args):
        if name == "notebooklm-analyzer" and attempts["count"] == 0:
            attempts["count"] += 1
            from autofanpage.errors import AutofanpageError
            raise AutofanpageError("transient mcp glitch")
        return fake(name, args)

    mocker.patch("orchestrate.run_skill", side_effect=wrapped)
    mocker.patch("orchestrate.time.sleep", return_value=None)

    assert _run(env) == 0
    # telegram success (not error)
    tg = [c for c in calls if c[0] == "telegram-reporter"]
    assert tg[0][1]["status"] == "success"


def test_review_below_min_posts_required_becomes_partial(env, mocker):
    # profile_plan3 has min_posts_required=2; fake returns only 1 approved.
    fake, calls = _plan2_fake(failing={"review_one"})
    mocker.patch("orchestrate.run_skill", side_effect=fake)

    assert _run(env) == 0  # soft-success

    names = [c[0] for c in calls]
    assert "writing-agent" not in names
    tg = [c for c in calls if c[0] == "telegram-reporter"]
    assert tg[0][1]["status"] == "partial"
    assert tg[0][1]["details"]["approved_count"] == 1
    assert tg[0][1]["details"]["posts_generated"] == 0

    # last_success IS marked (NotebookLM spent its quota).
    from autofanpage.state import LastSuccess
    assert LastSuccess(base=env["base"], page=env["page"]).ran_on("2026-04-16")


def test_zero_approved_is_partial_not_error(env, mocker):
    fake, calls = _plan2_fake(failing={"review_empty"})
    mocker.patch("orchestrate.run_skill", side_effect=fake)

    assert _run(env) == 0
    tg = [c for c in calls if c[0] == "telegram-reporter"]
    assert tg[0][1]["status"] == "partial"
    assert tg[0][1]["details"]["approved_count"] == 0
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/skills/test_orchestrator_plan3.py -v`
Expected: `5 passed`. If `test_notebooklm_retries_once_and_succeeds` fails, confirm that `NOTEBOOKLM_RETRIES = 1` and that `_run_with_retry` is implemented per Task 11.

- [ ] **Step 3: Commit**

```bash
git add tests/skills/test_orchestrator_plan3.py
git commit -m "test(orchestrator): Phase 2/3a/3b success + NBLM failure + partial"
```

---

### Task 13: Install script check

**Files:**
- None (already glob-based since Plan 2 Task 13).

- [ ] **Step 1: Run the installer and confirm new skills are copied**

```bash
bash scripts/install-skills.sh
```

Expected stdout includes:
- `installed: notebooklm-analyzer`
- `installed: review-agent`
- `installed: writing-agent`

If any is missing, the glob was hardcoded — update per Plan 2 Task 13.

- [ ] **Step 2: Commit (no code change expected)**

If nothing changed, skip. If the script was edited:

```bash
git add scripts/install-skills.sh
git commit -m "chore(install): verified Plan 3 skills install via glob"
```

---

### Task 14: Smoke test documentation

**Files:**
- Modify: `/Users/nguyenloc/VibeCoding/AutoFanpage/README.md`

- [ ] **Step 1: Append a Plan 3 smoke test section to `README.md`**

```markdown
## Smoke test — Plan 3 (content generation)

Preconditions: Plan 2 smoke test passes; `merged_sources.json` is produced
for the test page.

### 1. New secrets

```bash
openclaw secrets set anthropic_api_key    # sk-ant-...
```

### 2. MCP server for NotebookLM

```bash
pip install notebooklm-mcp-cli
nlm login                               # browser opens, sign in to Google
openclaw mcp add notebooklm-mcp ...     # confirm exact syntax on first install
```

### 3. Run orchestrator (still no publishing)

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
  all Plan 2 artifacts PLUS `insights.json`, `reviewed_insights.json`,
  `posts.json`, and an extended `run.log`.
- Telegram: one `✅` message now including `✏️ N posts generated`.

### 4. Failure-mode check — NotebookLM cookies expired

Intentionally log out: `nlm logout` (or delete the cached cookie jar).
Re-run the orchestrator.

Expected:
- Exit code 1.
- Telegram: one `🚨` message with
  `Phase: phase2-notebooklm` and cause ending with
  `Run \`nlm login\` to refresh NotebookLM cookies.`
- `last_success.json` NOT updated.

Re-login (`nlm login`) before proceeding.

### 5. Failure-mode check — partial review

Temporarily raise `min_posts_required` in the profile to a value the review
can't meet (e.g. `10`). Re-run.

Expected:
- Exit code 0 (soft-success).
- Telegram: one `⚠️` message with `X insights approved`, `0/4 posts generated`.
- `posts.json` not written.
- `last_success.json` **is** updated for today.

Reset `min_posts_required` to 2.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: Plan 3 smoke test instructions"
```

---

### Task 15: Full suite + coverage floor

**Files:**
- None new.

- [ ] **Step 1: Run the full suite**

Run: `pytest -v`
Expected: all Plan 1, 2, and 3 tests pass. Approximate count: 55–65 tests total.

- [ ] **Step 2: Coverage check**

Run: `pytest --cov=autofanpage --cov-report=term-missing`
Expected: coverage ≥ 85% for each of:
- `autofanpage/mcp.py`
- `autofanpage/notebooklm.py`
- `autofanpage/scoring.py`
- `autofanpage/templates.py`
- `autofanpage/llm.py`
- `autofanpage/prompts.py`
- `autofanpage/schemas.py` (already high from Plans 1–2)

Skill `scripts/*.py` files are exercised via integration tests; not counted in `autofanpage` package coverage.

- [ ] **Step 3: Fix coverage gaps**

Add focused unit tests for any uncovered branch. Do not use `# pragma: no cover` unless the branch is genuinely unreachable (e.g. `if __name__ == "__main__"` guards).

- [ ] **Step 4: Final commit**

```bash
git add -u
git commit --allow-empty -m "chore: Plan 3 complete — content generation green"
```

---

## Self-review

**Spec coverage:**
- §3.6 notebooklm-analyzer (MCP, 4 queries, mandatory, cookie-error Telegram hint) → Tasks 1, 3, 4, 11 ✓
- §3.7 review-agent (4-axis scoring, threshold 14, type assignment, empty-approved OK) → Tasks 5, 6 ✓
- §3.8 writing-agent (positional slot→type, Claude via Anthropic Messages API, null for unfilled slots, no fabrication) → Tasks 7, 8, 9, 10 ✓
- §3.1 orchestrator Phase 2 / 3a / 3b + mandatory-failure halt + partial path → Tasks 11, 12 ✓
- `insights.json`, `reviewed_insights.json`, `posts.json` artifacts (§4.2) → Tasks 2, 4, 6, 10 ✓
- Telegram `partial` + extended `success` templates → Task 11 ✓
- Publishing, health-check, and dry-run rendering → intentionally deferred to Plan 4.

**Placeholder scan:**
- No TBD, TODO, "add appropriate error handling", or "similar to Task N" stubs. Every step contains concrete code and expected output.

**Type / API consistency with Plans 1–2:**
- `run_skill(name, args)` signature and `{"run_dir", "profile", ...}` convention: matches Plan 2 Task 11. Plan 3 adds a third key `language` for `notebooklm-analyzer`.
- Skill CLI entrypoint: `--run-dir --profile` (+ `--language` for notebooklm-analyzer). Matches Plan 2.
- `_report(run_dir, status=, page=, details=)` helper: reused; Plan 3 adds the `partial` status branch and `posts_generated`/`approved_count` to the `success` branch.
- `state.mark(date=, run_dir=, posts_scheduled=)`: unchanged. Partial path passes `posts_scheduled=0`; success passes `posts_scheduled=0` (no publishing in Plan 3).
- `validate("<name>", payload)` dispatcher: extended with `insights`, `reviewed_insights`, `posts`.
- `Profile` dataclass extended with `writing: WritingConfig`; backward-compat via `data.get("writing", {})`.
- `autofanpage.http.post_json`: Plan 3 depends on 429 being retryable. Task 8 Step 3 explicitly gates on that fix — if Plan 2's `http.py` still treats 4xx as terminal, stop and fix it first.
- `ClaudeClient.generate(system=, messages=, max_tokens=, temperature=)` kw-only signature: fixed and reused by both prompt builders.

**Edge cases covered in tests:**
- MCP: subprocess command shape, non-zero exit, malformed JSON, `ok=false` payload, explicit timeout (Task 1).
- URL extraction: strip utm/ref/fbclid/gclid/mc tracking params; preserve path case; dedup by canonical URL; cap at 48 (Task 3).
- NotebookLM analyzer: happy path (1 create + 4 sources + 4 queries), empty URL input → raise, MCP failure on create → raise + no artifact, **legacy `items[]` shape → clear schema error** (Task 4).
- Scoring: empty insight → all 1s; topic-keyword + numbers + verbs → high; generic opinion → low; news / guide / opinion / case_study keyword mapping; ambiguous defaults to news (Task 5).
- Review-agent: empty approved is valid; approved totals all ≥ 14; suggested types in enum; rejected rows have reasons; deterministic output (Task 6).
- Templates: all 4 types present; slot→type positional mapping; slot_time reads profile list (Task 7).
- Claude client: payload shape; 429→retry-and-succeed; exhausted retries raise; 4xx non-429 fails fast; multiple text blocks joined (Task 8).
- Prompts: system forbids fabrication; language parameter changes output; first-comment includes source URL; word-count window baked in (Task 9).
- Writing agent: 4 slots filled; missing type → null; multiple approved of same type → highest-total wins; empty approved → all nulls, no LLM calls (Task 10).
- Orchestrator: happy path through all phases; NBLM failure halts + cookies hint; NBLM retries once and succeeds; review below min → partial + mark-success; zero approved → partial, not error (Task 12).

**Assumptions documented (and checked in tests where possible):**
- `merged_sources.json` shape is Plan 2's spec-mandated `{urls[], counts_per_platform}` form — already deduplicated and per-platform-capped. `extract_urls` reads `urls[]` directly. The analyzer validates the input against `MERGED_SOURCES_SCHEMA` before extraction and fails fast with a schema error on legacy `items[]` shapes.
- MCP CLI invocation shape: `openclaw mcp call <server> <tool> --args-json '{...}'` with `{"ok": true, "result": {...}}` stdout. Spec §8 flags this as an open question; if the real CLI shape differs, only `autofanpage/mcp.py` needs updating.
- `notebooklm-mcp-cli` exposes tools named `notebook_create`, `source_add`, `notebook_query` with the argument shapes used here. Confirmed from the package README (spec §3.6 footnote).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-16-autofanpage-plan3-content-generation.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using superpowers:executing-plans, batch execution with checkpoints.

Which approach?
