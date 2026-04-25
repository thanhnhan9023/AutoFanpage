# facebook-publisher

Publishes filled slots from `posts.json`. It supports two backends:

- direct Facebook Graph API scheduling
- Mixpost UI automation via stored browser state

## Entry Point

```bash
python skills/facebook-publisher/scripts/publish.py \
  --run-dir ~/.openclaw/autofanpage/runs/page_smoketest/2026-04-25 \
  --profile ./profiles/page_smoketest.json \
  --date 2026-04-25 \
  --dry-run
```

## Inputs

- `--run-dir`: directory containing `posts.json`
- `--profile`: page profile JSON
- `--date`: publishing date in profile timezone
- `--dry-run`: write preview only, do not publish

## Reads

- `posts.json`
- `post_assets.json` when `publishing.backend == "mixpost_ui"` and images are enabled

## Outputs

- `preview.md` in dry-run mode
- `publish_results.json` in real publish mode

## Backend Selection

- default: Facebook Graph API using `page_id` and `access_token_ref`
- `publishing.backend == "mixpost_ui"`: uses Mixpost browser session state

## Required Secrets and Services

- Graph mode: `secret:<page access token>`
- Mixpost mode: valid `publishing.mixpost.base_url` and
  `publishing.mixpost.storage_state_path`
- Playwright is required for Mixpost publishing with images

## Called By

- `daily-content-pipeline`
- `hourly-facebook-repost-pipeline`

## Notes

- Idempotent resume is based on existing successful entries in `publish_results.json`.
- Empty slots in `posts.json` are skipped.
