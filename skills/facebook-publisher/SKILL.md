---
name: facebook-publisher
description: Schedule posts to Facebook Graph API from posts.json, with idempotent resume and dry-run preview mode.
---

# facebook-publisher

**Inputs:** `run_dir` (contains `posts.json`), `profile`, `date`, optional `--dry-run`.
**Output:** `<run_dir>/publish_results.json` (or `preview.md` in dry-run mode).

**CLI invocation:**

    python scripts/publish.py --run-dir <path> --profile <profile.json> --date 2026-04-16 [--dry-run]
