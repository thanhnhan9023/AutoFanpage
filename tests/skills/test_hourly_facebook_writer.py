import json
import sys
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "hourly-facebook-writer"
    / "scripts"
)
sys.path.insert(0, str(SCRIPT))
import write_repost  # noqa: E402


def test_main_writes_single_active_repost_slot(tmp_path, fixtures_dir, mocker, capsys):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "latest_source_post.json").write_text(
        json.dumps(
            {
                "source_page_url": "https://www.facebook.com/0xSojalSec",
                "source_post_id": "123",
                "source_post_url": "https://facebook.com/post/123",
                "author": "0xSojalSec",
                "published_at": "2026-04-23T09:15:00Z",
                "content_text": "OpenAI launched a new model.",
                "media_urls": [],
                "backend": "browser_use_mcp",
                "fetched_at": "2026-04-23T10:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    mocker.patch.object(write_repost, "get_secret", return_value="sk-ant-fake")
    mocker.patch.object(write_repost.ClaudeClient, "generate", return_value="Bai viet moi")

    rc = write_repost.main(
        [
            "--run-dir",
            str(run_dir),
            "--profile",
            str(fixtures_dir / "profile_hourly_facebook_repost.json"),
            "--date",
            "2026-04-23",
            "--publish-time",
            "10:15",
        ]
    )

    assert rc == 0
    assert (run_dir / "posts.json").exists()

    out = json.loads((run_dir / "posts.json").read_text(encoding="utf-8"))
    assert len(out["posts"]) == 4

    first, second, third, fourth = out["posts"]
    assert first["time"] == "10:15"
    assert first["type"] == "news"
    assert first["content"] == "Bai viet moi"
    assert first["first_comment"] is None

    assert second["time"] == "12:00"
    assert second["type"] == "guide"
    assert second["content"] is None
    assert second["first_comment"] is None

    assert third["time"] == "16:00"
    assert third["type"] == "opinion"
    assert third["content"] is None
    assert third["first_comment"] is None

    assert fourth["time"] == "20:00"
    assert fourth["type"] == "case_study"
    assert fourth["content"] is None
    assert fourth["first_comment"] is None

    stdout = capsys.readouterr().out.strip()
    status = json.loads(stdout)
    assert status["artifact"] == "posts.json"
    assert status["posts_generated"] == 1
