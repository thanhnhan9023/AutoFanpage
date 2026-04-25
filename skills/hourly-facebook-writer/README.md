# hourly-facebook-writer

Rewrites one selected source Facebook post into a single filled `posts.json`
slot that can be published immediately by the hourly repost pipeline.

## Entry Point

```bash
python skills/hourly-facebook-writer/scripts/write_repost.py \
  --run-dir ~/.openclaw/autofanpage/runs/page_hourly/hourly/2026-04-25T08-00-00Z \
  --profile ./profiles/page_hourly.json \
  --date 2026-04-25 \
  --publish-time 08:00
```

## Inputs

- `--run-dir`
- `--profile`
- `--date`
- `--publish-time`

## Reads

- `latest_source_post.json`

## Outputs

- `posts.json`
- `review_feedback.json` when review is enabled

## Required Secrets and Models

From `profile.writing`:

- `api_key_ref`
- `model`
- optional `review_api_key_ref`
- optional `review_model`
- `review_max_rounds` defaults to `3`

## Called By

- `hourly-facebook-repost-pipeline`

## Notes

- The workflow fills only one slot, typed as `news`.
- Remaining three slots are placeholders with `content: null`.
- If review is enabled, it can rewrite the draft up to `review_max_rounds`.
