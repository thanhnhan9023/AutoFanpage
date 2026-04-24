#!/usr/bin/env python3
"""Generate 4 image candidates for the hourly repost and choose one."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from autofanpage.image_candidate_selector import choose_best_candidate
from autofanpage.codex_imagen import generate_with_codex_imagen
from autofanpage.local_image_card import render_local_editorial_card
from autofanpage.profile import load_profile
from autofanpage.schemas import validate
from autofanpage.secrets import get_secret
from autofanpage.useapi_flow import UseApiFlowClient
from autofanpage.zai_image import ZaiImageClient

_RETRYABLE_ERROR_MARKERS = ("429", "503", "Too Many Requests", "Service Unavailable")


def _provider_aspect_ratio(width: int, height: int) -> str:
    supported = {
        "16:9": 16 / 9,
        "4:3": 4 / 3,
        "1:1": 1.0,
        "3:4": 3 / 4,
        "9:16": 9 / 16,
    }
    target_ratio = width / height
    return min(supported, key=lambda key: abs(supported[key] - target_ratio))


def _download_image(url: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    destination.write_bytes(response.content)
    return destination


def _truncate_text(text: str, max_chars: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    clipped = normalized[: max_chars - 3].rstrip()
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return f"{clipped}..."


def _image_prompt(*, source_post: dict[str, Any], post: dict[str, Any]) -> str:
    author = _truncate_text(str(source_post.get("author") or "").strip(), 60)
    rewritten = _truncate_text(str(post.get("content") or "").strip(), 320)
    source = _truncate_text(str(source_post.get("content_text") or "").strip(), 220)
    return "\n".join(
        part
        for part in [
            "Clean editorial social image for a Facebook post.",
            f"Author/context: {author}" if author else "",
            f"Post theme: {rewritten}" if rewritten else "",
            f"Optional source context: {source}" if source else "",
            (
                "Style: premium editorial illustration, thoughtful, modern, cinematic lighting, "
                "high detail, single coherent scene."
            ),
            "No readable text, no letters, no watermark, no collage, no UI screenshot.",
        ]
        if part
    )


def _candidate_raw_path(*, run_dir: Path, slot_slug: str, candidate_index: int) -> Path:
    return run_dir / "assets" / f"{slot_slug}-raw-c{candidate_index}.png"


def _manifest_payload(
    *,
    provider: str,
    page: str,
    date: str,
    assets: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "page": page,
        "provider": provider,
        "date": date,
        "assets": assets,
    }


def _relative(path: Path, run_dir: Path) -> str:
    return str(path.relative_to(run_dir))


def _is_retryable_error(error: Exception) -> bool:
    text = str(error)
    return any(marker in text for marker in _RETRYABLE_ERROR_MARKERS)


def _generate_candidate(
    *,
    client: UseApiFlowClient,
    prompt: str,
    aspect_ratio: str,
    run_dir: Path,
    slot_slug: str,
    candidate_index: int,
) -> tuple[dict[str, Any], Path]:
    result = client.submit_image_job(prompt=prompt, aspect_ratio=aspect_ratio)
    raw_path = _download_image(
        result["raw_image_url"],
        _candidate_raw_path(
            run_dir=run_dir,
            slot_slug=slot_slug,
            candidate_index=candidate_index,
        ),
    )
    return result, raw_path


def _optional_secret(ref: str | None) -> str | None:
    if not ref:
        return None
    try:
        return get_secret(ref)
    except Exception:  # noqa: BLE001
        return None


def _top_level_provider(assets: list[dict[str, Any]]) -> str:
    providers = {asset["provider"] for asset in assets}
    if len(providers) == 1:
        return next(iter(providers))
    return "mixed"


def _render_fallback_image(
    *,
    run_dir: Path,
    slot_slug: str,
    source_post: dict[str, Any],
    profile: Any,
    post: dict[str, Any],
) -> Path:
    final_path = run_dir / "assets" / f"{slot_slug}-selected.png"
    title = str(source_post.get("author") or profile.name or "AutoFanpage").strip()
    summary = str(post.get("content") or "").strip()
    theme_text = str(profile.topic or "AI automation").strip()
    accent_text = summary.split("\n", 1)[0].strip() or theme_text
    return render_local_editorial_card(
        output_path=final_path,
        title=title,
        summary=summary,
        theme_text=theme_text,
        accent_text=accent_text,
        width=profile.publishing.images.canvas.width,
        height=profile.publishing.images.canvas.height,
    )


def _round_to_multiple(value: int, *, step: int) -> int:
    return max(step, int(round(value / step)) * step)


def _zai_size(width: int, height: int) -> str:
    normalized_width = min(2048, max(1024, _round_to_multiple(width, step=32)))
    normalized_height = min(2048, max(1024, _round_to_multiple(height, step=32)))
    max_pixels = 1 << 22
    while normalized_width * normalized_height > max_pixels:
        normalized_width = max(1024, normalized_width - 32)
        normalized_height = max(1024, normalized_height - 32)
        if normalized_width == 1024 and normalized_height == 1024:
            break
    return f"{normalized_width}x{normalized_height}"


def _render_zai_fallback_image(
    *,
    run_dir: Path,
    slot_slug: str,
    prompt: str,
    profile: Any,
) -> tuple[Path, Path, str]:
    images_cfg = profile.publishing.images
    client = ZaiImageClient(
        base_url=images_cfg.zai_base_url,
        api_key=get_secret(images_cfg.zai_api_key_ref),
        model=images_cfg.zai_model,
        quality=images_cfg.zai_quality,
    )
    result = client.generate_image(
        prompt=prompt,
        size=_zai_size(images_cfg.canvas.width, images_cfg.canvas.height),
    )
    raw_path = _download_image(
        result["raw_image_url"],
        run_dir / "assets" / f"{slot_slug}-raw-zai.png",
    )
    final_path = run_dir / "assets" / f"{slot_slug}-selected.png"
    shutil.copyfile(raw_path, final_path)
    return raw_path, final_path, result["raw_image_url"]


def _render_codex_imagen_fallback_image(
    *,
    run_dir: Path,
    slot_slug: str,
    prompt: str,
    profile: Any,
) -> tuple[Path, Path]:
    images_cfg = profile.publishing.images
    raw_path = run_dir / "assets" / f"{slot_slug}-raw-codex.png"
    result = generate_with_codex_imagen(
        script_path=images_cfg.codex_imagen_script_path,
        prompt=prompt,
        output_path=raw_path,
        auth_json_path=images_cfg.codex_auth_json_path,
        timeout_seconds=images_cfg.codex_timeout_seconds,
        model=images_cfg.codex_model,
    )
    saved_path = Path(result["image_path"])
    final_path = run_dir / "assets" / f"{slot_slug}-selected.png"
    if saved_path != raw_path:
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(saved_path, raw_path)
    shutil.copyfile(raw_path, final_path)
    return raw_path, final_path


def _collect_candidates(
    *,
    client: UseApiFlowClient,
    prompt: str,
    aspect_ratio: str,
    run_dir: Path,
    slot_slug: str,
    candidate_count: int,
) -> tuple[list[dict[str, Any]], list[Path], list[str]]:
    candidates: list[dict[str, Any]] = []
    candidate_paths: list[Path] = []
    candidate_failures: list[str] = []

    max_workers = min(candidate_count, 2)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _generate_candidate,
                client=client,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                run_dir=run_dir,
                slot_slug=slot_slug,
                candidate_index=candidate_index,
            ): candidate_index
            for candidate_index in range(1, candidate_count + 1)
        }
        for future in as_completed(futures):
            candidate_index = futures[future]
            try:
                result, raw_path = future.result()
                candidates.append(
                    {
                        "index": candidate_index,
                        "job_id": result["job_id"],
                        "raw_image_url": result["raw_image_url"],
                        "raw_image_path": _relative(raw_path, run_dir),
                    }
                )
                candidate_paths.append(raw_path)
            except Exception as exc:  # noqa: BLE001
                candidate_failures.append(f"candidate {candidate_index}: {exc}")

    candidates.sort(key=lambda candidate: candidate["index"])
    candidate_failures.sort()
    return candidates, candidate_paths, candidate_failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--date", required=True)
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir)
    profile = load_profile(args.profile)
    posts_payload = json.loads((run_dir / "posts.json").read_text(encoding="utf-8"))
    validate("posts", posts_payload)
    source_post = json.loads((run_dir / "latest_source_post.json").read_text(encoding="utf-8"))
    validate("latest_source_post", source_post)

    images_cfg = profile.publishing.images
    if not images_cfg.enabled:
        payload = _manifest_payload(
            provider=images_cfg.provider,
            page=profile.name,
            date=args.date,
            assets=[],
        )
        validate("post_assets", payload)
        (run_dir / "post_assets.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps({"status": "ok", "artifact": "post_assets.json", "assets_generated": 0}))
        return 0

    filled_posts = [post for post in posts_payload["posts"] if post["content"] is not None]
    token = get_secret(images_cfg.useapi_token_ref)
    account_id = _optional_secret(images_cfg.google_flow_account_ref)
    capsolver_api_key = _optional_secret(images_cfg.capsolver_api_key_ref)
    client = UseApiFlowClient(
        base_url=images_cfg.useapi_base_url,
        api_token=token,
        account_id=account_id,
    )
    if capsolver_api_key:
        client.configure_captcha_providers(capsolver_api_key=capsolver_api_key)
    aspect_ratio = _provider_aspect_ratio(
        images_cfg.canvas.width,
        images_cfg.canvas.height,
    )

    assets: list[dict[str, Any]] = []
    had_failure = False
    generated = 0
    for post in filled_posts:
        slot_slug = post["time"].replace(":", "-")
        prompt = _image_prompt(source_post=source_post, post=post)
        candidates: list[dict[str, Any]] = []
        candidate_paths: list[Path] = []
        selected_candidate_index: int | None = None
        selected_path: Path | None = None
        selected_job_id: str | None = None
        selected_raw_url: str | None = None
        final_path = run_dir / "assets" / f"{slot_slug}-selected.png"

        try:
            candidates, candidate_paths, candidate_failures = _collect_candidates(
                client=client,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                run_dir=run_dir,
                slot_slug=slot_slug,
                candidate_count=images_cfg.candidate_count,
            )

            if not candidate_paths:
                raise RuntimeError("; ".join(candidate_failures) or "no image candidates succeeded")

            selected_path = choose_best_candidate(candidate_paths)
            shutil.copyfile(selected_path, final_path)
            for candidate in candidates:
                if candidate["raw_image_path"] == _relative(selected_path, run_dir):
                    selected_candidate_index = candidate["index"]
                    selected_job_id = candidate["job_id"]
                    selected_raw_url = candidate["raw_image_url"]
                    break

            assets.append(
                {
                    "time": post["time"],
                    "type": post["type"],
                    "status": "ok",
                    "provider": "useapi_google_flow",
                    "image_prompt": prompt,
                    "job_id": selected_job_id,
                    "raw_image_url": selected_raw_url,
                    "raw_image_path": _relative(selected_path, run_dir),
                    "final_image_path": _relative(final_path, run_dir),
                    "selected_candidate_index": selected_candidate_index,
                    "candidates": candidates,
                    "error": "; ".join(candidate_failures) if candidate_failures else None,
                }
            )
            generated += 1
        except Exception as exc:  # noqa: BLE001
            fallback_provider = images_cfg.fallback_provider
            if fallback_provider == "codex_imagen_oauth":
                try:
                    raw_path, fallback_path = _render_codex_imagen_fallback_image(
                        run_dir=run_dir,
                        slot_slug=slot_slug,
                        prompt=prompt,
                        profile=profile,
                    )
                    assets.append(
                        {
                            "time": post["time"],
                            "type": post["type"],
                            "status": "ok",
                            "provider": "codex_imagen_oauth",
                            "image_prompt": prompt,
                            "job_id": None,
                            "raw_image_url": None,
                            "raw_image_path": _relative(raw_path, run_dir),
                            "final_image_path": _relative(fallback_path, run_dir),
                            "selected_candidate_index": None,
                            "candidates": candidates,
                            "error": "; ".join(candidate_failures) if candidate_failures else str(exc),
                        }
                    )
                    generated += 1
                    continue
                except Exception as codex_exc:  # noqa: BLE001
                    try:
                        raw_path, fallback_path, raw_url = _render_zai_fallback_image(
                            run_dir=run_dir,
                            slot_slug=slot_slug,
                            prompt=prompt,
                            profile=profile,
                        )
                        combined_error = "; ".join(
                            part
                            for part in [
                                "; ".join(candidate_failures) if candidate_failures else str(exc),
                                f"codex_imagen_oauth: {codex_exc}",
                            ]
                            if part
                        )
                        assets.append(
                            {
                                "time": post["time"],
                                "type": post["type"],
                                "status": "ok",
                                "provider": "zai_glm_image",
                                "image_prompt": prompt,
                                "job_id": None,
                                "raw_image_url": raw_url,
                                "raw_image_path": _relative(raw_path, run_dir),
                                "final_image_path": _relative(fallback_path, run_dir),
                                "selected_candidate_index": None,
                                "candidates": candidates,
                                "error": combined_error,
                            }
                        )
                        generated += 1
                        continue
                    except Exception as fallback_exc:  # noqa: BLE001
                        fallback_path = _render_fallback_image(
                            run_dir=run_dir,
                            slot_slug=slot_slug,
                            source_post=source_post,
                            profile=profile,
                            post=post,
                        )
                        combined_error = "; ".join(
                            part
                            for part in [
                                "; ".join(candidate_failures) if candidate_failures else str(exc),
                                f"codex_imagen_oauth: {codex_exc}",
                                f"zai_glm_image: {fallback_exc}",
                            ]
                            if part
                        )
                        assets.append(
                            {
                                "time": post["time"],
                                "type": post["type"],
                                "status": "ok",
                                "provider": "local_playwright_card",
                                "image_prompt": prompt,
                                "job_id": None,
                                "raw_image_url": None,
                                "raw_image_path": None,
                                "final_image_path": _relative(fallback_path, run_dir),
                                "selected_candidate_index": None,
                                "candidates": candidates,
                                "error": combined_error,
                            }
                        )
                        generated += 1
                        continue
            if fallback_provider == "zai_glm_image":
                try:
                    raw_path, fallback_path, raw_url = _render_zai_fallback_image(
                        run_dir=run_dir,
                        slot_slug=slot_slug,
                        prompt=prompt,
                        profile=profile,
                    )
                    assets.append(
                        {
                            "time": post["time"],
                            "type": post["type"],
                            "status": "ok",
                            "provider": "zai_glm_image",
                            "image_prompt": prompt,
                            "job_id": None,
                            "raw_image_url": raw_url,
                            "raw_image_path": _relative(raw_path, run_dir),
                            "final_image_path": _relative(fallback_path, run_dir),
                            "selected_candidate_index": None,
                            "candidates": candidates,
                            "error": "; ".join(candidate_failures) if candidate_failures else str(exc),
                        }
                    )
                    generated += 1
                    continue
                except Exception as fallback_exc:  # noqa: BLE001
                    fallback_path = _render_fallback_image(
                        run_dir=run_dir,
                        slot_slug=slot_slug,
                        source_post=source_post,
                        profile=profile,
                        post=post,
                    )
                    combined_error = "; ".join(
                        part
                        for part in [
                            "; ".join(candidate_failures) if candidate_failures else str(exc),
                            f"zai_glm_image: {fallback_exc}",
                        ]
                        if part
                    )
                    assets.append(
                        {
                            "time": post["time"],
                            "type": post["type"],
                            "status": "ok",
                            "provider": "local_playwright_card",
                            "image_prompt": prompt,
                            "job_id": None,
                            "raw_image_url": None,
                            "raw_image_path": None,
                            "final_image_path": _relative(fallback_path, run_dir),
                            "selected_candidate_index": None,
                            "candidates": candidates,
                            "error": combined_error,
                        }
                    )
                    generated += 1
                    continue
            if fallback_provider == "local_playwright_card":
                fallback_path = _render_fallback_image(
                    run_dir=run_dir,
                    slot_slug=slot_slug,
                    source_post=source_post,
                    profile=profile,
                    post=post,
                )
                assets.append(
                    {
                        "time": post["time"],
                        "type": post["type"],
                        "status": "ok",
                        "provider": "local_playwright_card",
                        "image_prompt": prompt,
                        "job_id": None,
                        "raw_image_url": None,
                        "raw_image_path": None,
                        "final_image_path": _relative(fallback_path, run_dir),
                        "selected_candidate_index": None,
                        "candidates": candidates,
                        "error": "; ".join(candidate_failures) if candidate_failures else str(exc),
                    }
                )
                generated += 1
            else:
                had_failure = True
                assets.append(
                    {
                        "time": post["time"],
                        "type": post["type"],
                        "status": "failed",
                        "provider": "useapi_google_flow",
                        "image_prompt": prompt,
                        "job_id": selected_job_id,
                        "raw_image_url": selected_raw_url,
                        "raw_image_path": _relative(selected_path, run_dir) if selected_path else None,
                        "final_image_path": _relative(final_path, run_dir) if final_path.exists() else None,
                        "selected_candidate_index": selected_candidate_index,
                        "candidates": candidates,
                        "error": "; ".join(candidate_failures) if candidate_failures else str(exc),
                    }
                )

    payload = _manifest_payload(
        provider=_top_level_provider(assets),
        page=profile.name,
        date=args.date,
        assets=assets,
    )
    validate("post_assets", payload)
    (run_dir / "post_assets.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "partial" if had_failure else "ok",
                "artifact": "post_assets.json",
                "assets_generated": generated,
                "assets_total": len(assets),
            },
            ensure_ascii=False,
        )
    )
    return 1 if had_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
