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


def _full_fake(failing: set[str] | None = None):
    failing = failing or set()
    calls: list[tuple[str, dict]] = []

    def researcher_key(name: str) -> str:
        if name == "reddit-researcher-apify":
            return "reddit"
        return name.replace("-researcher", "")

    def fake(name, args):
        calls.append((name, args))
        run_dir = Path(args.get("run_dir", "."))

        if name == "telegram-reporter":
            return {"status": "ok", "sent": True}

        if name.endswith("-researcher") or name == "reddit-researcher-apify":
            key = researcher_key(name)
            if key in failing:
                from autofanpage.errors import SourceFailedError
                raise SourceFailedError(f"fake fail {key}")
            run_dir.mkdir(parents=True, exist_ok=True)
            fake_artifacts = {
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
                json.dumps(fake_artifacts[key]),
            )
            return {"status": "ok"}

        if name == "notebooklm-analyzer":
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
            (run_dir / "reviewed_insights.json").write_text(json.dumps({
                "approved": [
                    {"insight": "a", "scores": {"relevance": 5, "novelty": 5, "viral": 5, "actionable": 2},
                     "total": 17, "suggested_post_type": "news", "hook_angle": "", "source_url": ""},
                    {"insight": "b", "scores": {"relevance": 5, "novelty": 4, "viral": 5, "actionable": 5},
                     "total": 19, "suggested_post_type": "guide", "hook_angle": "", "source_url": ""},
                    {"insight": "c", "scores": {"relevance": 5, "novelty": 4, "viral": 3, "actionable": 2},
                     "total": 14, "suggested_post_type": "opinion", "hook_angle": "", "source_url": ""},
                    {"insight": "d", "scores": {"relevance": 5, "novelty": 4, "viral": 5, "actionable": 4},
                     "total": 18, "suggested_post_type": "case_study", "hook_angle": "", "source_url": ""},
                ],
                "rejected": [],
            }))
            return {"status": "ok"}

        if name == "writing-agent":
            (run_dir / "posts.json").write_text(json.dumps({
                "language": "vi",
                "posts": [
                    {"time": "08:00", "type": "news", "content": "News post", "first_comment": "fc1"},
                    {"time": "12:00", "type": "guide", "content": "Guide post", "first_comment": "fc2"},
                    {"time": "16:00", "type": "opinion", "content": "Opinion post", "first_comment": "fc3"},
                    {"time": "20:00", "type": "case_study", "content": "Case post", "first_comment": "fc4"},
                ],
            }))
            return {"status": "ok"}

        if name == "facebook-publisher":
            if args.get("dry_run", False):
                (run_dir / "preview.md").write_text("# Preview\nContent")
                return {"status": "ok", "mode": "dry_run"}
            if "fb_fail" in failing:
                from autofanpage.errors import SourceFailedError
                raise SourceFailedError("FB token expired")
            (run_dir / "publish_results.json").write_text(json.dumps({
                "page": "page_test",
                "date": args.get("date", "2026-04-16"),
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


def _run(env, date="2026-04-16", dry_run=False):
    argv = [
        "--page", env["page"],
        "--profile-path", str(env["profile"]),
        "--base-dir", str(env["base"]),
        "--date", date,
    ]
    if dry_run:
        argv.append("--dry-run")
    return orchestrate.main(argv)


def test_full_pipeline_publishes_and_reports_scheduled_count(env, mocker):
    fake, calls = _full_fake()
    mocker.patch("orchestrate.run_skill", side_effect=fake)
    mcp = mocker.Mock()
    mcp.call_tool.return_value = {"notebook_id": "nb_preflight"}
    mocker.patch("orchestrate.MCPClient", return_value=mcp)
    mocker.patch("orchestrate.time.sleep", return_value=None)
    assert _run(env) == 0

    names = [call[0] for call in calls]
    assert "facebook-publisher" in names

    telegram = [call for call in calls if call[0] == "telegram-reporter"]
    assert telegram[-1][1]["status"] == "success"
    assert telegram[-1][1]["details"]["posts_scheduled"] == 4


def test_dry_run_skips_publish_sends_preview(env, mocker):
    fake, calls = _full_fake()
    mocker.patch("orchestrate.run_skill", side_effect=fake)
    mcp = mocker.Mock()
    mcp.call_tool.return_value = {"notebook_id": "nb_preflight"}
    mocker.patch("orchestrate.MCPClient", return_value=mcp)
    mocker.patch("orchestrate.time.sleep", return_value=None)
    assert _run(env, dry_run=True) == 0

    names = [call[0] for call in calls]
    assert "facebook-publisher" in names

    telegram = [call for call in calls if call[0] == "telegram-reporter"]
    last_telegram = telegram[-1]
    assert last_telegram[1]["status"] == "info"
    assert "preview" in last_telegram[1]["details"]["message"].lower()

    from autofanpage.state import LastSuccess
    assert not LastSuccess(base=env["base"], page=env["page"]).ran_on("2026-04-16")


def test_dry_run_run_log_records_phase4_completion(env, mocker):
    fake, _calls = _full_fake()
    mocker.patch("orchestrate.run_skill", side_effect=fake)
    mcp = mocker.Mock()
    mcp.call_tool.return_value = {"notebook_id": "nb_preflight"}
    mocker.patch("orchestrate.MCPClient", return_value=mcp)
    mocker.patch("orchestrate.time.sleep", return_value=None)

    assert _run(env, dry_run=True) == 0

    run_log = (
        Path(env["base"]) / "runs" / env["page"] / "2026-04-16" / "run.log"
    ).read_text(encoding="utf-8")
    assert "phase4 facebook-publisher complete dry_run=True preview=preview.md" in run_log


def test_publish_failure_reports_error(env, mocker):
    fake, calls = _full_fake(failing={"fb_fail"})
    mocker.patch("orchestrate.run_skill", side_effect=fake)
    mcp = mocker.Mock()
    mcp.call_tool.return_value = {"notebook_id": "nb_preflight"}
    mocker.patch("orchestrate.MCPClient", return_value=mcp)
    mocker.patch("orchestrate.time.sleep", return_value=None)

    rc = _run(env)
    assert rc in (1, 2)

    telegram = [call for call in calls if call[0] == "telegram-reporter"]
    assert any(call[1]["status"] == "error" for call in telegram)
