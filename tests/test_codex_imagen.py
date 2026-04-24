import json
import subprocess
from pathlib import Path

import pytest

from autofanpage.codex_imagen import generate_with_codex_imagen
from autofanpage.errors import AutofanpageError


def test_generate_with_codex_imagen_returns_saved_path(tmp_path, mocker):
    output_path = tmp_path / "out.png"

    mocker.patch(
        "autofanpage.codex_imagen.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "images": [
                        {
                            "path": str(output_path),
                        }
                    ]
                }
            ),
            stderr="",
        ),
    )

    result = generate_with_codex_imagen(
        script_path="/tmp/codex-imagen/scripts/codex-imagen.mjs",
        prompt="generate one image",
        output_path=output_path,
        auth_json_path="~/.codex/auth.json",
        timeout_seconds=300,
        model="gpt-5.4",
    )

    assert result["provider"] == "codex_imagen_oauth"
    assert result["image_path"] == output_path


def test_generate_with_codex_imagen_raises_on_nonzero_exit(tmp_path, mocker):
    mocker.patch(
        "autofanpage.codex_imagen.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="boom",
        ),
    )

    with pytest.raises(AutofanpageError, match="codex-imagen failed"):
        generate_with_codex_imagen(
            script_path="/tmp/codex-imagen/scripts/codex-imagen.mjs",
            prompt="generate one image",
            output_path=tmp_path / "out.png",
            auth_json_path="~/.codex/auth.json",
            timeout_seconds=300,
            model="gpt-5.4",
        )


def test_generate_with_codex_imagen_raises_on_malformed_json(tmp_path, mocker):
    mocker.patch(
        "autofanpage.codex_imagen.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="{bad json",
            stderr="",
        ),
    )

    with pytest.raises(AutofanpageError, match="invalid JSON"):
        generate_with_codex_imagen(
            script_path="/tmp/codex-imagen/scripts/codex-imagen.mjs",
            prompt="generate one image",
            output_path=tmp_path / "out.png",
            auth_json_path="~/.codex/auth.json",
            timeout_seconds=300,
            model="gpt-5.4",
        )


def test_generate_with_codex_imagen_raises_on_empty_images(tmp_path, mocker):
    mocker.patch(
        "autofanpage.codex_imagen.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"images": []}),
            stderr="",
        ),
    )

    with pytest.raises(AutofanpageError, match="returned no images"):
        generate_with_codex_imagen(
            script_path="/tmp/codex-imagen/scripts/codex-imagen.mjs",
            prompt="generate one image",
            output_path=tmp_path / "out.png",
            auth_json_path="~/.codex/auth.json",
            timeout_seconds=300,
            model="gpt-5.4",
        )
