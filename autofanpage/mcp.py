"""Wrapper around OpenClaw's `mcp call` CLI.

Each `call_tool` invocation expects the MCP CLI to emit a single JSON object
of the form {"ok": bool, "result": {...}, "error": "..."} on stdout. A
non-zero exit, non-JSON stdout, or ``ok == False`` is treated as an MCP
failure (MCPError).
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any

from autofanpage.errors import AutofanpageError


class MCPError(AutofanpageError):
    """Raised when an MCP tool call fails."""


@dataclass
class MCPClient:
    """Invoke MCP tools via ``openclaw mcp call <server> <tool> --args-json ...``."""
    cli: str = "openclaw"

    def call_tool(
        self,
        *,
        server: str,
        tool: str,
        args: dict[str, Any],
        timeout: int = 120,
    ) -> dict[str, Any]:
        cmd = [
            self.cli, "mcp", "call", server, tool,
            "--args-json", json.dumps(args, ensure_ascii=False),
        ]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        if proc.returncode != 0:
            raise MCPError(
                f"MCP call {server}/{tool} exit={proc.returncode}: "
                f"{proc.stderr.strip()}"
            )
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise MCPError(
                f"MCP call {server}/{tool} returned non-JSON stdout: {e}"
            ) from e
        if not payload.get("ok", False):
            raise MCPError(
                f"MCP call {server}/{tool} ok=false: "
                f"{payload.get('error', 'unknown error')}"
            )
        return payload.get("result", {})
