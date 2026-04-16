import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "daily-content-pipeline" / "scripts"
sys.path.insert(0, str(SCRIPT))
import orchestrate  # noqa: E402


@pytest.fixture
def env(tmp_path, fixtures_dir):
    return {
        "base": tmp_path,
        "profile": fixtures_dir / "profile_plan2.json",
        "page": "page_test",
    }


def _fake_factory(failing: set[str]):
    calls: list[tuple[str, dict]] = []

    artifacts: dict[str, dict] = {
        "youtube": {
            "source": "youtube",
            "fetched_at": "2026-04-15T06:00:00+07:00",
            "items": [{"title": "yt", "url": "https://y/1", "video_id": "1",
                       "channel": "c", "views": 200000, "subscribers": 30000,
                       "published_at": "2026-04-10T00:00:00Z"}],
        },
        "perplexity": {
            "source": "perplexity",
            "fetched_at": "2026-04-15T06:00:00+07:00",
            "news": [{"title": "n", "url": "https://n/1", "summary": "",
                      "source": "n.com"}],
            "reports": [], "twitter": [],
        },
        "reddit": {
            "source": "reddit",
            "fetched_at": "2026-04-15T06:00:00+07:00",
            "items": [{"title": "r", "url": "https://r/1",
                       "subreddit": "ChatGPT", "score": 500,
                       "num_comments": 30, "author": "u",
                       "permalink": "/r/1",
                       "created_at": "2026-04-14T00:00:00Z",
                       "is_self": False, "external_url": ""}],
        },
        "hackernews": {
            "source": "hackernews",
            "fetched_at": "2026-04-15T06:00:00+07:00",
            "items": [{"title": "hn", "url": "https://h/1",
                       "points": 300, "by": "u", "descendants": 10,
                       "created_at": "2026-04-14T00:00:00Z",
                       "hn_url": "https://news.ycombinator.com/item?id=1"}],
        },
    }

    def fake(name: str, args: dict):
        calls.append((name, args))
        if name == "telegram-reporter":
            return {"status": "ok", "sent": True}
        if name == "notebooklm-analyzer":
            run_dir = Path(args["run_dir"])
            (run_dir / "insights.json").write_text(json.dumps({
                "overview": "x", "pain_points": [], "insights": ["test insight with AI automation data 40% improvement — try it first."],
                "gap_topics": [], "source_urls": ["https://hn.com/1"], "language": "en",
            }))
            return {"status": "ok"}
        if name == "review-agent":
            run_dir = Path(args["run_dir"])
            (run_dir / "reviewed_insights.json").write_text(json.dumps({
                "approved": [
                    {"insight": "a", "scores": {"relevance": 5, "novelty": 5, "viral": 5, "actionable": 2}, "total": 17, "suggested_post_type": "news", "hook_angle": "", "source_url": ""},
                    {"insight": "b", "scores": {"relevance": 5, "novelty": 4, "viral": 5, "actionable": 5}, "total": 19, "suggested_post_type": "guide", "hook_angle": "", "source_url": ""},
                ],
                "rejected": [],
            }))
            return {"status": "ok"}
        if name == "writing-agent":
            run_dir = Path(args["run_dir"])
            (run_dir / "posts.json").write_text(json.dumps({
                "language": "en",
                "posts": [
                    {"time": "08:00", "type": "news", "content": "x", "first_comment": "y"},
                    {"time": "12:00", "type": "guide", "content": None, "first_comment": None},
                    {"time": "16:00", "type": "opinion", "content": None, "first_comment": None},
                    {"time": "20:00", "type": "case_study", "content": None, "first_comment": None},
                ],
            }))
            return {"status": "ok"}
        key = name.replace("-researcher", "")
        if key in failing:
            from autofanpage.errors import SourceFailedError
            raise SourceFailedError(f"fake fail for {key}")
        run_dir = Path(args["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)
        artifact_name = orchestrate.SOURCE_ARTIFACTS[key]
        (run_dir / artifact_name).write_text(
            json.dumps(artifacts[key]), encoding="utf-8",
        )
        return {"status": "ok", "artifact": str(run_dir / artifact_name)}

    return fake, calls


def _run(env, argv_date="2026-04-15"):
    return orchestrate.main([
        "--page", env["page"],
        "--profile-path", str(env["profile"]),
        "--base-dir", str(env["base"]),
        "--date", argv_date,
    ])


def test_happy_path_dispatches_all_4_sources(env, mocker):
    fake, calls = _fake_factory(failing=set())
    mocker.patch("orchestrate.run_skill", side_effect=fake)

    exit_code = _run(env)
    assert exit_code == 0

    names = [c[0] for c in calls]
    for expected in ("youtube-researcher", "perplexity-researcher",
                     "reddit-researcher", "hackernews-researcher"):
        assert expected in names
    assert names.count("telegram-reporter") == 1

    tg = next(c for c in calls if c[0] == "telegram-reporter")
    assert tg[1]["status"] == "success"
    details = tg[1]["details"]
    assert details["phase1_counts"]["youtube"] == 1
    assert details["phase1_counts"]["hackernews"] == 1
    assert details["phase1_failed_sources"] == []

    from autofanpage.state import LastSuccess
    assert LastSuccess(base=env["base"], page=env["page"]).ran_on("2026-04-15")

    merged_path = env["base"] / "runs" / env["page"] / "2026-04-15" / "merged_sources.json"
    merged = json.loads(merged_path.read_text())
    assert set(merged["sources_succeeded"]) == {"youtube", "perplexity", "reddit", "hackernews"}
    assert merged["sources_failed"] == []
    assert "urls" in merged and "counts_per_platform" in merged
    assert len(merged["urls"]) == sum(merged["counts_per_platform"].values())


def test_partial_failure_still_succeeds(env, mocker):
    fake, calls = _fake_factory(failing={"reddit"})
    mocker.patch("orchestrate.run_skill", side_effect=fake)

    exit_code = _run(env)
    assert exit_code == 0

    tg = next(c for c in calls if c[0] == "telegram-reporter")
    assert tg[1]["status"] == "success"
    assert tg[1]["details"]["phase1_failed_sources"] == ["reddit"]

    merged_path = env["base"] / "runs" / env["page"] / "2026-04-15" / "merged_sources.json"
    merged = json.loads(merged_path.read_text())
    assert "reddit" not in merged["sources_succeeded"]
    assert any(f["source"] == "reddit" for f in merged["sources_failed"])


def test_below_min_required_reports_error_and_does_not_mark(env, mocker):
    fake, calls = _fake_factory(
        failing={"youtube", "perplexity", "reddit"},
    )
    mocker.patch("orchestrate.run_skill", side_effect=fake)

    exit_code = _run(env)
    assert exit_code == 1

    err_calls = [c for c in calls if c[0] == "telegram-reporter"]
    assert len(err_calls) == 1
    assert err_calls[0][1]["status"] == "error"
    assert err_calls[0][1]["details"]["phase"] == "phase1-data-gathering"

    from autofanpage.state import LastSuccess
    assert not LastSuccess(base=env["base"], page=env["page"]).ran_on("2026-04-15")


def test_idempotent_second_run_emits_info(env, mocker):
    fake, calls = _fake_factory(failing=set())
    mocker.patch("orchestrate.run_skill", side_effect=fake)

    assert _run(env) == 0
    calls.clear()
    assert _run(env) == 0

    assert len(calls) == 1
    assert calls[0][0] == "telegram-reporter"
    assert calls[0][1]["status"] == "info"


def test_empty_items_aborts_and_does_not_mark(env, mocker):
    calls: list[tuple[str, dict]] = []
    empty_artifacts: dict[str, dict] = {
        "youtube": {
            "source": "youtube",
            "fetched_at": "2026-04-15T06:00:00+07:00",
            "items": [],
        },
        "perplexity": {
            "source": "perplexity",
            "fetched_at": "2026-04-15T06:00:00+07:00",
            "news": [], "reports": [], "twitter": [],
        },
        "reddit": {
            "source": "reddit",
            "fetched_at": "2026-04-15T06:00:00+07:00",
            "items": [],
        },
        "hackernews": {
            "source": "hackernews",
            "fetched_at": "2026-04-15T06:00:00+07:00",
            "items": [],
        },
    }

    def fake(skill_name, args):
        calls.append((skill_name, args))
        if skill_name == "telegram-reporter":
            return {"status": "ok"}
        source = skill_name.replace("-researcher", "")
        run_dir = Path(args["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)
        art_name = orchestrate.SOURCE_ARTIFACTS[source]
        (run_dir / art_name).write_text(json.dumps(empty_artifacts[source]))
        return {"status": "ok", "artifact": str(run_dir / art_name)}

    mocker.patch("orchestrate.run_skill", side_effect=fake)

    exit_code = _run(env)
    assert exit_code == 1

    err_calls = [c for c in calls if c[0] == "telegram-reporter"]
    assert len(err_calls) == 1
    assert err_calls[0][1]["status"] == "error"
    assert "urls=0" in err_calls[0][1]["details"]["cause"]

    from autofanpage.state import LastSuccess
    assert not LastSuccess(base=env["base"], page=env["page"]).ran_on("2026-04-15")
