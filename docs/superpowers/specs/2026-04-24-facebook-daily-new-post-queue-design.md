# AutoFanpage Facebook Daily New-Post Queue — Design Spec

**Date:** 2026-04-24
**Repo:** `AutoFanpage_codex`
**Scope:** Extend the hourly Facebook repost flow so it can choose from multiple source posts instead of only the single latest post. Each run still republishes exactly one post.

---

## 1. Goal

The current hourly repost flow only understands one source artifact:

- `latest_source_post.json`

That design works for "rewrite the newest post only", but it cannot support:

- multiple new posts in the same day
- backlog replay when there are no new posts today
- stable selection across repeated hourly runs

The new goal is:

1. fetch a set of recent source posts from the configured Facebook page
2. choose exactly one source post per run
3. prefer the newest unreposted post from **today** in profile timezone
4. if today has no unreposted source posts, fall back to the newest unreposted backlog post
5. keep writer, image generation, and publisher contracts as stable as possible

Non-goals:

1. publishing multiple posts in one hourly run
2. removing the existing `latest_source_post.json` downstream contract
3. adding a hard retention limit for backlog
4. changing writing/review/image/publisher behavior beyond input selection

---

## 2. User Rules To Preserve

These rules are the source of truth for selection:

1. Each run republishes **one** source post.
2. "Today" is evaluated in `profile.timezone`, currently `Asia/Ho_Chi_Minh`.
3. If there are unreposted source posts whose publish date is today, choose the **newest** of those.
4. If there are no unreposted source posts from today, choose the **newest** unreposted backlog post from previous days.
5. Backlog is unbounded at the product-rule level: if an unreposted post exists on the source page, it stays eligible until it is reposted.

This means the queue is not FIFO. It is a priority rule:

1. today's unreposted posts, newest first
2. older unreposted backlog posts, newest first

---

## 3. Existing Constraints

### 3.1 Current source contract

The current source layer in `autofanpage/sources/facebook_page_latest.py` normalizes one post only.

The fetch prompt for Browser Use explicitly asks for:

- "the newest top-level public post only"

The agent-browser path also returns one normalized object.

### 3.2 Current downstream contract

The writer, image generator, and publisher currently read a single normalized source post from:

- `latest_source_post.json`

This is valuable because it means downstream stages do not need to know how the source set was selected.

### 3.3 Current repost state

`autofanpage/hourly_state.py` stores only one last reposted item:

- `latest_reposted_source.json`

That is enough for single-item dedupe, but not enough to answer:

- has this older post already been reposted?
- which items remain in backlog?

---

## 4. Recommended Approach

Add a **multi-post source artifact plus history-backed selector** while keeping the existing single-post downstream artifact.

In practice:

1. source fetch stage writes `source_posts.json`
2. orchestrator selects one candidate from that list
3. orchestrator writes the selected item to `latest_source_post.json`
4. writer/image/publisher remain unchanged
5. state records repost history for all previously used source posts

This is the lowest-risk extension because it isolates the new complexity in:

1. source enumeration
2. source selection
3. repost-history state

It does not force a redesign of the writer or publisher.

---

## 5. Data Model

### 5.1 New artifact: `source_posts.json`

The source fetch stage should emit a list artifact:

```json
{
  "source_page_url": "https://www.facebook.com/0xSojalSec",
  "backend": "agent_browser",
  "fetched_at": "2026-04-24T17:20:00Z",
  "posts": [
    {
      "source_page_url": "https://www.facebook.com/0xSojalSec",
      "source_post_id": "pfbid-1",
      "source_post_url": "https://www.facebook.com/0xSojalSec/posts/pfbid-1",
      "author": "0xSojalSec",
      "published_at": "2026-04-24T08:15:00+07:00",
      "published_at_resolved": "2026-04-24T08:15:00+07:00",
      "content_text": "post body",
      "media_urls": [],
      "backend": "agent_browser",
      "fetched_at": "2026-04-24T17:20:00Z"
    }
  ]
}
```

Rules:

1. `posts` must contain zero or more normalized items using the same per-post shape as current `latest_source_post.json`, plus `published_at_resolved`.
2. `published_at_resolved` is required and must be either:
   - an ISO-8601 datetime string with timezone offset, or
   - `null` when the fetch layer cannot resolve an absolute publish time
3. `posts` should be sorted newest-first when emitted by the source layer.
4. The source layer may include posts from previous days; selection rules decide what gets reposted.

### 5.2 Keep `latest_source_post.json`

The orchestrator should continue writing:

- `latest_source_post.json`

But now it becomes:

- the selected source post for this run

This preserves compatibility for:

1. `hourly-facebook-writer`
2. `hourly-facebook-image-generator`
3. `facebook-publisher`
4. telegram reporting

### 5.3 New state: repost history

Add a state file such as:

- `state/<page>/reposted_source_posts.json`

Shape:

```json
{
  "items": [
    {
      "source_post_id": "pfbid-1",
      "source_post_url": "https://www.facebook.com/0xSojalSec/posts/pfbid-1",
      "published_at": "2026-04-24T08:15:00+07:00",
      "published_at_resolved": "2026-04-24T08:15:00+07:00",
      "reposted_at": "2026-04-24T09:00:00+07:00",
      "run_dir": "/path/to/run"
    }
  ]
}
```

Rules:

1. Deduplication key prefers `source_post_id`.
2. If `source_post_id` is absent, fall back to `source_post_url`.
3. History stores both raw `published_at` and machine-usable `published_at_resolved`.
4. History is append-only for now.
5. `latest_reposted_source.json` stays as a convenience pointer for the most recent reposted item.

### 5.4 Migration from existing state

This feature replaces single-item dedupe with history-backed dedupe, so rollout must not forget what was already reposted before history existed.

Required migration rule:

1. if `reposted_source_posts.json` does not exist yet
2. and `latest_reposted_source.json` exists
3. bootstrap the history file with that latest pointer as its first item

During the migration window, the implementation may also defensively check both:

1. `reposted_source_posts.json`
2. `latest_reposted_source.json`

but the steady-state source of truth should become:

- `reposted_source_posts.json`

Known rollout limitation:

1. the old system only persisted one pointer in `latest_reposted_source.json`
2. therefore rollout can bootstrap only the most recent already-reposted source post
3. older reposts from before this feature cannot be reconstructed automatically
4. those older posts may reappear as eligible backlog after rollout if the new source scan reaches them

This limitation is acceptable for this phase because the historical repost set does not exist anywhere in the current system.

---

## 6. Selection Logic

Given `source_posts.json` and repost history:

1. Remove any source post already present in repost history.
2. Use `published_at_resolved` as the authoritative selector timestamp.
3. Convert `published_at_resolved` into `profile.timezone`.
4. Partition remaining posts into:
   - `today_posts`
   - `backlog_posts`
5. Sort both partitions newest-first by `published_at_resolved`.
6. Choose:
   - first item of `today_posts` if non-empty
   - otherwise first item of `backlog_posts`
   - otherwise no-op / skip

Posts with `published_at_resolved = null` are not eligible for selection in this phase. They remain in the fetched artifact for observability, but the selector must not guess their day bucket.

### 6.1 Day classification

Day classification must be based on profile timezone, not UTC date.

For `Asia/Ho_Chi_Minh`, a post near midnight UTC may still belong to the next local day. The selector must therefore:

1. use `published_at_resolved`
2. convert to profile timezone
3. compare local calendar date with local "today"

### 6.2 Relative timestamps

Facebook extraction may yield relative timestamps such as:

- `8h`
- `2d`
- `Yesterday`
- `Today`

The selection logic cannot reliably classify "today" vs backlog using raw strings.

Therefore the source normalization layer must produce a machine-usable absolute publish datetime when possible. The concrete contract is:

1. preserve `published_at` for compatibility and visibility
2. add required field `published_at_resolved`
3. when Facebook provides only relative time, resolve it against fetch time in the profile timezone
4. if resolution fails, set `published_at_resolved = null`

If absolute resolution is impossible for a post, the pipeline must not silently misclassify it as "today" or backlog.

---

## 7. Source Fetch Changes

### 7.1 Browser Use backend

Change the Browser Use task prompt from:

- newest top-level public post only

to:

- recent top-level public posts from the page

Expected output becomes an object with `posts: []`.

### 7.2 Agent-browser backend

The agent-browser path should be extended to enumerate multiple recent posts from the page rather than jumping immediately to one detail post.

Recommended behavior:

1. open the page feed
2. collect recent top-level post URLs and visible timestamps
3. normalize each candidate post URL
4. open candidate detail pages as needed to extract full text and metadata
5. continue paging until one of these stop conditions is met:
   - at least one eligible candidate has been found, and every visible newer post has already been classified
   - the backend has positively detected end-of-feed
   - the backend reaches an explicit hard safety cap such as `max_posts_scanned`

The hard cap is an implementation safety limit, not a product rule. If a run stops because of the hard safety cap, the run must record that fact explicitly in logs/artifacts and may not claim backlog exhaustion.

The selector may treat backlog as exhausted only after a positive end-of-feed signal. Conditions such as:

1. DOM stall
2. rate limiting
3. login wall
4. paging control missing unexpectedly

must not be treated as feed exhaustion. They are `partial_search_scope` or another fetch error.

### 7.3 Backlog coverage contract

The source stage may not emit an arbitrary recent window and then treat backlog as exhausted.

Allowed conclusions:

1. `backlog_exhausted` only when the source feed has been exhausted
2. `partial_search_scope` when the run stopped at a hard safety cap before backlog exhaustion could be established

This gives a concrete contract:

1. finding one eligible candidate does not require full feed exhaustion
2. claiming "no eligible post exists" does require full feed exhaustion
3. hitting the hard safety cap always means `partial_search_scope`, never a clean skip

---

## 8. Orchestrator Changes

The hourly orchestrator should change from:

1. fetch one post
2. dedupe against last reposted post
3. write/review/publish

to:

1. fetch recent source posts into `source_posts.json`
2. select one candidate using the day/backlog rules
3. if no candidate exists, write a skip decision and report cleanly
4. write selected candidate into `latest_source_post.json`
5. continue through writer/image/publisher unchanged
6. append selected candidate to repost history on success
7. update `latest_reposted_source.json` pointer

The orchestrator must distinguish between:

1. `skip_no_posts_fetched`
2. `skip_no_eligible_post_after_full_search`
3. `error_partial_search_scope`
4. `error_unresolved_candidate_timestamps`

The third case is not a clean skip. It means the fetch stage stopped early, so the system cannot honestly claim backlog exhaustion.

The fourth case is also not a clean skip. It means the source stage found unreposted candidates, but none of them had a usable `published_at_resolved`, so the selector could not classify or order them honestly.

---

## 9. State Behavior

`LatestRepostedSource` is too narrow for the new requirements. It should become either:

1. a wrapper that manages both:
   - latest pointer
   - repost history

or

2. two separate classes:
   - `LatestRepostedSource`
   - `RepostedSourceHistory`

I recommend option `2` because it keeps responsibilities clear:

1. latest pointer remains a small compatibility helper
2. history handles dedupe membership and append operations

---

## 10. Error Handling

### 10.1 No posts fetched

If `source_posts.json.posts` is empty:

1. write skip decision
2. telegram info status
3. exit `0`

### 10.2 No eligible post after filtering

If the source stage completed a full enough search and all eligible fetched posts are already in repost history:

1. write skip decision
2. telegram info status explaining no unreposted source post exists
3. exit `0`

### 10.3 Partial search scope

If the source stage stops because of a hard safety cap before it can establish whether backlog is exhausted:

1. do not emit the same outcome as "no eligible post exists"
2. write an error or partial-search artifact explaining the cap
3. telegram error status
4. exit non-zero

### 10.4 Ambiguous timestamps

If some posts cannot be resolved to a reliable absolute publish time:

1. do not crash the whole run if at least one selectable candidate exists
2. exclude unresolved posts from selection
3. include enough detail in logs/artifacts to explain why a candidate was not selectable

If fetched unreposted candidates exist but every remaining candidate has `published_at_resolved = null`:

1. do not emit `skip_no_eligible_post_after_full_search`
2. write an artifact explaining that candidate timestamps were unresolved
3. telegram error status
4. exit non-zero as `error_unresolved_candidate_timestamps`

---

## 11. Testing Strategy

Required test coverage:

1. source normalization for multiple posts
2. `web.facebook.com` normalization still works
3. selection picks newest unreposted post from today
4. when today has no eligible post, selection picks newest unreposted backlog post
5. already reposted posts are excluded by history
6. `published_at_resolved` day classification respects `Asia/Ho_Chi_Minh`
7. orchestrator writes `latest_source_post.json` from selected candidate
8. orchestrator skip path works for:
   - zero fetched posts
   - zero eligible posts after full search
9. partial-search scope does not report a false clean skip
10. unresolved timestamps are not selected
11. first run bootstraps repost history from `latest_reposted_source.json`
12. unresolved-only candidates do not report a false clean skip

The end-to-end smoke target remains:

1. fetch recent posts from `0xSojalSec`
2. choose one post under the new rules
3. rewrite it
4. generate image
5. schedule via Mixpost

---

## 12. Files Expected To Change

Primary files:

1. `autofanpage/agent_browser.py`
2. `autofanpage/sources/facebook_page_latest.py`
3. `autofanpage/hourly_state.py`
4. `autofanpage/schemas.py`
5. `skills/facebook-page-latest-researcher/scripts/fetch_latest_post.py`
6. `skills/hourly-facebook-repost-pipeline/scripts/orchestrate.py`

Tests:

1. `tests/sources/test_facebook_page_latest.py`
2. `tests/test_hourly_state.py`
3. `tests/test_schemas.py`
4. `tests/skills/test_facebook_page_latest_researcher.py`
5. `tests/skills/test_hourly_facebook_repost_pipeline.py`

---

## 13. Recommendation

Proceed with:

1. new `source_posts.json` artifact
2. absolute timestamp resolution support
3. repost history state
4. orchestrator-side single-item selection

This is the smallest design that satisfies the user rules without rewriting the downstream repost pipeline.
