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
        generated = details.get("posts_generated")
        if generated is not None:
            lines.insert(2, f"✏️ {generated} posts generated")
        counts = details.get("phase1_counts")
        if counts:
            parts = ", ".join(f"{k}={v}" for k, v in counts.items())
            lines.append(f"🔎 sources: {parts}")
        failed = details.get("phase1_failed_sources") or []
        if failed:
            lines.append(f"⚠️ failed: {', '.join(failed)}")
        if details.get("source_page_url"):
            lines.append(f"📄 source page: {details['source_page_url']}")
        if details.get("source_post_url"):
            lines.append(f"🔗 source post: {details['source_post_url']}")
        if details.get("source_published_at"):
            lines.append(f"🕒 source published: {details['source_published_at']}")
        if details.get("fetch_backend"):
            lines.append(f"🧰 fetch backend: {details['fetch_backend']}")
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
        lines = [header]
        # Plan 3 partial shape
        if "approved_count" in details:
            lines.append(f"📝 {details.get('approved_count', 0)} insights approved")
            lines.append(f"✏️ {details.get('posts_generated', 0)}/4 posts generated")
            counts = details.get("phase1_counts")
            if counts:
                parts = ", ".join(f"{k}={v}" for k, v in counts.items())
                lines.append(f"🔎 sources: {parts}")
            if details.get("phase"):
                lines.append(f"🪜 phase: {details['phase']}")
        else:
            # Legacy Plan 1/2 partial shape
            lines.append(details.get("reason", ""))
            lines.append("Scheduled post ids:")
            lines.extend(f"- {pid}" for pid in details.get("post_ids", []))
    else:  # info
        lines = [header, details["message"]]

    return "\n".join(lines)
