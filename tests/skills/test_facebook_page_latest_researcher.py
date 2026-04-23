import json
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "facebook-page-latest-researcher"
    / "scripts"
)
sys.path.insert(0, str(SCRIPT))
import fetch_latest_post  # noqa: E402


def test_main_writes_latest_source_post(tmp_path, fixtures_dir, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    monkeypatch.setattr(
        fetch_latest_post,
        "fetch_latest_post_from_page",
        lambda source_cfg: {
            "source_page_url": "https://www.facebook.com/0xSojalSec",
            "source_post_id": "123",
            "source_post_url": "https://www.facebook.com/0xSojalSec/posts/123",
            "author": "0xSojalSec",
            "published_at": "2026-04-23T09:15:00Z",
            "content_text": "A useful post",
            "media_urls": [],
            "backend": "browser_use_mcp",
            "fetched_at": "2026-04-23T10:00:00Z",
        },
    )

    rc = fetch_latest_post.main(
        [
            "--run-dir",
            str(run_dir),
            "--profile",
            str(fixtures_dir / "profile_hourly_facebook_repost.json"),
        ]
    )

    assert rc == 0
    data = json.loads((run_dir / "latest_source_post.json").read_text(encoding="utf-8"))
    assert data["source_post_id"] == "123"
