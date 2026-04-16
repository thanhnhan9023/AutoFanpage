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
