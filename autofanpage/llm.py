"""Thin LLM clients used by the writing skills."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from autofanpage.errors import SourceFailedError
from autofanpage.http import post_json


ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
LOCAL_GATEWAY_CHAT_URL = "http://localhost:20128/v1/chat/completions"
DEFAULT_WRITER_FALLBACKS = {
    "cx/gpt-5.4": "minimax/MiniMax-M2.7",
}


class WriterClient(Protocol):
    def generate(
        self,
        *,
        system: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
    ) -> str: ...


@dataclass
class FallbackWriterClient:
    primary: WriterClient
    fallback: WriterClient

    def generate(
        self,
        *,
        system: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
    ) -> str:
        try:
            return self.primary.generate(
                system=system,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except SourceFailedError:
            return self.fallback.generate(
                system=system,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )


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
            ANTHROPIC_API_URL,
            headers=headers,
            json_body=body,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )
        content = resp.get("content") or []
        parts = [block.get("text", "") for block in content if block.get("type") == "text"]
        return "".join(parts)


@dataclass
class OpenAIChatClient:
    api_key: str
    model: str
    api_url: str = LOCAL_GATEWAY_CHAT_URL
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
            "stream": False,
            "messages": [{"role": "system", "content": system}, *messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }
        resp = post_json(
            self.api_url,
            headers=headers,
            json_body=body,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )
        choices = resp.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            return "".join(parts)
        return ""


def build_writer_client(*, api_key: str, model: str) -> WriterClient:
    if model.startswith("claude-"):
        return ClaudeClient(api_key=api_key, model=model)

    primary = OpenAIChatClient(api_key=api_key, model=model)
    fallback_model = DEFAULT_WRITER_FALLBACKS.get(model)
    if not fallback_model:
        return primary
    fallback = OpenAIChatClient(api_key=api_key, model=fallback_model)
    return FallbackWriterClient(primary=primary, fallback=fallback)
