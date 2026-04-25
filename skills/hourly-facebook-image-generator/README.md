# hourly-facebook-image-generator

Generates image candidates for the single filled hourly repost slot, chooses the
best candidate, and writes a publishable image manifest.

## Entry Point

```bash
python skills/hourly-facebook-image-generator/scripts/generate_images.py \
  --run-dir ~/.openclaw/autofanpage/runs/page_hourly/hourly/2026-04-25T08-00-00Z \
  --profile ./profiles/page_hourly.json \
  --date 2026-04-25
```

## Inputs

- `--run-dir`
- `--profile`
- `--date`

## Reads

- `posts.json`
- `latest_source_post.json`

## Outputs

- `post_assets.json`
- rendered files under `assets/`

Typical asset files:

- `assets/<slot>-raw-c1.png` ... `assets/<slot>-raw-c4.png`
- `assets/<slot>-selected.png`

## Providers

Primary provider from profile:

- `publishing.images.provider == "useapi_google_flow"`

Supported fallbacks:

- `codex_imagen_oauth`
- `zai_glm_image`
- `local_playwright_card`

## Required Secrets and Services

- `secret:useapi_token`
- optional `secret:<google flow account>`
- optional `secret:<capsolver api key>`
- optional `secret:zai_api_key`
- optional Codex OAuth auth file for `codex_imagen_oauth`

## Called By

- `hourly-facebook-repost-pipeline`

## Notes

- If `publishing.images.enabled` is `false`, the workflow still writes a valid
  empty `post_assets.json`.
- Candidate selection happens locally after multiple provider outputs are downloaded.
