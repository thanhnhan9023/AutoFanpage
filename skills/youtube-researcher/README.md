# youtube-researcher

Fetches topic-matching YouTube videos, filters them by view count and channel
subscriber count, and writes a wrapped source artifact.

## Entry Point

```bash
python skills/youtube-researcher/scripts/fetch_youtube.py \
  --run-dir ~/.openclaw/autofanpage/runs/page_smoketest/2026-04-25 \
  --profile ./profiles/page_smoketest.json
```

## Inputs

- `--run-dir`
- `--profile`

Relevant profile keys:

- `topic`
- `sources.youtube.enabled`
- `filters.youtube_min_views`
- `filters.youtube_min_subs`
- `sources.youtube.limit`

## Outputs

- `youtube_results.json`

## Required Secrets

- `secret:youtube_api_key`

## Called By

- `daily-content-pipeline`

## Notes

- When disabled, the workflow writes an empty wrapped artifact and exits cleanly.
- HTTP 5xx errors are retried via shared HTTP helpers.
