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
- Telegram channel: one success message with source counts.

### 4. Failure-mode check — force `min_posts_required` abort

Flip 3 of the 4 `enabled: true` to `false` in the profile so only 1 source runs; re-run.

Expected:
- Exit code 1.
- `last_success.json` NOT updated.
- Telegram error message with phase and cause.

Reset the profile after.
