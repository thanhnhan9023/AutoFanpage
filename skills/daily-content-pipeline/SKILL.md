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

## Flow (Plan 2)

1. Load profile, resolve today's date.
2. Abort + info Telegram if already ran today.
3. Dispatch all enabled Phase-1 researchers in parallel (youtube, perplexity, reddit, hackernews).
4. Collect artifacts; record failures.
5. Abort with error Telegram if fewer than `min_posts_required` sources succeeded.
6. Merge artifacts into `merged_sources.json` (deduplicated, per-platform capped).
7. Abort with error Telegram if merged URLs = 0.
8. Mark success + report via telegram-reporter with phase1_counts and failed sources.

## Flow (Plan 3 additions)

After the Plan 2 merge step and before `state.mark`:

1. **Phase 2 — `notebooklm-analyzer`** (mandatory). One retry on failure.
2. **Phase 3a — `review-agent`**. If `approved < min_posts_required` → partial.
3. **Phase 3b — `writing-agent`**. Writes `posts.json` with 4 slots.
