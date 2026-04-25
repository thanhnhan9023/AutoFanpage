# hourly-facebook-repost-pipeline

Top-level hourly repost workflow. It pulls recent source posts from one public
Facebook page, finds the next unreposted item, rewrites it, optionally creates
images, publishes it, and records repost history.

## Entry Point

```bash
python skills/hourly-facebook-repost-pipeline/scripts/orchestrate.py \
  --page page_hourly_repost \
  --profile-path ./profiles/page_hourly_repost.json \
  --base-dir ~/.openclaw/autofanpage \
  --run-label 2026-04-25T08-00-00Z \
  --date 2026-04-25
```

## Inputs

- `--page`
- `--profile-path`
- `--base-dir`
- `--run-label`
- `--date`: optional; defaults from profile timezone

## Run Artifacts

The workflow writes into:

`<base-dir>/runs/<page>/hourly/<run-label>/`

Main artifacts:

- `run.log`
- `source_posts.json`
- `repost_decision.json`
- `latest_source_post.json`
- `posts.json`
- `review_feedback.json`
- optional `post_assets.json`
- `publish_results.json`
- `telegram_sent.log`

State artifacts:

- `<base-dir>/state/<page>/latest_reposted_source.json`
- `<base-dir>/state/<page>/reposted_source_posts.json`

## Flow

1. Fetch recent source posts from the configured Facebook page.
2. Compare them against repost history and select the next candidate.
3. Persist the selected source post.
4. Run `hourly-facebook-writer`.
5. Optionally run `hourly-facebook-image-generator`.
6. Run `facebook-publisher`.
7. Update repost history state.
8. Format final status through `telegram-reporter`.

## Calls

- `facebook-page-latest-researcher`
- `hourly-facebook-writer`
- `hourly-facebook-image-generator` when images are enabled
- `facebook-publisher`
- `telegram-reporter`

## Required Configuration

Profile must include:

- `sources.facebook_page_latest.enabled = true`
- exactly one source page URL in `sources.facebook_page_latest.page_url`
- valid `writing` config
- valid `publishing` config

## Notes

- Queue selection prefers the newest unseen post first, then drains older backlog.
- History is timezone-aware and uses the profile timezone.
