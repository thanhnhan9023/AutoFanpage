import json

from autofanpage.health import find_stale_pages, prune_old_runs


def test_find_stale_pages_detects_missing_success(tmp_path):
    state_ok = tmp_path / "state" / "page_ok"
    state_ok.mkdir(parents=True)
    (state_ok / "last_success.json").write_text(json.dumps({
        "date": "2026-04-16",
        "run_dir": "x",
        "posts_scheduled": 4,
        "completed_at": "t",
    }))

    state_stale = tmp_path / "state" / "page_stale"
    state_stale.mkdir(parents=True)
    (state_stale / "last_success.json").write_text(json.dumps({
        "date": "2026-04-15",
        "run_dir": "x",
        "posts_scheduled": 4,
        "completed_at": "t",
    }))

    (tmp_path / "state" / "page_missing").mkdir(parents=True)

    stale = find_stale_pages(tmp_path, today="2026-04-16")
    assert sorted(stale) == ["page_missing", "page_stale"]


def test_find_stale_pages_empty_state_dir(tmp_path):
    stale = find_stale_pages(tmp_path, today="2026-04-16")
    assert stale == []


def test_prune_old_runs_removes_old_dirs(tmp_path):
    runs = tmp_path / "runs" / "page_test"
    (runs / "2026-03-01").mkdir(parents=True)
    (runs / "2026-03-01" / "run.log").write_text("old")
    (runs / "2026-04-10").mkdir(parents=True)
    (runs / "2026-04-10" / "run.log").write_text("recent")

    removed = prune_old_runs(tmp_path, max_age_days=30, today="2026-04-16")
    assert removed == ["2026-03-01"]
    assert not (runs / "2026-03-01").exists()
    assert (runs / "2026-04-10").exists()
