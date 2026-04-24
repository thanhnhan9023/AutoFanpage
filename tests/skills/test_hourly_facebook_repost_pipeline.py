import json
import sys
from pathlib import Path

import pytest

from autofanpage.errors import AutofanpageError, SkillInvocationError


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "hourly-facebook-repost-pipeline"
    / "scripts"
)
sys.path.insert(0, str(SCRIPT))
import orchestrate  # noqa: E402


@pytest.fixture
def env(tmp_path, fixtures_dir):
    return {
        "base": tmp_path,
        "profile": fixtures_dir / "profile_hourly_facebook_repost.json",
        "page": "page_hourly_repost",
    }


def _run(env, *, profile_path=None):
    return orchestrate.main(
        [
            "--page",
            env["page"],
            "--profile-path",
            str(profile_path or env["profile"]),
            "--base-dir",
            str(env["base"]),
            "--run-label",
            "2026-04-23T10-00-00Z",
        ]
    )


def test_duplicate_source_post_skips_writer_and_publisher(env, mocker):
    state_path = env["base"] / "state" / env["page"] / "latest_reposted_source.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "source_post_id": "123",
                "source_post_url": "https://www.facebook.com/0xSojalSec/posts/123",
                "published_at": "2026-04-23T09:15:00Z",
                "reposted_at": "2026-04-23T10:00:00Z",
                "run_dir": "/tmp/prev-run",
            }
        ),
        encoding="utf-8",
    )

    calls = []

    def fake(name, args):
        calls.append((name, args))
        run_dir = Path(args["run_dir"])
        if name == "facebook-page-latest-researcher":
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "latest_source_post.json").write_text(
                json.dumps(
                    {
                        "source_page_url": "https://www.facebook.com/0xSojalSec",
                        "source_post_id": "123",
                        "source_post_url": "https://www.facebook.com/0xSojalSec/posts/123",
                        "author": "0xSojalSec",
                        "published_at": "2026-04-23T09:15:00Z",
                        "content_text": "A useful post",
                        "media_urls": [],
                        "backend": "browser_use_mcp",
                        "fetched_at": "2026-04-23T10:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            return {"status": "ok"}
        if name == "telegram-reporter":
            return {"status": "ok"}
        raise AssertionError(f"unexpected skill {name}")

    mocker.patch("orchestrate.run_skill", side_effect=fake)

    rc = _run(env)

    assert rc == 0
    assert "hourly-facebook-writer" not in [name for name, _args in calls]
    assert "facebook-publisher" not in [name for name, _args in calls]


def test_new_source_post_runs_writer_and_publisher_and_marks_state(env, mocker):
    def fake(name, args):
        run_dir = Path(args["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)

        if name == "facebook-page-latest-researcher":
            (run_dir / "latest_source_post.json").write_text(
                json.dumps(
                    {
                        "source_page_url": "https://www.facebook.com/0xSojalSec",
                        "source_post_id": "123",
                        "source_post_url": "https://www.facebook.com/0xSojalSec/posts/123",
                        "author": "0xSojalSec",
                        "published_at": "2026-04-23T09:15:00Z",
                        "content_text": "A useful post",
                        "media_urls": [],
                        "backend": "browser_use_mcp",
                        "fetched_at": "2026-04-23T10:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            return {"status": "ok"}

        if name == "hourly-facebook-writer":
            (run_dir / "posts.json").write_text(
                json.dumps(
                    {
                        "language": "vi",
                        "posts": [
                            {
                                "time": "10:15",
                                "type": "news",
                                "content": "Bai viet moi",
                                "first_comment": None,
                            },
                            {
                                "time": "12:00",
                                "type": "guide",
                                "content": None,
                                "first_comment": None,
                            },
                            {
                                "time": "16:00",
                                "type": "opinion",
                                "content": None,
                                "first_comment": None,
                            },
                            {
                                "time": "20:00",
                                "type": "case_study",
                                "content": None,
                                "first_comment": None,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            return {"status": "ok"}

        if name == "facebook-publisher":
            (run_dir / "publish_results.json").write_text(
                json.dumps(
                    {
                        "page": env["page"],
                        "date": "2026-04-23",
                        "posts": [
                            {
                                "time": "10:15",
                                "type": "news",
                                "post_id": "123_post0",
                                "comment_id": None,
                                "status": 200,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            return {"status": "ok"}

        if name == "telegram-reporter":
            return {"status": "ok"}

        raise AssertionError(f"unexpected skill {name}")

    mocker.patch("orchestrate.run_skill", side_effect=fake)

    rc = _run(env)

    assert rc == 0
    marker = json.loads(
        (env["base"] / "state" / env["page"] / "latest_reposted_source.json").read_text(
            encoding="utf-8"
        )
    )
    assert marker["source_post_id"] == "123"


def test_mixpost_destination_profile_runs_writer_and_publisher(env, mocker, tmp_path):
    mixpost_profile = tmp_path / "profile_mixpost.json"
    profile_payload = json.loads(env["profile"].read_text(encoding="utf-8"))
    profile_payload["publishing"] = {
        "backend": "mixpost_ui",
        "mixpost": {
            "base_url": "https://mixpost.example.test",
            "storage_state_path": str(tmp_path / "state.json"),
            "headless": True,
        },
    }
    (tmp_path / "state.json").write_text("{}", encoding="utf-8")
    mixpost_profile.write_text(json.dumps(profile_payload), encoding="utf-8")

    calls = []

    def fake(name, args):
        calls.append((name, args))
        run_dir = Path(args["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)

        if name == "facebook-page-latest-researcher":
            (run_dir / "latest_source_post.json").write_text(
                json.dumps(
                    {
                        "source_page_url": "https://www.facebook.com/0xSojalSec",
                        "source_post_id": "123",
                        "source_post_url": "https://www.facebook.com/0xSojalSec/posts/123",
                        "author": "0xSojalSec",
                        "published_at": "2026-04-23T09:15:00Z",
                        "content_text": "A useful post",
                        "media_urls": [],
                        "backend": "browser_use_mcp",
                        "fetched_at": "2026-04-23T10:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            return {"status": "ok"}

        if name == "hourly-facebook-writer":
            (run_dir / "posts.json").write_text(
                json.dumps(
                    {
                        "language": "vi",
                        "posts": [
                            {
                                "time": "10:15",
                                "type": "news",
                                "content": "Bai viet moi",
                                "first_comment": None,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            return {"status": "ok"}

        if name == "facebook-publisher":
            (run_dir / "publish_results.json").write_text(
                json.dumps(
                    {
                        "page": env["page"],
                        "date": "2026-04-23",
                        "posts": [
                            {
                                "time": "10:15",
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
            return {"status": "ok"}

        if name == "telegram-reporter":
            return {"status": "ok"}

        raise AssertionError(f"unexpected skill {name}")

    mocker.patch("orchestrate.run_skill", side_effect=fake)

    rc = _run(env, profile_path=mixpost_profile)

    assert rc == 0
    assert "facebook-publisher" in [name for name, _ in calls]


def test_zero_successful_publish_results_returns_failure_without_marking_state(
    env, mocker
):
    def fake(name, args):
        run_dir = Path(args["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)

        if name == "facebook-page-latest-researcher":
            (run_dir / "latest_source_post.json").write_text(
                json.dumps(
                    {
                        "source_page_url": "https://www.facebook.com/0xSojalSec",
                        "source_post_id": "123",
                        "source_post_url": "https://www.facebook.com/0xSojalSec/posts/123",
                        "author": "0xSojalSec",
                        "published_at": "2026-04-23T09:15:00Z",
                        "content_text": "A useful post",
                        "media_urls": [],
                        "backend": "browser_use_mcp",
                        "fetched_at": "2026-04-23T10:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            return {"status": "ok"}

        if name == "hourly-facebook-writer":
            (run_dir / "posts.json").write_text(
                json.dumps(
                    {
                        "language": "vi",
                        "posts": [
                            {
                                "time": "10:15",
                                "type": "news",
                                "content": "Bai viet moi",
                                "first_comment": None,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            return {"status": "ok"}

        if name == "facebook-publisher":
            (run_dir / "publish_results.json").write_text(
                json.dumps(
                    {
                        "page": env["page"],
                        "date": "2026-04-23",
                        "posts": [
                            {
                                "time": "10:15",
                                "type": "news",
                                "post_id": None,
                                "comment_id": None,
                                "status": 500,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            return {"status": "ok"}

        if name == "telegram-reporter":
            return {"status": "ok"}

        raise AssertionError(f"unexpected skill {name}")

    mocker.patch("orchestrate.run_skill", side_effect=fake)

    rc = _run(env)

    assert rc == 1
    assert not (
        env["base"] / "state" / env["page"] / "latest_reposted_source.json"
    ).exists()


def test_downstream_skill_failure_returns_error_and_reports_error_status(env, mocker):
    calls = []

    def fake(name, args):
        calls.append((name, args))
        run_dir = Path(args["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)

        if name == "facebook-page-latest-researcher":
            (run_dir / "latest_source_post.json").write_text(
                json.dumps(
                    {
                        "source_page_url": "https://www.facebook.com/0xSojalSec",
                        "source_post_id": "123",
                        "source_post_url": "https://www.facebook.com/0xSojalSec/posts/123",
                        "author": "0xSojalSec",
                        "published_at": "2026-04-23T09:15:00Z",
                        "content_text": "A useful post",
                        "media_urls": [],
                        "backend": "browser_use_mcp",
                        "fetched_at": "2026-04-23T10:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            return {"status": "ok"}

        if name == "hourly-facebook-writer":
            raise AutofanpageError("writer failed")

        if name == "telegram-reporter":
            return {"status": "ok"}

        raise AssertionError(f"unexpected skill {name}")

    mocker.patch("orchestrate.run_skill", side_effect=fake)

    rc = _run(env)

    assert rc == 1
    telegram = [args for name, args in calls if name == "telegram-reporter"]
    assert len(telegram) == 1
    assert telegram[0]["status"] == "error"
    assert telegram[0]["details"]["phase"] == "orchestrator"
    assert "writer failed" in telegram[0]["details"]["cause"]


def test_telegram_reporter_failure_does_not_flip_successful_publish_run(
    env, mocker, capsys
):
    def fake(name, args):
        run_dir = Path(args["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)

        if name == "facebook-page-latest-researcher":
            (run_dir / "latest_source_post.json").write_text(
                json.dumps(
                    {
                        "source_page_url": "https://www.facebook.com/0xSojalSec",
                        "source_post_id": "123",
                        "source_post_url": "https://www.facebook.com/0xSojalSec/posts/123",
                        "author": "0xSojalSec",
                        "published_at": "2026-04-23T09:15:00Z",
                        "content_text": "A useful post",
                        "media_urls": [],
                        "backend": "browser_use_mcp",
                        "fetched_at": "2026-04-23T10:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            return {"status": "ok"}

        if name == "hourly-facebook-writer":
            (run_dir / "posts.json").write_text(
                json.dumps(
                    {
                        "language": "vi",
                        "posts": [
                            {
                                "time": "10:15",
                                "type": "news",
                                "content": "Bai viet moi",
                                "first_comment": None,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            return {"status": "ok"}

        if name == "facebook-publisher":
            (run_dir / "publish_results.json").write_text(
                json.dumps(
                    {
                        "page": env["page"],
                        "date": "2026-04-23",
                        "posts": [
                            {
                                "time": "10:15",
                                "type": "news",
                                "post_id": "123_post0",
                                "comment_id": None,
                                "status": 200,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            return {"status": "ok"}

        if name == "telegram-reporter":
            raise SkillInvocationError("telegram offline")

        raise AssertionError(f"unexpected skill {name}")

    mocker.patch("orchestrate.run_skill", side_effect=fake)

    rc = _run(env)

    assert rc == 0
    assert (
        env["base"] / "state" / env["page"] / "latest_reposted_source.json"
    ).exists()
    assert "telegram-reporter failed" in capsys.readouterr().err


def test_mixpost_with_images_runs_generator_before_publisher(env, mocker, tmp_path):
    mixpost_profile = tmp_path / "profile_mixpost_images.json"
    profile_payload = json.loads(env["profile"].read_text(encoding="utf-8"))
    profile_payload["publishing"] = {
        "backend": "mixpost_ui",
        "mixpost": {
            "base_url": "https://mixpost.example.test",
            "storage_state_path": str(tmp_path / "state.json"),
            "headless": True,
        },
        "images": {
            "enabled": True,
            "provider": "useapi_google_flow",
            "useapi_base_url": "https://api.useapi.net",
            "useapi_token_ref": "secret:useapi_token",
            "google_flow_account_ref": "secret:useapi_google_flow_account",
            "candidate_count": 4,
            "overlay_mode": "none",
            "require_image_for_publish": True,
            "canvas": {"width": 1080, "height": 1350, "theme": "ai5phut"},
        },
    }
    (tmp_path / "state.json").write_text("{}", encoding="utf-8")
    mixpost_profile.write_text(json.dumps(profile_payload), encoding="utf-8")

    calls = []

    def fake(name, args):
        calls.append((name, args))
        run_dir = Path(args["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)

        if name == "facebook-page-latest-researcher":
            (run_dir / "latest_source_post.json").write_text(
                json.dumps(
                    {
                        "source_page_url": "https://www.facebook.com/0xSojalSec",
                        "source_post_id": "123",
                        "source_post_url": "https://www.facebook.com/0xSojalSec/posts/123",
                        "author": "0xSojalSec",
                        "published_at": "2026-04-23T09:15:00Z",
                        "content_text": "A useful post",
                        "media_urls": [],
                        "backend": "agent_browser",
                        "fetched_at": "2026-04-23T10:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            return {"status": "ok"}

        if name == "hourly-facebook-writer":
            (run_dir / "posts.json").write_text(
                json.dumps(
                    {
                        "language": "vi",
                        "posts": [
                            {
                                "time": "10:15",
                                "type": "news",
                                "content": "Bai viet moi",
                                "first_comment": None,
                            },
                            {
                                "time": "12:00",
                                "type": "guide",
                                "content": None,
                                "first_comment": None,
                            },
                            {
                                "time": "16:00",
                                "type": "opinion",
                                "content": None,
                                "first_comment": None,
                            },
                            {
                                "time": "20:00",
                                "type": "case_study",
                                "content": None,
                                "first_comment": None,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            return {"status": "ok"}

        if name == "hourly-facebook-image-generator":
            (run_dir / "post_assets.json").write_text(
                json.dumps(
                    {
                        "page": env["page"],
                        "provider": "useapi_google_flow",
                        "date": "2026-04-23",
                        "assets": [
                            {
                                "time": "10:15",
                                "type": "news",
                                "status": "ok",
                                "provider": "useapi_google_flow",
                                "image_prompt": "editorial AI automation",
                                "job_id": "job-2",
                                "raw_image_url": "https://cdn.example/raw-2.png",
                                "raw_image_path": "assets/10-15-raw-c2.png",
                                "final_image_path": "assets/10-15-selected.png",
                                "selected_candidate_index": 2,
                                "candidates": [],
                                "error": None,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            return {"status": "ok", "artifact": "post_assets.json"}

        if name == "facebook-publisher":
            (run_dir / "publish_results.json").write_text(
                json.dumps(
                    {
                        "page": env["page"],
                        "backend": "mixpost_ui",
                        "date": "2026-04-23",
                        "posts": [
                            {
                                "time": "10:15",
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
            return {"status": "ok"}

        if name == "telegram-reporter":
            return {"status": "ok"}

        raise AssertionError(f"unexpected skill {name}")

    mocker.patch("orchestrate.run_skill", side_effect=fake)

    rc = _run(env, profile_path=mixpost_profile)

    assert rc == 0
    assert [name for name, _ in calls[:4]] == [
        "facebook-page-latest-researcher",
        "hourly-facebook-writer",
        "hourly-facebook-image-generator",
        "facebook-publisher",
    ]
