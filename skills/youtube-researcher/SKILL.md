---
name: youtube-researcher
description: Fetch top AI-automation YouTube videos matching a topic, filtered by views and channel subscribers.
---

# youtube-researcher

## Inputs

```json
{
  "topic": "AI automation business",
  "min_views": 100000,
  "min_subs": 10000,
  "api_key_ref": "secret:youtube_api_key",
  "limit": 10,
  "out_path": "/path/to/run_dir/youtube_results.json"
}
```

## Output

Writes `youtube_results.json` matching `YOUTUBE_RESULTS_SCHEMA`.

## Failure modes

- Missing/invalid API key -> `SourceFailedError` (HTTP 400/403).
- Quota exhausted -> `SourceFailedError` with HTTP 403 `quotaExceeded`.
- Any 5xx is retried up to 3x via `autofanpage.http`.
