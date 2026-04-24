# AutoFanpage

Automated social-media fanpage pipeline powered by OpenClaw skills.

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
- The four Phase 1 source artifacts are wrapped JSON documents, not bare arrays:
  - `youtube_results.json`, `reddit_results.json`, `hackernews_results.json` use `{source, fetched_at, items}`
  - `perplexity_results.json` uses `{source, fetched_at, news, reports, twitter}`
- Telegram channel: one success message with source counts.

### 4. Failure-mode check — force `min_posts_required` abort

Flip 3 of the 4 `enabled: true` to `false` in the profile so only 1 source runs; re-run.

Expected:
- Exit code 1.
- `last_success.json` NOT updated.
- Telegram error message with phase and cause.

Reset the profile after.

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
- Telegram: one success message now including `N posts generated`.

### 4. Failure-mode check — NotebookLM cookies expired

Intentionally log out: `nlm logout` (or delete the cached cookie jar).
Re-run the orchestrator.

Expected:
- Exit code 1.
- Telegram: one error message with
  `Phase: phase2-notebooklm` and cause ending with
  `Run \`nlm login\` to refresh NotebookLM cookies.`
- `last_success.json` NOT updated.

Re-login (`nlm login`) before proceeding.

### 5. Failure-mode check — partial review

Temporarily raise `min_posts_required` in the profile to a value the review
can't meet (e.g. `10`). Re-run.

Expected:
- Exit code 0 (soft-success).
- Telegram: one partial message with `X insights approved`, `0/4 posts generated`.
- `posts.json` not written.
- `last_success.json` **is** updated for today.

Reset `min_posts_required` to 2.

## Smoke test — Plan 4 (publishing)

Preconditions: Plan 3 smoke test passes; `posts.json` exists for the test page.

### 1. FB access token

```bash
openclaw secrets set fb_page_smoketest    # from FB App > Page Settings > Access Tokens
```

Required permissions: `pages_manage_posts`, `pages_read_engagement`.

### 2. Dry-run preview

```bash
openclaw skills run daily-content-pipeline -- \
    --page page_smoketest \
    --profile-path ./profiles/page_smoketest.json \
    --base-dir ~/.openclaw/autofanpage \
    --date "$(date +%F)" \
    --dry-run
```

Expected:
- Exit code 0.
- `preview.md` written to the run directory.
- Telegram: one info message with the full Markdown preview.
- `last_success.json` NOT updated.
- No posts published to Facebook.

### 3. Real publish (use a Test Page!)

Remove `--dry-run` and re-run. Use an FB **Test Page**, not production.

Expected:
- Exit code 0.
- `publish_results.json` with 4 entries, all `status: 200`.
- `last_success.json` updated with `posts_scheduled: 4`.
- Telegram: success message with scheduled count.
- FB Test Page: 4 scheduled posts with first-comments.

### 4. Cron setup

```bash
openclaw cron add --name "af-page_smoketest" \
    --cron "0 6 * * *" --session isolated \
    --tz "Asia/Ho_Chi_Minh" \
    --message "/daily_content_pipeline page=page_smoketest"

openclaw cron add --name "af-health" \
    --cron "0 9 * * *" \
    --message "/autofanpage_health_check"
```

### 5. Health check

```bash
openclaw skills run autofanpage-health-check -- \
    --base-dir ~/.openclaw/autofanpage \
    --date "$(date +%F)"
```

Expected:
- No stale pages if today's run succeeded.
- Old run dirs (>30 days) pruned.

## Hourly Facebook Latest Repost

Example profile: `tests/fixtures/profile_hourly_facebook_repost.json`

Run manually:

```bash
openclaw skills run hourly-facebook-repost-pipeline -- \
  --page page_hourly_repost \
  --profile-path ./tests/fixtures/profile_hourly_facebook_repost.json \
  --base-dir ~/.openclaw/autofanpage \
  --run-label "$(date -u +%Y-%m-%dT%H-%M-%SZ)"
```

Cron example:

```bash
openclaw cron add --name "af-hourly-page_hourly_repost" \
  --cron "0 * * * *" \
  --session isolated \
  --tz "Asia/Ho_Chi_Minh" \
  --message "/hourly_facebook_repost_pipeline page=page_hourly_repost"
```
