import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "autofanpage-health-check" / "scripts"
sys.path.insert(0, str(SCRIPT))
import check  # noqa: E402


def test_health_check_reports_stale_pages(tmp_path, mocker):
    state = tmp_path / "state" / "page_stale"
    state.mkdir(parents=True)
    (state / "last_success.json").write_text(json.dumps({
        "date": "2026-04-15",
        "run_dir": "x",
        "posts_scheduled": 4,
        "completed_at": "t",
    }))

    state_ok = tmp_path / "state" / "page_ok"
    state_ok.mkdir(parents=True)
    (state_ok / "last_success.json").write_text(json.dumps({
        "date": "2026-04-16",
        "run_dir": "x",
        "posts_scheduled": 4,
        "completed_at": "t",
    }))

    reported = []
    mocker.patch.object(check, "run_skill", side_effect=lambda name, args: reported.append((name, args)))

    rc = check.main([
        "--base-dir", str(tmp_path),
        "--date", "2026-04-16",
    ])
    assert rc == 0

    telegram = [call for call in reported if call[0] == "telegram-reporter"]
    assert len(telegram) == 1
    assert "page_stale" in telegram[0][1]["details"]["message"]
    assert "page_ok" not in telegram[0][1]["details"]["message"]


def test_health_check_prunes_old_runs(tmp_path, mocker):
    old_run = tmp_path / "runs" / "page_test" / "2026-03-01"
    old_run.mkdir(parents=True)
    (old_run / "run.log").write_text("old")

    mocker.patch.object(check, "run_skill", return_value=None)

    check.main([
        "--base-dir", str(tmp_path),
        "--date", "2026-04-16",
    ])
    assert not old_run.exists()


def test_health_check_no_stale_no_telegram(tmp_path, mocker):
    state = tmp_path / "state" / "page_ok"
    state.mkdir(parents=True)
    (state / "last_success.json").write_text(json.dumps({
        "date": "2026-04-16",
        "run_dir": "x",
        "posts_scheduled": 4,
        "completed_at": "t",
    }))

    reported = []
    mocker.patch.object(check, "run_skill", side_effect=lambda name, args: reported.append((name, args)))

    check.main([
        "--base-dir", str(tmp_path),
        "--date", "2026-04-16",
    ])
    assert len(reported) == 0
