"""Thin Z.AI image generation client."""
from __future__ import annotations

from dataclasses import dataclass

from autofanpage.errors import AutofanpageError
from autofanpage.http import post_json


@dataclass
class ZaiImageClient:
    api_key: str
    base_url: str = "https://api.z.ai/api/paas/v4"
    model: str = "glm-image"
    quality: str = "standard"
    timeout: int = 45
    max_retries: int = 2

    def _images_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/images/generations"

    def generate_image(self, *, prompt: str, size: str) -> dict[str, str]:
        payload = post_json(
            self._images_url(),
            headers={"Authorization": f"Bearer {self.api_key}"},
            json_body={
                "model": self.model,
                "prompt": prompt,
                "size": size,
                "quality": self.quality,
            },
            timeout=self.timeout,
            max_retries=self.max_retries,
        )
        if not isinstance(payload, dict):
            raise AutofanpageError(f"zai image returned unexpected payload: {payload!r}")
        data = payload.get("data")
        if not isinstance(data, list) or not data:
            raise AutofanpageError(
                "zai image generate response missing required fields: data"
            )
        first = data[0]
        if not isinstance(first, dict):
            raise AutofanpageError(
                "zai image generate response missing required fields: raw_image_url"
            )
        raw_image_url = first.get("url")
        if not isinstance(raw_image_url, str) or not raw_image_url:
            raise AutofanpageError(
                "zai image generate response missing required fields: raw_image_url"
            )
        return {
            "raw_image_url": raw_image_url,
            "model": self.model,
        }
