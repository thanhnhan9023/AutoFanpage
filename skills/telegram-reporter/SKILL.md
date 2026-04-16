---
name: telegram-reporter
description: Send a formatted status message about a pipeline run to the user's paired Telegram channel
---

# telegram-reporter

Terminal skill for pipeline status reporting.

## Inputs (CLI args)

- `--run-dir <path>` — run directory; appends to `telegram_sent.log`
- `--status <success|error|partial|info>` — template type
- `--page <name>` — page name
- `--details <json>` — status-specific payload

## Output

Prints formatted message + JSON envelope to stdout.
