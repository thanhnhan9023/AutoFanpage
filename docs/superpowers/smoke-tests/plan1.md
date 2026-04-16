# Plan 1 — Manual Smoke Test

Run this once after Plan 1 is implemented to confirm the vertical slice works
on real OpenClaw before moving to Plan 2.

## Prerequisites

- OpenClaw gateway running locally.
- Telegram channel paired and verified (you can send yourself a test message
  via `openclaw channels status`).
- `autofanpage` Python package installed: `pip install -e .[dev]` from repo root.

## Steps

1. Install the three Plan 1 skills into OpenClaw:

       ./scripts/install-skills.sh
       openclaw skills list | grep autofanpage   # expect 3 rows

2. Create a test profile at `~/.openclaw/autofanpage/pages/page_test.json`.
   Copy from `tests/fixtures/page_test.json`. Edit:
   - `page_id`: any non-empty string (not used in Plan 1)
   - `topic`: something that will match HN titles, e.g. `"AI"`
   - `sources.hackernews.enabled`: `true`
   - `sources.hackernews.min_points`: lower to `50` if you want more results

3. Invoke the orchestrator:

       openclaw skills run daily-content-pipeline --args \
           '{"page": "page_test", "profile_path": "~/.openclaw/autofanpage/pages/page_test.json", "base_dir": "~/.openclaw/autofanpage"}'

   (Exact flag names depend on how the slash command is wired; adjust to
   whatever `/daily_content_pipeline page=page_test` expands to.)

4. Expect on your Telegram:

       ✅ AutoFanpage [page_test]
       📝 0 posts scheduled
       📅 <today>
       ⏱ <N>s

5. Inspect the run directory:

       ls ~/.openclaw/autofanpage/runs/page_test/<today>/
       # Should include: hackernews_results.json, run.log, telegram_sent.log

   Optional quick check:

       jq '.source, (.items | length)' ~/.openclaw/autofanpage/runs/page_test/<today>/hackernews_results.json
       # Expect: "hackernews" and a non-negative item count

6. Confirm idempotency: re-run the same command.
   Expected Telegram: `ℹ️ AutoFanpage [page_test]  already ran on <today>`.

## Troubleshooting

- **"openclaw: command not found"** — activate OpenClaw's env or add it to PATH.
- **"skill not found: hackernews-researcher"** — rerun `install-skills.sh`; confirm
  `openclaw skills list` sees it.
- **Telegram silent** — verify channel pairing with `openclaw channels status`;
  check `telegram_sent.log` in the run directory for the formatted message
  (this confirms the orchestrator formatted it correctly even if the channel
  transport is broken).
- **HN returns 0 items** — lower `min_points` in the profile and broaden `topic`.

## Success criteria

All 6 steps complete without intervention, both the success Telegram and the
idempotency Telegram arrive, and the run directory contains the expected
artifacts.
