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
        (fixtures_dir / "posts_sample.json").read_text(),
        encoding="utf-8",
    )
    return rd


@responses.activate
def test_happy_path_publishes_non_null_slots(run_dir, fixtures_dir, mocker):
    mocker.patch.object(publish, "get_secret", return_value="fb_token_fake")
    responses.add(responses.POST, f"{GRAPH}/123/feed", json={"id": "123_post0"}, status=200)
    responses.add(responses.POST, f"{GRAPH}/123_post0/comments", json={"id": "123_cmt0"}, status=200)
    responses.add(responses.POST, f"{GRAPH}/123/feed", json={"id": "123_post1"}, status=200)
    responses.add(responses.POST, f"{GRAPH}/123_post1/comments", json={"id": "123_cmt1"}, status=200)

    rc = publish.main([
        "--run-dir", str(run_dir),
        "--profile", str(fixtures_dir / "profile_plan3.json"),
        "--date", "2026-04-16",
    ])
    assert rc == 0

    results = json.loads((run_dir / "publish_results.json").read_text())
    assert results["page"] == "page_test"
    assert len(results["posts"]) == 2
    assert results["posts"][0]["post_id"] == "123_post0"
    assert results["posts"][0]["comment_id"] == "123_cmt0"
    assert results["posts"][0]["status"] == 200
    assert results["posts"][1]["post_id"] == "123_post1"


@responses.activate
def test_skips_already_published_slots_on_resume(run_dir, fixtures_dir, mocker):
    mocker.patch.object(publish, "get_secret", return_value="fb_token_fake")
    (run_dir / "publish_results.json").write_text(
        (fixtures_dir / "publish_results_partial.json").read_text(),
        encoding="utf-8",
    )
    responses.add(responses.POST, f"{GRAPH}/123/feed", json={"id": "123_post1"}, status=200)
    responses.add(responses.POST, f"{GRAPH}/123_post1/comments", json={"id": "123_cmt1"}, status=200)

    rc = publish.main([
        "--run-dir", str(run_dir),
        "--profile", str(fixtures_dir / "profile_plan3.json"),
        "--date", "2026-04-16",
    ])
    assert rc == 0

    results = json.loads((run_dir / "publish_results.json").read_text())
    assert len(results["posts"]) == 2
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
    responses.add(responses.POST, f"{GRAPH}/123/feed", json={"id": "123_post0"}, status=200)
    responses.add(responses.POST, f"{GRAPH}/123_post0/comments", json={"id": "123_cmt0"}, status=200)
    responses.add(
        responses.POST,
        f"{GRAPH}/123/feed",
        json={"error": {"message": "token expired"}},
        status=401,
    )

    rc = publish.main([
        "--run-dir", str(run_dir),
        "--profile", str(fixtures_dir / "profile_plan3.json"),
        "--date", "2026-04-16",
    ])
    assert rc == 1

    results = json.loads((run_dir / "publish_results.json").read_text())
    assert results["posts"][0]["status"] == 200
    assert results["posts"][0]["post_id"] == "123_post0"
    assert results["posts"][1]["status"] == 401
    assert results["posts"][1]["post_id"] is None
