# writing-agent

Turns reviewed insights into four Facebook post slots and their first comments.
This is the final writing stage of the daily pipeline before publishing.

## Entry Point

```bash
python skills/writing-agent/scripts/write_posts.py \
  --run-dir ~/.openclaw/autofanpage/runs/page_smoketest/2026-04-25 \
  --profile ./profiles/page_smoketest.json
```

## Inputs

- `--run-dir`
- `--profile`

## Reads

- `reviewed_insights.json`

## Outputs

- `posts.json`

The artifact contains four typed slots:

- `news`
- `guide`
- `opinion`
- `case_study`

## Required Secrets and Models

From `profile.writing`:

- `api_key_ref`
- `model`
- `max_tokens`
- `temperature`
- optional `style`

## Called By

- `daily-content-pipeline`

## Notes

- The writer client supports Claude-style models and OpenAI-compatible chat models.
- Empty content in a slot means that slot will be skipped by the publisher.
