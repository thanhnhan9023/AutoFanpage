---
name: daily-content-pipeline
description: Orchestrator for the AutoFanpage daily content automation pipeline
---

# daily-content-pipeline

Top-level orchestrator. Plan 1: HN + Telegram vertical slice.

## Invocation

    python scripts/orchestrate.py --page <name> --profile-path <path> --base-dir <path> [--date YYYY-MM-DD]

## Flow (Plan 1)

1. Load profile, resolve today's date.
2. Abort + info Telegram if already ran today.
3. Call hackernews-researcher.
4. Mark success + report via telegram-reporter.
