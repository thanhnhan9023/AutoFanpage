# AutoFanpage Tavily Research Backend — Design Spec

**Date:** 2026-04-18
**Repo:** `AutoFanpage_codex`
**Scope:** Add Tavily as the default backend for the existing Phase 1 research skill currently named `perplexity-researcher`, while keeping Perplexity as a selectable fallback.

---

## 1. Purpose

Replace the current Perplexity-only Phase 1 research implementation with a multi-backend design:

- `sources.perplexity.backend = "tavily" | "perplexity"`
- default backend is `tavily`
- Tavily uses a new secret reference: `secret:tavily_api_key`
- Perplexity remains supported for rollback and compatibility

The downstream pipeline must remain unchanged. In particular:

- the skill name stays `perplexity-researcher`
- the artifact path stays `perplexity_results.json`
- the artifact schema stays `{source, fetched_at, news, reports, twitter}`

This avoids touching merge, review, writing, publishing, and Telegram reporting.

Non-goals:

- renaming `perplexity-researcher`
- introducing a new top-level Tavily-only skill
- changing downstream artifact schemas
- replacing other Phase 1 sources

---

## 2. Existing Context

Today, [skills/perplexity-researcher/scripts/fetch_perplexity.py](../../../skills/perplexity-researcher/scripts/fetch_perplexity.py) performs up to three Perplexity chat-completion calls:

- `sonar-pro` for news
- `sonar` for reports
- optional `sonar-pro` for Twitter/X results

The result is normalized into `perplexity_results.json`, and later phases only depend on that normalized document, not on the upstream provider. That existing boundary is the right place to add a backend switch.

The repo already uses this pattern for Reddit:

- profile/schema-level `backend`
- runtime routing based on the backend value
- a stable downstream artifact contract

Tavily should follow the same model.

---

## 3. Proposed Design

### 3.1 Profile and schema

Extend `sources.perplexity` with:

```json
{
  "enabled": true,
  "backend": "tavily"
}
```

Rules:

- allowed values: `tavily`, `perplexity`
- if `backend` is omitted, `load_profile()` sets it to `tavily`
- invalid values are rejected at schema-validation time

This keeps runtime error handling simple and makes the behavior explicit in tests.

### 3.2 Skill behavior

Keep the existing skill entrypoint and CLI:

- `skills/perplexity-researcher/scripts/fetch_perplexity.py`

Internally, split the provider-specific logic into two paths:

- `backend="perplexity"` -> existing request flow
- `backend="tavily"` -> Tavily search flow

The backend selection happens inside the skill, not in the orchestrator. The orchestrator still sees only one Phase 1 source named `perplexity`.

### 3.3 Tavily query model

The Tavily implementation performs up to three searches per run:

1. `news`
   - query for recent news about the page topic
   - favor recency and general web/news coverage
   - return up to 5 normalized items

2. `reports`
   - query for `report`, `research`, or `whitepaper` about the topic, constrained to recent years
   - return up to 3 normalized items

3. `twitter`
   - run only when `sources.twitter_via_perplexity.enabled == true`
   - query for recent X/Twitter discussion about the topic
   - keep only URLs whose host is `x.com` or `twitter.com`
   - return up to 5 normalized items

The exact Tavily prompt/query text is an implementation detail, but it must be deterministic, provider-appropriate, and sized to the current repo’s limits:

- news limit = 5
- reports limit = 3
- twitter limit = 5

### 3.4 Output contract

The skill continues to emit:

```json
{
  "source": "perplexity",
  "fetched_at": "...",
  "news": [
    {"title": "...", "url": "...", "summary": "...", "source": "..."}
  ],
  "reports": [],
  "twitter": []
}
```

Notes:

- `source` remains `"perplexity"` for compatibility with the current schema and downstream consumers
- the provider used is an internal concern of the skill, not a new downstream contract
- empty result buckets are valid and should still produce a schema-valid artifact

### 3.5 Data mapping

Tavily results are normalized as follows:

- `title` <- result title
- `url` <- result URL
- `summary` <- result content/snippet, trimmed if needed
- `source` <- hostname derived from URL

Normalization rules:

- deduplicate by `url`
- preserve ordering by provider relevance, then truncate to the configured limit
- discard malformed items with no usable URL
- for `twitter`, keep only `x.com` / `twitter.com`

### 3.6 Secrets and configuration

New secret:

- `tavily_api_key`

Selection rules:

- `backend=tavily` -> requires `secret:tavily_api_key`
- `backend=perplexity` -> requires `secret:perplexity_api_key`

Missing required secret is treated as a normal Phase 1 source failure and reported the same way as existing source failures.

---

## 4. File Changes

### 4.1 Existing files to modify

- `autofanpage/profile.py`
  - set default `sources.perplexity.backend = "tavily"`

- `autofanpage/schemas.py`
  - allow `sources.perplexity.backend`
  - restrict values to `tavily | perplexity`

- `skills/perplexity-researcher/scripts/fetch_perplexity.py`
  - branch on backend
  - keep Perplexity path intact
  - add Tavily request path

- optionally `autofanpage/sources/perplexity.py`
  - either keep Perplexity-only helpers there and add Tavily helpers nearby
  - or factor out provider-neutral shaping helpers there if it reduces duplication cleanly

### 4.2 Tests to add or update

- `tests/test_profile.py`
  - default `sources.perplexity.backend == "tavily"` when omitted

- `tests/test_schemas.py`
  - valid `backend=tavily`
  - invalid unknown backend rejected

- `tests/skills/test_perplexity_fetch.py`
  - existing Perplexity path remains green
  - new Tavily-path test covers normalization and output shape

If the Tavily normalization logic grows beyond trivial inline helpers, add a new focused unit test file for that shaping layer.

---

## 5. Error Handling

Expected failure behavior:

- missing `tavily_api_key`
  - skill fails clearly
  - orchestrator records the Perplexity/Tavily source as failed

- Tavily returns zero usable results
  - write a valid artifact with empty arrays
  - let orchestrator decide whether total Phase 1 results are sufficient

- Tavily request/network error
  - surface as a source failure, matching current Perplexity behavior

- invalid backend value
  - fail during profile validation, not during runtime fetch

No new partial-success semantics are introduced beyond the current Phase 1 source-failure handling.

---

## 6. Testing Strategy

Follow TDD:

1. add/adjust tests for schema and profile defaults
2. add a failing skill test for `backend=tavily`
3. implement the smallest code path to make the Tavily test pass
4. rerun existing Perplexity tests to confirm fallback behavior
5. rerun focused Phase 1 tests to ensure artifact compatibility remains intact

Minimum verification set before calling the change complete:

```bash
python -m pytest \
  tests/test_profile.py \
  tests/test_schemas.py \
  tests/skills/test_perplexity_fetch.py
```

If shaping helpers are added:

```bash
python -m pytest tests/skills/test_perplexity_fetch.py
```

---

## 7. Tradeoffs

### Chosen approach: backend switch inside the existing skill

Why:

- smallest downstream blast radius
- no orchestrator changes needed
- clean rollback to Perplexity
- matches the repo’s existing “stable artifact, swappable provider” direction

Rejected alternative: add a new `tavily-researcher` top-level source

Why not:

- would force orchestrator/source-map changes
- would expand the conceptual source graph even though the pipeline still wants one logical “web research” source
- higher regression risk for little gain

---

## 8. Open Questions

There are no blocking design questions left for implementation. The only runtime prerequisite is that the operator must provide:

```bash
openclaw secrets set tavily_api_key
```

Perplexity remains available as fallback if quality or coverage is not sufficient.
