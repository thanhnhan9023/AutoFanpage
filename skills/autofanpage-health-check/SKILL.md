---
name: autofanpage-health-check
description: Daily health check — detect stale pages missing today's success, prune old run directories.
---

# autofanpage-health-check

**Invocation:** `openclaw cron add --name "af-health" --cron "0 9 * * *" --message "/autofanpage_health_check"`

**CLI:**

    python scripts/check.py --base-dir <path> [--date YYYY-MM-DD] [--max-age-days 30]
