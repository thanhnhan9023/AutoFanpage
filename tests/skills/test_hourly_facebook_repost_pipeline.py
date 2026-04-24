import json
import sys
from pathlib import Path

import pytest


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


def test_mixpost_destination_profile_fails_preflight(env, mocker, tmp_path):
    bad_profile = tmp_path / "profile_mixpost.json"
    bad_profile.write_text(
        env["profile"].read_text(encoding="utf-8").replace(
            '"facebook_graph"',
            '"mixpost_ui"',
        ),
        encoding="utf-8",
    )

    mocker.patch("orchestrate.run_skill")

    rc = _run(env, profile_path=bad_profile)

    assert rc == 1
