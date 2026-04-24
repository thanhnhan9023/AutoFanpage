#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from autofanpage.errors import AutofanpageError
from autofanpage.llm import ClaudeClient
from autofanpage.profile import load_profile
from autofanpage.prompts import build_hourly_repost_prompt
from autofanpage.schemas import validate
from autofanpage.secrets import get_secret


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--publish-time", required=True)
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir)
    source_path = run_dir / "latest_source_post.json"
    if not source_path.exists():
        raise AutofanpageError(f"missing input: {source_path}")

    source_post = json.loads(source_path.read_text(encoding="utf-8"))
    validate("latest_source_post", source_post)

    profile = load_profile(args.profile)
    api_key = get_secret(profile.writing.api_key_ref)
    client = ClaudeClient(api_key=api_key, model=profile.writing.model)

    system, messages = build_hourly_repost_prompt(
        source_post=source_post,
        language=profile.language,
        style=profile.writing.style,
    )
    body = client.generate(
        system=system,
        messages=messages,
        max_tokens=profile.writing.max_tokens,
        temperature=profile.writing.temperature,
    ).strip()
    if not body:
        raise AutofanpageError("generated repost body is empty")

    placeholder_times = list(profile.post_times)
    try:
        placeholder_times.remove(args.publish_time)
    except ValueError:
        placeholder_times = placeholder_times[1:]
    if len(placeholder_times) != 3:
        raise AutofanpageError(
            f"expected exactly 3 placeholder times after excluding publish time; "
            f"got {len(placeholder_times)}"
        )

    posts = {
        "language": profile.language,
        "posts": [
            {
                "time": args.publish_time,
                "type": "news",
                "content": body,
                "first_comment": None,
            },
            {
                "time": placeholder_times[0],
                "type": "guide",
                "content": None,
                "first_comment": None,
            },
            {
                "time": placeholder_times[1],
                "type": "opinion",
                "content": None,
                "first_comment": None,
            },
            {
                "time": placeholder_times[2],
                "type": "case_study",
                "content": None,
                "first_comment": None,
            },
        ],
    }
    validate("posts", posts)
    (run_dir / "posts.json").write_text(
        json.dumps(posts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"status": "ok", "artifact": "posts.json", "posts_generated": 1},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
