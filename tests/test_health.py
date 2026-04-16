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


def test_find_stale_pages_ignores_files_and_flags_bad_json(tmp_path):
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "README.txt").write_text("ignore me")

    bad_page = state_dir / "page_bad"
    bad_page.mkdir()
    (bad_page / "last_success.json").write_text("{not json")

    stale = find_stale_pages(tmp_path, today="2026-04-16")
    assert stale == ["page_bad"]


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


def test_prune_old_runs_ignores_files_invalid_dates_and_missing_runs(tmp_path):
    assert prune_old_runs(tmp_path, today="2026-04-16") == []

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "notes.txt").write_text("ignore me")

    page_dir = runs_dir / "page_test"
    page_dir.mkdir()
    (page_dir / "latest").mkdir()
    (page_dir / "artifact.json").write_text("{}")

    removed = prune_old_runs(tmp_path, max_age_days=30, today="2026-04-16")
    assert removed == []
