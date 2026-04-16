---
name: reddit-researcher
description: Fetch top posts from configured AI-focused subreddits for a topic, filter by score, and combine into a single result set. Uses Reddit app-only OAuth.
---

# reddit-researcher

## Inputs

```json
{
  "subreddits": ["ChatGPT", "OpenAI", "LocalLLaMA"],
  "min_score": 100,
  "time_filter": "week",
  "top_per_sub": 5,
  "client_id_ref": "secret:reddit_client_id",
  "client_secret_ref": "secret:reddit_client_secret",
  "user_agent": "autofanpage/0.1 (by /u/yourname)",
  "out_path": "/path/to/run_dir/reddit_results.json"
}
```

## Output

Writes `reddit_results.json` matching `REDDIT_RESULTS_SCHEMA`.

## Failure modes

- OAuth 401 -> `SourceFailedError`.
- Single subreddit fail -> logged, skipped, others continue.
- All subreddits fail -> `SourceFailedError`.
