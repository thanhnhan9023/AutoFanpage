---
name: perplexity-researcher
description: Query Perplexity Sonar for today's AI automation news, recent research reports, and Twitter/X posts about a topic.
---

# perplexity-researcher

## Inputs

```json
{
  "topic": "AI automation business",
  "api_key_ref": "secret:perplexity_api_key",
  "news_limit": 5,
  "reports_limit": 3,
  "twitter_limit": 5,
  "twitter_enabled": true,
  "out_path": "/path/to/run_dir/perplexity_results.json"
}
```

## Output

Writes `perplexity_results.json` matching `PERPLEXITY_RESULTS_SCHEMA` (keys: `news`, `reports`, `twitter`).

## Failure modes

- Missing/invalid API key -> HTTP 401.
- Rate limited -> HTTP 429 retried via `autofanpage.http`.
- Malformed completion (no citations) -> empty list, does not fail.
