#!/usr/bin/env python3
"""review-agent: score insights, keep total>=14, assign post type.

Reads  <run_dir>/insights.json
Writes <run_dir>/reviewed_insights.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from autofanpage.errors import AutofanpageError
from autofanpage.profile import load_profile
from autofanpage.schemas import validate
from autofanpage.scoring import (
    APPROVAL_THRESHOLD, assign_type, score_insight, total,
)


def _hook_angle(insight: str) -> str:
    """Crude first-pass hook suggestion: the most number-dense sentence."""
    import re
    sentences = re.split(r"(?<=[.!?])\s+", insight.strip())
    if not sentences:
        return insight
    best = max(
        sentences,
        key=lambda s: (len(re.findall(r"\d", s)), len(s)),
    )
    return best.strip()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True)
    p.add_argument("--profile", required=True)
    args = p.parse_args(argv)

    run_dir = Path(args.run_dir)
    insights_path = run_dir / "insights.json"
    if not insights_path.exists():
        raise AutofanpageError(f"missing input: {insights_path}")
    insights = json.loads(insights_path.read_text(encoding="utf-8"))
    validate("insights", insights)

    profile = load_profile(args.profile)

    source_urls = insights.get("source_urls", [])
    fallback_url = source_urls[0] if source_urls else ""

    approved: list[dict] = []
    rejected: list[dict] = []
    for raw in insights["insights"]:
        text = (raw or "").strip()
        scores = score_insight(text, topic=profile.topic)
        t = total(scores)
        if t >= APPROVAL_THRESHOLD:
            approved.append({
                "insight": text,
                "scores": scores,
                "total": t,
                "suggested_post_type": assign_type(text),
                "hook_angle": _hook_angle(text),
                "source_url": fallback_url,
            })
        else:
            rejected.append({
                "insight": text,
                "total": t,
                "reason": f"total {t} < threshold {APPROVAL_THRESHOLD}",
            })

    approved.sort(key=lambda a: a["total"], reverse=True)

    out = {"approved": approved, "rejected": rejected}
    validate("reviewed_insights", out)
    (run_dir / "reviewed_insights.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(json.dumps({
        "status": "ok", "artifact": "reviewed_insights.json",
        "approved_count": len(approved), "rejected_count": len(rejected),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
