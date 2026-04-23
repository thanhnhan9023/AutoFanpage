from __future__ import annotations

import json
import subprocess

from autofanpage.errors import SourceFailedError


def run_agent_browser_extract(
    *,
    page_url: str,
    profile: str | None = None,
    session_name: str | None = None,
    state_path: str | None = None,
) -> dict:
    cmd = ["agent-browser"]
    if profile:
        cmd.extend(["--profile", profile])
    if session_name:
        cmd.extend(["--session-name", session_name])
    if state_path:
        cmd.extend(["--state", state_path])
    cmd.extend(["open", page_url, "--json"])

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except OSError as exc:
        raise SourceFailedError(f"agent_browser failed to launch: {exc}") from exc
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise SourceFailedError(f"agent_browser exited with code {proc.returncode}: {detail}")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SourceFailedError(f"agent_browser returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SourceFailedError("agent_browser returned non-object JSON")
    return payload
