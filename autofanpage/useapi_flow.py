"""Thin UseAPI Google Flow provider client."""
from __future__ import annotations

import time
from typing import Any

import requests

from autofanpage.errors import AutofanpageError

REQUEST_TIMEOUT_SECONDS = 30
IMAGE_REQUEST_TIMEOUT_SECONDS = 25
POLLING_STATUSES = {"queued", "pending", "running", "in_progress"}


class UseApiFlowClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_token: str,
        account_id: str | None,
        poll_interval_seconds: float = 3.0,
        max_polls: int = 40,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.account_id = account_id
        self.poll_interval_seconds = poll_interval_seconds
        self.max_polls = max_polls

    def _api_root(self) -> str:
        api_root = self.base_url
        if not api_root.endswith("/v1"):
            api_root = f"{api_root}/v1"
        return api_root

    def _jobs_base_url(self) -> str:
        return f"{self._api_root()}/google-flow/jobs"

    def _images_url(self) -> str:
        return f"{self._api_root()}/google-flow/images"

    def _accounts_url(self) -> str:
        return f"{self._api_root()}/google-flow/accounts"

    def _captcha_providers_url(self) -> str:
        return f"{self._api_root()}/google-flow/accounts/captcha-providers"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    def _extract_raw_image_url(self, payload: dict[str, Any]) -> str | None:
        media_collections: list[Any] = [payload.get("media")]
        response_payload = payload.get("response")
        if isinstance(response_payload, dict):
            media_collections.append(response_payload.get("media"))

        for media in media_collections:
            if not isinstance(media, list) or not media:
                continue
            first = media[0]
            if not isinstance(first, dict):
                continue
            image = first.get("image")
            if not isinstance(image, dict):
                continue
            generated = image.get("generatedImage")
            if not isinstance(generated, dict):
                continue
            image_url = generated.get("fifeUrl") or generated.get("imageUrl")
            if isinstance(image_url, str) and image_url:
                return image_url
        return None

    def _parse_json(self, response: requests.Response) -> dict[str, Any]:
        try:
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise AutofanpageError(f"useapi google flow request failed: {exc}") from exc
        if not isinstance(payload, dict):
            raise AutofanpageError(
                f"useapi google flow returned unexpected payload: {payload!r}"
            )
        return payload

    def _require_fields(
        self,
        payload: dict[str, Any],
        *,
        fields: tuple[str, ...],
        context: str,
    ) -> None:
        missing = [field for field in fields if field not in payload]
        if missing:
            raise AutofanpageError(
                f"useapi google flow {context} missing required fields: {', '.join(missing)}"
            )

    def _pick_account_id(self, payload: dict[str, Any]) -> str | None:
        healthy_accounts: list[str] = []
        fallback_accounts: list[str] = []
        for account_id, details in payload.items():
            if not isinstance(account_id, str) or not account_id:
                continue
            fallback_accounts.append(account_id)
            if isinstance(details, dict) and str(details.get("health", "")).upper() == "OK":
                healthy_accounts.append(account_id)
        if healthy_accounts:
            return healthy_accounts[0]
        if fallback_accounts:
            return fallback_accounts[0]
        return None

    def resolve_account_id(self) -> str:
        if self.account_id:
            return self.account_id
        payload = self._parse_json(
            requests.get(
                self._accounts_url(),
                headers=self._headers(),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        )
        account_id = self._pick_account_id(payload)
        if not account_id:
            raise AutofanpageError("useapi google flow has no configured accounts")
        self.account_id = account_id
        return account_id

    def configure_captcha_providers(self, *, capsolver_api_key: str) -> dict[str, Any]:
        payload = self._parse_json(
            requests.post(
                self._captcha_providers_url(),
                headers=self._headers(),
                json={"CapSolver": capsolver_api_key},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        )
        return payload

    def submit_image_job(self, *, prompt: str, aspect_ratio: str) -> dict[str, str]:
        account_id = self.resolve_account_id()
        payload = self._parse_json(
            requests.post(
                self._images_url(),
                headers=self._headers(),
                json={
                    "email": account_id,
                    "prompt": prompt,
                    "model": "imagen-4",
                    "aspectRatio": aspect_ratio,
                    "count": 1,
                    "captchaRetry": 3,
                },
                timeout=IMAGE_REQUEST_TIMEOUT_SECONDS,
            )
        )
        self._require_fields(payload, fields=("jobId", "media"), context="submit response")
        raw_image_url = self._extract_raw_image_url(payload)
        if not raw_image_url:
            raise AutofanpageError(
                "useapi google flow submit response missing required fields: raw_image_url"
            )
        return {
            "job_id": str(payload["jobId"]),
            "status": "completed",
            "raw_image_url": raw_image_url,
        }

    def wait_for_image_job(self, job_id: str) -> dict[str, Any]:
        last_payload: dict[str, Any] | None = None
        for attempt in range(self.max_polls):
            payload = self._parse_json(
                requests.get(
                    f"{self._jobs_base_url()}/{job_id}",
                    headers=self._headers(),
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
            )
            last_payload = payload
            self._require_fields(payload, fields=("status",), context="job status response")
            status = str(payload["status"]).lower()
            if status == "completed":
                image_url = self._extract_raw_image_url(payload)
                if not image_url:
                    raise AutofanpageError(
                        f"useapi google flow completed without image_url: {payload!r}"
                    )
                return {"job_id": job_id, "raw_image_url": image_url}
            if status == "failed":
                error = str(payload.get("error", "unknown provider error"))
                raise AutofanpageError(f"useapi google flow failed: {error}")
            if status in POLLING_STATUSES:
                if attempt < self.max_polls - 1:
                    time.sleep(self.poll_interval_seconds)
                continue
            raise AutofanpageError(
                f"useapi google flow unknown status: {payload['status']}"
            )
        raise AutofanpageError(f"useapi google flow timed out: {last_payload!r}")
