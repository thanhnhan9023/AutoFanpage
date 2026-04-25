# hackernews-researcher

Collects top Hacker News stories for the current topic, filters them by score
and relevance, and wraps the result into a standard source artifact.

## Entry Point

```bash
python skills/hackernews-researcher/scripts/fetch_hn.py \
  --run-dir ~/.openclaw/autofanpage/runs/page_smoketest/2026-04-25 \
  --profile ./profiles/page_smoketest.json
```

## Inputs

- `--run-dir`
- `--profile`

Relevant profile keys:

- `topic`
- `sources.hackernews.enabled`
- `sources.hackernews.min_points`

## Outputs

- `hackernews_results.json`

Artifact shape:

```json
{"source": "hackernews", "fetched_at": "...", "items": []}
```

## Required Secrets

None.

## Called By

- `daily-content-pipeline`

## Notes

- When the source is disabled, the workflow writes an empty wrapped artifact and exits cleanly.
