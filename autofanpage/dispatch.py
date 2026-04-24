"""Sub-skill dispatcher. Default backend shells out to local skill scripts."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from autofanpage.errors import SkillInvocationError


class SubprocessBackend:
    """Shell out to the local Python entrypoint for a skill."""

    @staticmethod
    def _repo_root() -> Path:
        return Path(__file__).resolve().parents[1]

    @classmethod
    def _resolve_skill_script(cls, name: str) -> Path:
        scripts_dir = cls._repo_root() / "skills" / name / "scripts"
        candidates = sorted(
            path for path in scripts_dir.glob("*.py") if path.name != "__init__.py"
        )
        if not candidates:
            raise SkillInvocationError(f"skill {name!r} has no runnable script")
        if len(candidates) > 1:
            raise SkillInvocationError(
                f"skill {name!r} has multiple runnable scripts: "
                + ", ".join(path.name for path in candidates)
            )
        return candidates[0]

    @staticmethod
    def _build_argv(script: Path, args: dict[str, Any]) -> list[str]:
        argv = [sys.executable, str(script)]
        for key, value in args.items():
            flag = f"--{key.replace('_', '-')}"
            if isinstance(value, bool):
                if value:
                    argv.append(flag)
                continue
            if value is None:
                continue
            if isinstance(value, (dict, list)):
                argv.extend([flag, json.dumps(value, ensure_ascii=False)])
                continue
            argv.extend([flag, str(value)])
        return argv

    @staticmethod
    def _parse_stdout(name: str, stdout: str) -> Any:
        lines = [line for line in stdout.splitlines() if line.strip()]
        for candidate in reversed(lines):
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
        raise SkillInvocationError(
            f"skill {name!r} did not return JSON: {stdout!r}"
        )

    def __call__(self, name: str, args: dict[str, Any]) -> Any:
        script = self._resolve_skill_script(name)
        argv = self._build_argv(script, args)
        try:
            result = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                check=True,
                cwd=self._repo_root(),
            )
        except subprocess.CalledProcessError as e:
            raise SkillInvocationError(
                f"skill {name!r} failed: {e.stderr or e.stdout}"
            ) from e
        return self._parse_stdout(name, result.stdout)


_backend: Callable[[str, dict[str, Any]], Any] = SubprocessBackend()


def set_backend(backend: Callable[[str, dict[str, Any]], Any]) -> None:
    global _backend
    _backend = backend


def run_skill(name: str, args: dict[str, Any]) -> Any:
    """Run another OpenClaw skill and return its JSON result."""
    return _backend(name, args)
