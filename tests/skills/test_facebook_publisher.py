import json
import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
import responses

from autofanpage.errors import AutofanpageError

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


@pytest.fixture
def graph_profile_path(tmp_path, fixtures_dir):
    src = json.loads((fixtures_dir / "profile_plan3.json").read_text())
    src["publishing"] = {"backend": "facebook_graph"}
    path = tmp_path / "graph-profile.json"
    path.write_text(json.dumps(src), encoding="utf-8")
    return path


@pytest.fixture
def mixpost_profile_path(tmp_path, fixtures_dir):
    src = json.loads((fixtures_dir / "profile_plan3.json").read_text())
    state_path = tmp_path / "mixpost-state.json"
    state_path.write_text("{}", encoding="utf-8")
    src["name"] = "Test"
    src["publishing"] = {
        "backend": "mixpost_ui",
        "mixpost": {
            "base_url": "https://mixpost.example.test",
            "storage_state_path": str(state_path),
            "headless": True,
        },
    }
    path = tmp_path / "mixpost-profile.json"
    path.write_text(json.dumps(src), encoding="utf-8")
    return path


def _with_mixpost_images_enabled(path: Path) -> Path:
    src = json.loads(path.read_text(encoding="utf-8"))
    src["publishing"]["images"] = {
        "enabled": True,
        "provider": "useapi_google_flow",
        "useapi_base_url": "https://api.useapi.net",
        "useapi_token_ref": "secret:useapi_token",
        "google_flow_account_ref": "secret:useapi_google_flow_account",
        "candidate_count": 4,
        "overlay_mode": "none",
        "require_image_for_publish": True,
        "canvas": {"width": 1080, "height": 1350, "theme": "ai5phut"},
    }
    path.write_text(json.dumps(src), encoding="utf-8")
    return path


@responses.activate
def test_happy_path_publishes_non_null_slots(run_dir, graph_profile_path, mocker):
    mocker.patch.object(publish, "get_secret", return_value="fb_token_fake")
    responses.add(responses.POST, f"{GRAPH}/123/feed", json={"id": "123_post0"}, status=200)
    responses.add(responses.POST, f"{GRAPH}/123_post0/comments", json={"id": "123_cmt0"}, status=200)
    responses.add(responses.POST, f"{GRAPH}/123/feed", json={"id": "123_post1"}, status=200)
    responses.add(responses.POST, f"{GRAPH}/123_post1/comments", json={"id": "123_cmt1"}, status=200)

    rc = publish.main([
        "--run-dir", str(run_dir),
        "--profile", str(graph_profile_path),
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
def test_skips_already_published_slots_on_resume(run_dir, fixtures_dir, graph_profile_path, mocker):
    mocker.patch.object(publish, "get_secret", return_value="fb_token_fake")
    (run_dir / "publish_results.json").write_text(
        (fixtures_dir / "publish_results_partial.json").read_text(),
        encoding="utf-8",
    )
    responses.add(responses.POST, f"{GRAPH}/123/feed", json={"id": "123_post1"}, status=200)
    responses.add(responses.POST, f"{GRAPH}/123_post1/comments", json={"id": "123_cmt1"}, status=200)

    rc = publish.main([
        "--run-dir", str(run_dir),
        "--profile", str(graph_profile_path),
        "--date", "2026-04-16",
    ])
    assert rc == 0

    results = json.loads((run_dir / "publish_results.json").read_text())
    assert len(results["posts"]) == 2
    assert results["posts"][0]["time"] == "08:00"
    assert results["posts"][1]["time"] == "12:00"


def test_dry_run_writes_preview_no_api_calls(run_dir, graph_profile_path, mocker):
    mocker.patch.object(publish, "get_secret", return_value="fb_token_fake")

    rc = publish.main([
        "--run-dir", str(run_dir),
        "--profile", str(graph_profile_path),
        "--date", "2026-04-16",
        "--dry-run",
    ])
    assert rc == 0

    preview = (run_dir / "preview.md").read_text()
    assert "Preview: page_test" in preview
    assert "Breaking: GPT-5" in preview
    assert not (run_dir / "publish_results.json").exists()


@responses.activate
def test_partial_failure_records_succeeded_slots(run_dir, graph_profile_path, mocker):
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
        "--profile", str(graph_profile_path),
        "--date", "2026-04-16",
    ])
    assert rc == 1

    results = json.loads((run_dir / "publish_results.json").read_text())
    assert results["posts"][0]["status"] == 200
    assert results["posts"][0]["post_id"] == "123_post0"
    assert results["posts"][1]["status"] == 401
    assert results["posts"][1]["post_id"] is None


def test_mixpost_backend_writes_publish_results(run_dir, mixpost_profile_path, mocker):
    scheduler = mocker.patch.object(
        publish,
        "schedule_slot_via_mixpost",
        side_effect=[
            {"post_id": None, "comment_id": None, "status": 200},
            {"post_id": None, "comment_id": None, "status": 200},
        ],
    )

    rc = publish.main([
        "--run-dir", str(run_dir),
        "--profile", str(mixpost_profile_path),
        "--date", "2026-04-16",
    ])

    assert rc == 0
    assert scheduler.call_count == 2
    results = json.loads((run_dir / "publish_results.json").read_text())
    assert results["page"] == "Test"
    assert len(results["posts"]) == 2
    assert all(post["status"] == 200 for post in results["posts"])


def test_mixpost_backend_skips_existing_success_slots(run_dir, mixpost_profile_path, mocker):
    (run_dir / "publish_results.json").write_text(
        json.dumps(
            {
                "page": "Test",
                "date": "2026-04-16",
                "posts": [
                    {
                        "time": "08:00",
                        "type": "news",
                        "post_id": None,
                        "comment_id": None,
                        "status": 200,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    scheduler = mocker.patch.object(
        publish,
        "schedule_slot_via_mixpost",
        return_value={"post_id": None, "comment_id": None, "status": 200},
    )

    rc = publish.main([
        "--run-dir", str(run_dir),
        "--profile", str(mixpost_profile_path),
        "--date", "2026-04-16",
    ])

    assert rc == 0
    assert scheduler.call_count == 1


def test_mixpost_backend_uses_selected_image_asset(run_dir, mixpost_profile_path, mocker):
    mixpost_profile_path = _with_mixpost_images_enabled(mixpost_profile_path)
    asset_dir = run_dir / "assets"
    asset_dir.mkdir()
    selected = asset_dir / "08-00-selected.png"
    selected.write_bytes(b"png")
    second_selected = asset_dir / "12-00-selected.png"
    second_selected.write_bytes(b"png")
    (run_dir / "post_assets.json").write_text(
        json.dumps(
            {
                "page": "Test",
                "provider": "useapi_google_flow",
                "date": "2026-04-16",
                "assets": [
                    {
                        "time": "08:00",
                        "type": "news",
                        "status": "ok",
                        "provider": "useapi_google_flow",
                        "image_prompt": "editorial image",
                        "job_id": "job-2",
                        "raw_image_url": "https://cdn.example/raw.png",
                        "raw_image_path": "assets/08-00-raw-c2.png",
                        "final_image_path": "assets/08-00-selected.png",
                        "selected_candidate_index": 2,
                        "candidates": [],
                        "error": None,
                    },
                    {
                        "time": "12:00",
                        "type": "guide",
                        "status": "ok",
                        "provider": "useapi_google_flow",
                        "image_prompt": "editorial image 2",
                        "job_id": "job-3",
                        "raw_image_url": "https://cdn.example/raw-2.png",
                        "raw_image_path": "assets/12-00-raw-c1.png",
                        "final_image_path": "assets/12-00-selected.png",
                        "selected_candidate_index": 1,
                        "candidates": [],
                        "error": None,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    scheduler = mocker.patch.object(
        publish,
        "schedule_slot_via_mixpost",
        side_effect=[
            {"post_id": None, "comment_id": None, "status": 200},
            {"post_id": None, "comment_id": None, "status": 200},
        ],
    )

    rc = publish.main([
        "--run-dir", str(run_dir),
        "--profile", str(mixpost_profile_path),
        "--date", "2026-04-16",
    ])

    assert rc == 0
    assert scheduler.call_args_list[0].kwargs["image_path"] == str(selected.resolve())
    assert scheduler.call_args_list[1].kwargs["image_path"] == str(second_selected.resolve())


def test_mixpost_backend_requires_image_asset_for_filled_slot(
    run_dir, mixpost_profile_path
):
    mixpost_profile_path = _with_mixpost_images_enabled(mixpost_profile_path)
    with pytest.raises(AutofanpageError, match="post_assets.json"):
        publish.main([
            "--run-dir", str(run_dir),
            "--profile", str(mixpost_profile_path),
            "--date", "2026-04-16",
        ])


def test_compute_mixpost_publish_slot_shifts_past_time_forward():
    date, time = publish._compute_mixpost_publish_slot(
        date="2026-04-24",
        post_time="08:00",
        timezone_name="Asia/Ho_Chi_Minh",
        wall_now=datetime(2026, 4, 24, 21, 10, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh")),
    )

    assert date == "2026-04-24"
    assert time == "21:25"


def test_publish_via_mixpost_uses_shifted_slot_when_past(mixpost_profile_path, mocker):
    profile = publish.load_profile(mixpost_profile_path)
    scheduler = mocker.patch.object(
        publish,
        "schedule_slot_via_mixpost",
        return_value={"post_id": None, "comment_id": None, "status": 200},
    )
    mocker.patch.object(
        publish,
        "_compute_mixpost_publish_slot",
        return_value=("2026-04-24", "21:25"),
    )

    result = publish._publish_via_mixpost(
        profile=profile,
        post={"time": "08:00", "type": "news", "content": "body", "first_comment": None},
        date="2026-04-24",
        image_path=None,
    )

    assert result["status"] == 200
    assert scheduler.call_args.kwargs["publish_date"] == "2026-04-24"
    assert scheduler.call_args.kwargs["publish_time"] == "21:25"
