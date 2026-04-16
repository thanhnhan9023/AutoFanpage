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
        "profile": fixtures_dir / "profile_plan3.json",
        "page": "page_test",
    }


def _plan2_fake(failing: set[str] | None = None):
    failing = failing or set()
    calls: list[tuple[str, dict]] = []

    def fake(name, args):
        calls.append((name, args))
        run_dir = Path(args.get("run_dir", "."))
        if name == "telegram-reporter":
            return {"status": "ok", "sent": True}

        if name.endswith("-researcher"):
            key = name.replace("-researcher", "")
            if key in failing:
                from autofanpage.errors import SourceFailedError
                raise SourceFailedError(f"fake fail {key}")
            run_dir.mkdir(parents=True, exist_ok=True)
            _FAKE_ARTIFACTS = {
                "youtube": {
                    "source": "youtube", "fetched_at": "t",
                    "items": [{"title": "yt", "url": "https://youtube.example/1",
                               "video_id": "1", "channel": "c", "views": 200000,
                               "subscribers": 30000,
                               "published_at": "2026-04-10T00:00:00Z"}],
                },
                "perplexity": {
                    "source": "perplexity", "fetched_at": "t",
                    "news": [{"title": "n", "url": "https://perplexity.example/1",
                              "summary": "", "source": "n.com"}],
                    "reports": [], "twitter": [],
                },
                "reddit": {
                    "source": "reddit", "fetched_at": "t",
                    "items": [{"title": "rd", "url": "https://reddit.example/1",
                               "subreddit": "ChatGPT", "score": 800,
                               "num_comments": 30, "author": "u",
                               "permalink": "/r/1",
                               "created_at": "2026-04-14T00:00:00Z",
                               "is_self": False, "external_url": ""}],
                },
                "hackernews": {
                    "source": "hackernews", "fetched_at": "t",
                    "items": [{"title": "hn", "url": "https://hackernews.example/1",
                               "points": 300, "by": "u", "descendants": 10,
                               "created_at": "2026-04-14T00:00:00Z",
                               "hn_url": "https://news.ycombinator.com/item?id=1"}],
                },
            }
            (run_dir / orchestrate.SOURCE_ARTIFACTS[key]).write_text(
                json.dumps(_FAKE_ARTIFACTS[key])
            )
            return {"status": "ok"}

        if name == "notebooklm-analyzer":
            if "nblm_fail" in failing:
                from autofanpage.errors import AutofanpageError
                raise AutofanpageError("cookies expired")
            (run_dir / "insights.json").write_text(json.dumps({
                "overview": "x",
                "pain_points": ["p"],
                "insights": [
                    "OpenAI launched GPT-5 — latency dropped 35% vs 4.5.",
                    "Teams using prompt caching cut API spend 60% in 8 weeks.",
                    "Why most AI agents still fail in production.",
                    "How Acme Corp cut support response 55% with AI routing.",
                ],
                "gap_topics": ["g"],
                "source_urls": ["https://y.example/1"],
                "language": "vi",
                "notebook_id": "nb_fake",
            }))
            return {"status": "ok"}

        if name == "review-agent":
            reviewed = {
                "approved": [
                    {"insight": "a", "scores": {"relevance": 5, "novelty": 5, "viral": 5, "actionable": 2},
                     "total": 17, "suggested_post_type": "news",
                     "hook_angle": "", "source_url": ""},
                    {"insight": "b", "scores": {"relevance": 5, "novelty": 4, "viral": 5, "actionable": 5},
                     "total": 19, "suggested_post_type": "guide",
                     "hook_angle": "", "source_url": ""},
                    {"insight": "c", "scores": {"relevance": 5, "novelty": 4, "viral": 3, "actionable": 2},
                     "total": 14, "suggested_post_type": "opinion",
                     "hook_angle": "", "source_url": ""},
                    {"insight": "d", "scores": {"relevance": 5, "novelty": 4, "viral": 5, "actionable": 4},
                     "total": 18, "suggested_post_type": "case_study",
                     "hook_angle": "", "source_url": ""},
                ],
                "rejected": [],
            }
            if "review_empty" in failing:
                reviewed = {"approved": [], "rejected": []}
            elif "review_one" in failing:
                reviewed["approved"] = reviewed["approved"][:1]
            (run_dir / "reviewed_insights.json").write_text(json.dumps(reviewed))
            return {"status": "ok"}

        if name == "writing-agent":
            (run_dir / "posts.json").write_text(json.dumps({
                "language": "vi",
                "posts": [
                    {"time": "08:00", "type": "news",       "content": "x", "first_comment": "y"},
                    {"time": "12:00", "type": "guide",      "content": "x", "first_comment": "y"},
                    {"time": "16:00", "type": "opinion",    "content": "x", "first_comment": "y"},
                    {"time": "20:00", "type": "case_study", "content": "x", "first_comment": "y"},
                ],
            }))
            return {"status": "ok"}

        if name == "facebook-publisher":
            (run_dir / "publish_results.json").write_text(json.dumps({
                "page": "page_test",
                "date": "2026-04-16",
                "posts": [
                    {"time": "08:00", "type": "news", "post_id": "p0", "comment_id": "c0", "status": 200},
                    {"time": "12:00", "type": "guide", "post_id": "p1", "comment_id": "c1", "status": 200},
                    {"time": "16:00", "type": "opinion", "post_id": "p2", "comment_id": "c2", "status": 200},
                    {"time": "20:00", "type": "case_study", "post_id": "p3", "comment_id": "c3", "status": 200},
                ],
            }))
            return {"status": "ok"}

        raise RuntimeError(f"unexpected skill {name}")

    return fake, calls


def _run(env, date="2026-04-16"):
    return orchestrate.main([
        "--page", env["page"],
        "--profile-path", str(env["profile"]),
        "--base-dir", str(env["base"]),
        "--date", date,
    ])


def test_happy_path_runs_all_phases_and_reports_success(env, mocker):
    fake, calls = _plan2_fake()
    mocker.patch("orchestrate.run_skill", side_effect=fake)
    assert _run(env) == 0

    names = [c[0] for c in calls]
    assert "notebooklm-analyzer" in names
    assert "review-agent" in names
    assert "writing-agent" in names

    tg = [c for c in calls if c[0] == "telegram-reporter"]
    assert len(tg) == 1
    assert tg[0][1]["status"] == "success"
    assert tg[0][1]["details"]["posts_generated"] == 4
    assert tg[0][1]["details"]["approved_count"] == 4


def test_notebooklm_failure_halts_pipeline_and_reports_cookies_hint(env, mocker):
    fake, calls = _plan2_fake(failing={"nblm_fail"})
    mocker.patch("orchestrate.run_skill", side_effect=fake)
    mocker.patch("orchestrate.time.sleep", return_value=None)
    assert _run(env) == 1

    names = [c[0] for c in calls]
    assert "review-agent" not in names
    assert "writing-agent" not in names

    tg = [c for c in calls if c[0] == "telegram-reporter"]
    assert len(tg) == 1
    assert tg[0][1]["status"] == "error"
    assert tg[0][1]["details"]["phase"] == "phase2-notebooklm"
    assert "nlm login" in tg[0][1]["details"]["cause"]

    from autofanpage.state import LastSuccess
    assert not LastSuccess(base=env["base"], page=env["page"]).ran_on("2026-04-16")


def test_notebooklm_retries_once_and_succeeds(env, mocker):
    attempts = {"count": 0}
    fake, calls = _plan2_fake()

    def wrapped(name, args):
        if name == "notebooklm-analyzer" and attempts["count"] == 0:
            attempts["count"] += 1
            from autofanpage.errors import AutofanpageError
            raise AutofanpageError("transient mcp glitch")
        return fake(name, args)

    mocker.patch("orchestrate.run_skill", side_effect=wrapped)
    mocker.patch("orchestrate.time.sleep", return_value=None)

    assert _run(env) == 0
    tg = [c for c in calls if c[0] == "telegram-reporter"]
    assert tg[0][1]["status"] == "success"


def test_review_below_min_posts_required_becomes_partial(env, mocker):
    fake, calls = _plan2_fake(failing={"review_one"})
    mocker.patch("orchestrate.run_skill", side_effect=fake)

    assert _run(env) == 0  # soft-success

    names = [c[0] for c in calls]
    assert "writing-agent" not in names
    tg = [c for c in calls if c[0] == "telegram-reporter"]
    assert tg[0][1]["status"] == "partial"
    assert tg[0][1]["details"]["approved_count"] == 1
    assert tg[0][1]["details"]["posts_generated"] == 0

    from autofanpage.state import LastSuccess
    assert LastSuccess(base=env["base"], page=env["page"]).ran_on("2026-04-16")


def test_zero_approved_is_partial_not_error(env, mocker):
    fake, calls = _plan2_fake(failing={"review_empty"})
    mocker.patch("orchestrate.run_skill", side_effect=fake)

    assert _run(env) == 0
    tg = [c for c in calls if c[0] == "telegram-reporter"]
    assert tg[0][1]["status"] == "partial"
    assert tg[0][1]["details"]["approved_count"] == 0
