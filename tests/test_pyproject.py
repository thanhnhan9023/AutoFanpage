from __future__ import annotations

from pathlib import Path
import tomllib


def test_runtime_dependencies_include_playwright_for_mixpost_image_publish():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    dependencies = payload["project"]["dependencies"]

    assert any(dependency.startswith("playwright") for dependency in dependencies)
