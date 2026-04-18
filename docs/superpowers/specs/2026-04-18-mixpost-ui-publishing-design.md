# AutoFanpage Mixpost UI Publishing — Design Spec

**Date:** 2026-04-18
**Repo:** `AutoFanpage_codex`
**Scope:** Add a Mixpost UI publishing backend that becomes the default publishing path, while keeping the existing direct Facebook Graph backend as an explicit fallback.

---

## 1. Purpose

The repo currently publishes scheduled Facebook posts directly through the Graph API in:

- `skills/facebook-publisher/scripts/publish.py`
- `autofanpage/facebook.py`

That path does not match the user's current operating model:

- Mixpost is already deployed on a VPS
- the Facebook account/page is already connected inside Mixpost
- Mixpost Free does not expose API tokens, so API integration is not available

The goal is to keep the current pipeline shape intact while changing the publishing adapter:

- `facebook-publisher` remains the publishing skill
- `posts.json` remains the input artifact
- `publish_results.json` remains the output artifact
- the default backend becomes Mixpost UI automation
- the old Graph API path stays available as a fallback option

Non-goals:

- replacing the orchestrator flow
- changing upstream artifacts from review/writing phases
- implementing auto-comment after publish
- depending on Mixpost API tokens

For this phase, `first_comment` is preserved in artifacts but is not published when the Mixpost backend is used.

---

## 2. Existing Context

Today, `skills/facebook-publisher/scripts/publish.py`:

1. loads `posts.json`
2. supports `--dry-run`
3. resolves a Facebook access token from secrets
4. schedules each non-null slot directly with Facebook Graph API
5. optionally creates `first_comment`
6. writes `publish_results.json`

The rest of the pipeline already depends on that stable boundary:

- orchestrator only calls `facebook-publisher`
- success/partial reporting depends on `publish_results.json`
- dry-run behavior already exists and should stay unchanged

That means the correct extension point is inside the existing publishing skill, not in the orchestrator.

The repo also already uses backend switches in profile config, for example on Reddit and Perplexity. Publishing should follow the same pattern.

---

## 3. Proposed Design

### 3.1 Publishing configuration

Extend the profile with a `publishing` block:

```json
{
  "publishing": {
    "backend": "mixpost_ui",
    "mixpost": {
      "base_url": "https://mixpost.34.87.51.15.sslip.io",
      "storage_state_path": "~/.openclaw/autofanpage/mixpost/storage_state.json",
      "headless": true
    }
  }
}
```

Rules:

- allowed `publishing.backend` values:
  - `mixpost_ui`
  - `facebook_graph`
- if `publishing` is omitted, `load_profile()` sets default backend to `mixpost_ui`
- if `publishing.mixpost.headless` is omitted, runtime defaults it to `true`
- `publishing.mixpost.*` is required only when `backend="mixpost_ui"`

This keeps profile-level intent explicit while preserving a clean runtime switch.

### 3.2 Stable skill entrypoint

Keep the current publishing skill and CLI entrypoint:

- `skills/facebook-publisher/scripts/publish.py`

Internally, it becomes a dispatcher:

- `backend="mixpost_ui"` -> create scheduled posts through the Mixpost web UI
- `backend="facebook_graph"` -> keep the current direct Graph API flow

This preserves:

- orchestrator wiring
- existing dry-run path
- success/partial status reporting
- artifact filenames

### 3.3 Mixpost UI backend

Add a new helper module:

- `autofanpage/mixpost.py`

Responsibilities:

- launch a Playwright browser/context using a persisted `storage_state`
- open the configured Mixpost base URL
- verify that the saved session is still authenticated
- navigate to the create-post UI
- select the connected Facebook page/account in Mixpost
- fill the post body from `post["content"]`
- set the scheduled publish date/time based on pipeline slot time
- submit the schedule action
- return enough structured information for `publish_results.json`

The backend must work from the current `posts.json` contract. No upstream rewriting of post content or slot shape is introduced.

### 3.4 Session bootstrap flow

Because the user wants browser-visible login and Mixpost Free has no API token, authentication is handled in two stages:

1. bootstrap step
   - run a dedicated script in visible browser mode
   - the user logs into Mixpost manually once
   - the script saves `storage_state.json`

2. scheduled publishing step
   - reuse the saved session for automated publishing
   - run headless by default, with optional visible mode for debugging

Add a separate script for the bootstrap step, for example:

- `skills/mixpost-login-session/scripts/login.py`

This script is not part of the daily orchestrator. It is an operator setup task used when creating or refreshing the session.

### 3.5 Time mapping

The Mixpost backend must schedule each post for the same logical slot currently used by the pipeline:

- input slot time comes from `posts.json`
- date comes from the skill CLI `--date`
- timezone comes from the page profile

The Mixpost automation should use the profile timezone as the source of truth when filling the schedule UI. If Mixpost UI uses browser-local timezone display, the backend must still compute the intended wall-clock time from profile data and fill the UI consistently.

The existing Graph helper `compute_publish_time()` remains specific to the Graph backend. Mixpost UI should have its own schedule-field mapping helper rather than forcing a fake Graph timestamp through the browser path.

### 3.6 `first_comment` behavior

For `backend="mixpost_ui"`:

- `first_comment` remains present in `posts.json`
- `first_comment` is not posted anywhere
- `publish_results.json` records only publish scheduling results
- logs should state that comment publishing is deferred/not supported on this backend

For `backend="facebook_graph"`:

- current behavior remains unchanged

This keeps the current artifact contract stable while avoiding a fake or half-working comment feature.

### 3.7 `publish_results.json`

Keep the top-level shape compatible with the existing schema:

```json
{
  "page": "page_test",
  "date": "2026-04-18",
  "posts": [
    {
      "time": "08:00",
      "type": "news",
      "post_id": null,
      "comment_id": null,
      "status": 200
    }
  ]
}
```

Compatibility rules:

- `status` remains the source of success/partial accounting
- `post_id` and `comment_id` may remain `null` for Mixpost backend if the UI does not expose a stable Facebook-side id at schedule time
- no schema expansion is required unless a later implementation needs extra fields that the current schema cannot represent

The main requirement is that orchestrator logic continues to count `status == 200` as scheduled success.

---

## 4. File Changes

### 4.1 Existing files to modify

- `autofanpage/profile.py`
  - parse `publishing`
  - set default `publishing.backend = "mixpost_ui"`
  - keep backward compatibility for profiles that do not yet define the block

- `autofanpage/schemas.py`
  - add `publishing` schema
  - validate allowed backend values
  - validate required Mixpost config when selected

- `skills/facebook-publisher/scripts/publish.py`
  - preserve dry-run behavior
  - route publish behavior by backend
  - keep partial-save semantics in `publish_results.json`

### 4.2 New files to add

- `autofanpage/mixpost.py`
  - browser automation helpers for Mixpost UI publishing

- `skills/mixpost-login-session/SKILL.md`
  - operator-facing skill for refreshing Mixpost session state

- `skills/mixpost-login-session/scripts/login.py`
  - visible-browser login bootstrap
  - save Playwright storage state to configured path

Optional:

- a small shared browser helper if it clearly reduces duplication between bootstrap and publish flow

### 4.3 Dependencies

Add Playwright for Python to the repo's dev/runtime dependencies as needed for the chosen implementation path.

The design assumption is Python Playwright, not Selenium, because:

- the repo is already Python-first
- session persistence via storage state is straightforward
- selector waiting and headful/headless switching are reliable

If Playwright browsers need installation in deployment docs, document that in README or operator notes during implementation.

---

## 5. Runtime Behavior

### 5.1 Dry-run

`--dry-run` remains unchanged:

- no Mixpost browser session opened
- no Graph API calls
- `preview.md` written
- `publish_results.json` not written

### 5.2 Resume / idempotency

The current publisher already supports resume through `publish_results.json`.

That behavior should remain backend-agnostic:

- if a slot already has `status == 200`, skip it
- if earlier slots succeeded and a later slot failed, rerun should attempt only the remaining slots

This is important for Mixpost UI too, since browser-driven publishing can fail mid-run due to session expiry or UI drift.

### 5.3 Headless vs visible mode

Default behavior:

- daily scheduled publishing uses `headless = true`

Debug/operator behavior:

- profile or CLI override can allow visible browser runs for troubleshooting

The bootstrap login script should always default to visible mode.

---

## 6. Error Handling

Expected failures for `mixpost_ui`:

- missing `base_url`
  - fail fast during startup

- missing `storage_state_path`
  - fail fast during startup

- session expired / redirected to login
  - fail with a clear operator message
  - recommended remediation: rerun Mixpost login bootstrap and refresh storage state

- connected Facebook page not found in Mixpost UI
  - fail with a clear message identifying account-selection problem

- schedule form submit fails or success confirmation never appears
  - record slot failure
  - persist partial `publish_results.json`

- UI selectors drift because Mixpost version changes
  - fail clearly as backend automation error
  - do not silently mark success

Expected failures for `facebook_graph` remain unchanged.

---

## 7. Testing Strategy

Follow TDD and keep tests focused on stable boundaries.

### 7.1 Profile/schema tests

Update:

- `tests/test_profile.py`
  - omitted `publishing` defaults to `mixpost_ui`
  - explicit `facebook_graph` still loads correctly

- `tests/test_schemas.py`
  - valid `publishing.backend = mixpost_ui`
  - invalid unknown backend rejected
  - missing required `mixpost` config rejected when selected

### 7.2 Publisher routing tests

Update:

- `tests/skills/test_facebook_publisher.py`
  - dry-run remains unchanged
  - Graph backend still passes existing tests
  - new Mixpost backend path writes `publish_results.json`
  - partial Mixpost failure persists succeeded slots
  - rerun skips previously successful slots

### 7.3 Mixpost helper tests

Add:

- `tests/test_mixpost.py`
  - session validation failure path
  - schedule form mapping from `date + time + timezone`
  - successful publish result shaping
  - selector-driven failure surfaces as backend error

These tests should mock Playwright objects rather than depending on a real browser or live Mixpost instance.

### 7.4 Verification set

Minimum verification before calling the change complete:

```bash
python -m pytest \
  tests/test_profile.py \
  tests/test_schemas.py \
  tests/test_mixpost.py \
  tests/skills/test_facebook_publisher.py
```

If the Graph fallback path is touched materially, rerun:

```bash
python -m pytest tests/test_facebook.py
```

---

## 8. Tradeoffs

### Chosen approach: backend switch inside existing publisher

Why:

- smallest blast radius
- preserves orchestrator contract
- keeps dry-run and resume behavior in one place
- supports rollback to Graph API without new orchestration branches

### Rejected approach: new top-level Mixpost-only publishing skill

Rejected because:

- duplicates publish entrypoint behavior
- forces orchestrator changes for little benefit
- spreads publish logic across two top-level skills

### Rejected approach: Mixpost API integration

Rejected because:

- user is on Mixpost Free
- no API token is available
- API path is blocked by product limitations, not just missing implementation

---

## 9. Open Decisions Already Resolved

The following scope decisions are intentionally fixed in this spec:

- default backend is `mixpost_ui`
- Graph API remains available as fallback
- bootstrap authentication is manual login captured into storage state
- daily publishing reuses saved session
- `first_comment` is preserved but not published on Mixpost backend
- no auto-comment implementation is included in this phase

This keeps the first Mixpost integration narrow enough to implement and verify cleanly.
