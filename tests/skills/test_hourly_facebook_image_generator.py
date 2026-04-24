import json
import sys
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "hourly-facebook-image-generator"
    / "scripts"
)
sys.path.insert(0, str(SCRIPT))
import generate_images  # noqa: E402


class _FakeClient:
    def __init__(self):
        self.configure_calls = []

    def configure_captcha_providers(self, *, capsolver_api_key):
        self.configure_calls.append(capsolver_api_key)
        return {"CapSolver": True}


def _write_inputs(run_dir: Path) -> None:
    (run_dir / "latest_source_post.json").write_text(
        json.dumps(
            {
                "source_page_url": "https://www.facebook.com/0xSojalSec",
                "source_post_id": "123",
                "source_post_url": "https://facebook.com/post/123",
                "author": "0xSojalSec",
                "published_at": "2026-04-24T09:00:00Z",
                "content_text": "A useful source post about AI workflow design.",
                "media_urls": [],
                "backend": "agent_browser",
                "fetched_at": "2026-04-24T10:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "posts.json").write_text(
        json.dumps(
            {
                "language": "vi",
                "posts": [
                    {
                        "time": "08:00",
                        "type": "news",
                        "content": "Bai viet da viet lai",
                        "first_comment": None,
                    },
                    {"time": "12:00", "type": "guide", "content": None, "first_comment": None},
                    {"time": "16:00", "type": "opinion", "content": None, "first_comment": None},
                    {"time": "20:00", "type": "case_study", "content": None, "first_comment": None},
                ],
            }
        ),
        encoding="utf-8",
    )


def test_main_uses_best_available_candidate_when_some_generations_fail(
    tmp_path, fixtures_dir, mocker, capsys
):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_inputs(run_dir)

    profile_path = tmp_path / "profile.json"
    profile_data = json.loads(
        (fixtures_dir / "profile_hourly_facebook_repost.json").read_text(encoding="utf-8")
    )
    profile_data["publishing"] = {
        "backend": "mixpost_ui",
        "mixpost": {
            "base_url": "https://mixpost.example.test",
            "storage_state_path": str(tmp_path / "state.json"),
            "headless": True,
        },
        "images": {
            "enabled": True,
            "provider": "useapi_google_flow",
            "fallback_provider": "local_playwright_card",
            "useapi_base_url": "https://api.useapi.net",
            "useapi_token_ref": "secret:useapi_token",
            "google_flow_account_ref": "secret:useapi_google_flow_account",
            "capsolver_api_key_ref": "secret:capsolver_api_key",
            "candidate_count": 4,
            "overlay_mode": "none",
            "require_image_for_publish": True,
            "canvas": {"width": 1080, "height": 1350, "theme": "ai5phut"},
        },
    }
    profile_path.write_text(json.dumps(profile_data), encoding="utf-8")

    fake_client = _FakeClient()
    mocker.patch.object(
        generate_images,
        "get_secret",
        side_effect=lambda ref: {
            "secret:useapi_token": "useapi-token",
            "secret:useapi_google_flow_account": "acct@example.com",
            "secret:capsolver_api_key": "capsolver-key",
        }[ref],
    )
    mocker.patch.object(generate_images, "UseApiFlowClient", return_value=fake_client)

    candidate_results = {
        1: ({"job_id": "job-1", "raw_image_url": "https://cdn/1.png"}, run_dir / "assets" / "08-00-raw-c1.png"),
        2: RuntimeError("503 Service Unavailable"),
        3: ({"job_id": "job-3", "raw_image_url": "https://cdn/3.png"}, run_dir / "assets" / "08-00-raw-c3.png"),
        4: RuntimeError("503 Service Unavailable"),
    }

    def fake_generate_candidate(*, candidate_index, **kwargs):
        result = candidate_results[candidate_index]
        if isinstance(result, Exception):
            raise result
        payload, path = result
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"candidate-{candidate_index}".encode("utf-8"))
        return payload, path

    mocker.patch.object(
        generate_images,
        "_generate_candidate",
        side_effect=fake_generate_candidate,
    )
    mocker.patch.object(
        generate_images,
        "choose_best_candidate",
        side_effect=lambda paths: next(path for path in paths if path.name.endswith("c3.png")),
    )

    rc = generate_images.main(
        [
            "--run-dir",
            str(run_dir),
            "--profile",
            str(profile_path),
            "--date",
            "2026-04-24",
        ]
    )

    assert rc == 0
    payload = json.loads((run_dir / "post_assets.json").read_text(encoding="utf-8"))
    asset = payload["assets"][0]
    assert asset["status"] == "ok"
    assert asset["selected_candidate_index"] == 3
    assert asset["job_id"] == "job-3"
    assert asset["raw_image_path"] == "assets/08-00-raw-c3.png"
    assert asset["final_image_path"] == "assets/08-00-selected.png"
    assert len(asset["candidates"]) == 2
    assert "candidate 2" in asset["error"]
    assert "candidate 4" in asset["error"]
    assert fake_client.configure_calls == ["capsolver-key"]
    assert (run_dir / "assets" / "08-00-selected.png").exists()

    stdout = json.loads(capsys.readouterr().out.strip())
    assert stdout["status"] == "ok"
    assert stdout["assets_generated"] == 1


def test_main_returns_failure_when_all_candidates_fail(tmp_path, fixtures_dir, mocker, capsys):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_inputs(run_dir)

    profile_path = tmp_path / "profile.json"
    profile_data = json.loads(
        (fixtures_dir / "profile_hourly_facebook_repost.json").read_text(encoding="utf-8")
    )
    profile_data["publishing"] = {
        "backend": "mixpost_ui",
        "mixpost": {
            "base_url": "https://mixpost.example.test",
            "storage_state_path": str(tmp_path / "state.json"),
            "headless": True,
        },
        "images": {
            "enabled": True,
            "provider": "useapi_google_flow",
            "useapi_base_url": "https://api.useapi.net",
            "useapi_token_ref": "secret:useapi_token",
            "candidate_count": 4,
            "overlay_mode": "none",
            "require_image_for_publish": True,
            "canvas": {"width": 1080, "height": 1350, "theme": "ai5phut"},
        },
    }
    profile_path.write_text(json.dumps(profile_data), encoding="utf-8")

    fake_client = _FakeClient()
    mocker.patch.object(generate_images, "get_secret", return_value="useapi-token")
    mocker.patch.object(generate_images, "UseApiFlowClient", return_value=fake_client)
    mocker.patch.object(
        generate_images,
        "_generate_candidate",
        side_effect=RuntimeError("503 Service Unavailable"),
    )

    rc = generate_images.main(
        [
            "--run-dir",
            str(run_dir),
            "--profile",
            str(profile_path),
            "--date",
            "2026-04-24",
        ]
    )

    assert rc == 1
    payload = json.loads((run_dir / "post_assets.json").read_text(encoding="utf-8"))
    asset = payload["assets"][0]
    assert asset["status"] == "failed"
    assert len(asset["candidates"]) == 0
    assert "candidate 1" in asset["error"]
    stdout = json.loads(capsys.readouterr().out.strip())
    assert stdout["status"] == "partial"
    assert stdout["assets_generated"] == 0


def test_main_falls_back_to_local_playwright_card_when_primary_provider_fails(
    tmp_path, fixtures_dir, mocker, capsys
):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_inputs(run_dir)

    profile_path = tmp_path / "profile.json"
    profile_data = json.loads(
        (fixtures_dir / "profile_hourly_facebook_repost.json").read_text(encoding="utf-8")
    )
    profile_data["publishing"] = {
        "backend": "mixpost_ui",
        "mixpost": {
            "base_url": "https://mixpost.example.test",
            "storage_state_path": str(tmp_path / "state.json"),
            "headless": True,
        },
        "images": {
            "enabled": True,
            "provider": "useapi_google_flow",
            "fallback_provider": "local_playwright_card",
            "useapi_base_url": "https://api.useapi.net",
            "useapi_token_ref": "secret:useapi_token",
            "candidate_count": 4,
            "overlay_mode": "none",
            "require_image_for_publish": True,
            "canvas": {"width": 1080, "height": 1350, "theme": "ai5phut"},
        },
    }
    profile_path.write_text(json.dumps(profile_data), encoding="utf-8")

    fake_client = _FakeClient()
    mocker.patch.object(generate_images, "get_secret", return_value="useapi-token")
    mocker.patch.object(generate_images, "UseApiFlowClient", return_value=fake_client)
    mocker.patch.object(
        generate_images,
        "_collect_candidates",
        return_value=([], [], ["candidate 1: 503", "candidate 2: timeout"]),
    )

    rendered = {}

    def fake_render(**kwargs):
        output_path = kwargs["output_path"]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"png")
        rendered.update(kwargs)
        return output_path

    mocker.patch.object(
        generate_images,
        "render_local_editorial_card",
        side_effect=fake_render,
    )

    rc = generate_images.main(
        [
            "--run-dir",
            str(run_dir),
            "--profile",
            str(profile_path),
            "--date",
            "2026-04-24",
        ]
    )

    assert rc == 0
    payload = json.loads((run_dir / "post_assets.json").read_text(encoding="utf-8"))
    asset = payload["assets"][0]
    assert payload["provider"] == "local_playwright_card"
    assert asset["status"] == "ok"
    assert asset["provider"] == "local_playwright_card"
    assert asset["final_image_path"] == "assets/08-00-selected.png"
    assert asset["job_id"] is None
    assert asset["raw_image_url"] is None
    assert asset["candidates"] == []
    assert "candidate 1: 503" in asset["error"]
    assert rendered["title"] == "0xSojalSec"
    assert rendered["theme_text"] == "AI automation"
    stdout = json.loads(capsys.readouterr().out.strip())
    assert stdout["status"] == "ok"
    assert stdout["assets_generated"] == 1


def test_main_falls_back_to_zai_before_local_card_when_primary_provider_fails(
    tmp_path, fixtures_dir, mocker, capsys
):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_inputs(run_dir)

    profile_path = tmp_path / "profile.json"
    profile_data = json.loads(
        (fixtures_dir / "profile_hourly_facebook_repost.json").read_text(encoding="utf-8")
    )
    profile_data["publishing"] = {
        "backend": "mixpost_ui",
        "mixpost": {
            "base_url": "https://mixpost.example.test",
            "storage_state_path": str(tmp_path / "state.json"),
            "headless": True,
        },
        "images": {
            "enabled": True,
            "provider": "useapi_google_flow",
            "fallback_provider": "zai_glm_image",
            "useapi_base_url": "https://api.useapi.net",
            "useapi_token_ref": "secret:useapi_token",
            "zai_api_key_ref": "secret:zai_api_key",
            "zai_model": "glm-image",
            "zai_quality": "standard",
            "candidate_count": 4,
            "overlay_mode": "none",
            "require_image_for_publish": True,
            "canvas": {"width": 1080, "height": 1350, "theme": "ai5phut"},
        },
    }
    profile_path.write_text(json.dumps(profile_data), encoding="utf-8")

    fake_client = _FakeClient()
    fake_zai_client = mocker.Mock()
    fake_zai_client.generate_image.return_value = {
        "raw_image_url": "https://cdn.z.ai/fallback.png",
        "model": "glm-image",
    }
    mocker.patch.object(
        generate_images,
        "get_secret",
        side_effect=lambda ref: {
            "secret:useapi_token": "useapi-token",
            "secret:zai_api_key": "zai-key",
        }[ref],
    )
    mocker.patch.object(generate_images, "UseApiFlowClient", return_value=fake_client)
    mocker.patch.object(generate_images, "ZaiImageClient", return_value=fake_zai_client)
    mocker.patch.object(
        generate_images,
        "_collect_candidates",
        return_value=([], [], ["candidate 1: 503", "candidate 2: timeout"]),
    )

    def fake_download(url, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"png")
        return destination

    mocker.patch.object(generate_images, "_download_image", side_effect=fake_download)
    render_mock = mocker.patch.object(generate_images, "render_local_editorial_card")

    rc = generate_images.main(
        [
            "--run-dir",
            str(run_dir),
            "--profile",
            str(profile_path),
            "--date",
            "2026-04-24",
        ]
    )

    assert rc == 0
    payload = json.loads((run_dir / "post_assets.json").read_text(encoding="utf-8"))
    asset = payload["assets"][0]
    assert payload["provider"] == "zai_glm_image"
    assert asset["provider"] == "zai_glm_image"
    assert asset["status"] == "ok"
    assert asset["raw_image_url"] == "https://cdn.z.ai/fallback.png"
    assert asset["raw_image_path"] == "assets/08-00-raw-zai.png"
    assert asset["final_image_path"] == "assets/08-00-selected.png"
    assert asset["job_id"] is None
    assert "candidate 1: 503" in asset["error"]
    fake_zai_client.generate_image.assert_called_once()
    render_mock.assert_not_called()
    stdout = json.loads(capsys.readouterr().out.strip())
    assert stdout["status"] == "ok"
    assert stdout["assets_generated"] == 1


def test_main_falls_back_to_codex_imagen_before_zai_when_primary_provider_fails(
    tmp_path, fixtures_dir, mocker, capsys
):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_inputs(run_dir)

    profile_path = tmp_path / "profile.json"
    profile_data = json.loads(
        (fixtures_dir / "profile_hourly_facebook_repost.json").read_text(encoding="utf-8")
    )
    profile_data["publishing"] = {
        "backend": "mixpost_ui",
        "mixpost": {
            "base_url": "https://mixpost.example.test",
            "storage_state_path": str(tmp_path / "state.json"),
            "headless": True,
        },
        "images": {
            "enabled": True,
            "provider": "useapi_google_flow",
            "fallback_provider": "codex_imagen_oauth",
            "useapi_base_url": "https://api.useapi.net",
            "useapi_token_ref": "secret:useapi_token",
            "codex_imagen_script_path": "/tmp/codex-imagen/scripts/codex-imagen.mjs",
            "codex_auth_json_path": "~/.codex/auth.json",
            "codex_timeout_seconds": 300,
            "codex_model": "gpt-5.4",
            "candidate_count": 4,
            "overlay_mode": "none",
            "require_image_for_publish": True,
            "canvas": {"width": 1080, "height": 1350, "theme": "ai5phut"},
        },
    }
    profile_path.write_text(json.dumps(profile_data), encoding="utf-8")

    fake_client = _FakeClient()
    mocker.patch.object(generate_images, "get_secret", return_value="useapi-token")
    mocker.patch.object(generate_images, "UseApiFlowClient", return_value=fake_client)
    mocker.patch.object(
        generate_images,
        "_collect_candidates",
        return_value=([], [], ["candidate 1: 503", "candidate 2: timeout"]),
    )
    def fake_codex_imagen(**kwargs):
        output_path = run_dir / "assets" / "08-00-raw-codex.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"png")
        return {
            "provider": "codex_imagen_oauth",
            "image_path": output_path,
        }

    mocker.patch.object(
        generate_images,
        "generate_with_codex_imagen",
        side_effect=fake_codex_imagen,
    )
    render_mock = mocker.patch.object(generate_images, "render_local_editorial_card")

    rc = generate_images.main(
        [
            "--run-dir",
            str(run_dir),
            "--profile",
            str(profile_path),
            "--date",
            "2026-04-24",
        ]
    )

    assert rc == 0
    payload = json.loads((run_dir / "post_assets.json").read_text(encoding="utf-8"))
    asset = payload["assets"][0]
    assert payload["provider"] == "codex_imagen_oauth"
    assert asset["provider"] == "codex_imagen_oauth"
    assert asset["status"] == "ok"
    assert asset["raw_image_url"] is None
    assert asset["raw_image_path"] == "assets/08-00-raw-codex.png"
    assert asset["final_image_path"] == "assets/08-00-selected.png"
    render_mock.assert_not_called()
    stdout = json.loads(capsys.readouterr().out.strip())
    assert stdout["status"] == "ok"


def test_main_falls_back_to_zai_when_codex_imagen_fails(
    tmp_path, fixtures_dir, mocker, capsys
):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_inputs(run_dir)

    profile_path = tmp_path / "profile.json"
    profile_data = json.loads(
        (fixtures_dir / "profile_hourly_facebook_repost.json").read_text(encoding="utf-8")
    )
    profile_data["publishing"] = {
        "backend": "mixpost_ui",
        "mixpost": {
            "base_url": "https://mixpost.example.test",
            "storage_state_path": str(tmp_path / "state.json"),
            "headless": True,
        },
        "images": {
            "enabled": True,
            "provider": "useapi_google_flow",
            "fallback_provider": "codex_imagen_oauth",
            "useapi_base_url": "https://api.useapi.net",
            "useapi_token_ref": "secret:useapi_token",
            "codex_imagen_script_path": "/tmp/codex-imagen/scripts/codex-imagen.mjs",
            "codex_auth_json_path": "~/.codex/auth.json",
            "codex_timeout_seconds": 300,
            "codex_model": "gpt-5.4",
            "zai_api_key_ref": "secret:zai_api_key",
            "zai_model": "glm-image",
            "zai_quality": "standard",
            "candidate_count": 4,
            "overlay_mode": "none",
            "require_image_for_publish": True,
            "canvas": {"width": 1080, "height": 1350, "theme": "ai5phut"},
        },
    }
    profile_path.write_text(json.dumps(profile_data), encoding="utf-8")

    fake_client = _FakeClient()
    fake_zai_client = mocker.Mock()
    fake_zai_client.generate_image.return_value = {
        "raw_image_url": "https://cdn.z.ai/fallback.png",
        "model": "glm-image",
    }
    mocker.patch.object(
        generate_images,
        "get_secret",
        side_effect=lambda ref: {
            "secret:useapi_token": "useapi-token",
            "secret:zai_api_key": "zai-key",
        }[ref],
    )
    mocker.patch.object(generate_images, "UseApiFlowClient", return_value=fake_client)
    mocker.patch.object(generate_images, "ZaiImageClient", return_value=fake_zai_client)
    mocker.patch.object(
        generate_images,
        "_collect_candidates",
        return_value=([], [], ["candidate 1: 503", "candidate 2: timeout"]),
    )
    mocker.patch.object(
        generate_images,
        "generate_with_codex_imagen",
        side_effect=RuntimeError("codex oauth failed"),
    )

    def fake_download(url, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"png")
        return destination

    mocker.patch.object(generate_images, "_download_image", side_effect=fake_download)
    render_mock = mocker.patch.object(generate_images, "render_local_editorial_card")

    rc = generate_images.main(
        [
            "--run-dir",
            str(run_dir),
            "--profile",
            str(profile_path),
            "--date",
            "2026-04-24",
        ]
    )

    assert rc == 0
    payload = json.loads((run_dir / "post_assets.json").read_text(encoding="utf-8"))
    asset = payload["assets"][0]
    assert payload["provider"] == "zai_glm_image"
    assert asset["provider"] == "zai_glm_image"
    assert "codex oauth failed" in asset["error"]
    fake_zai_client.generate_image.assert_called_once()
    render_mock.assert_not_called()
    stdout = json.loads(capsys.readouterr().out.strip())
    assert stdout["status"] == "ok"


def test_main_falls_back_to_local_card_when_zai_fallback_also_fails(
    tmp_path, fixtures_dir, mocker, capsys
):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_inputs(run_dir)

    profile_path = tmp_path / "profile.json"
    profile_data = json.loads(
        (fixtures_dir / "profile_hourly_facebook_repost.json").read_text(encoding="utf-8")
    )
    profile_data["publishing"] = {
        "backend": "mixpost_ui",
        "mixpost": {
            "base_url": "https://mixpost.example.test",
            "storage_state_path": str(tmp_path / "state.json"),
            "headless": True,
        },
        "images": {
            "enabled": True,
            "provider": "useapi_google_flow",
            "fallback_provider": "zai_glm_image",
            "useapi_base_url": "https://api.useapi.net",
            "useapi_token_ref": "secret:useapi_token",
            "zai_api_key_ref": "secret:zai_api_key",
            "zai_model": "glm-image",
            "zai_quality": "standard",
            "candidate_count": 4,
            "overlay_mode": "none",
            "require_image_for_publish": True,
            "canvas": {"width": 1080, "height": 1350, "theme": "ai5phut"},
        },
    }
    profile_path.write_text(json.dumps(profile_data), encoding="utf-8")

    fake_client = _FakeClient()
    fake_zai_client = mocker.Mock()
    fake_zai_client.generate_image.side_effect = RuntimeError("zai timeout")
    mocker.patch.object(
        generate_images,
        "get_secret",
        side_effect=lambda ref: {
            "secret:useapi_token": "useapi-token",
            "secret:zai_api_key": "zai-key",
        }[ref],
    )
    mocker.patch.object(generate_images, "UseApiFlowClient", return_value=fake_client)
    mocker.patch.object(generate_images, "ZaiImageClient", return_value=fake_zai_client)
    mocker.patch.object(
        generate_images,
        "_collect_candidates",
        return_value=([], [], ["candidate 1: 503", "candidate 2: timeout"]),
    )

    def fake_render(**kwargs):
        output_path = kwargs["output_path"]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"png")
        return output_path

    render_mock = mocker.patch.object(
        generate_images,
        "render_local_editorial_card",
        side_effect=fake_render,
    )

    rc = generate_images.main(
        [
            "--run-dir",
            str(run_dir),
            "--profile",
            str(profile_path),
            "--date",
            "2026-04-24",
        ]
    )

    assert rc == 0
    payload = json.loads((run_dir / "post_assets.json").read_text(encoding="utf-8"))
    asset = payload["assets"][0]
    assert payload["provider"] == "local_playwright_card"
    assert asset["provider"] == "local_playwright_card"
    assert "zai timeout" in asset["error"]
    fake_zai_client.generate_image.assert_called_once()
    render_mock.assert_called_once()
    stdout = json.loads(capsys.readouterr().out.strip())
    assert stdout["status"] == "ok"
