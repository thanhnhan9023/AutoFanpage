#!/usr/bin/env python3
"""writing-agent: compose 4 slot posts + first-comments from reviewed insights.

Reads  <run_dir>/reviewed_insights.json
Writes <run_dir>/posts.json
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
from autofanpage.llm import ClaudeClient, build_writer_client
from autofanpage.profile import load_profile
from autofanpage.prompts import build_first_comment_prompt, build_writing_prompt
from autofanpage.schemas import validate
from autofanpage.secrets import get_secret
from autofanpage.templates import POST_TYPE_BY_SLOT, TEMPLATES


def _pick_for_type(approved: list[dict], ptype: str) -> dict | None:
    """Return the highest-``total`` approved insight matching ``ptype``."""
    candidates = [a for a in approved if a["suggested_post_type"] == ptype]
    if not candidates:
        return None
    return max(candidates, key=lambda a: a["total"])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True)
    p.add_argument("--profile", required=True)
    args = p.parse_args(argv)

    run_dir = Path(args.run_dir)
    src = run_dir / "reviewed_insights.json"
    if not src.exists():
        raise AutofanpageError(f"missing input: {src}")
    reviewed = json.loads(src.read_text(encoding="utf-8"))
    validate("reviewed_insights", reviewed)

    profile = load_profile(args.profile)
    api_key = get_secret(profile.writing.api_key_ref)
    client = build_writer_client(api_key=api_key, model=profile.writing.model)

    posts = []
    for slot_index, ptype in enumerate(POST_TYPE_BY_SLOT):
        time_str = profile.post_times[slot_index]
        insight = _pick_for_type(reviewed["approved"], ptype)
        if insight is None:
            posts.append({
                "time": time_str, "type": ptype,
                "content": None, "first_comment": None,
            })
            continue
        template = TEMPLATES[ptype]
        system, messages = build_writing_prompt(
            insight=insight, template=template, language=profile.language,
        )
        body = client.generate(
            system=system, messages=messages,
            max_tokens=profile.writing.max_tokens,
            temperature=profile.writing.temperature,
        ).strip()

        fc_system, fc_messages = build_first_comment_prompt(
            insight=insight, template=template, language=profile.language,
            post_body=body,
        )
        first_comment = client.generate(
            system=fc_system, messages=fc_messages,
            max_tokens=max(profile.writing.max_tokens // 2, 300),
            temperature=profile.writing.temperature,
        ).strip()

        posts.append({
            "time": time_str, "type": ptype,
            "content": body, "first_comment": first_comment,
        })

    out = {"posts": posts, "language": profile.language}
    validate("posts", out)
    (run_dir / "posts.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    filled = sum(1 for p in posts if p["content"])
    print(json.dumps({
        "status": "ok", "artifact": "posts.json",
        "posts_generated": filled,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
