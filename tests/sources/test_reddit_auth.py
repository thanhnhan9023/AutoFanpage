import base64
import pytest
import responses

from autofanpage.sources.reddit_auth import get_app_token
from autofanpage.errors import SourceFailedError

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"


@responses.activate
def test_get_token_sends_basic_auth_and_form():
    def check(request):
        expected = base64.b64encode(b"cid:csec").decode()
        assert request.headers["Authorization"] == f"Basic {expected}"
        assert request.headers["User-Agent"].startswith("autofanpage")
        body = request.body
        if isinstance(body, (bytes, bytearray)):
            body = body.decode()
        assert "grant_type=client_credentials" in body
        return (200, {}, '{"access_token": "tkn", "token_type": "bearer", "expires_in": 3600}')

    responses.add_callback(
        responses.POST, TOKEN_URL,
        callback=check, content_type="application/json",
    )
    token = get_app_token("cid", "csec", user_agent="autofanpage/0.1")
    assert token == "tkn"


@responses.activate
def test_get_token_raises_on_401():
    responses.add(responses.POST, TOKEN_URL, status=401, json={"error": "invalid_grant"})
    with pytest.raises(SourceFailedError):
        get_app_token("cid", "csec", user_agent="autofanpage/0.1")
