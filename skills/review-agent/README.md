# review-agent

Scores NotebookLM insights and separates them into approved and rejected sets.
Approved insights also receive a post type assignment.

## Entry Point

```bash
python skills/review-agent/scripts/review.py \
  --run-dir ~/.openclaw/autofanpage/runs/page_smoketest/2026-04-25 \
  --profile ./profiles/page_smoketest.json
```

## Inputs

- `--run-dir`
- `--profile`

## Reads

- `insights.json`

## Outputs

- `reviewed_insights.json`

Artifact shape:

```json
{"approved": [], "rejected": []}
```

## Scoring Rules

- Relevance: 1-5
- Novelty: 1-5
- Viral: 1-5
- Actionable: 1-5
- approval threshold: total score `>= 14`

Assigned post types:

- `news`
- `guide`
- `opinion`
- `case_study`

## Called By

- `daily-content-pipeline`

## Notes

- This workflow is deterministic and local; it does not call an external model.
- The orchestrator can treat low approval count as a partial run instead of a hard failure.
