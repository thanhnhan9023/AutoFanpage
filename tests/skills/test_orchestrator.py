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
    profile_src = fixtures_dir / "page_test.json"
    profile_dst = tmp_path / "page_test.json"
    shutil.copy(profile_src, profile_dst)
    return {
        "base": tmp_path,
        "profile": profile_dst,
        "page": "page_test",
    }


def test_orchestrator_aborts_if_already_ran(test_env, mocker):
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

    calls = mock_run_skill.call_args_list
    assert len(calls) == 1
    assert calls[0][0][0] == "telegram-reporter"
    assert calls[0][0][1]["status"] == "info"


def test_orchestrator_runs_hn_then_telegram(test_env, mocker):
    captured = []

    def fake_run_skill(name, args):
        captured.append((name, args))
        if name == "hackernews-researcher":
            run_dir = Path(args["run_dir"])
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "hackernews_results.json").write_text(json.dumps({
                "source": "hackernews",
                "fetched_at": "2026-04-15T06:00:00+07:00",
                "items": [{"title": "hn1", "url": "https://hn.com/1",
                            "points": 100, "by": "u", "descendants": 5,
                            "created_at": "2026-04-14T00:00:00Z",
                            "hn_url": "https://news.ycombinator.com/item?id=1"}],
            }))
            return {"count": 1}
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
    tg_call = next(c for c in captured if c[0] == "telegram-reporter")
    assert tg_call[1]["status"] == "success"

    from autofanpage.state import LastSuccess
    assert LastSuccess(base=test_env["base"], page="page_test").ran_on("2026-04-15")
