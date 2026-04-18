---
name: reddit-researcher-apify
description: Fetch top Reddit posts per subreddit via Apify and write reddit_results.json
---

# reddit-researcher-apify

Phase 1 data-source skill backed by Apify.

## Inputs

- `run_dir` — absolute path to today's run directory
- `profile` — absolute path to the page profile JSON

## Behavior

1. Loads the profile.
2. If `sources.reddit.enabled` is `false`, writes an empty wrapped artifact and exits.
3. Calls the configured Apify Reddit actor once per subreddit and writes `reddit_results.json`.

## Output

Writes `<run_dir>/reddit_results.json` — object `{source, fetched_at, items}`.
