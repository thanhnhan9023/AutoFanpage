import sys
from pathlib import Path

import pytest
from autofanpage.dispatch import run_skill, set_backend, SubprocessBackend
from autofanpage.errors import SkillInvocationError


def test_run_skill_uses_custom_backend():
    captured = {}

    def backend(name, args):
        captured["name"] = name
        captured["args"] = args
        return {"ok": True}

    set_backend(backend)
    try:
        result = run_skill("youtube-researcher", {"run_dir": "/tmp/x"})
    finally:
        set_backend(SubprocessBackend())

    assert result == {"ok": True}
    assert captured["name"] == "youtube-researcher"
    assert captured["args"] == {"run_dir": "/tmp/x"}


def test_subprocess_backend_parses_json_stdout(mocker):
    mock_run = mocker.patch("autofanpage.dispatch.subprocess.run")
    mock_run.return_value.stdout = '{"result": 42}'
    mock_run.return_value.returncode = 0
    mocker.patch.object(
        SubprocessBackend,
        "_resolve_skill_script",
        return_value=Path("/tmp/my-skill.py"),
    )

    backend = SubprocessBackend()
    result = backend("my-skill", {"k": "v"})

    assert result == {"result": 42}
    args = mock_run.call_args[0][0]
    assert args == [sys.executable, "/tmp/my-skill.py", "--k", "v"]


def test_subprocess_backend_serializes_structured_args(mocker):
    mock_run = mocker.patch("autofanpage.dispatch.subprocess.run")
    mock_run.return_value.stdout = '{"ok": true}'
    mock_run.return_value.returncode = 0
    mocker.patch.object(
        SubprocessBackend,
        "_resolve_skill_script",
        return_value=Path("/tmp/report.py"),
    )

    backend = SubprocessBackend()
    backend("telegram-reporter", {"details": {"x": 1}, "dry_run": False, "enabled": True})

    args = mock_run.call_args[0][0]
    assert args == [
        sys.executable,
        "/tmp/report.py",
        "--details",
        '{"x": 1}',
        "--enabled",
    ]


def test_subprocess_backend_raises_on_failure(mocker):
    import subprocess as sp
    mock_run = mocker.patch("autofanpage.dispatch.subprocess.run")
    mock_run.side_effect = sp.CalledProcessError(1, "openclaw", stderr="boom")
    mocker.patch.object(
        SubprocessBackend,
        "_resolve_skill_script",
        return_value=Path("/tmp/my-skill.py"),
    )

    with pytest.raises(SkillInvocationError, match="boom"):
        SubprocessBackend()("my-skill", {})


def test_subprocess_backend_raises_on_bad_json(mocker):
    mock_run = mocker.patch("autofanpage.dispatch.subprocess.run")
    mock_run.return_value.stdout = "not json"
    mock_run.return_value.returncode = 0
    mocker.patch.object(
        SubprocessBackend,
        "_resolve_skill_script",
        return_value=Path("/tmp/my-skill.py"),
    )

    with pytest.raises(SkillInvocationError, match="JSON"):
        SubprocessBackend()("my-skill", {})


def test_subprocess_backend_parses_last_json_line(mocker):
    mock_run = mocker.patch("autofanpage.dispatch.subprocess.run")
    mock_run.return_value.stdout = "human message\n{\"sent\": true}\n"
    mock_run.return_value.returncode = 0
    mocker.patch.object(
        SubprocessBackend,
        "_resolve_skill_script",
        return_value=Path("/tmp/report.py"),
    )

    result = SubprocessBackend()("telegram-reporter", {})

    assert result == {"sent": True}
