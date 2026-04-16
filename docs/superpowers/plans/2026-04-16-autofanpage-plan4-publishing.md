# AutoFanpage — Plan 4: Publishing (Facebook + Health Check + Dry Run)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the pipeline by adding Facebook Graph API publishing (scheduled posts + first-comments), dry-run preview mode, a health-check skill, and orchestrator Phase 4 integration — making the system fully operational end-to-end.

**Architecture:** One new skill (`facebook-publisher`) handles all Graph API interaction with idempotent resume-after-failure. A new pure module (`autofanpage/facebook.py`) encapsulates the Graph API calls and time-shift logic so the skill script stays thin. Dry-run mode renders a Markdown preview instead of hitting the API. A separate `autofanpage-health-check` skill runs on its own cron to alert on stale pages and prune old run directories. The orchestrator gains `--dry-run` flag and Phase 4 dispatch.

**Tech Stack:** Python 3.11+, `requests` (Graph API via `autofanpage.http`), `responses` (HTTP mock in tests), `jsonschema`. No new runtime dependencies.

**Spec reference:** `docs/superpowers/specs/2026-04-15-autofanpage-openclaw-design.md` — §3.9 (facebook-publisher), §3.11 (health-check), §3.1 step 9 (dry-run), §5 error handling (FB token expired, rate limit, partial publish), §7 deployment checklist (cron setup).

**Integration assumptions (Plan 3 outputs consumed by Plan 4):**
- `<run_dir>/posts.json` with shape `{posts: [{time, type, content, first_comment}], language}` — exactly 4 entries, null content for unfilled slots.
- Profile has `page_id`, `access_token_ref`, `post_times`, `timezone`.
- `autofanpage.http.post_json` handles 429 as retryable (Plan 2 fix).
- `autofanpage.secrets.get_secret` resolves `secret:fb_<page>` references.

---

## File Structure

**New shared libraries under `autofanpage/`:**
- `autofanpage/facebook.py` — Pure helpers: `schedule_post(...)`, `add_first_comment(...)`, `compute_publish_time(...)`, `render_preview(...)`. All Graph API calls go through `autofanpage.http.post_json`. Time-shift logic (push forward 15min if within 10min of wall time) lives here.
- `autofanpage/health.py` — Pure helpers: `find_stale_pages(...)`, `prune_old_runs(...)`. No I/O beyond filesystem reads.

**New skill folders under `skills/`:**
- `skills/facebook-publisher/SKILL.md` + `scripts/__init__.py` + `scripts/publish.py`
- `skills/autofanpage-health-check/SKILL.md` + `scripts/__init__.py` + `scripts/check.py`

**Modified:**
- `autofanpage/schemas.py` — add `PUBLISH_RESULTS_SCHEMA`.
- `skills/daily-content-pipeline/scripts/orchestrate.py` — add `--dry-run` flag, Phase 4 dispatch, update `posts_scheduled` in success path.
- `autofanpage/telegram.py` — add dry-run preview info template.
- `skills/daily-content-pipeline/SKILL.md` — append Plan 4 flow.
- `README.md` — append Plan 4 smoke test section.

**New tests under `tests/`:**
- `tests/test_facebook.py`
- `tests/test_health.py`
- `tests/skills/test_facebook_publisher.py`
- `tests/skills/test_health_check.py`
- `tests/skills/test_orchestrator_plan4.py`

**New fixtures:**
- `tests/fixtures/posts_sample.json` — 4-slot posts (2 filled, 2 null) for publisher tests.
- `tests/fixtures/publish_results_partial.json` — partial publish (1 slot done) for resume tests.

---

### Task 1: Facebook Graph API helpers (pure)

**Files:**
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/autofanpage/facebook.py`
- Test: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/test_facebook.py`

- [ ] **Step 1: Write failing test `tests/test_facebook.py`**

```python
import time as _time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from autofanpage.facebook import (
    compute_publish_time,
    render_preview,
)


def test_compute_publish_time_normal_case():
    """Post at 12:00 when wall time is 06:30 — no shift needed."""
    wall = datetime(2026, 4, 16, 6, 30, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    ts = compute_publish_time(
        post_time="12:00", date="2026-04-16",
        tz_name="Asia/Ho_Chi_Minh", wall_now=wall,
    )
    # 12:00 ICT = 05:00 UTC
    assert ts == int(datetime(2026, 4, 16, 5, 0, tzinfo=timezone.utc).timestamp())


def test_compute_publish_time_shifts_when_within_10_min():
    """Post at 08:00 when wall time is 07:55 — shift to 08:15."""
    wall = datetime(2026, 4, 16, 7, 55, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    ts = compute_publish_time(
        post_time="08:00", date="2026-04-16",
        tz_name="Asia/Ho_Chi_Minh", wall_now=wall,
    )
    expected = datetime(2026, 4, 16, 1, 15, tzinfo=timezone.utc)  # 08:15 ICT
    assert ts == int(expected.timestamp())


def test_compute_publish_time_shifts_when_in_past():
    """Post at 08:00 when wall time is 08:05 — already passed, shift +15min."""
    wall = datetime(2026, 4, 16, 8, 5, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    ts = compute_publish_time(
        post_time="08:00", date="2026-04-16",
        tz_name="Asia/Ho_Chi_Minh", wall_now=wall,
    )
    expected = datetime(2026, 4, 16, 1, 15, tzinfo=timezone.utc)  # 08:15 ICT
    assert ts == int(expected.timestamp())


def test_compute_publish_time_no_shift_when_exactly_10_min_away():
    """Post at 08:00 when wall is 07:50 — exactly 10min, no shift."""
    wall = datetime(2026, 4, 16, 7, 50, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    ts = compute_publish_time(
        post_time="08:00", date="2026-04-16",
        tz_name="Asia/Ho_Chi_Minh", wall_now=wall,
    )
    expected = datetime(2026, 4, 16, 1, 0, tzinfo=timezone.utc)  # 08:00 ICT
    assert ts == int(expected.timestamp())


def test_render_preview_formats_posts_as_markdown():
    posts = {
        "posts": [
            {"time": "08:00", "type": "news", "content": "Breaking news content",
             "first_comment": "Source: https://example.com"},
            {"time": "12:00", "type": "guide", "content": None, "first_comment": None},
            {"time": "16:00", "type": "opinion", "content": "Hot take here",
             "first_comment": "What do you think?"},
            {"time": "20:00", "type": "case_study", "content": None, "first_comment": None},
        ],
        "language": "vi",
    }
    md = render_preview(posts, page="page_test", date="2026-04-16")
    assert "# Preview: page_test" in md
    assert "## 08:00 — news" in md
    assert "Breaking news content" in md
    assert "Source: https://example.com" in md
    assert "## 12:00 — guide" in md
    assert "(no content)" in md
    assert "## 16:00 — opinion" in md
    assert "Hot take here" in md
```

Run: `pytest tests/test_facebook.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autofanpage.facebook'`.

- [ ] **Step 2: Write `autofanpage/facebook.py`**

```python
"""Facebook Graph API helpers for the facebook-publisher skill.

All scheduling logic and Markdown preview rendering live here. The actual
HTTP calls go through ``autofanpage.http.post_json`` so retries and 429
handling are inherited.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from autofanpage.http import post_json


GRAPH_BASE = "https://graph.facebook.com/v19.0"
MIN_LEAD_MINUTES = 10
SHIFT_MINUTES = 15


def compute_publish_time(
    *,
    post_time: str,
    date: str,
    tz_name: str,
    wall_now: datetime | None = None,
) -> int:
    """Return a Unix timestamp for the scheduled publish time.

    If the target time is less than ``MIN_LEAD_MINUTES`` in the future
    (or already past), shift forward by ``SHIFT_MINUTES``.
    """
    tz = ZoneInfo(tz_name)
    hour, minute = int(post_time[:2]), int(post_time[3:])
    y, m, d = int(date[:4]), int(date[5:7]), int(date[8:10])
    target = datetime(y, m, d, hour, minute, tzinfo=tz)

    if wall_now is None:
        wall_now = datetime.now(tz)

    diff = (target - wall_now).total_seconds()
    if diff < MIN_LEAD_MINUTES * 60:
        target += timedelta(minutes=SHIFT_MINUTES)

    return int(target.astimezone(timezone.utc).timestamp())


def schedule_post(
    *,
    page_id: str,
    access_token: str,
    message: str,
    publish_time: int,
    timeout: float = 60,
    max_retries: int = 3,
) -> str:
    """POST to /{page_id}/feed with scheduled_publish_time. Return post_id."""
    url = f"{GRAPH_BASE}/{page_id}/feed"
    resp = post_json(
        url,
        json_body={
            "message": message,
            "scheduled_publish_time": publish_time,
            "published": False,
            "access_token": access_token,
        },
        timeout=timeout,
        max_retries=max_retries,
    )
    return resp["id"]


def add_first_comment(
    *,
    post_id: str,
    access_token: str,
    message: str,
    timeout: float = 30,
    max_retries: int = 3,
) -> str:
    """POST to /{post_id}/comments. Return comment_id."""
    url = f"{GRAPH_BASE}/{post_id}/comments"
    resp = post_json(
        url,
        json_body={
            "message": message,
            "access_token": access_token,
        },
        timeout=timeout,
        max_retries=max_retries,
    )
    return resp["id"]


def render_preview(
    posts_data: dict,
    *,
    page: str,
    date: str,
) -> str:
    """Render posts.json as a Markdown preview document."""
    lines = [
        f"# Preview: {page} — {date}",
        "",
    ]
    for post in posts_data["posts"]:
        lines.append(f"## {post['time']} — {post['type']}")
        lines.append("")
        if post["content"]:
            lines.append(post["content"])
            lines.append("")
            if post["first_comment"]:
                lines.append(f"> **First comment:** {post['first_comment']}")
                lines.append("")
        else:
            lines.append("*(no content)*")
            lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 3: Run tests to verify pass**

Run: `pytest tests/test_facebook.py -v`
Expected: `6 passed`.

- [ ] **Step 4: Commit**

```bash
git add autofanpage/facebook.py tests/test_facebook.py
git commit -m "feat(facebook): Graph API helpers + time-shift + preview renderer"
```

---

### Task 2: publish_results schema

**Files:**
- Modify: `/Users/nguyenloc/VibeCoding/AutoFanpage/autofanpage/schemas.py`
- Test: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/test_schemas.py` (extend)

- [ ] **Step 1: Write failing tests (append to `tests/test_schemas.py`)**

```python
from autofanpage.schemas import PUBLISH_RESULTS_SCHEMA


def test_publish_results_schema_accepts_valid():
    validate("publish_results", {
        "page": "page_test",
        "date": "2026-04-16",
        "posts": [
            {"time": "08:00", "type": "news", "post_id": "123_456",
             "comment_id": "123_789", "status": 200},
        ],
    })


def test_publish_results_schema_rejects_missing_page():
    with pytest.raises(Exception):
        validate("publish_results", {
            "date": "2026-04-16",
            "posts": [],
        })


def test_publish_results_allows_null_ids_for_failed_slots():
    validate("publish_results", {
        "page": "page_test",
        "date": "2026-04-16",
        "posts": [
            {"time": "08:00", "type": "news", "post_id": None,
             "comment_id": None, "status": 400},
        ],
    })
```

Run: `pytest tests/test_schemas.py -v`
Expected: FAIL with `ImportError: cannot import name 'PUBLISH_RESULTS_SCHEMA'`.

- [ ] **Step 2: Add `PUBLISH_RESULTS_SCHEMA` to `autofanpage/schemas.py`**

Add before the `_SCHEMAS` dict:

```python
PUBLISH_RESULTS_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["page", "date", "posts"],
    "additionalProperties": True,
    "properties": {
        "page": {"type": "string"},
        "date": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        "posts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["time", "type", "post_id", "comment_id", "status"],
                "additionalProperties": True,
                "properties": {
                    "time": {"type": "string", "pattern": "^[0-2][0-9]:[0-5][0-9]$"},
                    "type": {"type": "string", "enum": _POST_TYPES},
                    "post_id": {"type": ["string", "null"]},
                    "comment_id": {"type": ["string", "null"]},
                    "status": {"type": "integer"},
                },
            },
        },
    },
}
```

Add to `_SCHEMAS`:

```python
    "publish_results": PUBLISH_RESULTS_SCHEMA,
```

- [ ] **Step 3: Run tests to verify pass**

Run: `pytest tests/test_schemas.py -v`
Expected: all existing + 3 new pass.

- [ ] **Step 4: Commit**

```bash
git add autofanpage/schemas.py tests/test_schemas.py
git commit -m "feat(schemas): publish_results schema for FB audit log"
```

---

### Task 3: facebook-publisher skill

**Files:**
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/skills/facebook-publisher/SKILL.md`
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/skills/facebook-publisher/scripts/__init__.py`
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/skills/facebook-publisher/scripts/publish.py`
- Test: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/skills/test_facebook_publisher.py`
- Fixture: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/fixtures/posts_sample.json`
- Fixture: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/fixtures/publish_results_partial.json`

- [ ] **Step 1: Create fixture `tests/fixtures/posts_sample.json`**

```json
{
  "posts": [
    {"time": "08:00", "type": "news", "content": "Breaking: GPT-5 released.\n\n#AI #GPT5", "first_comment": "Source: https://news.example/gpt5"},
    {"time": "12:00", "type": "guide", "content": "How to cache prompts in 3 steps.\n\n#HowTo #AI", "first_comment": "Step details: ..."},
    {"time": "16:00", "type": "opinion", "content": null, "first_comment": null},
    {"time": "20:00", "type": "case_study", "content": null, "first_comment": null}
  ],
  "language": "vi"
}
```

- [ ] **Step 2: Create fixture `tests/fixtures/publish_results_partial.json`**

```json
{
  "page": "page_test",
  "date": "2026-04-16",
  "posts": [
    {"time": "08:00", "type": "news", "post_id": "123_456", "comment_id": "123_789", "status": 200}
  ]
}
```

- [ ] **Step 3: Write failing test `tests/skills/test_facebook_publisher.py`**

```python
import json
import sys
from pathlib import Path

import pytest
import responses

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "facebook-publisher" / "scripts"
sys.path.insert(0, str(SCRIPT))
import publish  # noqa: E402

GRAPH = "https://graph.facebook.com/v19.0"


@pytest.fixture
def run_dir(tmp_path, fixtures_dir):
    rd = tmp_path / "runs" / "page_test" / "2026-04-16"
    rd.mkdir(parents=True)
    (rd / "posts.json").write_text(
        (fixtures_dir / "posts_sample.json").read_text(), encoding="utf-8",
    )
    return rd


@responses.activate
def test_happy_path_publishes_non_null_slots(run_dir, fixtures_dir, mocker):
    mocker.patch.object(publish, "get_secret", return_value="fb_token_fake")
    # Slot 0 (news): post + comment
    responses.add(responses.POST, f"{GRAPH}/123/feed",
                  json={"id": "123_post0"}, status=200)
    responses.add(responses.POST, f"{GRAPH}/123_post0/comments",
                  json={"id": "123_cmt0"}, status=200)
    # Slot 1 (guide): post + comment
    responses.add(responses.POST, f"{GRAPH}/123/feed",
                  json={"id": "123_post1"}, status=200)
    responses.add(responses.POST, f"{GRAPH}/123_post1/comments",
                  json={"id": "123_cmt1"}, status=200)

    rc = publish.main([
        "--run-dir", str(run_dir),
        "--profile", str(fixtures_dir / "profile_plan3.json"),
        "--date", "2026-04-16",
    ])
    assert rc == 0

    results = json.loads((run_dir / "publish_results.json").read_text())
    assert results["page"] == "page_test"
    assert len(results["posts"]) == 2  # only non-null slots
    assert results["posts"][0]["post_id"] == "123_post0"
    assert results["posts"][0]["comment_id"] == "123_cmt0"
    assert results["posts"][0]["status"] == 200
    assert results["posts"][1]["post_id"] == "123_post1"


@responses.activate
def test_skips_already_published_slots_on_resume(run_dir, fixtures_dir, mocker):
    mocker.patch.object(publish, "get_secret", return_value="fb_token_fake")
    # Pre-populate partial results: slot 0 already done
    (run_dir / "publish_results.json").write_text(
        (fixtures_dir / "publish_results_partial.json").read_text(),
        encoding="utf-8",
    )
    # Only slot 1 (guide) needs publishing
    responses.add(responses.POST, f"{GRAPH}/123/feed",
                  json={"id": "123_post1"}, status=200)
    responses.add(responses.POST, f"{GRAPH}/123_post1/comments",
                  json={"id": "123_cmt1"}, status=200)

    rc = publish.main([
        "--run-dir", str(run_dir),
        "--profile", str(fixtures_dir / "profile_plan3.json"),
        "--date", "2026-04-16",
    ])
    assert rc == 0

    results = json.loads((run_dir / "publish_results.json").read_text())
    assert len(results["posts"]) == 2
    # First is the pre-existing one, second is newly published
    assert results["posts"][0]["time"] == "08:00"
    assert results["posts"][1]["time"] == "12:00"


def test_dry_run_writes_preview_no_api_calls(run_dir, fixtures_dir, mocker):
    mocker.patch.object(publish, "get_secret", return_value="fb_token_fake")

    rc = publish.main([
        "--run-dir", str(run_dir),
        "--profile", str(fixtures_dir / "profile_plan3.json"),
        "--date", "2026-04-16",
        "--dry-run",
    ])
    assert rc == 0

    preview = (run_dir / "preview.md").read_text()
    assert "Preview: page_test" in preview
    assert "Breaking: GPT-5" in preview
    assert not (run_dir / "publish_results.json").exists()


@responses.activate
def test_partial_failure_records_succeeded_slots(run_dir, fixtures_dir, mocker):
    mocker.patch.object(publish, "get_secret", return_value="fb_token_fake")
    # Slot 0 succeeds
    responses.add(responses.POST, f"{GRAPH}/123/feed",
                  json={"id": "123_post0"}, status=200)
    responses.add(responses.POST, f"{GRAPH}/123_post0/comments",
                  json={"id": "123_cmt0"}, status=200)
    # Slot 1 fails on post
    responses.add(responses.POST, f"{GRAPH}/123/feed",
                  json={"error": {"message": "token expired"}}, status=401)

    rc = publish.main([
        "--run-dir", str(run_dir),
        "--profile", str(fixtures_dir / "profile_plan3.json"),
        "--date", "2026-04-16",
    ])
    # Non-zero because slot 1 failed
    assert rc == 1

    results = json.loads((run_dir / "publish_results.json").read_text())
    # Slot 0 is recorded with status 200
    assert results["posts"][0]["status"] == 200
    assert results["posts"][0]["post_id"] == "123_post0"
    # Slot 1 is recorded with failure status
    assert results["posts"][1]["status"] == 401
    assert results["posts"][1]["post_id"] is None
```

Run: `pytest tests/skills/test_facebook_publisher.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'publish'`.

- [ ] **Step 4: Write `skills/facebook-publisher/scripts/publish.py`**

```python
#!/usr/bin/env python3
"""facebook-publisher: schedule posts to Facebook Graph API.

Reads  <run_dir>/posts.json
Writes <run_dir>/publish_results.json (or preview.md in dry-run mode)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from autofanpage.errors import AutofanpageError, SourceFailedError
from autofanpage.facebook import (
    add_first_comment,
    compute_publish_time,
    render_preview,
    schedule_post,
)
from autofanpage.profile import load_profile
from autofanpage.schemas import validate
from autofanpage.secrets import get_secret


def _load_existing_results(run_dir: Path) -> dict:
    """Load existing publish_results.json for resume, or empty scaffold."""
    path = run_dir / "publish_results.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _already_published(existing: dict | None, slot_time: str) -> bool:
    """Check if a slot was already successfully published."""
    if not existing:
        return False
    for entry in existing.get("posts", []):
        if entry["time"] == slot_time and entry["status"] == 200:
            return True
    return False


def _save_results(run_dir: Path, results: dict) -> None:
    validate("publish_results", results)
    (run_dir / "publish_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True)
    p.add_argument("--profile", required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    run_dir = Path(args.run_dir)
    posts_path = run_dir / "posts.json"
    if not posts_path.exists():
        raise AutofanpageError(f"missing input: {posts_path}")
    posts_data = json.loads(posts_path.read_text(encoding="utf-8"))
    validate("posts", posts_data)

    profile = load_profile(args.profile)

    if args.dry_run:
        md = render_preview(posts_data, page=profile.name, date=args.date)
        (run_dir / "preview.md").write_text(md, encoding="utf-8")
        print(json.dumps({"status": "ok", "artifact": "preview.md",
                          "mode": "dry_run"}))
        return 0

    access_token = get_secret(profile.access_token_ref)
    existing = _load_existing_results(run_dir)

    results: dict = {
        "page": profile.name,
        "date": args.date,
        "posts": list(existing["posts"]) if existing else [],
    }
    had_failure = False

    for post in posts_data["posts"]:
        if post["content"] is None:
            continue
        if _already_published(existing, post["time"]):
            continue

        ts = compute_publish_time(
            post_time=post["time"], date=args.date,
            tz_name=profile.timezone,
        )

        try:
            post_id = schedule_post(
                page_id=profile.page_id,
                access_token=access_token,
                message=post["content"],
                publish_time=ts,
            )
            comment_id = None
            if post["first_comment"]:
                comment_id = add_first_comment(
                    post_id=post_id,
                    access_token=access_token,
                    message=post["first_comment"],
                )
            results["posts"].append({
                "time": post["time"],
                "type": post["type"],
                "post_id": post_id,
                "comment_id": comment_id,
                "status": 200,
            })
        except SourceFailedError as e:
            had_failure = True
            status_code = 500
            err_str = str(e)
            # Extract HTTP status from error message if available
            import re
            m = re.search(r"HTTP (\d{3})", err_str)
            if m:
                status_code = int(m.group(1))
            results["posts"].append({
                "time": post["time"],
                "type": post["type"],
                "post_id": None,
                "comment_id": None,
                "status": status_code,
            })

        # Write after each slot for partial-failure resilience
        _save_results(run_dir, results)

    published = sum(1 for p in results["posts"] if p["status"] == 200)
    print(json.dumps({
        "status": "ok" if not had_failure else "partial",
        "artifact": "publish_results.json",
        "posts_published": published,
    }))
    return 1 if had_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Create `skills/facebook-publisher/SKILL.md`**

```markdown
---
name: facebook-publisher
description: Schedule posts to Facebook Graph API from posts.json, with idempotent resume and dry-run preview mode.
---

# facebook-publisher

**Inputs:** `run_dir` (contains `posts.json`), `profile`, `date`, optional `--dry-run`.
**Output:** `<run_dir>/publish_results.json` (or `preview.md` in dry-run mode).

**CLI invocation:**

    python scripts/publish.py --run-dir <path> --profile <profile.json> --date 2026-04-16 [--dry-run]
```

- [ ] **Step 6: Run tests to verify pass**

Run: `pytest tests/skills/test_facebook_publisher.py -v`
Expected: `4 passed`.

- [ ] **Step 7: Commit**

```bash
git add skills/facebook-publisher/ tests/skills/test_facebook_publisher.py \
        tests/fixtures/posts_sample.json tests/fixtures/publish_results_partial.json
git commit -m "feat(skill): facebook-publisher — scheduled posts + idempotent resume"
```

---

### Task 4: Health check helpers (pure)

**Files:**
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/autofanpage/health.py`
- Test: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/test_health.py`

- [ ] **Step 1: Write failing test `tests/test_health.py`**

```python
import json
from datetime import datetime, timezone
from pathlib import Path

from autofanpage.health import find_stale_pages, prune_old_runs


def test_find_stale_pages_detects_missing_success(tmp_path):
    base = tmp_path
    # page_ok has today's success
    state_ok = base / "state" / "page_ok"
    state_ok.mkdir(parents=True)
    (state_ok / "last_success.json").write_text(json.dumps({
        "date": "2026-04-16", "run_dir": "x",
        "posts_scheduled": 4, "completed_at": "t",
    }))
    # page_stale has yesterday's success
    state_stale = base / "state" / "page_stale"
    state_stale.mkdir(parents=True)
    (state_stale / "last_success.json").write_text(json.dumps({
        "date": "2026-04-15", "run_dir": "x",
        "posts_scheduled": 4, "completed_at": "t",
    }))
    # page_missing has no last_success at all
    state_miss = base / "state" / "page_missing"
    state_miss.mkdir(parents=True)

    stale = find_stale_pages(base, today="2026-04-16")
    assert sorted(stale) == ["page_missing", "page_stale"]


def test_find_stale_pages_empty_state_dir(tmp_path):
    stale = find_stale_pages(tmp_path, today="2026-04-16")
    assert stale == []


def test_prune_old_runs_removes_old_dirs(tmp_path):
    base = tmp_path
    runs = base / "runs" / "page_test"
    (runs / "2026-03-01").mkdir(parents=True)  # 46 days old
    (runs / "2026-03-01" / "run.log").write_text("old")
    (runs / "2026-04-10").mkdir(parents=True)  # 6 days old — keep
    (runs / "2026-04-10" / "run.log").write_text("recent")

    removed = prune_old_runs(base, max_age_days=30, today="2026-04-16")
    assert removed == ["2026-03-01"]
    assert not (runs / "2026-03-01").exists()
    assert (runs / "2026-04-10").exists()
```

Run: `pytest tests/test_health.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 2: Write `autofanpage/health.py`**

```python
"""Health check helpers: stale-page detection and run-directory pruning."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path


def find_stale_pages(base: Path, *, today: str) -> list[str]:
    """Return page names whose last_success.json date != today."""
    state_dir = Path(base) / "state"
    if not state_dir.exists():
        return []
    stale = []
    for page_dir in sorted(state_dir.iterdir()):
        if not page_dir.is_dir():
            continue
        success = page_dir / "last_success.json"
        if not success.exists():
            stale.append(page_dir.name)
            continue
        try:
            data = json.loads(success.read_text())
            if data.get("date") != today:
                stale.append(page_dir.name)
        except (json.JSONDecodeError, KeyError):
            stale.append(page_dir.name)
    return stale


def prune_old_runs(
    base: Path,
    *,
    max_age_days: int = 30,
    today: str,
) -> list[str]:
    """Remove run directories older than max_age_days. Return removed dates."""
    runs_dir = Path(base) / "runs"
    if not runs_dir.exists():
        return []
    today_dt = datetime.strptime(today, "%Y-%m-%d")
    cutoff = today_dt - timedelta(days=max_age_days)
    removed = []
    for page_dir in runs_dir.iterdir():
        if not page_dir.is_dir():
            continue
        for date_dir in sorted(page_dir.iterdir()):
            if not date_dir.is_dir():
                continue
            try:
                dt = datetime.strptime(date_dir.name, "%Y-%m-%d")
            except ValueError:
                continue
            if dt < cutoff:
                shutil.rmtree(date_dir)
                removed.append(date_dir.name)
    return removed
```

- [ ] **Step 3: Run tests to verify pass**

Run: `pytest tests/test_health.py -v`
Expected: `3 passed`.

- [ ] **Step 4: Commit**

```bash
git add autofanpage/health.py tests/test_health.py
git commit -m "feat(health): stale-page detection + run-dir pruning"
```

---

### Task 5: autofanpage-health-check skill

**Files:**
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/skills/autofanpage-health-check/SKILL.md`
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/skills/autofanpage-health-check/scripts/__init__.py`
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/skills/autofanpage-health-check/scripts/check.py`
- Test: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/skills/test_health_check.py`

- [ ] **Step 1: Write failing test `tests/skills/test_health_check.py`**

```python
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "autofanpage-health-check" / "scripts"
sys.path.insert(0, str(SCRIPT))
import check  # noqa: E402


def test_health_check_reports_stale_pages(tmp_path, mocker):
    base = tmp_path
    # Create a stale page
    state = base / "state" / "page_stale"
    state.mkdir(parents=True)
    (state / "last_success.json").write_text(json.dumps({
        "date": "2026-04-15", "run_dir": "x",
        "posts_scheduled": 4, "completed_at": "t",
    }))
    # Create a healthy page
    state_ok = base / "state" / "page_ok"
    state_ok.mkdir(parents=True)
    (state_ok / "last_success.json").write_text(json.dumps({
        "date": "2026-04-16", "run_dir": "x",
        "posts_scheduled": 4, "completed_at": "t",
    }))

    reported = []
    mocker.patch.object(check, "run_skill", side_effect=lambda n, a: reported.append((n, a)))

    rc = check.main([
        "--base-dir", str(base),
        "--date", "2026-04-16",
    ])
    assert rc == 0

    tg = [r for r in reported if r[0] == "telegram-reporter"]
    assert len(tg) == 1
    assert "page_stale" in tg[0][1]["details"]["message"]
    assert "page_ok" not in tg[0][1]["details"]["message"]


def test_health_check_prunes_old_runs(tmp_path, mocker):
    base = tmp_path
    old_run = base / "runs" / "page_test" / "2026-03-01"
    old_run.mkdir(parents=True)
    (old_run / "run.log").write_text("old")

    mocker.patch.object(check, "run_skill", return_value=None)

    check.main([
        "--base-dir", str(base),
        "--date", "2026-04-16",
    ])
    assert not old_run.exists()


def test_health_check_no_stale_no_telegram(tmp_path, mocker):
    base = tmp_path
    state = base / "state" / "page_ok"
    state.mkdir(parents=True)
    (state / "last_success.json").write_text(json.dumps({
        "date": "2026-04-16", "run_dir": "x",
        "posts_scheduled": 4, "completed_at": "t",
    }))

    reported = []
    mocker.patch.object(check, "run_skill", side_effect=lambda n, a: reported.append((n, a)))

    check.main([
        "--base-dir", str(base),
        "--date", "2026-04-16",
    ])
    # No stale pages → no telegram
    assert len(reported) == 0
```

Run: `pytest tests/skills/test_health_check.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'check'`.

- [ ] **Step 2: Write `skills/autofanpage-health-check/scripts/check.py`**

```python
#!/usr/bin/env python3
"""autofanpage-health-check: detect stale pages and prune old runs.

Intended to run on its own cron (daily 09:00).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from autofanpage.dispatch import run_skill
from autofanpage.health import find_stale_pages, prune_old_runs


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-dir", required=True)
    p.add_argument("--date", default=None)
    p.add_argument("--tz", default="Asia/Ho_Chi_Minh")
    p.add_argument("--max-age-days", type=int, default=30)
    args = p.parse_args(argv)

    base = Path(args.base_dir)
    today = args.date or datetime.now(tz=ZoneInfo(args.tz)).strftime("%Y-%m-%d")

    stale = find_stale_pages(base, today=today)
    if stale:
        msg = f"Stale pages ({today}): {', '.join(stale)}"
        run_skill("telegram-reporter", {
            "run_dir": str(base),
            "status": "error",
            "page": "health-check",
            "details": {
                "phase": "health-check",
                "cause": msg,
                "message": msg,
                "log_tail": "",
            },
        })

    removed = prune_old_runs(base, max_age_days=args.max_age_days, today=today)
    if removed:
        print(json.dumps({"pruned": removed}))

    print(json.dumps({
        "status": "ok",
        "stale_pages": stale,
        "pruned_runs": len(removed),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Create `skills/autofanpage-health-check/SKILL.md`**

```markdown
---
name: autofanpage-health-check
description: Daily health check — detect stale pages missing today's success, prune old run directories.
---

# autofanpage-health-check

**Invocation:** `openclaw cron add --name "af-health" --cron "0 9 * * *" --message "/autofanpage_health_check"`

**CLI:**

    python scripts/check.py --base-dir <path> [--date YYYY-MM-DD] [--max-age-days 30]
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/skills/test_health_check.py -v`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add skills/autofanpage-health-check/ tests/skills/test_health_check.py
git commit -m "feat(skill): autofanpage-health-check — stale detection + pruning"
```

---

### Task 6: Orchestrator — Phase 4 + dry-run

**Files:**
- Modify: `/Users/nguyenloc/VibeCoding/AutoFanpage/skills/daily-content-pipeline/scripts/orchestrate.py`
- Modify: `/Users/nguyenloc/VibeCoding/AutoFanpage/autofanpage/telegram.py`
- Modify: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/test_telegram.py`
- Modify: `/Users/nguyenloc/VibeCoding/AutoFanpage/skills/daily-content-pipeline/SKILL.md`

- [ ] **Step 1: Add `--dry-run` flag to orchestrator**

In `orchestrate.py`, add after `parser.add_argument("--date", ...)`:

```python
    parser.add_argument("--dry-run", action="store_true", default=False)
```

- [ ] **Step 2: Add Phase 4 constants**

After `PHASE3B_SKILL`:

```python
PHASE4_SKILL = "facebook-publisher"
```

- [ ] **Step 3: Add Phase 4 dispatch after Phase 3b**

Replace the current success block (after `run_dir.log(f"writing generated={posts_generated}")`) with:

```python
        # ----- Phase 4: Publish / Dry-run -----
        run_dir.log(f"phase4 facebook-publisher start dry_run={args.dry_run}")
        run_skill(PHASE4_SKILL, {
            "run_dir": str(run_dir.path),
            "profile": args.profile_path,
            "date": date,
            "dry_run": args.dry_run,
        })

        if args.dry_run:
            preview_path = run_dir.path / "preview.md"
            preview = preview_path.read_text() if preview_path.exists() else "(empty)"
            _report(run_dir.path, status="info", page=args.page, details={
                "message": f"Dry-run preview:\n\n{preview}",
            })
            return 0

        pub_results = json.loads(
            (run_dir.path / "publish_results.json").read_text(encoding="utf-8")
        )
        posts_scheduled = sum(
            1 for p in pub_results["posts"] if p["status"] == 200
        )
        run_dir.log(f"publish scheduled={posts_scheduled}")

        elapsed = int(time.monotonic() - started)
        state.mark(date=date, run_dir=str(run_dir.path),
                   posts_scheduled=posts_scheduled)
        _report(run_dir.path, status="success", page=args.page, details={
            "date": date,
            "posts_scheduled": posts_scheduled,
            "posts_generated": posts_generated,
            "approved_count": approved_count,
            "elapsed_sec": elapsed,
            "phase1_counts": counts,
            "phase1_failed_sources": list(failures),
        })
        return 0
```

- [ ] **Step 4: Add Telegram dry-run message test**

Append to `tests/test_telegram.py`:

```python
def test_info_template_renders_dry_run_preview():
    msg = format_message(
        status="info", page="p",
        details={"message": "Dry-run preview:\n\n## 08:00 — news\nContent here"},
    )
    assert "ℹ️" in msg
    assert "Dry-run preview" in msg
    assert "Content here" in msg
```

- [ ] **Step 5: Update SKILL.md**

Append to `skills/daily-content-pipeline/SKILL.md`:

```markdown

## Flow (Plan 4 additions)

After Phase 3b (writing-agent):

1. **Phase 4 — `facebook-publisher`**. Posts non-null slots to FB Graph API.
   - `--dry-run`: renders `preview.md` + sends via Telegram info, returns 0.
   - Normal: schedules posts, writes `publish_results.json`.
   - Partial failure: succeeded slots recorded; orchestrator reports partial.
2. Success Telegram now carries `posts_scheduled` (actual FB posts) in addition
   to `posts_generated`.

**New CLI flag:** `--dry-run` — skips Graph API, renders Markdown preview.

**Cron setup:**
```
openclaw cron add --name "af-<page>" --cron "0 6 * * *" --session isolated --tz <tz> --message "/daily_content_pipeline page=<name>"
openclaw cron add --name "af-health" --cron "0 9 * * *" --message "/autofanpage_health_check"
```
```

- [ ] **Step 6: Commit**

```bash
git add skills/daily-content-pipeline/ autofanpage/telegram.py tests/test_telegram.py
git commit -m "feat(orchestrator): Phase 4 publish + dry-run preview mode"
```

---

### Task 7: Orchestrator Plan 4 integration tests

**Files:**
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/skills/test_orchestrator_plan4.py`

- [ ] **Step 1: Write integration tests**

```python
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "daily-content-pipeline" / "scripts"
sys.path.insert(0, str(SCRIPT))
import orchestrate  # noqa: E402


@pytest.fixture
def env(tmp_path, fixtures_dir):
    return {
        "base": tmp_path,
        "profile": fixtures_dir / "profile_plan3.json",
        "page": "page_test",
    }


def _full_fake(failing: set[str] | None = None):
    """Fake dispatcher handling all Plan 1-4 skills."""
    failing = failing or set()
    calls: list[tuple[str, dict]] = []

    def fake(name, args):
        calls.append((name, args))
        run_dir = Path(args.get("run_dir", "."))

        if name == "telegram-reporter":
            return {"status": "ok", "sent": True}

        if name.endswith("-researcher"):
            key = name.replace("-researcher", "")
            if key in failing:
                from autofanpage.errors import SourceFailedError
                raise SourceFailedError(f"fake fail {key}")
            run_dir.mkdir(parents=True, exist_ok=True)
            _FAKE_ARTIFACTS = {
                "youtube": {
                    "source": "youtube", "fetched_at": "t",
                    "items": [{"title": "yt", "url": "https://youtube.example/1",
                               "video_id": "1", "channel": "c", "views": 200000,
                               "subscribers": 30000,
                               "published_at": "2026-04-10T00:00:00Z"}],
                },
                "perplexity": {
                    "source": "perplexity", "fetched_at": "t",
                    "news": [{"title": "n", "url": "https://perplexity.example/1",
                              "summary": "", "source": "n.com"}],
                    "reports": [], "twitter": [],
                },
                "reddit": {
                    "source": "reddit", "fetched_at": "t",
                    "items": [{"title": "rd", "url": "https://reddit.example/1",
                               "subreddit": "ChatGPT", "score": 800,
                               "num_comments": 30, "author": "u",
                               "permalink": "/r/1",
                               "created_at": "2026-04-14T00:00:00Z",
                               "is_self": False, "external_url": ""}],
                },
                "hackernews": {
                    "source": "hackernews", "fetched_at": "t",
                    "items": [{"title": "hn", "url": "https://hackernews.example/1",
                               "points": 300, "by": "u", "descendants": 10,
                               "created_at": "2026-04-14T00:00:00Z",
                               "hn_url": "https://news.ycombinator.com/item?id=1"}],
                },
            }
            (run_dir / orchestrate.SOURCE_ARTIFACTS[key]).write_text(
                json.dumps(_FAKE_ARTIFACTS[key])
            )
            return {"status": "ok"}

        if name == "notebooklm-analyzer":
            (run_dir / "insights.json").write_text(json.dumps({
                "overview": "x", "pain_points": ["p"],
                "insights": [
                    "OpenAI launched GPT-5 — latency dropped 35% vs 4.5.",
                    "Teams using prompt caching cut API spend 60% in 8 weeks.",
                    "Why most AI agents still fail in production.",
                    "How Acme Corp cut support response 55% with AI routing.",
                ],
                "gap_topics": ["g"],
                "source_urls": ["https://y.example/1"],
                "language": "vi", "notebook_id": "nb_fake",
            }))
            return {"status": "ok"}

        if name == "review-agent":
            (run_dir / "reviewed_insights.json").write_text(json.dumps({
                "approved": [
                    {"insight": "a", "scores": {"relevance": 5, "novelty": 5, "viral": 5, "actionable": 2},
                     "total": 17, "suggested_post_type": "news", "hook_angle": "", "source_url": ""},
                    {"insight": "b", "scores": {"relevance": 5, "novelty": 4, "viral": 5, "actionable": 5},
                     "total": 19, "suggested_post_type": "guide", "hook_angle": "", "source_url": ""},
                    {"insight": "c", "scores": {"relevance": 5, "novelty": 4, "viral": 3, "actionable": 2},
                     "total": 14, "suggested_post_type": "opinion", "hook_angle": "", "source_url": ""},
                    {"insight": "d", "scores": {"relevance": 5, "novelty": 4, "viral": 5, "actionable": 4},
                     "total": 18, "suggested_post_type": "case_study", "hook_angle": "", "source_url": ""},
                ],
                "rejected": [],
            }))
            return {"status": "ok"}

        if name == "writing-agent":
            (run_dir / "posts.json").write_text(json.dumps({
                "language": "vi",
                "posts": [
                    {"time": "08:00", "type": "news", "content": "News post", "first_comment": "fc1"},
                    {"time": "12:00", "type": "guide", "content": "Guide post", "first_comment": "fc2"},
                    {"time": "16:00", "type": "opinion", "content": "Opinion post", "first_comment": "fc3"},
                    {"time": "20:00", "type": "case_study", "content": "Case post", "first_comment": "fc4"},
                ],
            }))
            return {"status": "ok"}

        if name == "facebook-publisher":
            dry_run = args.get("dry_run", False)
            if dry_run:
                (run_dir / "preview.md").write_text("# Preview\nContent")
                return {"status": "ok", "mode": "dry_run"}
            if "fb_fail" in failing:
                from autofanpage.errors import SourceFailedError
                raise SourceFailedError("FB token expired")
            (run_dir / "publish_results.json").write_text(json.dumps({
                "page": "page_test", "date": args.get("date", "2026-04-16"),
                "posts": [
                    {"time": "08:00", "type": "news", "post_id": "p0", "comment_id": "c0", "status": 200},
                    {"time": "12:00", "type": "guide", "post_id": "p1", "comment_id": "c1", "status": 200},
                    {"time": "16:00", "type": "opinion", "post_id": "p2", "comment_id": "c2", "status": 200},
                    {"time": "20:00", "type": "case_study", "post_id": "p3", "comment_id": "c3", "status": 200},
                ],
            }))
            return {"status": "ok"}

        raise RuntimeError(f"unexpected skill {name}")

    return fake, calls


def _run(env, date="2026-04-16", dry_run=False):
    argv = [
        "--page", env["page"],
        "--profile-path", str(env["profile"]),
        "--base-dir", str(env["base"]),
        "--date", date,
    ]
    if dry_run:
        argv.append("--dry-run")
    return orchestrate.main(argv)


def test_full_pipeline_publishes_and_reports_scheduled_count(env, mocker):
    fake, calls = _full_fake()
    mocker.patch("orchestrate.run_skill", side_effect=fake)
    mocker.patch("orchestrate.time.sleep", return_value=None)
    assert _run(env) == 0

    names = [c[0] for c in calls]
    assert "facebook-publisher" in names

    tg = [c for c in calls if c[0] == "telegram-reporter"]
    assert tg[-1][1]["status"] == "success"
    assert tg[-1][1]["details"]["posts_scheduled"] == 4


def test_dry_run_skips_publish_sends_preview(env, mocker):
    fake, calls = _full_fake()
    mocker.patch("orchestrate.run_skill", side_effect=fake)
    mocker.patch("orchestrate.time.sleep", return_value=None)
    assert _run(env, dry_run=True) == 0

    names = [c[0] for c in calls]
    assert "facebook-publisher" in names

    tg = [c for c in calls if c[0] == "telegram-reporter"]
    last_tg = tg[-1]
    assert last_tg[1]["status"] == "info"
    assert "preview" in last_tg[1]["details"]["message"].lower()

    # No last_success marked in dry-run
    from autofanpage.state import LastSuccess
    assert not LastSuccess(base=env["base"], page=env["page"]).ran_on("2026-04-16")


def test_publish_failure_reports_error(env, mocker):
    fake, calls = _full_fake(failing={"fb_fail"})
    mocker.patch("orchestrate.run_skill", side_effect=fake)
    mocker.patch("orchestrate.time.sleep", return_value=None)
    # Publisher failure falls through to the AutofanpageError catch
    rc = _run(env)
    assert rc in (1, 2)

    tg = [c for c in calls if c[0] == "telegram-reporter"]
    assert any(t[1]["status"] == "error" for t in tg)
```

- [ ] **Step 2: Run and commit**

Run: `pytest tests/skills/test_orchestrator_plan4.py -v`
Expected: `3 passed`.

```bash
git add tests/skills/test_orchestrator_plan4.py
git commit -m "test(orchestrator): Plan 4 publish + dry-run + failure integration"
```

---

### Task 8: Update existing orchestrator tests

**Files:**
- Modify: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/skills/test_orchestrator.py`
- Modify: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/skills/test_orchestrator_plan3.py` (if needed)

The existing Plan 2 and Plan 3 orchestrator tests need updating since the orchestrator now calls Phase 4 (`facebook-publisher`). Add handlers for `facebook-publisher` to each test's fake dispatcher.

- [ ] **Step 1: Update Plan 2 orchestrator test**

In `tests/skills/test_orchestrator.py`, in `test_orchestrator_runs_hn_then_telegram`'s `fake_run_skill`, add after the `writing-agent` handler:

```python
        if name == "facebook-publisher":
            run_dir = Path(args["run_dir"])
            (run_dir / "publish_results.json").write_text(json.dumps({
                "page": "page_test", "date": args.get("date", "2026-04-15"),
                "posts": [{"time": "08:00", "type": "news", "post_id": "p0",
                           "comment_id": "c0", "status": 200}],
            }))
            return {"status": "ok"}
```

- [ ] **Step 2: Update Plan 3 orchestrator tests**

In `tests/skills/test_orchestrator_plan3.py`, in `_plan2_fake`, add after the `writing-agent` handler:

```python
        if name == "facebook-publisher":
            (run_dir / "publish_results.json").write_text(json.dumps({
                "page": "page_test", "date": "2026-04-16",
                "posts": [
                    {"time": "08:00", "type": "news", "post_id": "p0", "comment_id": "c0", "status": 200},
                    {"time": "12:00", "type": "guide", "post_id": "p1", "comment_id": "c1", "status": 200},
                    {"time": "16:00", "type": "opinion", "post_id": "p2", "comment_id": "c2", "status": 200},
                    {"time": "20:00", "type": "case_study", "post_id": "p3", "comment_id": "c3", "status": 200},
                ],
            }))
            return {"status": "ok"}
```

- [ ] **Step 3: Run full suite**

Run: `pytest -v`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add tests/skills/test_orchestrator.py tests/skills/test_orchestrator_plan3.py
git commit -m "fix(tests): add facebook-publisher handler to Plan 2/3 orchestrator tests"
```

---

### Task 9: Smoke test documentation

**Files:**
- Modify: `/Users/nguyenloc/VibeCoding/AutoFanpage/README.md`

- [ ] **Step 1: Append Plan 4 smoke test section**

```markdown
## Smoke test — Plan 4 (publishing)

Preconditions: Plan 3 smoke test passes; `posts.json` exists for the test page.

### 1. FB access token

```bash
openclaw secrets set fb_page_smoketest    # from FB App > Page Settings > Access Tokens
```

Required permissions: `pages_manage_posts`, `pages_read_engagement`.

### 2. Dry-run preview

```bash
openclaw skills run daily-content-pipeline -- \
    --page page_smoketest \
    --profile-path ./profiles/page_smoketest.json \
    --base-dir ~/.openclaw/autofanpage \
    --date "$(date +%F)" \
    --dry-run
```

Expected:
- Exit code 0.
- `preview.md` written to the run directory.
- Telegram: one info message with the full Markdown preview.
- `last_success.json` NOT updated.
- No posts published to Facebook.

### 3. Real publish (use a Test Page!)

Remove `--dry-run` and re-run. Use an FB **Test Page**, not production.

Expected:
- Exit code 0.
- `publish_results.json` with 4 entries, all `status: 200`.
- `last_success.json` updated with `posts_scheduled: 4`.
- Telegram: success message with scheduled count.
- FB Test Page: 4 scheduled posts with first-comments.

### 4. Cron setup

```bash
openclaw cron add --name "af-page_smoketest" \
    --cron "0 6 * * *" --session isolated \
    --tz "Asia/Ho_Chi_Minh" \
    --message "/daily_content_pipeline page=page_smoketest"

openclaw cron add --name "af-health" \
    --cron "0 9 * * *" \
    --message "/autofanpage_health_check"
```

### 5. Health check

```bash
openclaw skills run autofanpage-health-check -- \
    --base-dir ~/.openclaw/autofanpage \
    --date "$(date +%F)"
```

Expected:
- No stale pages if today's run succeeded.
- Old run dirs (>30 days) pruned.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: Plan 4 smoke test + cron setup instructions"
```

---

### Task 10: Full suite + coverage floor

**Files:**
- None new.

- [ ] **Step 1: Run the full suite**

Run: `pytest -v`
Expected: all Plan 1, 2, 3, and 4 tests pass. Approximate count: 175–190 tests.

- [ ] **Step 2: Coverage check**

Run: `pytest --cov=autofanpage --cov-report=term-missing`
Expected: coverage ≥ 85% for each of:
- `autofanpage/facebook.py`
- `autofanpage/health.py`
- `autofanpage/schemas.py`

- [ ] **Step 3: Fix coverage gaps**

Add focused unit tests for any uncovered branch. Do not use `# pragma: no cover` unless the branch is genuinely unreachable.

- [ ] **Step 4: Final commit**

```bash
git add -u
git commit --allow-empty -m "chore: Plan 4 complete — publishing pipeline green"
```

---

## Self-review

**Spec coverage:**
- §3.9 facebook-publisher (Graph API, scheduled_publish_time, first-comment, idempotency, partial-failure resilience, dry-run) → Tasks 1, 2, 3, 6 ✓
- §3.11 health-check (stale-page detection, run-directory pruning, Telegram alert) → Tasks 4, 5 ✓
- §3.1 step 9 dry-run (skip Graph API, render preview.md, send via Telegram) → Tasks 1, 3, 6 ✓
- §5 error handling: FB token expired, rate limit (via http.py 429 retry), partial publish → Tasks 3, 7 ✓
- §7 cron setup → Task 9 (documented, not automated — cron registration is a one-time manual step) ✓
- Orchestrator `posts_scheduled` now reflects actual FB posts (not 0) → Task 6 ✓

**Placeholder scan:**
- No TBD, TODO, "add appropriate error handling", or "similar to Task N" stubs.

**Type/API consistency with Plans 1–3:**
- `run_skill(name, args)` convention: maintained. `facebook-publisher` receives `{run_dir, profile, date, dry_run}`.
- `_report(run_dir, status=, page=, details=)`: reused unchanged.
- `state.mark(date=, run_dir=, posts_scheduled=)`: now receives actual scheduled count from publish_results.
- `autofanpage.http.post_json`: used by `facebook.schedule_post` and `facebook.add_first_comment`.
- `Profile` dataclass: uses existing `page_id`, `access_token_ref`, `post_times`, `timezone`, `writing` fields.

**Edge cases covered in tests:**
- Time shift: normal (>10min future), within 10min, already past, exactly 10min boundary (Task 1).
- Preview rendering: filled and null slots both handled (Task 1).
- Publisher: happy path (2 non-null slots), idempotent resume from partial, dry-run, partial failure records succeeded slots (Task 3).
- Health: stale detection, no-stale no-telegram, pruning (Tasks 4, 5).
- Orchestrator: full pipeline with publish, dry-run skips publish + sends preview, publish failure reports error (Task 7).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-16-autofanpage-plan4-publishing.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
