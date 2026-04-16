# AutoFanpage — Plan 1: Foundation + Vertical Slice

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the AutoFanpage skill package on OpenClaw with a minimal end-to-end vertical slice: orchestrator skill → 1 data-source skill (Hacker News) → Telegram reporter. Proves the OpenClaw skill-invocation pattern, profile loading, run-directory contract, and Telegram reporting all work together before we add the harder integrations.

**Architecture:** Python package `autofanpage/` under the project root holds shared libraries (profile loader, run-directory manager, schema validator, secrets wrapper, sub-skill dispatcher). Skill folders under `skills/` hold OpenClaw SKILL.md files plus per-skill Python scripts in `skills/<name>/scripts/`. Tests under `tests/` use pytest. Skills developed in-repo are copied (or symlinked) into `~/.openclaw/skills/autofanpage/` for runtime via a `scripts/install.sh`.

**Tech Stack:** Python 3.11+, pytest, `jsonschema` for validation, `requests` for HTTP, OpenClaw CLI (`openclaw skills run`, `openclaw secrets get`) invoked via `subprocess` from a mockable dispatcher. No framework beyond that.

**Spec reference:** `docs/superpowers/specs/2026-04-15-autofanpage-openclaw-design.md` (EN) / `.vi.md` (VN). This plan implements §2 (file layout), §3.1 (orchestrator scaffold only — HN + Telegram path), §3.5 (hackernews-researcher), §3.10 (telegram-reporter), §4.1 (profile schema), §4.3 (state/last_success.json). Remaining skills are Plan 2/3/4.

---

## File Structure

**Python package (`autofanpage/`) — shared libraries used by every skill:**
- `autofanpage/__init__.py` — empty
- `autofanpage/profile.py` — `load_profile(path) -> Profile` with validation
- `autofanpage/run_dir.py` — `RunDir` class: create/resolve run dirs, read/write JSON artifacts
- `autofanpage/state.py` — `LastSuccess` class: read/write `state/<page>/last_success.json`
- `autofanpage/schemas.py` — JSON-schema fragments for every artifact, plus `validate(name, data)`
- `autofanpage/secrets.py` — `get_secret(ref) -> str`; backend is subprocess to `openclaw secrets get`, swappable for tests
- `autofanpage/dispatch.py` — `run_skill(name, args_dict) -> dict`; backend is subprocess to `openclaw skills run`, swappable for tests
- `autofanpage/telegram.py` — thin wrapper used by `telegram-reporter`
- `autofanpage/errors.py` — typed exceptions (`ProfileError`, `SchemaError`, `SkillInvocationError`, `AlreadyRanError`)

**Skill folders (`skills/`) — shipped to `~/.openclaw/skills/autofanpage/`:**
- `skills/daily-content-pipeline/SKILL.md` + `scripts/orchestrate.py`
- `skills/hackernews-researcher/SKILL.md` + `scripts/fetch_hn.py`
- `skills/telegram-reporter/SKILL.md` + `scripts/report.py`

**Tests (`tests/`):**
- `tests/conftest.py` — shared fixtures
- `tests/fixtures/` — sample profile JSON, sample run_dir artifacts
- `tests/test_profile.py`, `tests/test_run_dir.py`, `tests/test_state.py`, `tests/test_schemas.py`, `tests/test_secrets.py`, `tests/test_dispatch.py`
- `tests/skills/test_hackernews.py`, `tests/skills/test_telegram.py`, `tests/skills/test_orchestrator.py`

**Project root:**
- `pyproject.toml`, `README.md`, `.gitignore`
- `scripts/install-skills.sh` — copies `skills/*` into `~/.openclaw/skills/autofanpage/`

---

### Task 1: Project initialization

**Files:**
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/pyproject.toml`
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/.gitignore`
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/autofanpage/__init__.py`
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/__init__.py`
- Create: `/Users/nguyenloc/VibeCoding/AutoFanpage/tests/conftest.py`

- [ ] **Step 1: Initialize git repo (if not already)**

Run: `cd /Users/nguyenloc/VibeCoding/AutoFanpage && git init && git branch -M main`

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "autofanpage"
version = "0.1.0"
description = "OpenClaw skill package for daily Facebook content automation"
requires-python = ">=3.11"
dependencies = [
    "requests>=2.31",
    "jsonschema>=4.21",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.12",
    "pytest-cov>=4.1",
    "responses>=0.25",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]
include = ["autofanpage*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 3: Write `.gitignore`**

```
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
htmlcov/
*.egg-info/
build/
dist/
.venv/
venv/
.env
.DS_Store
```

- [ ] **Step 4: Write empty package init + tests init + conftest**

`autofanpage/__init__.py`:
```python
"""AutoFanpage OpenClaw skill package."""
```

`tests/__init__.py`: empty file.

`tests/conftest.py`:
```python
"""Shared pytest fixtures."""
from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"
```

- [ ] **Step 5: Verify install + empty test run**

Run: `cd /Users/nguyenloc/VibeCoding/AutoFanpage && python -m pip install -e ".[dev]"`
Expected: Installs `autofanpage` in editable mode.

Run: `pytest`
Expected: `no tests ran in 0.XXs` (exit 5 is fine — no tests yet).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore autofanpage/ tests/
git commit -m "chore: initialize autofanpage python package"
```

---

### Task 2: Typed exceptions

**Files:**
- Create: `autofanpage/errors.py`
- Test: `tests/test_errors.py`

- [ ] **Step 1: Write failing test**

`tests/test_errors.py`:
```python
import pytest
from autofanpage.errors import (
    AutofanpageError, ProfileError, SchemaError,
    SkillInvocationError, AlreadyRanError, SourceFailedError,
)


def test_all_errors_inherit_from_base():
    assert issubclass(ProfileError, AutofanpageError)
    assert issubclass(SchemaError, AutofanpageError)
    assert issubclass(SkillInvocationError, AutofanpageError)
    assert issubclass(AlreadyRanError, AutofanpageError)
    assert issubclass(SourceFailedError, AutofanpageError)


def test_schema_error_carries_context():
    err = SchemaError("posts.json", ["missing key: time"])
    assert err.artifact == "posts.json"
    assert err.violations == ["missing key: time"]
    assert "posts.json" in str(err)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_errors.py -v`
Expected: `ModuleNotFoundError: No module named 'autofanpage.errors'`

- [ ] **Step 3: Write `autofanpage/errors.py`**

```python
"""Typed exceptions for autofanpage."""
from __future__ import annotations


class AutofanpageError(Exception):
    """Base class."""


class ProfileError(AutofanpageError):
    """Raised when a page profile is missing keys or has invalid values."""


class SchemaError(AutofanpageError):
    """Raised when a JSON artifact fails schema validation."""

    def __init__(self, artifact: str, violations: list[str]) -> None:
        self.artifact = artifact
        self.violations = violations
        super().__init__(f"{artifact}: {'; '.join(violations)}")


class SkillInvocationError(AutofanpageError):
    """Raised when a sub-skill invocation fails."""


class AlreadyRanError(AutofanpageError):
    """Raised when today's run has already succeeded for this page."""


class SourceFailedError(AutofanpageError):
    """Raised by an individual Phase-1 source after retries exhausted."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_errors.py -v`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add autofanpage/errors.py tests/test_errors.py
git commit -m "feat(autofanpage): add typed exceptions"
```

---

### Task 3: JSON schema validation helper

**Files:**
- Create: `autofanpage/schemas.py`
- Test: `tests/test_schemas.py`

- [ ] **Step 1: Write failing test**

`tests/test_schemas.py`:
```python
import pytest
from autofanpage.schemas import validate
from autofanpage.errors import SchemaError


def test_validate_profile_accepts_valid_payload():
    valid = {
        "name": "page_test",
        "page_id": "123",
        "access_token_ref": "secret:fb_test",
        "topic": "AI",
        "language": "en",
        "post_times": ["08:00", "12:00", "16:00", "20:00"],
        "timezone": "UTC",
        "min_posts_required": 2,
        "max_sources_per_platform": 12,
        "sources": {
            "youtube": {"enabled": False},
            "perplexity": {"enabled": False},
            "twitter_via_perplexity": {"enabled": False},
            "reddit": {"enabled": False, "subreddits": [], "min_score": 0,
                       "time_filter": "week", "top_per_sub": 0},
            "hackernews": {"enabled": True, "min_points": 10},
        },
    }
    # No exception
    validate("profile", valid)


def test_validate_profile_rejects_missing_page_id():
    invalid = {"name": "x", "post_times": ["08:00", "12:00", "16:00", "20:00"]}
    with pytest.raises(SchemaError) as exc:
        validate("profile", invalid)
    assert exc.value.artifact == "profile"
    assert any("page_id" in v for v in exc.value.violations)


def test_validate_hackernews_results_requires_array():
    with pytest.raises(SchemaError):
        validate("hackernews_results", {"not": "an array"})
    # Empty array is valid
    validate("hackernews_results", [])


def test_validate_hackernews_item_requires_points():
    item = {"title": "x", "url": "http://x", "by": "u", "descendants": 0,
            "created_at": "2026-04-15T00:00:00Z", "hn_url": "http://h"}
    # Missing "points"
    with pytest.raises(SchemaError):
        validate("hackernews_results", [item])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_schemas.py -v`
Expected: `ModuleNotFoundError: No module named 'autofanpage.schemas'`

- [ ] **Step 3: Write `autofanpage/schemas.py`**

```python
"""JSON schema validation for all pipeline artifacts."""
from __future__ import annotations

from typing import Any

import jsonschema

from autofanpage.errors import SchemaError


PROFILE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "name", "page_id", "access_token_ref", "topic", "language",
        "post_times", "timezone", "min_posts_required",
        "max_sources_per_platform", "sources",
    ],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "page_id": {"type": "string", "minLength": 1},
        "access_token_ref": {"type": "string", "pattern": r"^secret:"},
        "topic": {"type": "string", "minLength": 1},
        "language": {"type": "string", "minLength": 2},
        "post_times": {
            "type": "array",
            "minItems": 4, "maxItems": 4,
            "items": {"type": "string", "pattern": r"^\d{2}:\d{2}$"},
        },
        "timezone": {"type": "string", "minLength": 1},
        "filters": {"type": "object"},
        "min_posts_required": {"type": "integer", "minimum": 0, "maximum": 4},
        "max_sources_per_platform": {"type": "integer", "minimum": 1},
        "sources": {
            "type": "object",
            "required": ["youtube", "perplexity", "twitter_via_perplexity",
                         "reddit", "hackernews"],
        },
    },
}


HACKERNEWS_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["title", "url", "points", "by", "descendants",
                 "created_at", "hn_url"],
    "properties": {
        "title": {"type": "string"},
        "url": {"type": "string"},
        "points": {"type": "integer"},
        "by": {"type": "string"},
        "descendants": {"type": "integer"},
        "created_at": {"type": "string"},
        "hn_url": {"type": "string"},
    },
}

HACKERNEWS_RESULTS_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": HACKERNEWS_ITEM_SCHEMA,
}


LAST_SUCCESS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["date", "run_dir", "posts_scheduled", "completed_at"],
    "properties": {
        "date": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        "run_dir": {"type": "string"},
        "posts_scheduled": {"type": "integer", "minimum": 0},
        "completed_at": {"type": "string"},
    },
}


_SCHEMAS = {
    "profile": PROFILE_SCHEMA,
    "hackernews_results": HACKERNEWS_RESULTS_SCHEMA,
    "last_success": LAST_SUCCESS_SCHEMA,
}


def validate(name: str, data: Any) -> None:
    """Validate `data` against schema `name`. Raise SchemaError on failure."""
    if name not in _SCHEMAS:
        raise KeyError(f"unknown schema: {name}")
    validator = jsonschema.Draft7Validator(_SCHEMAS[name])
    errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
    if errors:
        violations = [
            f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in errors
        ]
        raise SchemaError(name, violations)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_schemas.py -v`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add autofanpage/schemas.py tests/test_schemas.py
git commit -m "feat(autofanpage): add JSON schema validation for core artifacts"
```

---

### Task 4: Profile loader

**Files:**
- Create: `autofanpage/profile.py`
- Create: `tests/fixtures/page_test.json`
- Test: `tests/test_profile.py`

- [ ] **Step 1: Write sample fixture `tests/fixtures/page_test.json`**

```json
{
  "name": "page_test",
  "page_id": "000000000000000",
  "access_token_ref": "secret:fb_page_test",
  "topic": "AI automation business",
  "language": "en",
  "post_times": ["08:00", "12:00", "16:00", "20:00"],
  "timezone": "UTC",
  "filters": {"youtube_min_views": 100000, "youtube_min_subs": 10000},
  "min_posts_required": 2,
  "max_sources_per_platform": 12,
  "sources": {
    "youtube": {"enabled": false},
    "perplexity": {"enabled": false},
    "twitter_via_perplexity": {"enabled": false},
    "reddit": {"enabled": false, "subreddits": [], "min_score": 100,
               "time_filter": "week", "top_per_sub": 5},
    "hackernews": {"enabled": true, "min_points": 50}
  }
}
```

- [ ] **Step 2: Write failing test `tests/test_profile.py`**

```python
from pathlib import Path

import pytest
from autofanpage.profile import Profile, load_profile
from autofanpage.errors import ProfileError


def test_load_profile_returns_typed_object(fixtures_dir):
    profile = load_profile(fixtures_dir / "page_test.json")
    assert isinstance(profile, Profile)
    assert profile.name == "page_test"
    assert profile.page_id == "000000000000000"
    assert profile.topic == "AI automation business"
    assert profile.language == "en"
    assert profile.post_times == ["08:00", "12:00", "16:00", "20:00"]
    assert profile.timezone == "UTC"
    assert profile.min_posts_required == 2
    assert profile.sources["hackernews"]["enabled"] is True


def test_load_profile_raises_on_missing_file(tmp_path):
    with pytest.raises(ProfileError, match="not found"):
        load_profile(tmp_path / "missing.json")


def test_load_profile_raises_on_invalid_schema(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"name": "x"}')
    with pytest.raises(ProfileError, match="page_id"):
        load_profile(path)


def test_load_profile_raises_on_malformed_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json")
    with pytest.raises(ProfileError, match="parse"):
        load_profile(path)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_profile.py -v`
Expected: `ModuleNotFoundError: No module named 'autofanpage.profile'`

- [ ] **Step 4: Write `autofanpage/profile.py`**

```python
"""Per-page profile loader."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autofanpage.errors import ProfileError, SchemaError
from autofanpage.schemas import validate


@dataclass(frozen=True)
class Profile:
    name: str
    page_id: str
    access_token_ref: str
    topic: str
    language: str
    post_times: list[str]
    timezone: str
    min_posts_required: int
    max_sources_per_platform: int
    sources: dict[str, Any]
    filters: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        return cls(
            name=data["name"],
            page_id=data["page_id"],
            access_token_ref=data["access_token_ref"],
            topic=data["topic"],
            language=data["language"],
            post_times=list(data["post_times"]),
            timezone=data["timezone"],
            min_posts_required=data["min_posts_required"],
            max_sources_per_platform=data["max_sources_per_platform"],
            sources=data["sources"],
            filters=data.get("filters", {}),
        )


def load_profile(path: str | Path) -> Profile:
    p = Path(path)
    if not p.exists():
        raise ProfileError(f"profile file not found: {p}")
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        raise ProfileError(f"failed to parse profile {p}: {e}") from e
    try:
        validate("profile", data)
    except SchemaError as e:
        raise ProfileError(str(e)) from e
    return Profile.from_dict(data)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_profile.py -v`
Expected: `4 passed`.

- [ ] **Step 6: Commit**

```bash
git add autofanpage/profile.py tests/test_profile.py tests/fixtures/page_test.json
git commit -m "feat(autofanpage): add profile loader with validation"
```

---

### Task 5: Run directory manager

**Files:**
- Create: `autofanpage/run_dir.py`
- Test: `tests/test_run_dir.py`

- [ ] **Step 1: Write failing test**

`tests/test_run_dir.py`:
```python
import json
from pathlib import Path

import pytest
from autofanpage.run_dir import RunDir


def test_create_for_today(tmp_path):
    rd = RunDir.create(base=tmp_path, page="page_test", date="2026-04-15")
    assert rd.path == tmp_path / "runs" / "page_test" / "2026-04-15"
    assert rd.path.is_dir()
    assert rd.log_path == rd.path / "run.log"


def test_write_and_read_json(tmp_path):
    rd = RunDir.create(base=tmp_path, page="p", date="2026-04-15")
    rd.write_json("hackernews_results", [{"title": "x"}])
    assert (rd.path / "hackernews_results.json").exists()
    data = rd.read_json("hackernews_results")
    assert data == [{"title": "x"}]


def test_has_artifact(tmp_path):
    rd = RunDir.create(base=tmp_path, page="p", date="2026-04-15")
    assert not rd.has_artifact("posts")
    rd.write_json("posts", {"posts": []})
    assert rd.has_artifact("posts")


def test_append_log(tmp_path):
    rd = RunDir.create(base=tmp_path, page="p", date="2026-04-15")
    rd.log("hello")
    rd.log("world")
    text = rd.log_path.read_text()
    assert "hello" in text
    assert "world" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_run_dir.py -v`
Expected: `ModuleNotFoundError: No module named 'autofanpage.run_dir'`

- [ ] **Step 3: Write `autofanpage/run_dir.py`**

```python
"""Run-directory management: artifact files + run.log for one day/page."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunDir:
    path: Path

    @property
    def log_path(self) -> Path:
        return self.path / "run.log"

    @classmethod
    def create(cls, base: Path, page: str, date: str) -> "RunDir":
        p = Path(base) / "runs" / page / date
        p.mkdir(parents=True, exist_ok=True)
        return cls(path=p)

    def write_json(self, name: str, data: Any) -> None:
        target = self.path / f"{name}.json"
        target.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def read_json(self, name: str) -> Any:
        return json.loads((self.path / f"{name}.json").read_text())

    def has_artifact(self, name: str) -> bool:
        return (self.path / f"{name}.json").exists()

    def log(self, message: str) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        with self.log_path.open("a") as fh:
            fh.write(f"[{ts}] {message}\n")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_run_dir.py -v`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add autofanpage/run_dir.py tests/test_run_dir.py
git commit -m "feat(autofanpage): add run directory manager"
```

---

### Task 6: State / idempotency manager

**Files:**
- Create: `autofanpage/state.py`
- Test: `tests/test_state.py`

- [ ] **Step 1: Write failing test**

`tests/test_state.py`:
```python
from pathlib import Path

import pytest
from autofanpage.state import LastSuccess


def test_not_ran_yet(tmp_path):
    ls = LastSuccess(base=tmp_path, page="p")
    assert ls.ran_on("2026-04-15") is False


def test_mark_and_check_same_day(tmp_path):
    ls = LastSuccess(base=tmp_path, page="p")
    ls.mark(date="2026-04-15", run_dir=str(tmp_path / "x"), posts_scheduled=4)
    assert ls.ran_on("2026-04-15") is True
    assert ls.ran_on("2026-04-16") is False


def test_mark_overwrites_previous(tmp_path):
    ls = LastSuccess(base=tmp_path, page="p")
    ls.mark(date="2026-04-15", run_dir="a", posts_scheduled=2)
    ls.mark(date="2026-04-16", run_dir="b", posts_scheduled=4)
    assert ls.ran_on("2026-04-15") is False
    assert ls.ran_on("2026-04-16") is True


def test_read_returns_payload(tmp_path):
    ls = LastSuccess(base=tmp_path, page="p")
    ls.mark(date="2026-04-15", run_dir="/x", posts_scheduled=4)
    data = ls.read()
    assert data["date"] == "2026-04-15"
    assert data["run_dir"] == "/x"
    assert data["posts_scheduled"] == 4
    assert "completed_at" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_state.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `autofanpage/state.py`**

```python
"""Idempotency marker for successful daily runs."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from autofanpage.schemas import validate


@dataclass(frozen=True)
class LastSuccess:
    base: Path
    page: str

    @property
    def path(self) -> Path:
        return Path(self.base) / "state" / self.page / "last_success.json"

    def ran_on(self, date: str) -> bool:
        if not self.path.exists():
            return False
        data = json.loads(self.path.read_text())
        return data.get("date") == date

    def read(self) -> dict:
        return json.loads(self.path.read_text())

    def mark(self, *, date: str, run_dir: str, posts_scheduled: int) -> None:
        payload = {
            "date": date,
            "run_dir": str(run_dir),
            "posts_scheduled": posts_scheduled,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        validate("last_success", payload)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_state.py -v`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add autofanpage/state.py tests/test_state.py
git commit -m "feat(autofanpage): add last_success idempotency marker"
```

---

### Task 7: Secrets wrapper

**Files:**
- Create: `autofanpage/secrets.py`
- Test: `tests/test_secrets.py`

- [ ] **Step 1: Write failing test**

`tests/test_secrets.py`:
```python
from unittest.mock import patch

import pytest
from autofanpage.secrets import get_secret, set_backend, SubprocessBackend


def test_get_secret_strips_prefix():
    fake = {"my_key": "s3cret"}

    def backend(name: str) -> str:
        return fake[name]

    set_backend(backend)
    try:
        assert get_secret("secret:my_key") == "s3cret"
    finally:
        set_backend(SubprocessBackend())


def test_get_secret_rejects_non_ref():
    with pytest.raises(ValueError, match="must start with 'secret:'"):
        get_secret("my_key")


def test_subprocess_backend_calls_openclaw(mocker):
    mock_run = mocker.patch("autofanpage.secrets.subprocess.run")
    mock_run.return_value.stdout = "the-value\n"
    mock_run.return_value.returncode = 0

    backend = SubprocessBackend()
    result = backend("abc")

    assert result == "the-value"
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args[0] == "openclaw"
    assert "secrets" in args
    assert "get" in args
    assert "abc" in args
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_secrets.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `autofanpage/secrets.py`**

```python
"""Secret resolution. Default backend shells out to `openclaw secrets get`."""
from __future__ import annotations

import subprocess
from typing import Callable


class SubprocessBackend:
    """Shell out to `openclaw secrets get <name>`."""

    def __call__(self, name: str) -> str:
        result = subprocess.run(
            ["openclaw", "secrets", "get", name],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()


_backend: Callable[[str], str] = SubprocessBackend()


def set_backend(backend: Callable[[str], str]) -> None:
    """Install a custom backend (used by tests)."""
    global _backend
    _backend = backend


def get_secret(ref: str) -> str:
    """Resolve a `secret:<name>` reference to the actual value."""
    if not ref.startswith("secret:"):
        raise ValueError(f"secret ref must start with 'secret:', got {ref!r}")
    name = ref[len("secret:"):]
    return _backend(name)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_secrets.py -v`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add autofanpage/secrets.py tests/test_secrets.py
git commit -m "feat(autofanpage): add openclaw secrets wrapper"
```

---

### Task 8: Sub-skill dispatcher

**Files:**
- Create: `autofanpage/dispatch.py`
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write failing test**

`tests/test_dispatch.py`:
```python
import json
from unittest.mock import MagicMock

import pytest
from autofanpage.dispatch import run_skill, set_backend, SubprocessBackend
from autofanpage.errors import SkillInvocationError


def test_run_skill_uses_custom_backend():
    captured = {}

    def backend(name, args):
        captured["name"] = name
        captured["args"] = args
        return {"ok": True}

    set_backend(backend)
    try:
        result = run_skill("youtube-researcher", {"run_dir": "/tmp/x"})
    finally:
        set_backend(SubprocessBackend())

    assert result == {"ok": True}
    assert captured["name"] == "youtube-researcher"
    assert captured["args"] == {"run_dir": "/tmp/x"}


def test_subprocess_backend_parses_json_stdout(mocker):
    mock_run = mocker.patch("autofanpage.dispatch.subprocess.run")
    mock_run.return_value.stdout = '{"result": 42}'
    mock_run.return_value.returncode = 0

    backend = SubprocessBackend()
    result = backend("my-skill", {"k": "v"})

    assert result == {"result": 42}
    args = mock_run.call_args[0][0]
    assert args == ["openclaw", "skills", "run", "my-skill",
                    "--args", '{"k": "v"}']


def test_subprocess_backend_raises_on_failure(mocker):
    import subprocess as sp
    mock_run = mocker.patch("autofanpage.dispatch.subprocess.run")
    mock_run.side_effect = sp.CalledProcessError(1, "openclaw", stderr="boom")

    with pytest.raises(SkillInvocationError, match="boom"):
        SubprocessBackend()("my-skill", {})


def test_subprocess_backend_raises_on_bad_json(mocker):
    mock_run = mocker.patch("autofanpage.dispatch.subprocess.run")
    mock_run.return_value.stdout = "not json"
    mock_run.return_value.returncode = 0

    with pytest.raises(SkillInvocationError, match="JSON"):
        SubprocessBackend()("my-skill", {})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dispatch.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `autofanpage/dispatch.py`**

```python
"""Sub-skill dispatcher. Default backend shells out to `openclaw skills run`."""
from __future__ import annotations

import json
import subprocess
from typing import Any, Callable

from autofanpage.errors import SkillInvocationError


class SubprocessBackend:
    """Shell out to `openclaw skills run <name> --args <json>`."""

    def __call__(self, name: str, args: dict[str, Any]) -> Any:
        args_json = json.dumps(args)
        try:
            result = subprocess.run(
                ["openclaw", "skills", "run", name, "--args", args_json],
                capture_output=True, text=True, check=True,
            )
        except subprocess.CalledProcessError as e:
            raise SkillInvocationError(
                f"skill {name!r} failed: {e.stderr or e.stdout}"
            ) from e
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise SkillInvocationError(
                f"skill {name!r} did not return JSON: {result.stdout!r}"
            ) from e


_backend: Callable[[str, dict[str, Any]], Any] = SubprocessBackend()


def set_backend(backend: Callable[[str, dict[str, Any]], Any]) -> None:
    global _backend
    _backend = backend


def run_skill(name: str, args: dict[str, Any]) -> Any:
    """Run another OpenClaw skill and return its JSON result."""
    return _backend(name, args)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dispatch.py -v`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add autofanpage/dispatch.py tests/test_dispatch.py
git commit -m "feat(autofanpage): add sub-skill dispatcher"
```

---

### Task 9: Hacker News fetcher logic (pure function, network-free for tests)

**Files:**
- Create: `autofanpage/sources/__init__.py`
- Create: `autofanpage/sources/hackernews.py`
- Test: `tests/sources/test_hackernews.py`
- Test fixture: `tests/fixtures/hn_items.json`

- [ ] **Step 1: Create the fixture `tests/fixtures/hn_items.json`**

```json
[
  {"id": 1, "type": "story", "title": "GPT-5 released", "url": "https://openai.com/gpt5",
   "score": 450, "by": "sama", "descendants": 200, "time": 1744156800},
  {"id": 2, "type": "story", "title": "Ask HN: what editor?", "url": null,
   "score": 80, "by": "u2", "descendants": 50, "time": 1744156800},
  {"id": 3, "type": "story", "title": "New AI chip beats H100", "url": "https://example.com/chip",
   "score": 300, "by": "u3", "descendants": 120, "time": 1744156800},
  {"id": 4, "type": "story", "title": "Unrelated story", "url": "https://ex.com/x",
   "score": 200, "by": "u4", "descendants": 40, "time": 1744156800},
  {"id": 5, "type": "job", "title": "We are hiring", "url": "https://j.com",
   "score": 100, "by": "u5", "descendants": 0, "time": 1744156800}
]
```

- [ ] **Step 2: Write failing test `tests/sources/test_hackernews.py`**

Create `tests/sources/__init__.py` (empty), then:

```python
import json
from pathlib import Path

import pytest
from autofanpage.sources.hackernews import (
    filter_and_rank, matches_topic, to_result,
)


@pytest.fixture
def items(fixtures_dir):
    return json.loads((fixtures_dir / "hn_items.json").read_text())


def test_matches_topic_substring_any_word():
    assert matches_topic("GPT-5 released today", "AI automation") is False
    assert matches_topic("New AI chip beats H100", "AI automation") is True
    assert matches_topic("automated workflow wins", "AI automation") is True


def test_matches_topic_case_insensitive():
    assert matches_topic("OPENAI ships GPT", "openai") is True


def test_filter_rejects_low_score(items):
    out = filter_and_rank(items, topic="AI", min_points=100, limit=10)
    ids = [i["id"] for i in out]
    assert 2 not in ids  # score 80 < 100


def test_filter_rejects_non_story(items):
    out = filter_and_rank(items, topic="hiring", min_points=0, limit=10)
    ids = [i["id"] for i in out]
    assert 5 not in ids  # type=job


def test_filter_requires_topic_match(items):
    out = filter_and_rank(items, topic="GPT", min_points=0, limit=10)
    titles = [i["title"] for i in out]
    # story 1 matches, story 3/4 do not
    assert "GPT-5 released" in titles
    assert "Unrelated story" not in titles


def test_sorted_by_score_desc(items):
    out = filter_and_rank(items, topic="AI OR GPT", min_points=0, limit=10)
    scores = [i["score"] for i in out]
    assert scores == sorted(scores, reverse=True)


def test_limit(items):
    out = filter_and_rank(items, topic="a", min_points=0, limit=1)
    assert len(out) == 1


def test_to_result_has_required_shape():
    item = {"id": 42, "title": "t", "url": "https://x.com",
            "score": 150, "by": "u", "descendants": 9, "time": 1744156800}
    r = to_result(item)
    assert r["title"] == "t"
    assert r["url"] == "https://x.com"
    assert r["points"] == 150
    assert r["by"] == "u"
    assert r["descendants"] == 9
    assert r["hn_url"] == "https://news.ycombinator.com/item?id=42"
    assert r["created_at"].startswith("2025-") or r["created_at"].startswith("2024-")


def test_to_result_ask_hn_uses_hn_url_as_url():
    item = {"id": 2, "title": "Ask HN", "url": None,
            "score": 80, "by": "u", "descendants": 5, "time": 1744156800}
    r = to_result(item)
    assert r["url"] == r["hn_url"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/sources/test_hackernews.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Write `autofanpage/sources/__init__.py`** (empty) **and `autofanpage/sources/hackernews.py`**

```python
"""Pure logic for Hacker News source filtering and shaping.

Network calls live in `skills/hackernews-researcher/scripts/fetch_hn.py`;
this module is network-free so it can be unit tested deterministically.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable


def matches_topic(title: str, topic: str) -> bool:
    """True if any word of topic is a case-insensitive substring of title."""
    title_l = title.lower()
    for word in topic.lower().split():
        if word and word in title_l:
            return True
    return False


def filter_and_rank(
    items: Iterable[dict[str, Any]],
    *,
    topic: str,
    min_points: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Apply HN filters: type=story, score>=min_points, title matches topic.

    Returns top `limit` items sorted by score descending.
    """
    keep: list[dict[str, Any]] = []
    for item in items:
        if item.get("type") != "story":
            continue
        if item.get("score", 0) < min_points:
            continue
        if not matches_topic(item.get("title", ""), topic):
            continue
        keep.append(item)
    keep.sort(key=lambda i: i.get("score", 0), reverse=True)
    return keep[:limit]


def to_result(item: dict[str, Any]) -> dict[str, Any]:
    """Shape an HN item into the pipeline's hackernews_results schema."""
    hn_url = f"https://news.ycombinator.com/item?id={item['id']}"
    created_at = datetime.fromtimestamp(
        item["time"], tz=timezone.utc
    ).isoformat()
    return {
        "title": item["title"],
        "url": item["url"] or hn_url,
        "points": item["score"],
        "by": item["by"],
        "descendants": item.get("descendants", 0),
        "created_at": created_at,
        "hn_url": hn_url,
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/sources/test_hackernews.py -v`
Expected: `9 passed`.

- [ ] **Step 6: Commit**

```bash
git add autofanpage/sources/ tests/sources/ tests/fixtures/hn_items.json
git commit -m "feat(sources): add hackernews filter/rank/shape logic"
```

---

### Task 10: Hacker News network fetcher (skill script)

**Files:**
- Create: `skills/hackernews-researcher/SKILL.md`
- Create: `skills/hackernews-researcher/scripts/__init__.py`
- Create: `skills/hackernews-researcher/scripts/fetch_hn.py`
- Test: `tests/skills/test_hackernews_fetch.py`

- [ ] **Step 1: Write failing integration test `tests/skills/test_hackernews_fetch.py`**

Create `tests/skills/__init__.py` (empty), then:

```python
import json
from pathlib import Path
import sys

import pytest
import responses

# Import by path since skills/ is not a package
SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "hackernews-researcher" / "scripts"
sys.path.insert(0, str(SCRIPT))
import fetch_hn  # noqa: E402


@responses.activate
def test_fetch_returns_filtered_results(tmp_path):
    # Mock top stories list
    responses.add(
        responses.GET,
        "https://hacker-news.firebaseio.com/v0/topstories.json",
        json=[1, 2, 3],
    )
    # Mock individual items
    responses.add(
        responses.GET,
        "https://hacker-news.firebaseio.com/v0/item/1.json",
        json={"id": 1, "type": "story", "title": "AI breakthrough",
              "url": "https://x.com/a", "score": 200, "by": "u1",
              "descendants": 30, "time": 1744156800},
    )
    responses.add(
        responses.GET,
        "https://hacker-news.firebaseio.com/v0/item/2.json",
        json={"id": 2, "type": "story", "title": "Not relevant",
              "url": "https://x.com/b", "score": 300, "by": "u2",
              "descendants": 10, "time": 1744156800},
    )
    responses.add(
        responses.GET,
        "https://hacker-news.firebaseio.com/v0/item/3.json",
        json={"id": 3, "type": "story", "title": "AI automation wins",
              "url": "https://x.com/c", "score": 500, "by": "u3",
              "descendants": 80, "time": 1744156800},
    )

    results = fetch_hn.run(
        topic="AI automation",
        min_points=100,
        limit=10,
        top_n=3,
    )

    titles = [r["title"] for r in results]
    assert "AI automation wins" in titles
    assert "AI breakthrough" in titles
    assert "Not relevant" not in titles
    # Sorted by points desc
    assert results[0]["points"] >= results[-1]["points"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/skills/test_hackernews_fetch.py -v`
Expected: `ModuleNotFoundError: No module named 'fetch_hn'`.

- [ ] **Step 3: Write the skill scaffolding**

`skills/hackernews-researcher/scripts/__init__.py`: empty.

`skills/hackernews-researcher/scripts/fetch_hn.py`:
```python
"""Hacker News researcher entry point.

Usage (from OpenClaw):
    python fetch_hn.py --run-dir <path> --profile <path>

Writes:
    <run_dir>/hackernews_results.json
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

# Ensure autofanpage package is importable
_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

from autofanpage.profile import load_profile  # noqa: E402
from autofanpage.run_dir import RunDir  # noqa: E402
from autofanpage.schemas import validate  # noqa: E402
from autofanpage.sources.hackernews import filter_and_rank, to_result  # noqa: E402


HN_BASE = "https://hacker-news.firebaseio.com/v0"


def _fetch_top_ids(top_n: int) -> list[int]:
    r = requests.get(f"{HN_BASE}/topstories.json", timeout=10)
    r.raise_for_status()
    return r.json()[:top_n]


def _fetch_item(item_id: int) -> dict:
    r = requests.get(f"{HN_BASE}/item/{item_id}.json", timeout=10)
    r.raise_for_status()
    return r.json()


def run(*, topic: str, min_points: int, limit: int, top_n: int = 200) -> list[dict]:
    ids = _fetch_top_ids(top_n)
    with ThreadPoolExecutor(max_workers=20) as pool:
        items = list(pool.map(_fetch_item, ids))
    filtered = filter_and_rank(
        items, topic=topic, min_points=min_points, limit=limit,
    )
    return [to_result(i) for i in filtered]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--profile", required=True)
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    rd = RunDir(path=Path(args.run_dir))

    hn_cfg = profile.sources.get("hackernews", {})
    if not hn_cfg.get("enabled", False):
        rd.write_json("hackernews_results", [])
        print(json.dumps({"skipped": True, "count": 0}))
        return 0

    results = run(
        topic=profile.topic,
        min_points=hn_cfg.get("min_points", 50),
        limit=10,
    )
    validate("hackernews_results", results)
    rd.write_json("hackernews_results", results)
    print(json.dumps({"count": len(results)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/skills/test_hackernews_fetch.py -v`
Expected: `1 passed`.

- [ ] **Step 5: Write `skills/hackernews-researcher/SKILL.md`**

```markdown
---
name: hackernews-researcher
description: Fetch top Hacker News stories matching the page topic for the past week
---

# hackernews-researcher

Phase 1 data-source skill: pulls top Hacker News stories for the current week,
filters by score + topic match, and writes `hackernews_results.json` to the run
directory.

## Inputs (JSON args)

- `run_dir` — absolute path to today's run directory
- `profile` — absolute path to the page profile JSON

## Behavior

The skill is a thin wrapper around `scripts/fetch_hn.py`. It:

1. Loads the profile.
2. If `sources.hackernews.enabled` is `false`, writes an empty
   `hackernews_results.json` and exits.
3. Otherwise pulls the top 200 stories from `hacker-news.firebaseio.com`,
   keeps only `type=story` items with `score >= sources.hackernews.min_points`
   whose titles mention any word of the page topic (case-insensitive),
   and returns the top 10 by score.

## Output

Writes `<run_dir>/hackernews_results.json` — an array of
`{title, url, points, by, descendants, created_at, hn_url}`.

Stdout returns a one-line JSON `{"count": N}` that the orchestrator reads.

## Invocation

Run via the Python entrypoint:

    python scripts/fetch_hn.py --run-dir <path> --profile <path>

## No auth required.
```

- [ ] **Step 6: Commit**

```bash
git add skills/hackernews-researcher/ tests/skills/test_hackernews_fetch.py tests/skills/__init__.py
git commit -m "feat(hackernews-researcher): skill + fetcher"
```

---

### Task 11: Telegram reporter skill

**Files:**
- Create: `autofanpage/telegram.py`
- Test: `tests/test_telegram.py`
- Create: `skills/telegram-reporter/SKILL.md`
- Create: `skills/telegram-reporter/scripts/report.py`
- Test: `tests/skills/test_telegram_report.py`

**Note on transport:** OpenClaw's native Telegram channel delivers messages by printing to stdout within the agent turn (per OpenClaw "Chat Integrations" — confirm exact mechanism on first smoke test). Until we verify, this skill writes the message both to stdout (as JSON) AND to a log file `run_dir/telegram_sent.log`, so we can inspect it manually even if the OpenClaw-side wiring isn't perfect on first try.

- [ ] **Step 1: Write failing test for template formatting**

`tests/test_telegram.py`:
```python
from autofanpage.telegram import format_message


def test_success_template_includes_page_and_count():
    msg = format_message(
        status="success",
        page="page_vn_ai",
        details={"date": "2026-04-15", "posts_scheduled": 4,
                 "elapsed_sec": 287},
    )
    assert "✅" in msg
    assert "page_vn_ai" in msg
    assert "2026-04-15" in msg
    assert "4" in msg


def test_error_template_includes_phase_and_cause():
    msg = format_message(
        status="error",
        page="p",
        details={"phase": "notebooklm-analyzer", "cause": "cookie expired",
                 "log_tail": "line1\nline2"},
    )
    assert "🚨" in msg
    assert "notebooklm-analyzer" in msg
    assert "cookie expired" in msg
    assert "line1" in msg


def test_partial_template():
    msg = format_message(
        status="partial",
        page="p",
        details={"reason": "Review approved 2/4 insights",
                 "post_ids": ["123_1", "123_2"]},
    )
    assert "⚠️" in msg
    assert "2/4" in msg


def test_info_template():
    msg = format_message(status="info", page="p",
                         details={"message": "already ran today"})
    assert "ℹ️" in msg
    assert "already ran today" in msg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_telegram.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `autofanpage/telegram.py`**

```python
"""Telegram message formatting. Transport is handled by the skill script."""
from __future__ import annotations

from typing import Any


_PREFIX = {"success": "✅", "error": "🚨", "partial": "⚠️", "info": "ℹ️"}


def format_message(*, status: str, page: str, details: dict[str, Any]) -> str:
    if status not in _PREFIX:
        raise ValueError(f"unknown status: {status}")
    prefix = _PREFIX[status]
    header = f"{prefix} AutoFanpage [{page}]"

    if status == "success":
        lines = [
            header,
            f"📝 {details['posts_scheduled']} posts scheduled",
            f"📅 {details['date']}",
            f"⏱ {details['elapsed_sec']}s",
        ]
    elif status == "error":
        lines = [
            header,
            f"Phase: {details['phase']}",
            f"Cause: {details['cause']}",
            "",
            "Log tail:",
            details.get("log_tail", "(no log)"),
        ]
    elif status == "partial":
        lines = [
            header,
            details["reason"],
            "Scheduled post ids:",
            *[f"- {pid}" for pid in details.get("post_ids", [])],
        ]
    else:  # info
        lines = [header, details["message"]]

    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_telegram.py -v`
Expected: `4 passed`.

- [ ] **Step 5: Write failing test for skill entry point**

`tests/skills/test_telegram_report.py`:
```python
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "telegram-reporter" / "scripts"
sys.path.insert(0, str(SCRIPT))
import report  # noqa: E402


def test_report_writes_log_and_prints_json(tmp_path, capsys):
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    exit_code = report.main([
        "--run-dir", str(run_dir),
        "--status", "success",
        "--page", "page_test",
        "--details", json.dumps({"date": "2026-04-15",
                                 "posts_scheduled": 4, "elapsed_sec": 10}),
    ])
    assert exit_code == 0

    # Log was written
    log = (run_dir / "telegram_sent.log").read_text()
    assert "page_test" in log
    assert "4 posts scheduled" in log

    # Stdout contained the JSON envelope
    captured = capsys.readouterr()
    envelope = json.loads(captured.out.strip().splitlines()[-1])
    assert envelope["status"] == "success"
    assert envelope["sent"] is True
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/skills/test_telegram_report.py -v`
Expected: `ModuleNotFoundError: No module named 'report'`.

- [ ] **Step 7: Write `skills/telegram-reporter/scripts/report.py`**

```python
"""Telegram reporter entrypoint.

Writes the formatted message to `<run_dir>/telegram_sent.log` and prints a
JSON envelope to stdout that OpenClaw's Telegram channel forwards to the
user's paired chat.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

from autofanpage.telegram import format_message  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--status", required=True,
                        choices=["success", "error", "partial", "info"])
    parser.add_argument("--page", required=True)
    parser.add_argument("--details", required=True,
                        help="JSON object with status-specific keys")
    args = parser.parse_args(argv)

    details = json.loads(args.details)
    msg = format_message(status=args.status, page=args.page, details=details)

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "telegram_sent.log").open("a") as fh:
        fh.write(msg + "\n---\n")

    # Print the full message for OpenClaw Telegram channel to forward.
    print(msg)
    # Also emit a JSON envelope on the final line for callers that parse it.
    print(json.dumps({"status": args.status, "page": args.page, "sent": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/skills/test_telegram_report.py -v`
Expected: `1 passed`.

- [ ] **Step 9: Write `skills/telegram-reporter/SKILL.md`**

```markdown
---
name: telegram-reporter
description: Send a formatted status message about a pipeline run to the user's paired Telegram channel
---

# telegram-reporter

Terminal skill at the end (or on any error branch) of every
`daily-content-pipeline` run. Formats the run summary and emits it to stdout,
which the OpenClaw Telegram channel forwards to the user's paired chat.

## Inputs (CLI args to `scripts/report.py`)

- `--run-dir <path>` — today's run directory; the skill appends the message
  to `<run_dir>/telegram_sent.log` as a tamper-proof audit.
- `--status <success|error|partial|info>` — which template to use.
- `--page <name>` — the page this run belongs to.
- `--details <json>` — status-specific payload:
  - success: `{date, posts_scheduled, elapsed_sec}`
  - error: `{phase, cause, log_tail}`
  - partial: `{reason, post_ids}`
  - info: `{message}`

## Output

Prints the formatted message to stdout, followed by a JSON envelope
`{"status", "page", "sent"}` on the last line.
```

- [ ] **Step 10: Commit**

```bash
git add autofanpage/telegram.py tests/test_telegram.py skills/telegram-reporter/ tests/skills/test_telegram_report.py
git commit -m "feat(telegram-reporter): skill + formatting helper"
```

---

### Task 12: Orchestrator skill (HN + Telegram vertical slice)

**Files:**
- Create: `skills/daily-content-pipeline/SKILL.md`
- Create: `skills/daily-content-pipeline/scripts/orchestrate.py`
- Test: `tests/skills/test_orchestrator.py`

- [ ] **Step 1: Write failing end-to-end test**

`tests/skills/test_orchestrator.py`:
```python
import json
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "daily-content-pipeline" / "scripts"
sys.path.insert(0, str(SCRIPT))
import orchestrate  # noqa: E402


@pytest.fixture
def test_env(tmp_path, fixtures_dir):
    # Stage a profile pointing at a disabled-everywhere config, HN only
    profile_src = fixtures_dir / "page_test.json"
    profile_dst = tmp_path / "page_test.json"
    shutil.copy(profile_src, profile_dst)
    return {
        "base": tmp_path,
        "profile": profile_dst,
        "page": "page_test",
    }


def test_orchestrator_aborts_if_already_ran(test_env, mocker):
    # Pre-populate last_success for today
    from autofanpage.state import LastSuccess
    LastSuccess(base=test_env["base"], page="page_test").mark(
        date="2026-04-15", run_dir="x", posts_scheduled=4,
    )

    mock_run_skill = mocker.patch("orchestrate.run_skill")
    exit_code = orchestrate.main([
        "--page", "page_test",
        "--profile-path", str(test_env["profile"]),
        "--base-dir", str(test_env["base"]),
        "--date", "2026-04-15",
    ])
    assert exit_code == 0

    # Only telegram-reporter should have been called (with info status)
    calls = mock_run_skill.call_args_list
    assert len(calls) == 1
    assert calls[0][0][0] == "telegram-reporter"
    assert calls[0][0][1]["status"] == "info"


def test_orchestrator_runs_hn_then_telegram(test_env, mocker):
    # Stub run_skill to record calls and return fake HN count
    captured = []

    def fake_run_skill(name, args):
        captured.append((name, args))
        if name == "hackernews-researcher":
            # Simulate the real skill writing its output file
            run_dir = Path(args["run_dir"])
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "hackernews_results.json").write_text("[]")
            return {"count": 0}
        if name == "telegram-reporter":
            return {"status": args["status"], "sent": True}
        raise AssertionError(f"unexpected skill: {name}")

    mocker.patch("orchestrate.run_skill", side_effect=fake_run_skill)

    exit_code = orchestrate.main([
        "--page", "page_test",
        "--profile-path", str(test_env["profile"]),
        "--base-dir", str(test_env["base"]),
        "--date", "2026-04-15",
    ])
    assert exit_code == 0

    skills_called = [c[0] for c in captured]
    assert "hackernews-researcher" in skills_called
    assert "telegram-reporter" in skills_called
    # Telegram reported success (HN produced 0 results but no errors)
    tg_call = next(c for c in captured if c[0] == "telegram-reporter")
    assert tg_call[1]["status"] == "success"

    # State was marked
    from autofanpage.state import LastSuccess
    assert LastSuccess(base=test_env["base"], page="page_test").ran_on("2026-04-15")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/skills/test_orchestrator.py -v`
Expected: `ModuleNotFoundError: No module named 'orchestrate'`.

- [ ] **Step 3: Write `skills/daily-content-pipeline/scripts/orchestrate.py`**

```python
"""Orchestrator entry point for the AutoFanpage daily pipeline.

Plan 1 vertical slice: calls hackernews-researcher then telegram-reporter.
Plan 2+ will add the remaining phases.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

from autofanpage.dispatch import run_skill  # noqa: E402
from autofanpage.errors import AutofanpageError, SkillInvocationError  # noqa: E402
from autofanpage.profile import load_profile  # noqa: E402
from autofanpage.run_dir import RunDir  # noqa: E402
from autofanpage.state import LastSuccess  # noqa: E402


def _report(run_dir: Path, *, status: str, page: str, details: dict) -> None:
    """Fire-and-forget call to telegram-reporter."""
    try:
        run_skill("telegram-reporter", {
            "run_dir": str(run_dir),
            "status": status,
            "page": page,
            "details": details,
        })
    except SkillInvocationError as e:
        # Don't let a reporter failure mask the real error path.
        sys.stderr.write(f"[orchestrate] telegram-reporter failed: {e}\n")


def _today(profile_tz: str) -> str:
    return datetime.now(tz=ZoneInfo(profile_tz)).strftime("%Y-%m-%d")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", required=True)
    parser.add_argument("--profile-path", required=True)
    parser.add_argument("--base-dir", required=True,
                        help="~/.openclaw/autofanpage or override for tests")
    parser.add_argument("--date", default=None,
                        help="Override date (for tests); defaults to today")
    args = parser.parse_args(argv)

    base = Path(args.base_dir)
    profile = load_profile(args.profile_path)
    date = args.date or _today(profile.timezone)

    state = LastSuccess(base=base, page=args.page)
    if state.ran_on(date):
        run_dir = RunDir.create(base=base, page=args.page, date=date)
        _report(run_dir.path, status="info", page=args.page,
                details={"message": f"already ran on {date}"})
        return 0

    run_dir = RunDir.create(base=base, page=args.page, date=date)
    run_dir.log(f"orchestrator start page={args.page} date={date}")
    started = time.monotonic()

    try:
        # Phase 1 (Plan 1 slice: HN only)
        result = run_skill("hackernews-researcher", {
            "run_dir": str(run_dir.path),
            "profile": str(args.profile_path),
        })
        run_dir.log(f"hackernews-researcher -> {json.dumps(result)}")

        # Plan 1 stops here. Mark success and report.
        elapsed = int(time.monotonic() - started)
        posts_scheduled = 0  # No publishing in Plan 1
        state.mark(date=date, run_dir=str(run_dir.path),
                   posts_scheduled=posts_scheduled)
        _report(run_dir.path, status="success", page=args.page, details={
            "date": date,
            "posts_scheduled": posts_scheduled,
            "elapsed_sec": elapsed,
        })
        return 0

    except AutofanpageError as e:
        run_dir.log(f"ERROR: {e}")
        log_tail = "\n".join(
            run_dir.log_path.read_text().splitlines()[-20:]
        )
        _report(run_dir.path, status="error", page=args.page, details={
            "phase": "orchestrator",
            "cause": str(e),
            "log_tail": log_tail,
        })
        return 1
    except Exception as e:  # noqa: BLE001
        run_dir.log(f"UNEXPECTED: {type(e).__name__}: {e}")
        log_tail = "\n".join(
            run_dir.log_path.read_text().splitlines()[-20:]
        )
        _report(run_dir.path, status="error", page=args.page, details={
            "phase": "orchestrator",
            "cause": f"{type(e).__name__}: {e}",
            "log_tail": log_tail,
        })
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/skills/test_orchestrator.py -v`
Expected: `2 passed`.

- [ ] **Step 5: Write `skills/daily-content-pipeline/SKILL.md`**

```markdown
---
name: daily-content-pipeline
description: Orchestrator for the AutoFanpage daily content automation pipeline
---

# daily-content-pipeline

Top-level, user-invocable orchestrator for AutoFanpage.

**Plan 1 scope:** this version only calls `hackernews-researcher` then
`telegram-reporter`, to validate the skill-invocation and reporting path.
Plan 2+ add the rest of the phases.

## Invocation

    /daily_content_pipeline page=<name>

The slash command resolves to:

    python scripts/orchestrate.py --page <name> \
        --profile-path ~/.openclaw/autofanpage/pages/<name>.json \
        --base-dir ~/.openclaw/autofanpage

## Flow (Plan 1)

1. Load & validate the page profile.
2. Resolve today's date in the profile's timezone.
3. Abort + `info` Telegram if `last_success.json.date == today`.
4. Create `runs/<page>/<today>/` run directory.
5. Invoke `hackernews-researcher`; it writes `hackernews_results.json`.
6. Mark success in `state/<page>/last_success.json`.
7. Invoke `telegram-reporter` with the run summary.

Any exception in steps 4–6 routes to `telegram-reporter` with status=error
and the last 20 lines of `run.log`.
```

- [ ] **Step 6: Commit**

```bash
git add skills/daily-content-pipeline/ tests/skills/test_orchestrator.py
git commit -m "feat(orchestrator): Plan-1 vertical slice (HN + Telegram)"
```

---

### Task 13: Install script (sync `skills/` to OpenClaw)

**Files:**
- Create: `scripts/install-skills.sh`

- [ ] **Step 1: Write the install script**

`scripts/install-skills.sh`:
```bash
#!/usr/bin/env bash
# Sync the skill folders in this repo to the OpenClaw skills directory.
# Usage: ./scripts/install-skills.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${OPENCLAW_SKILLS_DIR:-$HOME/.openclaw/skills}/autofanpage"

echo "Installing skills from $REPO_ROOT/skills -> $TARGET"
mkdir -p "$TARGET"

for skill_dir in "$REPO_ROOT"/skills/*/; do
    skill_name="$(basename "$skill_dir")"
    dest="$TARGET/$skill_name"
    rm -rf "$dest"
    cp -R "$skill_dir" "$dest"
    echo "  ✓ $skill_name"
done

echo "Done. Skills installed at $TARGET"
echo "Verify with: openclaw skills list | grep autofanpage"
```

- [ ] **Step 2: Make it executable**

Run: `chmod +x /Users/nguyenloc/VibeCoding/AutoFanpage/scripts/install-skills.sh`

- [ ] **Step 3: Smoke-test the script against a scratch target directory**

Run:
```bash
cd /Users/nguyenloc/VibeCoding/AutoFanpage
OPENCLAW_SKILLS_DIR=/tmp/fake-openclaw-skills ./scripts/install-skills.sh
ls /tmp/fake-openclaw-skills/autofanpage/
```
Expected output includes: `daily-content-pipeline  hackernews-researcher  telegram-reporter`

- [ ] **Step 4: Clean up**

Run: `rm -rf /tmp/fake-openclaw-skills`

- [ ] **Step 5: Commit**

```bash
git add scripts/install-skills.sh
git commit -m "chore: add install-skills.sh to sync skill folders to openclaw"
```

---

### Task 14: Manual smoke test documentation

**Files:**
- Create: `docs/superpowers/smoke-tests/plan1.md`

- [ ] **Step 1: Write the smoke-test doc**

`docs/superpowers/smoke-tests/plan1.md`:
```markdown
# Plan 1 — Manual Smoke Test

Run this once after Plan 1 is implemented to confirm the vertical slice works
on real OpenClaw before moving to Plan 2.

## Prerequisites

- OpenClaw gateway running locally.
- Telegram channel paired and verified (you can send yourself a test message
  via `openclaw channels status`).
- `autofanpage` Python package installed: `pip install -e .[dev]` from repo root.

## Steps

1. Install the three Plan 1 skills into OpenClaw:

       ./scripts/install-skills.sh
       openclaw skills list | grep autofanpage   # expect 3 rows

2. Create a test profile at `~/.openclaw/autofanpage/pages/page_test.json`.
   Copy from `tests/fixtures/page_test.json`. Edit:
   - `page_id`: any non-empty string (not used in Plan 1)
   - `topic`: something that will match HN titles, e.g. `"AI"`
   - `sources.hackernews.enabled`: `true`
   - `sources.hackernews.min_points`: lower to `50` if you want more results

3. Invoke the orchestrator:

       openclaw skills run daily-content-pipeline --args \
           '{"page": "page_test", "profile_path": "~/.openclaw/autofanpage/pages/page_test.json", "base_dir": "~/.openclaw/autofanpage"}'

   (Exact flag names depend on how the slash command is wired; adjust to
   whatever `/daily_content_pipeline page=page_test` expands to.)

4. Expect on your Telegram:

       ✅ AutoFanpage [page_test]
       📝 0 posts scheduled
       📅 <today>
       ⏱ <N>s

5. Inspect the run directory:

       ls ~/.openclaw/autofanpage/runs/page_test/<today>/
       # Should include: hackernews_results.json, run.log, telegram_sent.log

6. Confirm idempotency: re-run the same command.
   Expected Telegram: `ℹ️ AutoFanpage [page_test]  already ran on <today>`.

## Troubleshooting

- **"openclaw: command not found"** — activate OpenClaw's env or add it to PATH.
- **"skill not found: hackernews-researcher"** — rerun `install-skills.sh`; confirm
  `openclaw skills list` sees it.
- **Telegram silent** — verify channel pairing with `openclaw channels status`;
  check `telegram_sent.log` in the run directory for the formatted message
  (this confirms the orchestrator formatted it correctly even if the channel
  transport is broken).
- **HN returns 0 items** — lower `min_points` in the profile and broaden `topic`.

## Success criteria

All 6 steps complete without intervention, both the success Telegram and the
idempotency Telegram arrive, and the run directory contains the expected
artifacts.
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/smoke-tests/plan1.md
git commit -m "docs: add Plan 1 smoke test procedure"
```

---

### Task 15: Full test suite green + coverage check

- [ ] **Step 1: Run the full test suite**

Run: `pytest -v`
Expected: All tests from Tasks 2–12 pass. Roughly 25+ tests.

- [ ] **Step 2: Check coverage of the core library**

Run: `pytest --cov=autofanpage --cov-report=term-missing`
Expected: `autofanpage/` package coverage ≥ 85%. Lines uncovered should be limited to subprocess backends (exercised manually in smoke test) and error paths hard to reach without real OpenClaw.

- [ ] **Step 3: If coverage < 85%, add targeted tests**

Identify the uncovered branches from Step 2 output and add tests. Commit separately:
```bash
git add tests/
git commit -m "test: lift autofanpage coverage above 85%"
```

- [ ] **Step 4: Tag Plan 1 milestone**

```bash
git tag -a plan1-complete -m "Plan 1: foundation + HN+Telegram vertical slice"
```

---

## Self-review against the spec

Spec coverage (Plan 1 scope only):
- §2 file layout — implemented in Tasks 1, 10, 11, 12 (skill folders + python package + runtime data layout via `RunDir` and `LastSuccess`).
- §3.1 orchestrator — Plan 1 implements steps 1–3 (profile load, date, idempotency check) plus the HN branch of step 4. Remaining steps (Perplexity/YouTube/Reddit merge, NotebookLM, Review/Writing/Publisher) intentionally deferred to Plans 2–4.
- §3.5 hackernews-researcher — Task 9 (pure logic) + Task 10 (network + skill wiring).
- §3.10 telegram-reporter — Task 11 (formatting + skill wiring). Transport via OpenClaw native channel is confirmed on the smoke test (Task 14).
- §3.11 autofanpage-health-check — deferred to Plan 4.
- §4.1 profile schema — Task 3 schemas + Task 4 profile loader.
- §4.3 last_success.json — Task 6.
- §5 error handling — orchestrator catches `AutofanpageError` + `Exception` and routes both to `telegram-reporter` with `status=error`. The specific error rows in §5 for YouTube/Perplexity/Reddit/NotebookLM etc. are added progressively in Plans 2–4 as those skills land.
- §6 testing — unit tests throughout, integration test in Task 10, orchestrator E2E test in Task 12, manual smoke test in Task 14.
- §7 deployment — `install-skills.sh` in Task 13; full deployment checklist deferred to Plan 4 since it depends on skills not yet implemented.
- §8 open questions — Question 1 (OpenClaw sub-agent invocation syntax) is partially answered by the `SubprocessBackend` assumption. The smoke test in Task 14 is the first real confirmation; if the assumption is wrong, only `autofanpage/dispatch.py` changes — no other code depends on the transport mechanism.

No placeholders found. Types consistent (`Profile`, `RunDir`, `LastSuccess`, `SchemaError`, `SkillInvocationError` used the same way across all tasks).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-15-autofanpage-plan1-foundation.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
