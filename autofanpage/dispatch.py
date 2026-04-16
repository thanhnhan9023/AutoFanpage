"""Sub-skill dispatcher. Default backend shells out to `openclaw skills run`."""
from __future__ import annotations

import json
import subprocess
from typing import Any, Callable

from autofanpage.errors import SkillInvocationError


class SubprocessBackend:
    """Shell out to `openclaw skills run <name> --args <json>`."""

    def __call__(self, name: str, args: dict[str, Any]) -> Any:
        args_json = json.dumps(args)
        try:
            result = subprocess.run(
                ["openclaw", "skills", "run", name, "--args", args_json],
                capture_output=True, text=True, check=True,
            )
        except subprocess.CalledProcessError as e:
            raise SkillInvocationError(
                f"skill {name!r} failed: {e.stderr or e.stdout}"
            ) from e
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise SkillInvocationError(
                f"skill {name!r} did not return JSON: {result.stdout!r}"
            ) from e


_backend: Callable[[str, dict[str, Any]], Any] = SubprocessBackend()


def set_backend(backend: Callable[[str, dict[str, Any]], Any]) -> None:
    global _backend
    _backend = backend


def run_skill(name: str, args: dict[str, Any]) -> Any:
    """Run another OpenClaw skill and return its JSON result."""
    return _backend(name, args)
