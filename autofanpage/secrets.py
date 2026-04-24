"""Secret resolution with OpenClaw env/.env compatibility."""
from __future__ import annotations

import ast
import os
import subprocess
from pathlib import Path
from typing import Callable


class SubprocessBackend:
    """Shell out to legacy `openclaw secrets get <name>`."""

    def __call__(self, name: str) -> str:
        result = subprocess.run(
            ["openclaw", "secrets", "get", name],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()


class EnvironmentBackend:
    """Resolve secrets from environment variables or OpenClaw's `.env` file."""

    def __call__(self, name: str) -> str:
        for candidate in _env_candidates(name):
            value = os.environ.get(candidate)
            if value:
                return value

        dotenv = _read_dotenv(_default_openclaw_env_path())
        for candidate in _env_candidates(name):
            value = dotenv.get(candidate)
            if value:
                return value

        raise KeyError(name)


class DefaultBackend:
    """Prefer env/.env resolution and fall back to legacy OpenClaw CLI."""

    def __init__(
        self,
        env_backend: Callable[[str], str] | None = None,
        subprocess_backend: Callable[[str], str] | None = None,
    ) -> None:
        self._env_backend = env_backend or EnvironmentBackend()
        self._subprocess_backend = subprocess_backend or SubprocessBackend()

    def __call__(self, name: str) -> str:
        try:
            return self._env_backend(name)
        except KeyError:
            pass

        try:
            return self._subprocess_backend(name)
        except FileNotFoundError as exc:
            raise RuntimeError(_missing_secret_message(name)) from exc
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            if "unknown command 'get'" in stderr:
                raise RuntimeError(_missing_secret_message(name)) from exc
            raise


def _env_candidates(name: str) -> list[str]:
    candidates = [name, name.upper(), _normalize_env_name(name)]
    seen: set[str] = set()
    return [candidate for candidate in candidates if not (candidate in seen or seen.add(candidate))]


def _normalize_env_name(name: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in name).upper()


def _default_openclaw_env_path() -> Path:
    state_dir = os.environ.get("OPENCLAW_STATE_DIR")
    if state_dir:
        return Path(state_dir) / ".env"
    return Path(os.environ.get("HOME", str(Path.home()))) / ".openclaw" / ".env"


def _read_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        values[key] = _parse_dotenv_value(value)
    return values


def _parse_dotenv_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return value[1:-1]
        if isinstance(parsed, str):
            return parsed
    return value


def _missing_secret_message(name: str) -> str:
    env_name = _normalize_env_name(name)
    return (
        f"Secret {name!r} was not found. Set {env_name} in the environment or "
        f"in {_default_openclaw_env_path()}."
    )


_backend: Callable[[str], str] = DefaultBackend()


def set_backend(backend: Callable[[str], str]) -> None:
    """Install a custom backend (used by tests)."""
    global _backend
    _backend = backend


def get_secret(ref: str) -> str:
    """Resolve a `secret:<name>` reference to the actual value."""
    if not ref.startswith("secret:"):
        raise ValueError(f"secret ref must start with 'secret:', got {ref!r}")
    name = ref[len("secret:"):]
    return _backend(name)
