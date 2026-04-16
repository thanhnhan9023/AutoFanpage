import json
from unittest.mock import MagicMock

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

    backend = SubprocessBackend()
    result = backend("my-skill", {"k": "v"})

    assert result == {"result": 42}
    args = mock_run.call_args[0][0]
    assert args == ["openclaw", "skills", "run", "my-skill",
                    "--args", '{"k": "v"}']


def test_subprocess_backend_raises_on_failure(mocker):
    import subprocess as sp
    mock_run = mocker.patch("autofanpage.dispatch.subprocess.run")
    mock_run.side_effect = sp.CalledProcessError(1, "openclaw", stderr="boom")

    with pytest.raises(SkillInvocationError, match="boom"):
        SubprocessBackend()("my-skill", {})


def test_subprocess_backend_raises_on_bad_json(mocker):
    mock_run = mocker.patch("autofanpage.dispatch.subprocess.run")
    mock_run.return_value.stdout = "not json"
    mock_run.return_value.returncode = 0

    with pytest.raises(SkillInvocationError, match="JSON"):
        SubprocessBackend()("my-skill", {})
