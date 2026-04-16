"""Shared HTTP client with retry + timeout for all source fetchers.

Retries on 5xx and connection errors up to ``max_retries`` times with
exponential backoff. 4xx responses fail immediately (caller bug or auth
problem). All failure paths raise ``SourceFailedError`` with the URL
and final status in the message so orchestrator logs are useful.
"""
from __future__ import annotations

import time
from typing import Any

import requests

from autofanpage.errors import SourceFailedError

DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF = 1.0


def _request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None,
    params: dict[str, Any] | None,
    json_body: dict[str, Any] | None,
    timeout: float,
    max_retries: int,
    backoff: float,
) -> Any:
    last_err: str | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.request(
                method, url,
                headers=headers, params=params, json=json_body,
                timeout=timeout,
            )
        except requests.RequestException as e:
            last_err = f"{type(e).__name__}: {e}"
            if attempt >= max_retries:
                break
            time.sleep(backoff * (2 ** attempt))
            continue

        if 200 <= resp.status_code < 300:
            return resp.json()
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else backoff * (2 ** attempt)
            last_err = f"HTTP 429 (rate limited)"
            if attempt >= max_retries:
                break
            time.sleep(wait)
            continue
        if 400 <= resp.status_code < 500:
            raise SourceFailedError(
                f"{method} {url} -> HTTP {resp.status_code}: {resp.text[:200]}"
            )
        last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
        if attempt >= max_retries:
            break
        time.sleep(backoff * (2 ** attempt))
    raise SourceFailedError(f"{method} {url} failed after {max_retries} retries: {last_err}")


def get_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
) -> Any:
    return _request_json(
        "GET", url,
        headers=headers, params=params, json_body=None,
        timeout=timeout, max_retries=max_retries, backoff=backoff,
    )


def post_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
) -> Any:
    merged_headers = {"Content-Type": "application/json"}
    if headers:
        merged_headers.update(headers)
    return _request_json(
        "POST", url,
        headers=merged_headers, params=None, json_body=json_body,
        timeout=timeout, max_retries=max_retries, backoff=backoff,
    )
