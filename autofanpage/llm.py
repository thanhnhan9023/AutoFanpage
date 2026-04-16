"""Thin Anthropic Messages API client used by the writing-agent."""
from __future__ import annotations

from dataclasses import dataclass

from autofanpage.http import post_json


API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


@dataclass
class ClaudeClient:
    api_key: str
    model: str = "claude-opus-4-6"
    max_retries: int = 4
    timeout: int = 120

    def generate(
        self,
        *,
        system: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
    ) -> str:
        body = {
            "model": self.model,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        resp = post_json(
            API_URL,
            headers=headers,
            json_body=body,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )
        content = resp.get("content") or []
        parts = [b.get("text", "") for b in content if b.get("type") == "text"]
        return "".join(parts)
