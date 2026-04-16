"""Telegram message formatting. Transport is handled by the skill script."""
from __future__ import annotations

from typing import Any


_PREFIX = {"success": "✅", "error": "🚨", "partial": "⚠️", "info": "ℹ️"}


def format_message(*, status: str, page: str, details: dict[str, Any]) -> str:
    if status not in _PREFIX:
        raise ValueError(f"unknown status: {status}")
    prefix = _PREFIX[status]
    header = f"{prefix} AutoFanpage [{page}]"

    if status == "success":
        lines = [
            header,
            f"📝 {details['posts_scheduled']} posts scheduled",
            f"📅 {details['date']}",
            f"⏱ {details['elapsed_sec']}s",
        ]
    elif status == "error":
        lines = [
            header,
            f"Phase: {details['phase']}",
            f"Cause: {details['cause']}",
            "",
            "Log tail:",
            details.get("log_tail", "(no log)"),
        ]
    elif status == "partial":
        lines = [
            header,
            details["reason"],
            "Scheduled post ids:",
            *[f"- {pid}" for pid in details.get("post_ids", [])],
        ]
    else:  # info
        lines = [header, details["message"]]

    return "\n".join(lines)
