# daily-content-pipeline

Top-level daily automation workflow. It gathers sources, merges them, turns
them into insights, reviews the insights, writes four post slots, and can
publish those slots to Facebook or Mixpost.

## Entry Point

```bash
python skills/daily-content-pipeline/scripts/orchestrate.py \
  --page page_smoketest \
  --profile-path ./profiles/page_smoketest.json \
  --base-dir ~/.openclaw/autofanpage \
  --date 2026-04-25 \
  --dry-run
```

## Inputs

- `--page`: page key used in run/state paths
- `--profile-path`: page profile JSON
- `--base-dir`: AutoFanpage base directory
- `--date`: optional wall date; defaults from profile timezone
- `--dry-run`: skip publishing and write `preview.md` instead

## Run Artifacts

The workflow writes into:

`<base-dir>/runs/<page>/<date>/`

Common artifacts:

- `run.log`
- `merged_sources.json`
- `telegram_sent.log`
- `last_success.json` under `<base-dir>/state/<page>/`

Phase-specific artifacts:

- Phase 1: `youtube_results.json`, `perplexity_results.json`,
  `reddit_results.json`, `hackernews_results.json`
- Phase 2: `insights.json`
- Phase 3: `reviewed_insights.json`, `posts.json`
- Phase 4: `preview.md` or `publish_results.json`

## Flow

1. Load profile and resolve target date.
2. Abort early if the page already succeeded for that date.
3. Run enabled Phase 1 source workflows.
4. Merge and deduplicate gathered URLs into `merged_sources.json`.
5. Run `notebooklm-analyzer`.
6. Run `review-agent`.
7. Run `writing-agent`.
8. Run `facebook-publisher` unless `--dry-run` is enabled.
9. Format final status through `telegram-reporter`.

## Calls

- `youtube-researcher`
- `perplexity-researcher`
- `reddit-researcher` or `reddit-researcher-apify`
- `hackernews-researcher`
- `notebooklm-analyzer`
- `review-agent`
- `writing-agent`
- `facebook-publisher`
- `telegram-reporter`

## Required Secrets and Services

Depends on the enabled sources and publishing backend in the page profile:

- `secret:youtube_api_key`
- `secret:perplexity_api_key` or `secret:tavily_api_key`
- `secret:reddit_client_id`
- `secret:reddit_client_secret`
- `secret:apify_api_token` when Reddit backend is Apify
- `secret:anthropic_api_key` or another writer API key configured in `writing`
- NotebookLM MCP login/session
- `secret:<page access token>` for Graph publish
- Mixpost storage state when `publishing.backend == "mixpost_ui"`

## Notes

- `--dry-run` still runs source gathering, NotebookLM, review, and writing.
- A partial Phase 1 result can still succeed if enough sources pass the
  `min_posts_required` gate.
