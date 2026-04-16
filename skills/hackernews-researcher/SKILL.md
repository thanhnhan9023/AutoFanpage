---
name: hackernews-researcher
description: Fetch top Hacker News stories matching the page topic for the past week
---

# hackernews-researcher

Phase 1 data-source skill: pulls top Hacker News stories for the current week,
filters by score + topic match, and writes `hackernews_results.json` to the run
directory.

## Inputs (JSON args)

- `run_dir` — absolute path to today's run directory
- `profile` — absolute path to the page profile JSON

## Behavior

1. Loads the profile.
2. If `sources.hackernews.enabled` is `false`, writes an empty wrapped artifact and exits.
3. Otherwise pulls top 200 stories from HN API, filters by type=story + score + topic.

## Output

Writes `<run_dir>/hackernews_results.json` — object `{source, fetched_at, items}` where
`items` is an array of `{title, url, points, by, descendants, created_at, hn_url}`.

## No auth required.
