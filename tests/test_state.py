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
