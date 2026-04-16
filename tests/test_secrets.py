from unittest.mock import patch

import pytest
from autofanpage.secrets import get_secret, set_backend, SubprocessBackend


def test_get_secret_strips_prefix():
    fake = {"my_key": "s3cret"}

    def backend(name: str) -> str:
        return fake[name]

    set_backend(backend)
    try:
        assert get_secret("secret:my_key") == "s3cret"
    finally:
        set_backend(SubprocessBackend())


def test_get_secret_rejects_non_ref():
    with pytest.raises(ValueError, match="must start with 'secret:'"):
        get_secret("my_key")


def test_subprocess_backend_calls_openclaw(mocker):
    mock_run = mocker.patch("autofanpage.secrets.subprocess.run")
    mock_run.return_value.stdout = "the-value\n"
    mock_run.return_value.returncode = 0

    backend = SubprocessBackend()
    result = backend("abc")

    assert result == "the-value"
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args[0] == "openclaw"
    assert "secrets" in args
    assert "get" in args
    assert "abc" in args
