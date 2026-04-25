# perplexity-researcher

Fetches topic-specific news, reports, and optional Twitter/X discussion into one
wrapped source artifact.

## Entry Point

```bash
python skills/perplexity-researcher/scripts/fetch_perplexity.py \
  --run-dir ~/.openclaw/autofanpage/runs/page_smoketest/2026-04-25 \
  --profile ./profiles/page_smoketest.json
```

## Inputs

- `--run-dir`
- `--profile`

Relevant profile keys:

- `topic`
- `sources.perplexity.enabled`
- `sources.perplexity.backend`
- `sources.perplexity.news_limit`
- `sources.perplexity.reports_limit`
- `sources.perplexity.twitter_limit`
- `sources.perplexity.twitter_enabled`

## Outputs

- `perplexity_results.json`

Artifact keys:

- `news`
- `reports`
- `twitter`

## Required Secrets

- `secret:perplexity_api_key` for Perplexity-backed mode
- `secret:tavily_api_key` when profile backend resolves to Tavily mode

## Called By

- `daily-content-pipeline`

## Notes

- When disabled, the workflow writes an empty wrapped artifact and exits cleanly.
- Malformed model output can degrade to empty lists without failing the whole source.
