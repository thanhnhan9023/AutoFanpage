# telegram-reporter

Formats a pipeline status message and records it in the run directory. The
script itself is transport-agnostic; it prints the formatted message and a JSON
envelope to stdout for the caller.

## Entry Point

```bash
python skills/telegram-reporter/scripts/report.py \
  --run-dir ~/.openclaw/autofanpage/runs/page_smoketest/2026-04-25 \
  --status success \
  --page page_smoketest \
  --details '{"date":"2026-04-25","elapsed_sec":12,"posts_scheduled":4}'
```

## Inputs

- `--run-dir`
- `--status`: `success`, `error`, `partial`, or `info`
- `--page`
- `--details`: JSON payload used by the status formatter

## Outputs

- appends formatted text to `telegram_sent.log`
- prints the formatted message
- prints a JSON envelope such as `{"status":"success","page":"...","sent":true}`

## Called By

- `daily-content-pipeline`
- `hourly-facebook-repost-pipeline`
- `autofanpage-health-check`

## Notes

- This workflow is the reporting contract for the rest of the repo.
- Status payload shape varies by workflow and phase.
