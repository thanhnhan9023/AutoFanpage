import pytest
from autofanpage.secrets import (
    DefaultBackend,
    SubprocessBackend,
    get_secret,
    set_backend,
)


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


def test_default_backend_reads_environment_variable(mocker):
    mocker.patch.dict("autofanpage.secrets.os.environ", {"WRITER_GATEWAY_KEY": "env-value"})
    mock_run = mocker.patch("autofanpage.secrets.subprocess.run")

    backend = DefaultBackend()

    assert backend("writer_gateway_key") == "env-value"
    mock_run.assert_not_called()


def test_default_backend_reads_openclaw_dotenv(tmp_path, mocker):
    state_dir = tmp_path / ".openclaw"
    state_dir.mkdir()
    (state_dir / ".env").write_text("WRITER_GATEWAY_KEY=file-value\n", encoding="utf-8")
    mocker.patch.dict("autofanpage.secrets.os.environ", {"HOME": str(tmp_path)}, clear=True)
    mock_run = mocker.patch("autofanpage.secrets.subprocess.run")

    backend = DefaultBackend()

    assert backend("writer_gateway_key") == "file-value"
    mock_run.assert_not_called()


def test_default_backend_falls_back_to_legacy_openclaw_cli(tmp_path, mocker):
    mocker.patch.dict("autofanpage.secrets.os.environ", {"HOME": str(tmp_path)}, clear=True)
    mock_run = mocker.patch("autofanpage.secrets.subprocess.run")
    mock_run.return_value.stdout = "legacy-value\n"
    mock_run.return_value.returncode = 0

    backend = DefaultBackend()

    assert backend("writer_gateway_key") == "legacy-value"
