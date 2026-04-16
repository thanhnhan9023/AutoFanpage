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
