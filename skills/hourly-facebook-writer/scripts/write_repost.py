#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from autofanpage.errors import AutofanpageError
from autofanpage.llm import build_writer_client
from autofanpage.profile import load_profile
from autofanpage.prompts import (
    build_hourly_repost_prompt,
    build_hourly_repost_rewrite_prompt,
    build_hourly_repost_review_prompt,
)
from autofanpage.schemas import validate
from autofanpage.secrets import get_secret


def _generate_non_empty(
    client: Any,
    *,
    system: str,
    messages: list[dict],
    max_tokens: int,
    temperature: float,
    error_message: str,
) -> str:
    body = client.generate(
        system=system,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    ).strip()
    if not body:
        raise AutofanpageError(error_message)
    return body


def _parse_review_response(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AutofanpageError(f"review returned invalid JSON: {e}") from e
    if not isinstance(payload, dict):
        raise AutofanpageError("review returned non-object JSON")
    approved = payload.get("approved")
    feedback = str(payload.get("feedback") or "").strip()
    if not isinstance(approved, bool):
        raise AutofanpageError("review JSON missing boolean approved field")
    if not feedback:
        raise AutofanpageError("review JSON missing feedback text")
    return {"approved": approved, "feedback": feedback}


def _review_once(
    *,
    client: Any,
    source_post: dict[str, Any],
    draft_post: str,
    language: str,
    style: str | None,
) -> dict[str, Any]:
    review_system, review_messages = build_hourly_repost_review_prompt(
        source_post=source_post,
        draft_post=draft_post,
        language=language,
        style=style,
    )
    review_raw = _generate_non_empty(
        client,
        system=review_system,
        messages=review_messages,
        max_tokens=400,
        temperature=0,
        error_message="review output is empty",
    )
    return _parse_review_response(review_raw)


def _review_and_rewrite_if_needed(
    *,
    run_dir: Path,
    source_post: dict[str, Any],
    profile: Any,
    writer_client: Any,
    draft_body: str,
) -> str:
    review_model = profile.writing.review_model
    if not review_model:
        return draft_body

    review_api_key = get_secret(
        profile.writing.review_api_key_ref or profile.writing.api_key_ref
    )
    review_client = build_writer_client(api_key=review_api_key, model=review_model)
    max_rounds = profile.writing.review_max_rounds
    attempts: list[dict[str, Any]] = []
    current_body = draft_body
    approved = False
    writer_model = profile.writing.model

    for round_no in range(1, max_rounds + 1):
        try:
            review = _review_once(
                client=review_client,
                source_post=source_post,
                draft_post=current_body,
                language=profile.language,
                style=profile.writing.style,
            )
        except AutofanpageError as exc:
            if review_model != writer_model:
                try:
                    review = _review_once(
                        client=writer_client,
                        source_post=source_post,
                        draft_post=current_body,
                        language=profile.language,
                        style=profile.writing.style,
                    )
                except AutofanpageError:
                    review = {
                        "approved": False,
                        "feedback": f"Reviewer returned empty output or invalid review JSON: {exc}",
                    }
            else:
                review = {
                    "approved": False,
                    "feedback": f"Reviewer returned empty output or invalid review JSON: {exc}",
                }
        attempts.append(
            {
                "round": round_no,
                "approved": review["approved"],
                "feedback": review["feedback"],
                "draft": current_body,
            }
        )
        if review["approved"]:
            approved = True
            break
        if round_no == max_rounds:
            break

        rewrite_system, rewrite_messages = build_hourly_repost_rewrite_prompt(
            source_post=source_post,
            current_draft=current_body,
            feedback=review["feedback"],
            language=profile.language,
            style=profile.writing.style,
        )
        current_body = _generate_non_empty(
            writer_client,
            system=rewrite_system,
            messages=rewrite_messages,
            max_tokens=profile.writing.max_tokens,
            temperature=profile.writing.temperature,
            error_message="rewritten repost body is empty",
        )

    (run_dir / "review_feedback.json").write_text(
        json.dumps(
            {
                "review_model": review_model,
                "approved": approved,
                "attempts": attempts,
                "final_body": current_body,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return current_body


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
    client = build_writer_client(api_key=api_key, model=profile.writing.model)

    system, messages = build_hourly_repost_prompt(
        source_post=source_post,
        language=profile.language,
        style=profile.writing.style,
    )
    body = _generate_non_empty(
        client,
        system=system,
        messages=messages,
        max_tokens=profile.writing.max_tokens,
        temperature=profile.writing.temperature,
        error_message="generated repost body is empty",
    )
    body = _review_and_rewrite_if_needed(
        run_dir=run_dir,
        source_post=source_post,
        profile=profile,
        writer_client=client,
        draft_body=body,
    )

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
