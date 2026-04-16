import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "writing-agent" / "scripts"
sys.path.insert(0, str(SCRIPT))
import write_posts  # noqa: E402


@pytest.fixture
def run_dir(tmp_path, fixtures_dir):
    rd = tmp_path / "runs" / "page_test" / "2026-04-16"
    rd.mkdir(parents=True)
    (rd / "reviewed_insights.json").write_text(
        (fixtures_dir / "reviewed_insights_sample.json").read_text(),
        encoding="utf-8",
    )
    return rd


class _FakeClaude:
    def __init__(self, body: str = "BODY", comment: str = "COMMENT"):
        self.body = body
        self.comment = comment
        self.calls: list[dict] = []

    def generate(self, *, system, messages, max_tokens, temperature):
        self.calls.append({
            "system": system, "messages": messages,
            "max_tokens": max_tokens, "temperature": temperature,
        })
        if "first comment" in messages[0]["content"].lower():
            return self.comment
        return self.body


def test_happy_path_writes_four_posts_matching_slot_types(run_dir, fixtures_dir, mocker):
    fake = _FakeClaude()
    mocker.patch.object(write_posts, "ClaudeClient", return_value=fake)
    mocker.patch.object(write_posts, "get_secret", return_value="sk-ant-fake")

    rc = write_posts.main([
        "--run-dir", str(run_dir),
        "--profile", str(fixtures_dir / "profile_plan3.json"),
    ])
    assert rc == 0

    out = json.loads((run_dir / "posts.json").read_text())
    assert out["language"] == "vi"
    assert [p["type"] for p in out["posts"]] == ["news", "guide", "opinion", "case_study"]
    assert [p["time"] for p in out["posts"]] == ["08:00", "12:00", "16:00", "20:00"]
    assert all(p["content"] == "BODY" for p in out["posts"])
    assert all(p["first_comment"] == "COMMENT" for p in out["posts"])
    assert len(fake.calls) == 8


def test_slot_without_matching_insight_emits_null(run_dir, fixtures_dir, mocker):
    src = json.loads((run_dir / "reviewed_insights.json").read_text())
    src["approved"] = [a for a in src["approved"]
                       if a["suggested_post_type"] != "guide"]
    (run_dir / "reviewed_insights.json").write_text(json.dumps(src))

    fake = _FakeClaude()
    mocker.patch.object(write_posts, "ClaudeClient", return_value=fake)
    mocker.patch.object(write_posts, "get_secret", return_value="sk")

    write_posts.main([
        "--run-dir", str(run_dir),
        "--profile", str(fixtures_dir / "profile_plan3.json"),
    ])
    out = json.loads((run_dir / "posts.json").read_text())
    assert out["posts"][1]["content"] is None
    assert out["posts"][1]["first_comment"] is None
    for i in (0, 2, 3):
        assert out["posts"][i]["content"] == "BODY"
    assert len(fake.calls) == 6


def test_multiple_approved_of_same_type_picks_highest_total(run_dir, fixtures_dir, mocker):
    src = json.loads((run_dir / "reviewed_insights.json").read_text())
    src["approved"].append({
        "insight": "weak news item",
        "scores": {"relevance": 3, "novelty": 3, "viral": 4, "actionable": 2},
        "total": 12,
        "suggested_post_type": "news",
        "hook_angle": "weak",
        "source_url": "https://weak.example/1",
    })
    (run_dir / "reviewed_insights.json").write_text(json.dumps(src))

    fake = _FakeClaude()
    mocker.patch.object(write_posts, "ClaudeClient", return_value=fake)
    mocker.patch.object(write_posts, "get_secret", return_value="sk")

    write_posts.main([
        "--run-dir", str(run_dir),
        "--profile", str(fixtures_dir / "profile_plan3.json"),
    ])

    news_body_prompt = fake.calls[0]["messages"][0]["content"]
    assert "GPT-5" in news_body_prompt
    assert "weak news item" not in news_body_prompt


def test_empty_approved_produces_four_null_posts(tmp_path, fixtures_dir, mocker):
    rd = tmp_path / "runs" / "page_test" / "2026-04-16"
    rd.mkdir(parents=True)
    (rd / "reviewed_insights.json").write_text(json.dumps({
        "approved": [], "rejected": [],
    }))

    fake = _FakeClaude()
    mocker.patch.object(write_posts, "ClaudeClient", return_value=fake)
    mocker.patch.object(write_posts, "get_secret", return_value="sk")

    rc = write_posts.main([
        "--run-dir", str(rd),
        "--profile", str(fixtures_dir / "profile_plan3.json"),
    ])
    assert rc == 0
    out = json.loads((rd / "posts.json").read_text())
    assert all(p["content"] is None for p in out["posts"])
    assert all(p["first_comment"] is None for p in out["posts"])
    assert len(fake.calls) == 0
