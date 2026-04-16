# AutoFanpage on OpenClaw — Design Spec

**Date:** 2026-04-15
**Target platform:** [OpenClaw](https://openclaw.ai/) (self-hosted personal AI assistant)
**Source workflow:** `workflow.md` (AutoFanpage AI content automation pipeline)

---

## 1. Purpose

Port the 6-phase AutoFanpage content-automation pipeline described in `workflow.md` onto the OpenClaw agent platform, with the following adaptations agreed during brainstorming:

- **Multi-page** support: one physical Facebook Page per configuration profile, each with its own topic, language, tokens, and cron schedule.
- **Configurable language** per page (Vietnamese, English, or any other the writing model supports).
- **4 posts per day** at **08:00, 12:00, 16:00, 20:00** (local page timezone), replacing the original 3-post schedule.
- Four post types mapped 1:1 to the four slots: `news`, `guide`, `opinion`, `case_study`.
- **NotebookLM is mandatory** for Phase 2 analysis — no fallback. Any NotebookLM failure halts the run and notifies the user via Telegram.
- **Telegram reporting** uses the OpenClaw-native Telegram channel (already paired to the gateway) rather than a custom bot token.
- **Perplexity** is accessed via the Perplexity HTTP API using an API key (the workflow requires two distinct model calls — `sonar-pro` for news and `sonar` academic for reports — which maps cleanly to the HTTP endpoint).

Non-goals for this spec: automated A/B testing of content, engagement dashboards, image generation, and automatic FB access-token refresh (the user rotates tokens manually when Telegram alerts fire).

---

## 2. Architecture Overview

### 2.1 Why OpenClaw fits

OpenClaw documentation (`docs.openclaw.ai/llms.txt`) confirms the primitives we need:

| Primitive | Docs reference | How we use it |
|---|---|---|
| AgentSkills-compatible skill folders | "Skill Creation" section | Each phase = one skill |
| Cron jobs | `automation/cron-jobs.md` | `openclaw cron add --cron "0 6 * * *" --session isolated --message "/daily_content_pipeline page=<name>"` |
| Sub-agents / Agent Send | "Inter-Skill Communication" section | Orchestrator skill invokes each phase as a sub-agent |
| MCP support | CLI `openclaw mcp` | Register `notebooklm-mcp` for Phase 2 |
| Telegram channel (native) | "Chat Integrations" section | Reporter sends to the user's paired Telegram |
| Secrets management | `gateway/secrets.md` | FB / YouTube / Perplexity keys stored as `secret:<name>` references |
| Isolated sessions | Cron job `--session isolated` flag | Each daily run gets a clean session |

### 2.2 File layout

**Skill package (the code we ship):**

```
~/.openclaw/skills/autofanpage/
├── daily-content-pipeline/        # Orchestrator skill (top-level, user-invocable)
│   └── SKILL.md
├── youtube-researcher/
│   └── SKILL.md
├── perplexity-researcher/
│   └── SKILL.md
├── reddit-researcher/
│   └── SKILL.md
├── hackernews-researcher/
│   └── SKILL.md
├── notebooklm-analyzer/
│   └── SKILL.md
├── review-agent/
│   └── SKILL.md
├── writing-agent/
│   └── SKILL.md
├── facebook-publisher/
│   └── SKILL.md
├── telegram-reporter/
│   └── SKILL.md
└── autofanpage-health-check/      # Second cron: verifies daily runs succeeded
    └── SKILL.md
```

**Runtime data (not checked into the skill package):**

```
~/.openclaw/autofanpage/
├── pages/                          # One JSON profile per Facebook Page
│   ├── page_vn_ai.json
│   └── page_en_biz.json
├── runs/                           # Per-page, per-date artifacts
│   └── <page>/<YYYY-MM-DD>/
│       ├── youtube_results.json       # YouTube
│       ├── perplexity_results.json    # Perplexity (news + reports + tweets)
│       ├── reddit_results.json         # Reddit
│       ├── hackernews_results.json     # Hacker News
│       ├── merged_sources.json         # Unified URL list fed to NotebookLM
│       ├── insights.json
│       ├── reviewed_insights.json
│       ├── posts.json
│       ├── publish_results.json
│       └── run.log
└── state/
    └── <page>/last_success.json    # Idempotency marker: last successful date
```

Run directories older than 30 days are purged by `autofanpage-health-check` on each invocation.

### 2.3 Control plane

- **Cron:** one cron job per page, created via `openclaw cron add`. Suggested naming: `af-<page_name>`.
- **Invocation style:** `openclaw cron add --name "af-page_vn_ai" --cron "0 6 * * *" --session isolated --tz Asia/Ho_Chi_Minh --message "/daily_content_pipeline page=page_vn_ai"`.
- **Health cron:** a single `af-health` cron at 09:00 Asia/Ho_Chi_Minh verifies every page has a `last_success.json` entry for the current date and raises a Telegram alert for any that are missing.
- **Secrets:** stored via `openclaw secrets set`; referenced in profiles and skills as `secret:<name>` strings. Never inlined in JSON files or prompts.

### 2.4 Data-flow principle

Every sub-skill **reads JSON input files and writes JSON output files** inside the run directory that the orchestrator passes in as `run_dir`. The orchestrator never holds large payloads in prompt memory — it only passes paths and validates schema after each phase. This enables:

- Independent unit testing of each skill with a fixture run directory.
- Resume-on-failure: if phase 4 fails, phase 1–3 outputs remain on disk; re-running skips them via presence checks.
- Clean audit trail: 30 days of runs available for debugging content quality.

---

## 3. Components (11 skills)

All skills accept the two conventional parameters `run_dir` (path) and `page_profile` (path to profile JSON). Additional parameters are listed per-skill below.

### 3.1 `daily-content-pipeline` (orchestrator)

- **User-invocable:** yes. Slash command: `/daily_content_pipeline page=<name>` (optionally `dry_run=true`).
- **Flow:**
  1. Load `pages/<name>.json`; validate required keys (`page_id`, `access_token_ref`, `topic`, `language`, `post_times`, `timezone`). Halt + Telegram error if invalid.
  2. Compute `today = now(timezone).date()`; `run_dir = runs/<name>/<today>/`. Create if absent.
  3. Idempotency check: if `state/<name>/last_success.json.date == today`, abort, Telegram info "đã chạy".
  4. Kick Phase 1 in parallel via sub-agents (4 branches, all respecting the page profile's `sources` toggles):
     - `youtube-researcher` → `youtube_results.json`
     - `perplexity-researcher` → `perplexity_results.json`
     - `reddit-researcher` → `reddit_results.json`
     - `hackernews-researcher` → `hackernews_results.json`
     Wait for all four. Disabled sources return an empty wrapped artifact immediately (no sub-agent spawned). If **all four** sources return 0 items after retries, halt + Telegram error "no sources found".
  5. Merge step: orchestrator reads all four files, deduplicates by URL, and writes `merged_sources.json` — a unified list of `{url, title, platform, score_or_views, created_at}` capped at `max_sources_per_platform` per platform (default 12, so up to 48 total — well under NotebookLM's 50-source limit).
  6. Phase 2: `notebooklm-analyzer` reads `merged_sources.json`. On failure (after 1 retry), halt + Telegram error (NotebookLM is mandatory).
  7. Phase 3a: `review-agent`. If `approved.length < page_profile.min_posts_required` (default 2), halt Writing+Publisher, Telegram partial.
  8. Phase 3b: `writing-agent`. Produces 0–4 posts depending on how many approved insights mapped to each type.
  9. Phase 4: `facebook-publisher`. In `dry_run` mode, skip Graph API calls and instead render `run_dir/preview.md` and send it via Telegram for human approval.
  10. On success: write `state/<name>/last_success.json`, invoke `telegram-reporter` with `status=success` and the run summary.
- **Schema validation** happens after every phase; any mismatch is treated as that phase having failed (see error matrix §5).

### 3.2 `youtube-researcher`

- **Inputs:** `run_dir`, `topic` (from profile), `api_key_ref=secret:youtube_api`, `filters` (from profile: `youtube_min_views`, `youtube_min_subs`, default 100000 and 10000).
- **Logic:** `GET youtube/v3/search` with `q=<topic>`, `order=viewCount`, `type=video`, `publishedAfter=<today - 7d>`, `maxResults=10`. Post-filter by `viewCount` and `channelSubscriberCount` (latter requires a follow-up `channels.list` call; batch by channel IDs).
- **Output:** `run_dir/youtube_results.json` — object `{source, fetched_at, items}` where each item is `{title, url, video_id, channel, views, published_at}` (plus optional `channel_id` / `subscribers` when available).

### 3.3 `perplexity-researcher`

- **Inputs:** `run_dir`, `topic`, `language`, `api_key_ref=secret:perplexity_api`, `sources.twitter_via_perplexity.enabled` (from profile).
- **Logic:** Three POSTs to `https://api.perplexity.ai/chat/completions`:
  - `sonar-pro` — prompt: "Top 5 {topic} news today, return title/url/summary/source for each." → `type: "news"`
  - `sonar` academic — prompt: "Recent {topic} reports 2025–2026, return title/url/summary/source/key_stats for 3 reports." → `type: "report"`
  - `sonar-pro` — prompt: "Find 5 viral tweets from the past 7 days about {topic} on x.com/twitter.com. Return title/url/summary/source (tweet author) for each. Restrict results to site:x.com OR site:twitter.com." → `type: "tweet"`. Skipped if `sources.twitter_via_perplexity.enabled == false`.
- **Output:** `run_dir/perplexity_results.json` — object `{source, fetched_at, news, reports, twitter}` where each bucket contains `{title, url, summary, source}` items.
- **Rationale for tweets via Perplexity:** the direct X API costs $100+/month and has tight rate limits; Perplexity already indexes public tweets and returns them with URLs at no incremental cost since we hold a Perplexity key anyway.

### 3.4 `reddit-researcher`

- **Inputs:** `run_dir`, `sources.reddit` (from profile: `subreddits`, `min_score`, `time_filter`), `client_id_ref=secret:reddit_client_id`, `client_secret_ref=secret:reddit_client_secret`.
- **Logic:**
  1. Obtain OAuth token via `POST https://www.reddit.com/api/v1/access_token` with `grant_type=client_credentials` (Reddit "script" / "installed" app flow).
  2. For each subreddit in the profile list, `GET https://oauth.reddit.com/r/<sub>/top?t=<time_filter>&limit=25` with a descriptive `User-Agent` (required by Reddit policy, e.g. `openclaw-autofanpage/1.0`).
  3. Filter posts by `score >= min_score`; drop NSFW; keep top N per subreddit (default top 5).
- **Output:** `run_dir/reddit_results.json` — object `{source, fetched_at, items}` where each item is `{title, url, permalink, subreddit, score, num_comments, author, created_at, is_self}`. `url` is the external link if the post is a link post, else `permalink` (full Reddit URL) for self posts.
- **Skip mode:** if `sources.reddit.enabled == false`, write a wrapped object with `items: []` and return immediately (no OAuth call).

### 3.5 `hackernews-researcher`

- **Inputs:** `run_dir`, `topic`, `sources.hackernews` (from profile: `min_points`).
- **Logic:**
  1. `GET https://hacker-news.firebaseio.com/v0/topstories.json` → first 200 story IDs.
  2. Batch-fetch story details (parallel up to 20) via `/v0/item/<id>.json`.
  3. Filter: `score >= min_points` AND created within last 7 days AND title/URL matches topic keywords (simple case-insensitive substring match across the topic words — model-free filter to keep this skill cheap).
  4. Keep top 10 by score.
- **Output:** `run_dir/hackernews_results.json` — object `{source, fetched_at, items}` where each item is `{title, url, points, by, descendants, created_at, hn_url}`. `hn_url` is `https://news.ycombinator.com/item?id=<id>`; `url` is the external link (may equal `hn_url` for Ask-HN posts).
- **Skip mode:** if `sources.hackernews.enabled == false`, write a wrapped object with `items: []` and return immediately.
- **No auth required.**

### 3.6 `notebooklm-analyzer` (MCP-based) — **mandatory phase**

- **Inputs:** `run_dir`, `language`.
- **Depends on:** `notebooklm-mcp-cli` ([jacob-bd/notebooklm-mcp-cli](https://github.com/jacob-bd/notebooklm-mcp-cli)) installed via `pip install notebooklm-mcp-cli` (or `uv tool install notebooklm-mcp-cli`). The package provides both a `nlm` CLI and an MCP server binary named `notebooklm-mcp`. Registered with OpenClaw via `openclaw mcp add notebooklm-mcp` (or equivalent per the OpenClaw `openclaw mcp` CLI — confirm exact syntax on first install).
  - **Official status:** NotebookLM has no first-party Google MCP server (unlike Stitch / Developer Knowledge / Firestore which use `gcloud beta services mcp enable ...`). `notebooklm-mcp-cli` is the most-active community implementation; it uses NotebookLM's undocumented internal APIs, so expect occasional breakage on Google-side changes.
  - **Auth (cookie-based):** user runs `nlm login` once — a browser opens, user signs in to Google, cookies are extracted and cached locally. Cookies typically last 2–4 weeks; when they expire, all `notebooklm-analyzer` runs fail until the user re-runs `nlm login`. This is the failure mode we route to Telegram (see §5).
  - **Rate limit:** ~50 NotebookLM queries/day on the free tier. One page consumes 4 queries/day (Q1–Q4), so one Google account supports ~12 pages comfortably. If scaling beyond that, a separate Google account (with its own `nlm login --profile <name>`) is required per bucket of ~12 pages.
- **Logic:**
  1. Read `run_dir/merged_sources.json` (produced by the orchestrator after Phase 1) for the deduplicated, capped URL list.
  2. Call MCP tool `notebook_create` with `title="AI Research {today}"` → capture `notebook_id`.
  3. For each URL in `merged_sources.json`, call `source_add` with the URL (≤50 total, per NotebookLM limit).
  4. Call `notebook_query` four times (Q1 overview / Q2 pain_points / Q3 insights 5–10 / Q4 gap_topics), all phrased in the profile `language`.
- **Output:** `run_dir/insights.json` — `{overview, pain_points[], insights[], gap_topics[]}`.
- **Failure modes routed to Telegram:**
  - Cookie expired (auth error from any tool call) → halt + Telegram error with exact text "Run `nlm login` to refresh NotebookLM cookies."
  - Rate limit hit (HTTP 429 or equivalent) → halt + Telegram error; next day's cron will likely succeed.
  - Any other failure → 1 retry (30s backoff), then halt + Telegram error with the MCP log tail.

### 3.7 `review-agent`

- **Inputs:** `run_dir/insights.json`, `language`.
- **Logic:** score each raw insight on Relevance / Novelty / Viral / Actionable, each 1–5. Keep where `total ≥ 14`. For each approved insight, assign `suggested_post_type ∈ {news, guide, opinion, case_study}` based on content shape (heuristics described in `review-agent/SKILL.md`) and a `hook_angle` suggestion.
- **Output:** `run_dir/reviewed_insights.json`:
  ```json
  {
    "approved": [
      { "insight": "...", "scores": {"relevance":5,"novelty":4,"viral":4,"actionable":3},
        "total": 16, "suggested_post_type": "news", "hook_angle": "..." }
    ],
    "rejected": [ {"insight": "...", "reason": "..."} ]
  }
  ```
- **Edge:** if `approved.length == 0`, file is still written (empty `approved[]`) and the orchestrator handles the partial case.

### 3.8 `writing-agent`

- **Inputs:** `run_dir/reviewed_insights.json`, `language`, `post_times` (from profile).
- **Hard constraint:** only use facts/quotes from `reviewed_insights.json`. Never invent statistics, never pull outside context. If a slot has no matching insight, emit `content: null` for that slot — do not fabricate.
- **Slot-to-type mapping (by slot index, not clock time):**

  The profile's `post_times` array defines the clock time of each slot. The slot→type mapping is **positional**: slot 0 is always `news`, slot 1 `guide`, slot 2 `opinion`, slot 3 `case_study`, regardless of what clock times the page profile sets. A page can therefore shift its schedule earlier/later without disturbing the type rotation.

  | Slot index | Default clock time | Type | Template |
  |---|---|---|---|
  | 0 | 08:00 | `news` | Hook = breaking event; Body 150–250w summary + impact on the target business audience; CTA = "Bạn nghĩ điều này ảnh hưởng thế nào đến công việc của bạn?"; 3–5 hashtags |
  | 1 | 12:00 | `guide` | Hook = concrete numeric result; Body = 3–5 actionable steps; CTA = "Bạn đã thử bước nào rồi?"; 3–5 hashtags |
  | 2 | 16:00 | `opinion` | Hook = inverted common belief; Body = balanced two-sided argument; CTA = "Bạn ở phía nào? Comment xuống dưới!"; 3–5 hashtags |
  | 3 | 20:00 | `case_study` | Hook = before/after numbers of a real business applying AI; Body = context → AI solution → measured outcome; CTA = "Doanh nghiệp bạn đã thử chưa?"; 3–5 hashtags |

  CTA wording above is the Vietnamese default; the skill translates to the profile's `language` automatically.

- **First comment** per post (avoids FB reach penalty for links in main body):

  | Type | First comment content |
  |---|---|
  | news | Original source URL + a short list of related resources |
  | guide | Full step-by-step expansion of the post's 3–5 steps |
  | opinion | A follow-up question designed to prompt replies |
  | case_study | Source link to the case + measured-outcome breakdown |

- **Output:** `run_dir/posts.json`:
  ```json
  {
    "posts": [
      {"time": "08:00", "type": "news",       "content": "...", "first_comment": "..."},
      {"time": "12:00", "type": "guide",      "content": "...", "first_comment": "..."},
      {"time": "16:00", "type": "opinion",    "content": "...", "first_comment": "..."},
      {"time": "20:00", "type": "case_study", "content": "...", "first_comment": "..."}
    ]
  }
  ```

### 3.9 `facebook-publisher`

- **Inputs:** `run_dir/posts.json`, `page_profile`.
- **Logic per post** (skipping posts whose `content` is `null`):
  1. `POST /v19.0/{page_id}/feed` with `message = content + "\n\n" + hashtags`, `scheduled_publish_time = <unix ts at page timezone, today, post.time>`, `published=false`. Facebook requires `scheduled_publish_time` to be ≥10 minutes in the future and ≤6 months out — if current wall time is already within 10 minutes of `post.time`, shift that post forward by 15 minutes.
  2. Capture returned `post_id`.
  3. `POST /v19.0/{post_id}/comments` with `message = first_comment`. Capture `comment_id`.
  4. Append `{time, type, post_id, comment_id, status}` to `run_dir/publish_results.json` immediately (so partial failures leave a clean record).
- **Idempotency:** before posting, read existing `publish_results.json`; skip any slot whose `status==200` is already recorded (handles resume-after-failure without double-posting).
- **Dry-run mode:** when orchestrator passes `dry_run=true`, skip all Graph API calls, render `run_dir/preview.md` with all four posts formatted, and return to orchestrator so it can send preview via Telegram.
- **Output:** `run_dir/publish_results.json`:
  ```json
  {
    "page": "page_vn_ai",
    "date": "2026-04-15",
    "posts": [
      {"time": "08:00", "type": "news", "post_id": "123_456", "comment_id": "123_789", "status": 200}
    ]
  }
  ```

### 3.10 `telegram-reporter`

- **Inputs:** `status` ∈ `{success, error, partial, info}`, `page`, `details` (dict).
- **Transport:** native OpenClaw Telegram channel. The message goes to whichever Telegram chat the user has paired with their OpenClaw gateway — no bot token in this skill.
- **Templates:**
  - `success`: ✅ + page name + date + N posts scheduled + elapsed seconds
  - `error`: 🚨 + page + failed phase + root cause one-liner + last 20 lines of `run.log`
  - `partial`: ⚠️ + page + what happened (e.g., "Review duyệt 2/4 insights, đăng 2/4 bài") + list of scheduled post_ids
  - `info`: ℹ️ + page + message (used for "already ran today" and dry-run previews)

### 3.11 `autofanpage-health-check`

- **Invocation:** its own cron (`af-health`, daily 09:00 Asia/Ho_Chi_Minh).
- **Logic:** iterate every `pages/*.json`; for each, check `state/<page>/last_success.json.date`. If missing or ≠ today, emit a Telegram alert per page. Also prunes `runs/<page>/<date>/` directories older than 30 days.

---

## 4. Data Contracts

### 4.1 Per-page profile — `pages/<name>.json`

```json
{
  "name": "page_vn_ai",
  "page_id": "123456789",
  "access_token_ref": "secret:fb_page_vn_ai",
  "topic": "AI automation business",
  "language": "vi",
  "post_times": ["08:00", "12:00", "16:00", "20:00"],
  "timezone": "Asia/Ho_Chi_Minh",
  "filters": { "youtube_min_views": 100000, "youtube_min_subs": 10000 },
  "min_posts_required": 2,
  "max_sources_per_platform": 12,
  "sources": {
    "youtube":                  { "enabled": true },
    "perplexity":               { "enabled": true },
    "twitter_via_perplexity":   { "enabled": true },
    "reddit": {
      "enabled": true,
      "subreddits": [
        "ChatGPT",
        "ArtificialIntelligence",
        "artificial",
        "singularity",
        "OpenAI",
        "LocalLLaMA",
        "ClaudeAI",
        "MachineLearning"
      ],
      "min_score": 100,
      "time_filter": "week",
      "top_per_sub": 5
    },
    "hackernews": { "enabled": true, "min_points": 50 }
  }
}
```

`max_sources_per_platform` caps how many URLs each platform contributes to the merged list fed into NotebookLM. With the default 12 × 4 platforms = 48 URLs, we stay under NotebookLM's 50-source limit. Within each platform, top items are ranked by the platform's native score signal (YouTube `viewCount`, Reddit `score`, Hacker News `points`, Perplexity order returned by the API).

`min_posts_required` controls when a run is treated as partial-but-acceptable (continues Writing+Publisher) versus a hard failure (halts and Telegrams error). Default 2.

### 4.2 Intermediate files

- `youtube_results.json` — `{source, fetched_at, items[]}` with YouTube video metadata
- `perplexity_results.json` — `{source, fetched_at, news[], reports[], twitter[]}` with parsed Perplexity citations
- `reddit_results.json` — `{source, fetched_at, items[]}` with flattened Reddit posts
- `hackernews_results.json` — `{source, fetched_at, items[]}` with filtered Hacker News stories
- `insights.json` — NotebookLM output (`overview`, `pain_points`, `insights`, `gap_topics`)
- `reviewed_insights.json` — `approved[]` + `rejected[]` with scores and type suggestions
- `posts.json` — 4-slot posts array with `time`, `type`, `content`, `first_comment`

### 4.3 New artifacts

- `merged_sources.json` — deduplicated, capped URL list fed to NotebookLM. Shape: `{ "urls": [{"url", "title", "platform", "score_or_views", "created_at"}], "counts_per_platform": {"youtube": N, "perplexity": N, "reddit": N, "hackernews": N} }`
- `publish_results.json` — audit record of what made it to FB (see §3.9)
- `state/<page>/last_success.json` — idempotency marker: `{ "date": "...", "run_dir": "...", "posts_scheduled": N, "completed_at": "..." }`
- `preview.md` (dry-run only) — rendered markdown preview of all four posts

### 4.4 Validation

Every file is validated against a JSON-schema fragment embedded in the consumer skill (required keys, value types, enum checks on `type`/`status`). Schema mismatch = phase failure = halt + Telegram error.

---

## 5. Error Handling

| Category | Example cause | Behavior |
|---|---|---|
| Config invalid | `pages/<name>.json` missing key, malformed `post_times` | Halt immediately; Telegram error; no run_dir created |
| Already ran today | `last_success.json.date == today` | Abort gracefully; Telegram `info` |
| YouTube fail | API quota, revoked key, network | 2 retries (30s backoff) → write empty wrapped `youtube_results.json` and CONTINUE; Telegram warning |
| Perplexity fail | API down, rate limit | 2 retries (30s backoff) → write empty wrapped `perplexity_results.json` and CONTINUE; Telegram warning |
| Reddit fail | OAuth rejected, subreddit banned, 429 | 2 retries (30s backoff) → write empty wrapped `reddit_results.json` and CONTINUE; Telegram warning |
| Hacker News fail | Firebase transient error | 2 retries (30s backoff) → write empty wrapped `hackernews_results.json` and CONTINUE; Telegram warning |
| All Phase 1 sources empty | Every source failed or returned 0 items | Halt before NotebookLM; Telegram error "no sources available, cannot analyze" |
| NotebookLM cookie expired | `nlm login` cookies older than ~2–4 weeks | Halt + Telegram error with instruction "Run `nlm login` to refresh NotebookLM cookies." (Mandatory phase; no auto-refresh.) |
| NotebookLM rate limit | Free-tier limit ~50 queries/day hit | Halt + Telegram error; next day's cron should succeed automatically |
| NotebookLM other fail | MCP server down, notebook create fail, Q-timeout | 1 retry (30s backoff) → halt + Telegram error with MCP log tail. (Mandatory phase.) |
| Review approves 0 | No insight scores ≥14 | Write empty `approved[]`; orchestrator skips Writing+Publisher; Telegram partial with top 3 rejected reasons |
| Review approves 1 | Below `min_posts_required` (default 2) | Same as approves 0 — halt Writing+Publisher; Telegram partial |
| Writing under-fills slots | Only 2/4 slots mapped to insights | Writing emits `content: null` for missing slots; Publisher posts only non-null slots; Telegram partial reports "đã đăng 2/4" |
| FB scheduled_time <10 min away | Cron ran late and 08:00 already passed/near | Shift that post forward by 15 minutes; Telegram warning |
| FB access token expired | Token TTL lapsed | Halt Publisher; `posts.json` preserved; Telegram **error** with manual-refresh instructions |
| FB rate limit | OAuthException, rapid posting | Exponential backoff 1m / 5m / 15m; 3 attempts; then halt + Telegram error |
| Partial publish | 1 post OK, later post fails | `publish_results.json` already written for succeeded posts; Telegram partial lists succeeded `post_id`s |
| Unexpected exception | Code bug, OpenClaw issue | Catch-all in orchestrator; stack dumped to `run.log`; Telegram error with last 20 log lines |

**Global retry policy:** default 3 attempts with exponential backoff (2s / 10s / 60s), except where the table overrides. Every retry and outcome is logged to `run_dir/run.log`.

**Secret rotation:** the pipeline never refreshes tokens automatically. When expiry-class errors occur, the user rotates via `openclaw secrets set ...` and triggers a manual re-run.

---

## 6. Testing Strategy

### 6.1 Unit tests (per skill, in isolation)

- Fixtures checked into `tests/fixtures/sample_run/` containing realistic sample JSON input files.
- Each skill is invoked via `openclaw skills run <skill> --args '{"run_dir": "tests/fixtures/sample_run", "page_profile": "tests/fixtures/page_test.json"}'`.
- Assertions: output file exists, schema validates, business rules hold (e.g., `review-agent` keeps only `total≥14`; `youtube-researcher` filter respects profile thresholds).
- External HTTP calls are stubbed via env overrides (`YOUTUBE_API_BASE`, `PERPLEXITY_API_BASE`) pointed at a local mock server or fixture-replay layer.

### 6.2 Integration tests (paired skills)

- `youtube-researcher` → `notebooklm-analyzer`: low-volume real run against a disposable notebook to verify MCP wiring.
- `writing-agent` → `facebook-publisher`: uses an FB **Test Page** (not the production page) to verify scheduled publish + first-comment flow end-to-end.
- Data-contract drift detection: each pair tests the producer's output parses under the consumer's schema.

### 6.3 End-to-end dry-run

- `dry_run=true` on the orchestrator skips Graph API calls entirely; produces `run_dir/preview.md`; sends preview via Telegram for human approval.
- Required before enabling cron on any new page.

### 6.4 Smoke test checklist (pre-cron)

1. `openclaw skills run daily-content-pipeline --args '{"page":"page_test","dry_run":true}'`
2. Verify all 6 intermediate JSON files + `preview.md` written correctly.
3. Verify Telegram preview received.
4. Turn off dry-run; run once manually; verify FB Test Page has 4 scheduled posts and 4 first comments.
5. Enable cron via `openclaw cron add …`.

### 6.5 Runtime monitoring

- `run.log` retained 30 days per run (pruning handled by `autofanpage-health-check`).
- Weekly (manual): review `publish_results.json` across pages for anomalies + FB Page Insights engagement trends.
- Daily (automated): `af-health` cron at 09:00 alerts Telegram for any page missing a `last_success.json` for today.

### 6.6 Out of scope (YAGNI)

No automated CI pipeline, no unit-test framework beyond `openclaw skills run`, no dashboard, no content A/B testing. Revisit if recurrence of specific failure classes justifies the investment.

---

## 7. Deployment Checklist

**One-time setup:**

- [ ] OpenClaw gateway running; Telegram channel paired; user verified.
- [ ] `openclaw secrets set youtube_api <key>`
- [ ] `openclaw secrets set perplexity_api <key>`
- [ ] Create Reddit OAuth app at `https://www.reddit.com/prefs/apps` (type: "script" or "installed"); then `openclaw secrets set reddit_client_id <id>` and `openclaw secrets set reddit_client_secret <secret>`.
- [ ] Per-page: `openclaw secrets set fb_<page_name> <token>` (with `pages_manage_posts` + `pages_read_engagement`)
- [ ] `pip install notebooklm-mcp-cli` (or `uv tool install notebooklm-mcp-cli`)
- [ ] `nlm login` — opens browser, sign in to Google account that owns NotebookLM Pro/free. Cookies cached locally.
- [ ] `openclaw mcp add notebooklm-mcp ...` — register the MCP server binary with OpenClaw. (Confirm the exact OpenClaw `mcp add` syntax on first install.)
- [ ] Verify MCP tools resolve: invoke a trivial `nlm notebook list` before relying on the cron pipeline.
- [ ] Copy the eleven skill folders into `~/.openclaw/skills/autofanpage/`.
- [ ] Write a profile JSON for each page under `~/.openclaw/autofanpage/pages/`.
- [ ] Smoke test each page with `dry_run=true` (see §6.4).
- [ ] Create one cron per page (`openclaw cron add --name "af-<page>" --cron "0 6 * * *" --session isolated --tz <tz> --message "/daily_content_pipeline page=<name>"`).
- [ ] Create the health cron (`openclaw cron add --name "af-health" --cron "0 9 * * *" --message "/autofanpage_health_check"`).

**Weekly ops:**

- [ ] Verify Telegram success messages arrived for every page.
- [ ] Spot-check FB Page Insights engagement.
- [ ] Check FB access tokens not expiring within a week.
- [ ] Check YouTube API quota remaining.
- [ ] Re-run `nlm login` if last login was >2 weeks ago (cookies expire 2–4 weeks; proactively refresh before they break a daily run).
- [ ] Rotate topic in page profile if content is becoming repetitive.

---

## 8. Open Questions (to resolve during implementation)

1. **Exact OpenClaw sub-agent invocation syntax.** Docs list "Agent Send" and "Sub-Agents" as capabilities but show no concrete example. First implementation task will verify this on a trivial hello-world orchestrator before porting the real pipeline.
2. **Secret injection into sub-agents.** We assume secret references resolve transparently within a sub-agent's session; confirm on first smoke test.
3. **Exact OpenClaw `mcp add` syntax for `notebooklm-mcp-cli`.** The tool names (`notebook_create`, `source_add`, `notebook_query`) are confirmed from the package README. The exact OpenClaw registration command will be finalized when we run through the first install.
4. **FB scheduling race condition.** If a cron is badly delayed and the 08:00 slot window has already closed, current behavior shifts forward by 15 minutes. We may want to instead push that post to the next day — decision deferred until we observe real lateness.
