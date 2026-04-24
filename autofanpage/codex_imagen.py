"""Thin subprocess wrapper for the external codex-imagen helper."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from autofanpage.errors import AutofanpageError


def generate_with_codex_imagen(
    *,
    script_path: str,
    prompt: str,
    output_path: Path,
    auth_json_path: str,
    timeout_seconds: int,
    model: str,
) -> dict[str, Path | str]:
    resolved_script = Path(os.path.expanduser(script_path))
    if not resolved_script.exists():
        raise AutofanpageError(f"codex-imagen script not found: {resolved_script}")

    resolved_auth = Path(os.path.expanduser(auth_json_path))
    if not resolved_auth.exists():
        raise AutofanpageError(f"codex-imagen auth file not found: {resolved_auth}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "node",
        str(resolved_script),
        "--json",
        "--auth",
        str(resolved_auth),
        "--model",
        model,
        "--timeout",
        str(timeout_seconds),
        "--output",
        str(output_path),
        "--prompt",
        prompt,
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        raise AutofanpageError(f"codex-imagen failed: {stderr or f'exit {completed.returncode}'}")

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AutofanpageError("codex-imagen returned invalid JSON") from exc

    images = payload.get("images")
    if not isinstance(images, list) or not images:
        raise AutofanpageError("codex-imagen returned no images")

    first = images[0]
    if not isinstance(first, dict):
        raise AutofanpageError("codex-imagen returned invalid image payload")

    path_value = first.get("path") or first.get("decodedPath")
    if not isinstance(path_value, str) or not path_value:
        raise AutofanpageError("codex-imagen returned no image path")

    image_path = Path(path_value)
    return {
        "provider": "codex_imagen_oauth",
        "image_path": image_path,
    }
