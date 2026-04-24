import json
import sys
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "hourly-facebook-writer"
    / "scripts"
)
sys.path.insert(0, str(SCRIPT))
import write_repost  # noqa: E402


class _FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, *, system, messages, max_tokens, temperature):
        self.calls.append(
            {
                "system": system,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )
        if not self.responses:
            raise AssertionError("unexpected extra generate() call")
        return self.responses.pop(0)


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
    writer = _FakeClient(["Ban nhap 1", "Ban nhap da sua"])
    reviewer = _FakeClient([
        '{"approved": false, "feedback": "Hook chua du manh"}',
        '{"approved": true, "feedback": "Dat"}',
    ])
    mocker.patch.object(write_repost, "build_writer_client", side_effect=[writer, reviewer])

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
    assert first["content"] == "Ban nhap da sua"
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
    review = json.loads((run_dir / "review_feedback.json").read_text(encoding="utf-8"))
    assert review["approved"] is True
    assert len(review["attempts"]) == 2
    assert writer.calls[1]["messages"][0]["content"].count("Hook chua du manh") == 1


def test_main_uses_later_profile_time_without_duplicate_slot(
    tmp_path, fixtures_dir, mocker, capsys
):
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
    writer = _FakeClient(["Ban nhap 1"])
    reviewer = _FakeClient(['{"approved": true, "feedback": "Dat"}'])
    mocker.patch.object(write_repost, "build_writer_client", side_effect=[writer, reviewer])

    rc = write_repost.main(
        [
            "--run-dir",
            str(run_dir),
            "--profile",
            str(fixtures_dir / "profile_hourly_facebook_repost.json"),
            "--date",
            "2026-04-23",
            "--publish-time",
            "16:00",
        ]
    )

    assert rc == 0
    out = json.loads((run_dir / "posts.json").read_text(encoding="utf-8"))
    assert [post["time"] for post in out["posts"]] == ["16:00", "08:00", "12:00", "20:00"]
    assert [post["type"] for post in out["posts"]] == ["news", "guide", "opinion", "case_study"]
    assert len({post["time"] for post in out["posts"]}) == 4

    for post in out["posts"][1:]:
        assert post["content"] is None
        assert post["first_comment"] is None

    stdout = capsys.readouterr().out.strip()
    status = json.loads(stdout)
    assert status["artifact"] == "posts.json"
    assert status["posts_generated"] == 1


def test_main_rejects_empty_generated_body(tmp_path, fixtures_dir, mocker, capsys):
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
    writer = _FakeClient(["   "])
    reviewer = _FakeClient([])
    mocker.patch.object(write_repost, "build_writer_client", side_effect=[writer, reviewer])

    with pytest.raises(write_repost.AutofanpageError):
        write_repost.main(
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

    assert not (run_dir / "posts.json").exists()
    assert capsys.readouterr().out == ""


def test_main_handles_duplicate_profile_times_by_removing_one_matching_occurrence(
    tmp_path, fixtures_dir, mocker, capsys
):
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

    profile_data = json.loads(
        (fixtures_dir / "profile_hourly_facebook_repost.json").read_text(encoding="utf-8")
    )
    profile_data["post_times"] = ["08:00", "12:00", "12:00", "20:00"]
    profile_path = tmp_path / "profile_duplicate_times.json"
    profile_path.write_text(
        json.dumps(profile_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    mocker.patch.object(write_repost, "get_secret", return_value="sk-ant-fake")
    writer = _FakeClient(["Ban nhap 1"])
    reviewer = _FakeClient(['{"approved": true, "feedback": "Dat"}'])
    mocker.patch.object(write_repost, "build_writer_client", side_effect=[writer, reviewer])

    rc = write_repost.main(
        [
            "--run-dir",
            str(run_dir),
            "--profile",
            str(profile_path),
            "--date",
            "2026-04-23",
            "--publish-time",
            "12:00",
        ]
    )

    assert rc == 0
    out = json.loads((run_dir / "posts.json").read_text(encoding="utf-8"))
    assert len(out["posts"]) == 4
    assert [post["time"] for post in out["posts"]] == ["12:00", "08:00", "12:00", "20:00"]
    assert [post["type"] for post in out["posts"]] == ["news", "guide", "opinion", "case_study"]

    for post in out["posts"][1:]:
        assert post["content"] is None
        assert post["first_comment"] is None

    stdout = capsys.readouterr().out.strip()
    status = json.loads(stdout)
    assert status["artifact"] == "posts.json"
    assert status["posts_generated"] == 1


def test_main_uses_last_draft_when_review_never_approves_after_max_rounds(
    tmp_path, fixtures_dir, mocker, capsys
):
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
    writer = _FakeClient(["Ban nhap 1", "Ban nhap 2", "Ban nhap 3"])
    reviewer = _FakeClient([
        '{"approved": false, "feedback": "Can gon hon"}',
        '{"approved": false, "feedback": "Van dai dong"}',
        '{"approved": false, "feedback": "Van chua dat"}',
    ])
    mocker.patch.object(write_repost, "build_writer_client", side_effect=[writer, reviewer])

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
    review = json.loads((run_dir / "review_feedback.json").read_text(encoding="utf-8"))
    assert review["approved"] is False
    assert len(review["attempts"]) == 3
    out = json.loads((run_dir / "posts.json").read_text(encoding="utf-8"))
    assert out["posts"][0]["content"] == "Ban nhap 3"
    status = json.loads(capsys.readouterr().out.strip())
    assert status["artifact"] == "posts.json"


def test_main_recovers_when_review_output_is_empty(tmp_path, fixtures_dir, mocker):
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
                "backend": "agent_browser",
                "fetched_at": "2026-04-23T10:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    mocker.patch.object(write_repost, "get_secret", return_value="sk-ant-fake")
    writer = _FakeClient([
        "Ban nhap 1",
        "writer fallback non-json",
        "Ban nhap da sua",
    ])
    reviewer = _FakeClient([
        "   ",
        '{"approved": true, "feedback": "Dat"}',
    ])
    mocker.patch.object(write_repost, "build_writer_client", side_effect=[writer, reviewer])

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
    out = json.loads((run_dir / "posts.json").read_text(encoding="utf-8"))
    assert out["posts"][0]["content"] == "Ban nhap da sua"
    review = json.loads((run_dir / "review_feedback.json").read_text(encoding="utf-8"))
    assert review["approved"] is True
    assert review["attempts"][0]["approved"] is False
    assert "Reviewer returned empty output" in review["attempts"][0]["feedback"]


def test_main_falls_back_to_writer_model_when_reviewer_output_is_empty(
    tmp_path, fixtures_dir, mocker
):
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
                "backend": "agent_browser",
                "fetched_at": "2026-04-23T10:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    mocker.patch.object(write_repost, "get_secret", return_value="sk-ant-fake")
    writer = _FakeClient([
        "Ban nhap 1",
        '{"approved": true, "feedback": "Approved by writer fallback"}',
    ])
    reviewer = _FakeClient(["   "])
    mocker.patch.object(write_repost, "build_writer_client", side_effect=[writer, reviewer])

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
    out = json.loads((run_dir / "posts.json").read_text(encoding="utf-8"))
    assert out["posts"][0]["content"] == "Ban nhap 1"
    review = json.loads((run_dir / "review_feedback.json").read_text(encoding="utf-8"))
    assert review["approved"] is True
    assert review["attempts"][0]["approved"] is True
    assert review["attempts"][0]["feedback"] == "Approved by writer fallback"
