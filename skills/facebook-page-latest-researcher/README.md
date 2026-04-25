# facebook-page-latest-researcher

Fetches recent public posts from a configured Facebook source page. This is the
source discovery workflow used by the hourly repost pipeline.

## Entry Point

```bash
python skills/facebook-page-latest-researcher/scripts/fetch_latest_post.py \
  --run-dir ~/.openclaw/autofanpage/runs/page_hourly/hourly/2026-04-25T08-00-00Z \
  --profile ./profiles/page_hourly.json
```

## Inputs

- `--run-dir`: hourly run directory
- `--profile`: page profile JSON with `sources.facebook_page_latest.enabled=true`

Relevant profile keys:

- `sources.facebook_page_latest.page_url`
- `sources.facebook_page_latest.backend`
- `sources.facebook_page_latest.browser_use_profile_id`
- `sources.facebook_page_latest.agent_browser_profile`
- `sources.facebook_page_latest.agent_browser_session_name`
- `sources.facebook_page_latest.agent_browser_state_path`

## Outputs

- `source_posts.json`: normalized candidate source posts fetched from the source page

## Backends

- `browser_use_mcp` (default)
- `agent_browser`

## Called By

- `hourly-facebook-repost-pipeline`

## Notes

- This workflow writes `source_posts.json`, not `latest_source_post.json`.
- The hourly pipeline applies queue selection and writes
  `latest_source_post.json` after it decides what to repost.
