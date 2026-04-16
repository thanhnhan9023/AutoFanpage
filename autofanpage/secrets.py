"""Secret resolution. Default backend shells out to `openclaw secrets get`."""
from __future__ import annotations

import subprocess
from typing import Callable


class SubprocessBackend:
    """Shell out to `openclaw secrets get <name>`."""

    def __call__(self, name: str) -> str:
        result = subprocess.run(
            ["openclaw", "secrets", "get", name],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()


_backend: Callable[[str], str] = SubprocessBackend()


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
