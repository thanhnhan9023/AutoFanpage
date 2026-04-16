#!/usr/bin/env python3
"""notebooklm-analyzer: create a NotebookLM notebook and run 4 fixed queries.

Reads  <run_dir>/merged_sources.json
Writes <run_dir>/insights.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from autofanpage.errors import AutofanpageError
from autofanpage.mcp import MCPClient
from autofanpage.notebooklm import extract_urls
from autofanpage.schemas import validate, SchemaError


SERVER = "notebooklm-mcp"


def _bullets(text: str) -> list[str]:
    """Parse a bulleted answer string into a list of clean items."""
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        for marker in ("- ", "* ", "• "):
            if line.startswith(marker):
                line = line[len(marker):]
                break
        if line[:2].rstrip(".").isdigit() and line[2:3] in (".", ")", " "):
            line = line.split(None, 1)[-1]
        out.append(line)
    return out


def _queries(language: str) -> dict[str, str]:
    instruct = f"Respond in {language}. Use bullets where the answer is a list."
    return {
        "overview":    f"{instruct}\nWrite a 3-5 sentence overview of the state of this topic today based on the provided sources.",
        "pain_points": f"{instruct}\nList 5-8 concrete pain points or friction areas users describe in these sources.",
        "insights":    f"{instruct}\nGive 5-10 sharp, non-obvious business insights the sources collectively support. One bullet each.",
        "gap_topics":  f"{instruct}\nList 3-5 gap topics the sources hint at but do not explore in depth.",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True)
    p.add_argument("--profile", required=True)
    p.add_argument("--language", required=True,
                   help="BCP-47 or plain language name, e.g. 'vi' or 'English'")
    p.add_argument("--max-sources", type=int, default=48)
    args = p.parse_args(argv)

    run_dir = Path(args.run_dir)
    merged_path = run_dir / "merged_sources.json"
    if not merged_path.exists():
        raise AutofanpageError(f"missing input: {merged_path}")
    merged = json.loads(merged_path.read_text(encoding="utf-8"))

    try:
        validate("merged_sources", merged)
    except SchemaError as e:
        raise AutofanpageError(
            f"merged_sources.json does not match Plan 2 schema: {e}"
        ) from e

    urls = extract_urls(merged, max_sources=args.max_sources)
    if not urls:
        raise AutofanpageError("no source urls after extraction — cannot analyze")

    client = MCPClient()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    nb = client.call_tool(
        server=SERVER, tool="notebook_create",
        args={"title": f"AI Research {today}"},
    )
    notebook_id = nb["notebook_id"]

    for url in urls:
        client.call_tool(
            server=SERVER, tool="source_add",
            args={"notebook_id": notebook_id, "url": url},
        )

    queries = _queries(args.language)
    answers = {}
    for key, prompt in queries.items():
        resp = client.call_tool(
            server=SERVER, tool="notebook_query",
            args={"notebook_id": notebook_id, "query": prompt},
            timeout=180,
        )
        answers[key] = resp.get("answer", "")

    insights = {
        "overview":    answers["overview"].strip(),
        "pain_points": _bullets(answers["pain_points"]),
        "insights":    _bullets(answers["insights"]),
        "gap_topics":  _bullets(answers["gap_topics"]),
        "source_urls": urls,
        "language":    args.language,
        "notebook_id": notebook_id,
    }
    validate("insights", insights)
    (run_dir / "insights.json").write_text(
        json.dumps(insights, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(json.dumps({"status": "ok", "artifact": "insights.json",
                      "notebook_id": notebook_id, "sources": len(urls)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
