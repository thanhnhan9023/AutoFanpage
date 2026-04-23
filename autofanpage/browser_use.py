from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Any

from autofanpage.errors import SourceFailedError


_DEFAULT_CONFIG = "/home/thanhnhan9023/config/mcporter.json"
_MCPORTER_TIMEOUT_SECONDS = 30


def _run_mcporter(*, config: str, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    cmd = [
        "mcporter",
        "--config",
        config,
        "call",
        tool_name,
        json.dumps(payload, ensure_ascii=False),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_MCPORTER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise SourceFailedError(
            f"{tool_name} timed out after {_MCPORTER_TIMEOUT_SECONDS} seconds"
        ) from exc
    except OSError as exc:
        raise SourceFailedError(f"{tool_name} failed to launch: {exc}") from exc
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise SourceFailedError(f"{tool_name} exited with code {proc.returncode}: {detail}")
    try:
        body = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SourceFailedError(f"{tool_name} returned invalid JSON: {exc}") from exc
    if not isinstance(body, dict):
        raise SourceFailedError(f"{tool_name} returned non-object JSON")
    return body


def run_browser_use_task(
    *,
    task: str,
    output_schema: dict[str, Any],
    profile_id: str | None = None,
) -> dict[str, Any]:
    config = os.environ.get("BROWSER_USE_MCPORTER_CONFIG", _DEFAULT_CONFIG)
    launch_payload: dict[str, Any] = {
        "task": task,
        "output_schema": output_schema,
    }
    if profile_id:
        launch_payload["profile_id"] = profile_id

    launched = _run_mcporter(
        config=config,
        tool_name="browser-use.run_session",
        payload=launch_payload,
    )
    session_id = launched.get("session_id")
    if not session_id:
        raise SourceFailedError("browser_use_mcp launch response missing session_id")

    for _ in range(30):
        polled = _run_mcporter(
            config=config,
            tool_name="browser-use.get_session",
            payload={"session_id": session_id},
        )
        status = str(polled.get("status") or "").strip()
        if status in {"idle", "stopped"}:
            output = polled.get("output")
            if not isinstance(output, dict):
                raise SourceFailedError("browser_use_mcp session output missing or invalid")
            return output
        if status in {"timed_out", "error"}:
            message = polled.get("error") or polled.get("message") or f"browser_use_mcp session {status}"
            raise SourceFailedError(str(message))
        time.sleep(2)

    raise SourceFailedError("browser_use_mcp session did not finish within 60 seconds")
