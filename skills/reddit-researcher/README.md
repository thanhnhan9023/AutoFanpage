# reddit-researcher

Fetches top Reddit posts from configured subreddits using app-only OAuth and
combines them into a single wrapped result artifact.

## Entry Point

```bash
python skills/reddit-researcher/scripts/fetch_reddit.py \
  --run-dir ~/.openclaw/autofanpage/runs/page_smoketest/2026-04-25 \
  --profile ./profiles/page_smoketest.json
```

## Inputs

- `--run-dir`
- `--profile`

Relevant profile keys:

- `sources.reddit.enabled`
- `sources.reddit.subreddits`
- `sources.reddit.min_score`
- `sources.reddit.time_filter`
- `sources.reddit.top_per_sub`

## Outputs

- `reddit_results.json`

## Required Secrets

- `secret:reddit_client_id`
- `secret:reddit_client_secret`

## Called By

- `daily-content-pipeline`

## Notes

- A single subreddit failure is logged and skipped.
- If every subreddit fails, the workflow raises a source failure.
