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


def _run_dir(env):
    return env["base"] / "runs" / env["page"] / "hourly" / "2026-04-23T10-00-00Z"


def _source_post(
    *,
    source_post_id="123",
    source_post_url=None,
    published_at="2026-04-23T09:15:00Z",
    published_at_resolved=None,
    content_text="A useful post",
    backend="browser_use_mcp",
):
    if source_post_url is None:
        source_post_url = f"https://www.facebook.com/0xSojalSec/posts/{source_post_id}"
    return {
        "source_page_url": "https://www.facebook.com/0xSojalSec",
        "source_post_id": source_post_id,
        "source_post_url": source_post_url,
        "author": "0xSojalSec",
        "published_at": published_at,
        "published_at_resolved": published_at_resolved or published_at,
        "content_text": content_text,
        "media_urls": [],
        "backend": backend,
        "fetched_at": "2026-04-23T10:00:00Z",
    }


def _source_posts(
    posts,
    *,
    search_status="selection_ready",
    end_of_feed_reached=None,
    scan_stopped_reason=None,
    backend="browser_use_mcp",
    fetched_at="2026-04-23T10:00:00Z",
    posts_scanned=None,
):
    if end_of_feed_reached is None:
        end_of_feed_reached = search_status == "full_search_complete"
    if scan_stopped_reason is None:
        scan_stopped_reason = "end_of_feed" if end_of_feed_reached else search_status
    return {
        "source_page_url": "https://www.facebook.com/0xSojalSec",
        "backend": backend,
        "fetched_at": fetched_at,
        "search_status": search_status,
        "end_of_feed_reached": end_of_feed_reached,
        "scan_stopped_reason": scan_stopped_reason,
        "posts_scanned": len(posts) if posts_scanned is None else posts_scanned,
        "posts": posts,
    }


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
            (run_dir / "source_posts.json").write_text(
                json.dumps(
                    _source_posts(
                        [_source_post()],
                        search_status="full_search_complete",
                    )
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
    validate_spy = mocker.spy(orchestrate, "validate")

    def fake(name, args):
        run_dir = Path(args["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)

        if name == "facebook-page-latest-researcher":
            (run_dir / "source_posts.json").write_text(
                json.dumps(_source_posts([_source_post()])),
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
    repost_decision = json.loads((_run_dir(env) / "repost_decision.json").read_text(encoding="utf-8"))
    assert repost_decision == {
        "action": "publish",
        "reason": "publish_backlog_newest",
        "selected_post": _source_post(),
    }
    assert any(
        call.args == ("repost_decision", repost_decision)
        for call in validate_spy.call_args_list
    )
    latest_source_post = json.loads(
        (_run_dir(env) / "latest_source_post.json").read_text(encoding="utf-8")
    )
    assert latest_source_post["source_post_id"] == "123"
    marker = json.loads(
        (env["base"] / "state" / env["page"] / "latest_reposted_source.json").read_text(
            encoding="utf-8"
        )
    )
    assert marker["source_post_id"] == "123"
    history = json.loads(
        (env["base"] / "state" / env["page"] / "reposted_source_posts.json").read_text(
            encoding="utf-8"
        )
    )
    assert history["items"][0]["source_post_id"] == "123"


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
            (run_dir / "source_posts.json").write_text(
                json.dumps(_source_posts([_source_post()])),
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
            (run_dir / "source_posts.json").write_text(
                json.dumps(_source_posts([_source_post()])),
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
    assert not (
        env["base"] / "state" / env["page"] / "reposted_source_posts.json"
    ).exists()


def test_downstream_skill_failure_returns_error_and_reports_error_status(env, mocker):
    calls = []

    def fake(name, args):
        calls.append((name, args))
        run_dir = Path(args["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)

        if name == "facebook-page-latest-researcher":
            (run_dir / "source_posts.json").write_text(
                json.dumps(_source_posts([_source_post()])),
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
            (run_dir / "source_posts.json").write_text(
                json.dumps(_source_posts([_source_post()])),
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
            (run_dir / "source_posts.json").write_text(
                json.dumps(
                    _source_posts(
                        [_source_post(backend="agent_browser")],
                        backend="agent_browser",
                    )
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


def test_full_search_complete_with_no_posts_skips_cleanly(env, mocker):
    calls = []

    def fake(name, args):
        calls.append((name, args))
        run_dir = Path(args["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)

        if name == "facebook-page-latest-researcher":
            (run_dir / "source_posts.json").write_text(
                json.dumps(_source_posts([], search_status="full_search_complete")),
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
    decision = json.loads(
        (_run_dir(env) / "repost_decision.json").read_text(encoding="utf-8")
    )
    assert decision["action"] == "skip"
    assert decision["reason"] == "skip_no_posts_fetched_after_full_search"


@pytest.mark.parametrize(
    ("source_posts", "expected_cause"),
    [
        (
            _source_posts(
                [_source_post()],
                search_status="selection_ready",
            ),
            "error_partial_search_scope",
        ),
        (
            _source_posts(
                [],
                search_status="selection_ready",
                posts_scanned=0,
            ),
            "error_source_fetch_failed",
        ),
    ],
)
def test_selector_error_paths_return_non_zero_and_report_selector_reason(
    env, mocker, source_posts, expected_cause
):
    state_path = env["base"] / "state" / env["page"] / "reposted_source_posts.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "source_post_id": None,
                        "source_post_url": "https://www.facebook.com/0xSojalSec/posts/123",
                        "published_at": "2026-04-23T09:15:00Z",
                        "published_at_resolved": "2026-04-23T09:15:00Z",
                        "reposted_at": "2026-04-23T09:30:00Z",
                        "run_dir": "/tmp/old-run",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    calls = []

    def fake(name, args):
        calls.append((name, args))
        run_dir = Path(args["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)

        if name == "facebook-page-latest-researcher":
            (run_dir / "source_posts.json").write_text(
                json.dumps(source_posts),
                encoding="utf-8",
            )
            return {"status": "ok"}

        if name == "telegram-reporter":
            return {"status": "ok"}

        raise AssertionError(f"unexpected skill {name}")

    mocker.patch("orchestrate.run_skill", side_effect=fake)

    rc = _run(env)

    assert rc == 1
    assert "hourly-facebook-writer" not in [name for name, _args in calls]
    decision = json.loads(
        (_run_dir(env) / "repost_decision.json").read_text(encoding="utf-8")
    )
    assert decision["action"] == "error"
    assert decision["reason"] == expected_cause
    telegram = [args for name, args in calls if name == "telegram-reporter"]
    assert telegram[0]["details"]["cause"] == expected_cause
