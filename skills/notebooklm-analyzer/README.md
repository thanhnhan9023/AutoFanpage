# notebooklm-analyzer

Turns merged source URLs into structured insights using NotebookLM through MCP.
This is the analysis workflow between source gathering and writing.

## Entry Point

```bash
python skills/notebooklm-analyzer/scripts/analyze.py \
  --run-dir ~/.openclaw/autofanpage/runs/page_smoketest/2026-04-25 \
  --profile ./profiles/page_smoketest.json \
  --language vi \
  --max-sources 48
```

## Inputs

- `--run-dir`
- `--profile`
- `--language`
- `--max-sources`

## Reads

- `merged_sources.json`

## Outputs

- `insights.json`

Artifact shape:

```json
{
  "overview": "",
  "pain_points": [],
  "insights": [],
  "gap_topics": [],
  "source_urls": [],
  "language": "vi",
  "notebook_id": ""
}
```

## Required Services

- NotebookLM MCP server installed and authenticated
- reachable source URLs from `merged_sources.json`

## Called By

- `daily-content-pipeline`

## Notes

- URL extraction is deduplicated and capped at 48 entries.
- A failure here is treated as a hard pipeline error, with one retry in the orchestrator.
