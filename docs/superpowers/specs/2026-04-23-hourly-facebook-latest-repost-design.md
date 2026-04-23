# AutoFanpage Hourly Facebook Latest Repost — Design Spec

**Date:** 2026-04-23
**Repo:** `AutoFanpage_codex`
**Scope:** Add a separate hourly workflow that fetches the latest public post from `https://www.facebook.com/0xSojalSec`, rewrites it in the `ai5phut` voice, and republishes it to the already configured destination page. The source-fetch layer must support two backends: `browser_use_mcp` and `agent_browser`.

---

## 1. Purpose

The current repo already has a daily pipeline:

- gather multiple research sources
- analyze them with NotebookLM
- review insights
- generate 4 scheduled posts
- publish through `facebook-publisher`

That flow is not the right shape for the requested behavior:

- one upstream source only
- source is a public Facebook page, not news/reddit/youtube
- cadence is every 60 minutes, not once per day
- output is one rewritten post, not 4 daily slots

The goal of this feature is to add a new hourly repost pipeline without breaking the existing daily pipeline.

Required outcomes:

- fetch the newest public post from `0xSojalSec`
- detect whether that source post was already reposted
- rewrite it into the destination page's configured language using `writing.style = "ai5phut"`
- publish exactly one new post when there is a new source item
- skip cleanly when there is no new source post

Non-goals:

- replacing `daily-content-pipeline`
- changing NotebookLM behavior
- scraping comments/reactions from the source page
- backfilling older source posts
- implementing Mixpost publishing in this scope

The existing publisher path remains the one already implemented in this repo. Profiles may still contain extra runtime-only fields such as `publishing`, but this feature does not depend on them.

---

## 2. Existing Context

### 2.1 Current pipeline shape

`skills/daily-content-pipeline/scripts/orchestrate.py` is a once-per-day orchestrator. It:

1. runs Phase 1 research sources
2. requires NotebookLM in Phase 2
3. reviews insights
4. writes 4 fixed slot posts
5. publishes them

It also uses daily idempotency through `state/<page>/last_success.json`, which is unsuitable for a job that must run every hour.

### 2.2 Profile compatibility gap

`autofanpage/profile.py` currently supports:

- `writing.model`
- `writing.max_tokens`
- `writing.temperature`
- `writing.api_key_ref`

It does not support `writing.style`, so runtime profiles like `page_test_ai5phut_live_headless.json` are not loadable as-is.

### 2.3 Source gap

The repo has source skills for:

- YouTube
- Perplexity/Tavily
- Reddit
- Hacker News

It has no Phase 1 source that can read the latest post from a public Facebook page.

### 2.4 Available browser infrastructure

The environment already has working access to Browser Use cloud through MCP/mcporter, and the user explicitly wants that path supported.

The user also asked for an additional option using `agent-browser`. That option should exist as an alternative fetch backend for the same source contract.

---

## 3. Proposed Design

### 3.1 Keep the daily pipeline untouched

Do not retrofit the new behavior into `daily-content-pipeline`.

Instead add a separate skill, for example:

- `skills/hourly-facebook-repost-pipeline/scripts/orchestrate.py`

This keeps the boundary clear:

- daily pipeline remains a 4-post research flow
- hourly pipeline becomes a 1-post source-rewrite-republish flow

This avoids coupling hourly repost behavior to NotebookLM, daily idempotency, or the 4-slot review logic.

### 3.2 New source type: `facebook_page_latest`

Add a new profile source block:

```json
{
  "sources": {
    "facebook_page_latest": {
      "enabled": true,
      "backend": "browser_use_mcp",
      "page_url": "https://www.facebook.com/0xSojalSec"
    }
  }
}
```

Rules:

- allowed backends:
  - `browser_use_mcp`
  - `agent_browser`
- if the source exists and `backend` is omitted, default to `browser_use_mcp`
- `page_url` is required
- this source is intended for public pages; no login is required for the upstream fetch

The rest of the existing Phase 1 sources may be disabled in the hourly profile.

### 3.3 Source artifact contract

Both backends must produce the same artifact:

- `latest_source_post.json`

Shape:

```json
{
  "source_page_url": "https://www.facebook.com/0xSojalSec",
  "source_post_id": "1234567890",
  "source_post_url": "https://www.facebook.com/0xSojalSec/posts/1234567890",
  "author": "0xSojalSec",
  "published_at": "2026-04-23T09:15:00Z",
  "content_text": "post body text",
  "media_urls": [],
  "backend": "browser_use_mcp",
  "fetched_at": "2026-04-23T10:00:00Z"
}
```

Contract rules:

- `source_post_id` is preferred when extractable
- if `source_post_id` is not extractable, `source_post_url` becomes the dedupe key
- `content_text` is required and must be non-empty after trimming
- `media_urls` may be empty
- the artifact represents one latest post only, never an array

### 3.4 Fetch backend: `browser_use_mcp`

Implementation shape:

- use the existing Browser Use MCP client path
- call `browser-use.run_session(...)`
- pass a strict `output_schema`
- instruct the agent to:
  - open the page URL
  - wait for the public feed to render
  - identify the newest top-level post
  - extract the structured fields required by `latest_source_post.json`

Why this is the default:

- the environment already has the MCP endpoint configured
- structured output is a better fit for Python pipeline code than shelling out to a separate CLI
- it avoids DOM parsing logic in repo code

### 3.5 Fetch backend: `agent_browser`

Implementation shape:

- shell out to the `agent-browser` CLI
- use it as a browser automation transport only
- run a deterministic extract step that returns the same structured output as `browser_use_mcp`

The exact command sequence is an implementation detail, but it must satisfy two constraints:

1. it must fail clearly when `agent-browser` is unavailable on `PATH`
2. it must return a normalized artifact matching `latest_source_post.json`

This backend is an operator-selected alternative, not the default.

### 3.6 Hourly idempotency and skip behavior

Daily idempotency via `last_success.json` is not usable here.

Add a new hourly state file:

- `state/<page>/latest_reposted_source.json`

Shape:

```json
{
  "source_post_id": "1234567890",
  "source_post_url": "https://www.facebook.com/0xSojalSec/posts/1234567890",
  "published_at": "2026-04-23T09:15:00Z",
  "reposted_at": "2026-04-23T10:01:12Z",
  "run_dir": "..."
}
```

Decision logic:

- if the latest fetched source post matches the saved source marker, skip publishing
- if it differs, continue
- if no marker exists yet, continue

Skip is a normal success path:

- exit code `0`
- write a small decision artifact, for example `repost_decision.json`
- optionally emit an info Telegram report

### 3.7 Timestamped hourly run directories

The existing `RunDir.create(base, page, date)` writes one directory per day, which would collide for hourly runs.

Add a separate hourly run-dir convention, for example:

- `runs/<page>/hourly/2026-04-23T10-00-00Z/`

This run dir stores:

- `latest_source_post.json`
- `repost_decision.json`
- `posts.json`
- `publish_results.json`
- `run.log`

The daily run-dir layout stays unchanged.

### 3.8 Writing style support

Extend `WritingConfig` with:

```json
{
  "writing": {
    "style": "ai5phut"
  }
}
```

Rules:

- `style` is optional
- initial supported preset:
  - `ai5phut`
- if omitted, prompt behavior remains current default

`ai5phut` in this scope means:

- short Vietnamese paragraphs
- direct, benefit-first opening
- fast and clear wording
- one direct CTA near the end
- no invented facts beyond the extracted source content

This is a prompt preset, not a separate model choice. The existing writer model configuration remains in `writing.model`.

### 3.9 New rewriting step

Do not reuse the existing `writing-agent` directly. It expects:

- `reviewed_insights.json`
- 4 post slots
- post-type rotation

That contract does not fit hourly reposting.

Add a new skill, for example:

- `skills/hourly-facebook-writer/scripts/write_repost.py`

Input:

- `latest_source_post.json`
- page profile

Output:

- a schema-compatible `posts.json` with exactly one filled post and three null placeholders

Example shape:

```json
{
  "language": "vi",
  "posts": [
    {
      "time": "10:15",
      "type": "news",
      "content": "rewritten ai5phut-style post",
      "first_comment": null
    },
    {"time": "00:00", "type": "guide", "content": null, "first_comment": null},
    {"time": "00:00", "type": "opinion", "content": null, "first_comment": null},
    {"time": "00:00", "type": "case_study", "content": null, "first_comment": null}
  ]
}
```

Rationale:

- this preserves compatibility with the existing `posts` schema and the current `facebook-publisher`
- only one slot is active
- the active post should be scheduled a few minutes ahead of now so the existing Graph publish constraints can still be satisfied

The prompt should be source-faithful:

- preserve the core claim of the source post
- rewrite voice and structure into `ai5phut`
- avoid fabricating numbers, names, or events
- output only the final post body

### 3.10 Publishing path

The hourly pipeline reuses the existing `facebook-publisher` skill and `publish_results.json` contract.

This design intentionally does **not** add new publishing adapters. The hourly pipeline's job is:

1. fetch source
2. dedupe
3. rewrite into one active post slot
4. call the existing publisher

That keeps this feature focused on the source + rewrite workflow.

### 3.11 Reporting

Reuse `telegram-reporter` where possible.

Expected statuses:

- `success`
  - one new source post rewritten and published
- `info`
  - no new source post; skip
- `error`
  - source fetch failed
  - source extract returned empty content
  - writer failed
  - publisher failed

Suggested success details:

- source page
- source post URL
- source published time
- fetch backend used
- posts scheduled: `1`

---

## 4. File Changes

### 4.1 Existing files to modify

- `autofanpage/profile.py`
  - add `writing.style`
  - default `sources.facebook_page_latest.backend = "browser_use_mcp"` when present

- `autofanpage/schemas.py`
  - allow `sources.facebook_page_latest`
  - validate allowed backend values
  - allow `writing.style`

- `autofanpage/prompts.py`
  - add style-aware repost prompt builder or shared helpers for `ai5phut`

### 4.2 New modules / skills

- `autofanpage/hourly_state.py`
  - read/write latest reposted source marker

- `autofanpage/hourly_run_dir.py` or an equivalent extension to run-dir handling
  - timestamped hourly artifact directories

- `autofanpage/sources/facebook_page_latest.py`
  - backend-neutral fetch interface
  - normalization into `latest_source_post.json`

- `skills/facebook-page-latest-researcher/scripts/fetch_latest_post.py`
  - source skill entrypoint

- `skills/hourly-facebook-writer/scripts/write_repost.py`
  - rewrite latest source post into one active post slot

- `skills/hourly-facebook-repost-pipeline/scripts/orchestrate.py`
  - end-to-end hourly flow

Optional:

- `autofanpage/agent_browser.py`
  - small helper for the CLI wrapper path if that keeps subprocess logic out of the skill script

### 4.3 Profile examples / fixtures

Add or update one profile fixture showing:

- `writing.style = "ai5phut"`
- only `facebook_page_latest` enabled
- page URL = `https://www.facebook.com/0xSojalSec`
- all other sources disabled

This fixture can be derived from the runtime `page_test_ai5phut_live_headless.json`, but the repo-owned test fixture should be minimal and focused on the new hourly flow.

---

## 5. Error Handling

### 5.1 Source fetch failures

- MCP failure / Browser Use error
- `agent-browser` missing from `PATH`
- Facebook page markup did not yield a usable top post

Behavior:

- treat as source failure
- write useful error text to `run.log`
- send Telegram `error`
- do not update hourly dedupe state

### 5.2 Empty or unusable source content

If extraction returns a post object but `content_text` is empty after trimming:

- fail the run as `error`
- do not attempt rewrite

This avoids publishing vague or fabricated rewrite output.

### 5.3 Duplicate detection

If the newest source post matches the latest reposted state:

- write `repost_decision.json = {"action": "skip_duplicate", ...}`
- return success/info
- do not call writer or publisher

### 5.4 Writer failures

If the LLM returns empty output or malformed `posts.json`:

- fail the run
- do not mark the source as reposted

### 5.5 Publish failures

If publish fails:

- preserve the run artifacts
- do not update `latest_reposted_source.json`
- allow the next hourly run to retry the same source post

This is important: source dedupe should reflect completed publish, not just completed rewrite.

---

## 6. Testing Strategy

### 6.1 Profile / schema tests

- `tests/test_profile.py`
  - `writing.style` loads correctly
  - `facebook_page_latest.backend` defaults to `browser_use_mcp`

- `tests/test_schemas.py`
  - accept valid `facebook_page_latest`
  - reject unknown backend values

### 6.2 Source normalization tests

- `tests/sources/test_facebook_page_latest.py`
  - normalize a structured Browser Use payload
  - normalize an `agent-browser` payload
  - reject empty `content_text`
  - dedupe key preference: `source_post_id` then `source_post_url`

### 6.3 Writer tests

- `tests/skills/test_hourly_facebook_writer.py`
  - generates one active slot and three null placeholders
  - includes style-aware prompt inputs
  - keeps output schema-valid

### 6.4 Orchestrator tests

- `tests/skills/test_hourly_facebook_repost_pipeline.py`
  - new source post -> writer + publisher called
  - duplicate source post -> writer/publisher skipped
  - publish failure does not mark repost state
  - successful publish updates repost state

### 6.5 Verification expectations

At minimum, implementation should verify:

- focused unit tests for new schema/profile/source/writer/orchestrator behavior
- one dry-run style manual invocation of the hourly pipeline against a test profile

If the local environment lacks `pytest`, that must be called out explicitly in the completion report.

---

## 7. Deployment Shape

The hourly behavior should be driven by cron, not by a long-running loop inside the repo.

Intended invocation pattern:

```bash
openclaw cron add --name "af-hourly-<page>" \
  --cron "0 * * * *" \
  --session isolated \
  --tz "Asia/Ho_Chi_Minh" \
  --message "/hourly_facebook_repost_pipeline page=<name>"
```

This keeps operational behavior consistent with the rest of the system.

---

## 8. Recommendation Summary

Recommended architecture:

1. add a new hourly pipeline skill instead of modifying the daily orchestrator
2. add a new `facebook_page_latest` source with two backends:
   - default `browser_use_mcp`
   - optional `agent_browser`
3. add `writing.style` support with initial preset `ai5phut`
4. reuse the existing publisher by emitting a compatible one-active-slot `posts.json`
5. track hourly dedupe in a dedicated source-post state file

This is the narrowest design that satisfies the requested behavior while minimizing risk to the existing daily automation.
