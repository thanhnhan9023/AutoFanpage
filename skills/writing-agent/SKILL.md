---
name: writing-agent
description: Compose four Facebook slot posts (news / guide / opinion / case_study) and their first-comments from reviewed_insights.json via the Anthropic Messages API.
---

# writing-agent

**Inputs:** `run_dir` (contains `reviewed_insights.json`), `profile`.
**Output:** `<run_dir>/posts.json`

**CLI invocation:**

    python scripts/write_posts.py --run-dir <path> --profile <profile.json>
