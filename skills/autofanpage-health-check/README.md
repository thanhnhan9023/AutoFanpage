# autofanpage-health-check

Daily maintenance workflow for the run store. It detects pages that did not
record success for the target date, reports them through `telegram-reporter`,
and prunes old run directories.

## Entry Point

```bash
python skills/autofanpage-health-check/scripts/check.py \
  --base-dir ~/.openclaw/autofanpage \
  --date 2026-04-25 \
  --tz Asia/Ho_Chi_Minh \
  --max-age-days 30
```

## Inputs

- `--base-dir`: AutoFanpage state root containing `runs/` and `state/`
- `--date`: optional target date; defaults to today in `--tz`
- `--tz`: timezone used to derive "today"
- `--max-age-days`: retention window for old run directories

## Outputs

- stdout JSON summary with stale pages and pruned paths
- `telegram_sent.log` entries under affected run directories when stale pages are reported

## Calls

- `telegram-reporter`

## Notes

- This workflow does not fix stale pages; it only reports them.
- Safe to run from cron after the daily publishing window.
