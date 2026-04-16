"""Reddit app-only OAuth (client_credentials) token fetcher."""
from __future__ import annotations

import requests

from autofanpage.errors import SourceFailedError

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"


def get_app_token(client_id: str, client_secret: str, *, user_agent: str) -> str:
    resp = requests.post(
        TOKEN_URL,
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials"},
        headers={"User-Agent": user_agent},
        timeout=30,
    )
    if resp.status_code != 200:
        raise SourceFailedError(
            f"Reddit token fetch failed: HTTP {resp.status_code}: {resp.text[:200]}"
        )
    body = resp.json()
    token = body.get("access_token")
    if not token:
        raise SourceFailedError(f"Reddit token response missing access_token: {body}")
    return token
