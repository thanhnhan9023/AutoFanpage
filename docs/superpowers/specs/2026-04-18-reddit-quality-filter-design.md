# AutoFanpage Reddit Quality Filter — Design Spec

**Date:** 2026-04-18
**Repo:** `AutoFanpage_codex`
**Scope:** Improve Reddit source quality by filtering low-signal meme/media posts inside `reddit-researcher-apify` before writing `reddit_results.json`.

---

## 1. Purpose

The current Reddit Phase 1 source returns the highest-score posts from `r/ChatGPT`, but those posts are often image/video memes with weak informational value. They pass through merge cleanly and NotebookLM ingests them, yet they reduce the quality of downstream insights and generated Facebook posts.

The goal of this change is to keep Reddit as a useful signal source while making it more content-weighted:

- prefer posts with stronger discussion value
- still allow up to 1-2 viral media posts if they are unusually strong
- keep the downstream artifact shape unchanged

Non-goals:

- changing orchestrator behavior
- changing `merged_sources.json` schema
- introducing model-based filtering in Phase 1
- removing Reddit as a source entirely

---

## 2. Existing Context

Today, [skills/reddit-researcher-apify/scripts/fetch_reddit_apify.py](../../../skills/reddit-researcher-apify/scripts/fetch_reddit_apify.py) does the following per subreddit:

1. fetch up to `max(top_per_sub * 3, 15)` posts from the Apify Reddit actor
2. normalize each post into the repo’s Reddit schema
3. filter only by `min_score`
4. sort by raw `score`
5. keep the first `top_per_sub`

This makes the source cheap and deterministic, but too score-heavy. On `r/ChatGPT`, that pulls in posts like:

- very short meme titles (`lol`)
- image/video posts with high engagement but little reusable substance
- low-context viral posts that are poor inputs for NotebookLM

The best place to fix this is inside the Reddit skill itself, because:

- `reddit_results.json` becomes cleaner from the start
- merge and later phases remain unchanged
- tests can stay narrow and deterministic

---

## 3. Proposed Design

### 3.1 Filtering boundary

The filtering logic lives inside `reddit-researcher-apify`, after normalization and before truncating to `top_per_sub`.

The runtime contract remains:

```json
{
  "source": "reddit",
  "fetched_at": "...",
  "items": [...]
}
```

No downstream file format changes are introduced.

### 3.2 Post classification

Each normalized Reddit post is classified into one of two buckets:

- `substantive`
- `media_heavy`

`media_heavy` means the post is primarily a video, image, or gallery style item, recognized by `external_url` host/path patterns such as:

- `v.redd.it`
- `i.redd.it`
- `reddit.com/gallery`

Everything else is treated as potentially substantive, including:

- self posts
- external article links
- Reddit discussion threads whose primary value appears to be in the comments or title framing

This is intentionally conservative. A post is not penalized only for being popular; it is penalized when its format is usually low-signal for the pipeline’s downstream use.

### 3.3 Quality scoring

Each normalized post receives a temporary `quality_score` used only inside the fetcher for ranking.

The score is a weighted combination of:

- raw Reddit `score`
- `num_comments`
- title quality
- post format

Rules:

- positive signals:
  - higher `num_comments`
  - title length above a small floor
  - enough words to suggest context, not just a punchline
  - self post or non-media external link

- negative signals:
  - `media_heavy`
  - very short titles
  - very low-word titles

The score should stay simple and mechanical. It does not need to be statistically calibrated; it only needs to rank clearly better discussion posts above meme-like posts in common `r/ChatGPT` batches.

### 3.4 Low-signal title heuristic

Title quality is intentionally simple:

- treat titles below a small character floor as low-signal
- treat titles with too few words as low-signal

Examples likely to be penalized:

- `lol`
- `7 years ago`

Examples likely to survive:

- `These videos are hilarious, but why does this work?`
- titles that frame a concrete behavior, question, product change, or user problem

This heuristic should not try to infer semantic meaning; it should only down-rank obvious low-context titles.

### 3.5 Selection strategy

Selection happens in two passes per subreddit:

1. build all normalized posts that pass `min_score`
2. sort by `quality_score` descending
3. fill result slots with `substantive` posts first
4. allow `media_heavy` posts only after that, subject to a quota cap
5. stop at `top_per_sub`

Default media cap for v1:

- maximum `2` media-heavy posts per subreddit

This preserves the user’s requested balanced behavior:

- Reddit stays interesting and can still carry a standout viral post
- the batch is no longer dominated by memes when better discussion items exist

### 3.6 Configuration surface

This first version should avoid expanding the profile schema unless implementation forces it.

Defaults remain internal constants in the fetcher:

- title minimum characters
- title minimum words
- media-heavy quota cap

Reasoning:

- the user asked for better default behavior, not a new tuning surface
- keeping these as code constants makes the initial change smaller and easier to test

If later tuning is needed, these values can be exposed through `sources.reddit` in a separate spec.

---

## 4. Implementation Plan Surface

### 4.1 File changes

Primary file:

- `skills/reddit-researcher-apify/scripts/fetch_reddit_apify.py`

Likely additions:

- helper to detect media-heavy posts
- helper to detect low-signal titles
- helper to compute `quality_score`
- helper to select top posts with a media quota

No changes are expected in:

- orchestrator
- merge
- NotebookLM analyzer
- review agent

### 4.2 Data shape discipline

The fetcher may compute temporary fields during ranking, but those fields must not leak into the persisted artifact.

`reddit_results.json` must continue to contain only the validated schema fields already expected by the repo.

---

## 5. Test Coverage

Tests should focus on ranking behavior, not on implementation details.

Update or extend:

- `tests/skills/test_reddit_fetch_apify.py`

Required cases:

1. `substantive` discussion post outranks meme/media post even when the meme has somewhat higher raw score
2. low-signal short-title media posts are pushed down or excluded from the final `top_per_sub`
3. media-heavy posts are still allowed up to the quota cap when there are not enough stronger substantive posts

These tests should assert the final ordered titles in `reddit_results.json`, because that is the observable behavior that matters to the pipeline.

---

## 6. Error Handling and Risk

The change should not create new hard-failure paths.

Expected behavior:

- if the actor returns usable results, ranking always completes
- if all posts are media-heavy, the quota still allows a small number through
- if all titles are weak, the fetcher still returns the best available posts rather than failing

Primary risk:

- over-filtering and accidentally discarding too many Reddit posts

Mitigation:

- no hard drop based only on media type
- media items are down-ranked and capped, not fully banned
- first implementation keeps thresholds small and conservative

---

## 7. Recommendation

Implement the quality-score approach with a small media quota cap inside `reddit-researcher-apify`.

This is the lowest-risk way to improve source quality without changing the rest of the pipeline. It keeps the repo’s current boundaries intact, improves NotebookLM input quality immediately, and remains easy to test and tune later.
