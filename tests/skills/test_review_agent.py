import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "review-agent" / "scripts"
sys.path.insert(0, str(SCRIPT))
import review  # noqa: E402


@pytest.fixture
def run_dir(tmp_path, fixtures_dir):
    rd = tmp_path / "runs" / "page_test" / "2026-04-16"
    rd.mkdir(parents=True)
    (rd / "insights.json").write_text(
        (fixtures_dir / "insights_sample.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return rd


def test_review_writes_reviewed_insights_with_approved_and_rejected(run_dir, fixtures_dir):
    profile_path = fixtures_dir / "profile_plan2.json"
    rc = review.main([
        "--run-dir", str(run_dir),
        "--profile", str(profile_path),
    ])
    assert rc == 0

    out = json.loads((run_dir / "reviewed_insights.json").read_text())
    assert "approved" in out
    assert "rejected" in out
    assert len(out["approved"]) >= 3
    assert len(out["rejected"]) >= 1


def test_all_approved_entries_have_total_ge_threshold(run_dir, fixtures_dir):
    review.main([
        "--run-dir", str(run_dir),
        "--profile", str(fixtures_dir / "profile_plan2.json"),
    ])
    out = json.loads((run_dir / "reviewed_insights.json").read_text())
    from autofanpage.scoring import APPROVAL_THRESHOLD
    assert all(a["total"] >= APPROVAL_THRESHOLD for a in out["approved"])


def test_every_approved_has_valid_post_type(run_dir, fixtures_dir):
    review.main([
        "--run-dir", str(run_dir),
        "--profile", str(fixtures_dir / "profile_plan2.json"),
    ])
    out = json.loads((run_dir / "reviewed_insights.json").read_text())
    allowed = {"news", "guide", "opinion", "case_study"}
    assert all(a["suggested_post_type"] in allowed for a in out["approved"])


def test_rejected_rows_have_reason(run_dir, fixtures_dir):
    review.main([
        "--run-dir", str(run_dir),
        "--profile", str(fixtures_dir / "profile_plan2.json"),
    ])
    out = json.loads((run_dir / "reviewed_insights.json").read_text())
    for r in out["rejected"]:
        assert r["reason"]
        assert r["total"] < 14


def test_empty_approved_is_still_valid_output(tmp_path, fixtures_dir):
    rd = tmp_path / "runs" / "page_test" / "2026-04-16"
    rd.mkdir(parents=True)
    (rd / "insights.json").write_text(json.dumps({
        "overview": "x",
        "pain_points": [],
        "insights": ["AI is the future.", "Vague stuff."],
        "gap_topics": [],
        "source_urls": [],
        "language": "vi",
    }), encoding="utf-8")

    rc = review.main([
        "--run-dir", str(rd),
        "--profile", str(fixtures_dir / "profile_plan2.json"),
    ])
    assert rc == 0
    out = json.loads((rd / "reviewed_insights.json").read_text())
    assert out["approved"] == []
    assert len(out["rejected"]) == 2
