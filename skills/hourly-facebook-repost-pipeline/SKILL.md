---
name: hourly-facebook-repost-pipeline
description: Fetch, dedupe, rewrite, and republish the latest Facebook source post every hour.
---

# hourly-facebook-repost-pipeline

Inputs: `page`, `profile_path`, `base_dir`, `run_label`, optional `date`
Writes: hourly run artifacts under `runs/<page>/hourly/<run_label>/`
