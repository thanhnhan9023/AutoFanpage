---
name: review-agent
description: Score NotebookLM insights on Relevance / Novelty / Viral / Actionable (1-5 each), keep total >= 14, assign news/guide/opinion/case_study, write reviewed_insights.json.
---

# review-agent

**Inputs:** `run_dir` (contains `insights.json`), `profile` (for `topic`).
**Output:** `<run_dir>/reviewed_insights.json` — `{approved[], rejected[]}` per spec §3.7.

**CLI invocation:**

    python scripts/review.py --run-dir <path> --profile <profile.json>
