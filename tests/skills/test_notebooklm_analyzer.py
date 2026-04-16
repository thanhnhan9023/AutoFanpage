import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "notebooklm-analyzer" / "scripts"
sys.path.insert(0, str(SCRIPT))
import analyze  # noqa: E402


@pytest.fixture
def run_dir(tmp_path, fixtures_dir):
    rd = tmp_path / "runs" / "page_test" / "2026-04-16"
    rd.mkdir(parents=True)
    src = fixtures_dir / "merged_sources_small.json"
    (rd / "merged_sources.json").write_text(src.read_text(), encoding="utf-8")
    return rd


def _fake_mcp_client(notebook_id="nb_42"):
    class Fake:
        def __init__(self):
            self.calls = []

        def call_tool(self, *, server, tool, args, timeout=120):
            self.calls.append((server, tool, dict(args)))
            if tool == "notebook_create":
                return {"notebook_id": notebook_id}
            if tool == "source_add":
                return {"source_id": f"src_{len(self.calls)}"}
            if tool == "notebook_query":
                q = args.get("query", "")
                if "overview" in q.lower():
                    return {"answer": "overview text"}
                if "pain" in q.lower():
                    return {"answer": "- p1\n- p2\n- p3"}
                if "insights" in q.lower() or "business insight" in q.lower():
                    return {
                        "answer": "\n".join([f"- insight {i}" for i in range(7)]),
                    }
                if "gap" in q.lower():
                    return {"answer": "- gap1\n- gap2"}
            raise RuntimeError(f"unexpected tool {tool}")

    return Fake()


def test_happy_path_creates_notebook_adds_sources_runs_four_queries(run_dir, mocker):
    fake = _fake_mcp_client()
    mocker.patch.object(analyze, "MCPClient", return_value=fake)

    out = analyze.main([
        "--run-dir", str(run_dir),
        "--profile", str(run_dir.parent.parent / "does_not_matter.json"),
        "--language", "vi",
    ])
    assert out == 0

    tool_names = [t for (_, t, _) in fake.calls]
    assert tool_names.count("notebook_create") == 1
    assert tool_names.count("source_add") == 4
    assert tool_names.count("notebook_query") == 4

    insights_path = run_dir / "insights.json"
    assert insights_path.exists()
    payload = json.loads(insights_path.read_text())
    assert payload["language"] == "vi"
    assert payload["overview"] == "overview text"
    assert len(payload["pain_points"]) == 3
    assert len(payload["insights"]) >= 5
    assert len(payload["gap_topics"]) == 2
    assert payload["notebook_id"] == "nb_42"
    assert payload["source_urls"] == [
        "https://y.example/v1",
        "https://n.example/a",
        "https://r.example/p1",
        "https://h.example/i1",
    ]


def test_mcp_failure_on_notebook_create_raises_and_writes_no_artifact(run_dir, mocker):
    from autofanpage.mcp import MCPError

    class Fake:
        def call_tool(self, **kw):
            raise MCPError("cookies expired")

    mocker.patch.object(analyze, "MCPClient", return_value=Fake())

    with pytest.raises(MCPError):
        analyze.main([
            "--run-dir", str(run_dir),
            "--profile", str(run_dir.parent.parent / "x.json"),
            "--language", "vi",
        ])
    assert not (run_dir / "insights.json").exists()


def test_all_empty_urls_raises(tmp_path, mocker):
    rd = tmp_path / "runs" / "page_test" / "2026-04-16"
    rd.mkdir(parents=True)
    (rd / "merged_sources.json").write_text(json.dumps({
        "topic": "x", "language": "vi", "urls": [],
        "counts_per_platform": {},
        "sources_succeeded": [], "sources_failed": [],
        "fetched_at": "2026-04-16T06:00:00+07:00", "profile": "page_test",
    }), encoding="utf-8")

    from autofanpage.errors import AutofanpageError
    with pytest.raises(AutofanpageError) as exc:
        analyze.main([
            "--run-dir", str(rd),
            "--profile", str(tmp_path / "x.json"),
            "--language", "vi",
        ])
    assert "no source urls" in str(exc.value).lower()


def test_legacy_items_shape_raises_schema_error(tmp_path):
    rd = tmp_path / "runs" / "page_test" / "2026-04-16"
    rd.mkdir(parents=True)
    (rd / "merged_sources.json").write_text(json.dumps({
        "profile": "page_test",
        "topic": "x", "language": "vi",
        "fetched_at": "2026-04-16T06:00:00+07:00",
        "sources_succeeded": ["youtube"], "sources_failed": [],
        "items": [{"source": "youtube", "url": "https://y/1", "title": "t", "score": 1}],
    }), encoding="utf-8")

    from autofanpage.errors import AutofanpageError
    with pytest.raises(AutofanpageError) as exc:
        analyze.main([
            "--run-dir", str(rd),
            "--profile", str(tmp_path / "x.json"),
            "--language", "vi",
        ])
    assert "schema" in str(exc.value).lower()
