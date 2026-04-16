---
name: notebooklm-analyzer
description: Create a NotebookLM notebook from merged_sources.json, add each source URL, run four fixed queries, write insights.json.
---

# notebooklm-analyzer

**Inputs:** `run_dir` (contains `merged_sources.json`), `profile` (path to per-page JSON), `language`.
**Output:** `<run_dir>/insights.json` — `{overview, pain_points[], insights[], gap_topics[], source_urls[], language, notebook_id}`.

**Flow:**
1. Read `<run_dir>/merged_sources.json` → extract deduplicated URL list (`autofanpage.notebooklm.extract_urls`), capped at 48.
2. `notebook_create(title="AI Research <today>")` via the `notebooklm-mcp` MCP server.
3. For each URL, `source_add(notebook_id, url)`.
4. Call `notebook_query` four times with fixed prompts (overview / pain_points / insights / gap_topics), all instructed to respond in `language`.
5. Parse bulleted answers, validate against `INSIGHTS_SCHEMA`, write `insights.json`.

**CLI invocation:**

    python scripts/analyze.py \
        --run-dir <path> \
        --profile <profile.json> \
        --language vi \
        [--max-sources 48]

**Exit codes:** 0 on success; non-zero raises `AutofanpageError`/`MCPError` for the orchestrator to catch.
