# reddit-researcher-apify

Alternative Reddit source workflow backed by Apify actors instead of native
Reddit OAuth.

## Entry Point

```bash
python skills/reddit-researcher-apify/scripts/fetch_reddit_apify.py \
  --run-dir ~/.openclaw/autofanpage/runs/page_smoketest/2026-04-25 \
  --profile ./profiles/page_smoketest.json
```

## Inputs

- `--run-dir`
- `--profile`

Relevant profile keys:

- `sources.reddit.enabled`
- `sources.reddit.subreddits`
- `sources.reddit.top_per_sub`
- optional `sources.reddit.api_token_ref`

## Outputs

- `reddit_results.json`

## Required Secrets

- `secret:apify_api_token` by default

## Called By

- `daily-content-pipeline` when `sources.reddit.backend == "apify"`

## Notes

- Writes the same artifact contract as `reddit-researcher`.
- Use this workflow when you prefer Apify scraping over Reddit API credentials.
