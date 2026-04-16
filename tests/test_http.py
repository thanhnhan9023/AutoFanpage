import pytest
import responses

from autofanpage.http import get_json, post_json
from autofanpage.errors import SourceFailedError


@responses.activate
def test_get_json_returns_parsed_body():
    responses.add(
        responses.GET, "https://api.example/x",
        json={"ok": True}, status=200,
    )
    assert get_json("https://api.example/x") == {"ok": True}


@responses.activate
def test_get_json_retries_on_5xx_then_succeeds():
    responses.add(responses.GET, "https://api.example/x", status=503)
    responses.add(responses.GET, "https://api.example/x", status=502)
    responses.add(
        responses.GET, "https://api.example/x",
        json={"ok": True}, status=200,
    )
    assert get_json("https://api.example/x", max_retries=3, backoff=0) == {"ok": True}
    assert len(responses.calls) == 3


@responses.activate
def test_get_json_raises_after_exhausted_retries():
    for _ in range(4):
        responses.add(responses.GET, "https://api.example/x", status=500)
    with pytest.raises(SourceFailedError) as exc:
        get_json("https://api.example/x", max_retries=3, backoff=0)
    assert "https://api.example/x" in str(exc.value)


@responses.activate
def test_get_json_does_not_retry_4xx():
    responses.add(responses.GET, "https://api.example/x", status=404)
    with pytest.raises(SourceFailedError):
        get_json("https://api.example/x", max_retries=3, backoff=0)
    assert len(responses.calls) == 1


@responses.activate
def test_get_json_retries_on_429_then_succeeds():
    responses.add(responses.GET, "https://api.example/x", status=429,
                  headers={"Retry-After": "1"})
    responses.add(responses.GET, "https://api.example/x",
                  json={"ok": True}, status=200)
    assert get_json("https://api.example/x", max_retries=3, backoff=0) == {"ok": True}
    assert len(responses.calls) == 2


@responses.activate
def test_get_json_raises_after_exhausted_429_retries():
    for _ in range(4):
        responses.add(responses.GET, "https://api.example/x", status=429)
    with pytest.raises(SourceFailedError):
        get_json("https://api.example/x", max_retries=3, backoff=0)
    assert len(responses.calls) == 4


@responses.activate
def test_post_json_sends_body_and_headers():
    def check(request):
        assert request.headers["Authorization"] == "Bearer tok"
        assert request.headers["Content-Type"] == "application/json"
        body = request.body
        if isinstance(body, (bytes, bytearray)):
            body = body.decode()
        assert '"q": "hi"' in body
        return (200, {}, '{"result": 1}')

    responses.add_callback(
        responses.POST, "https://api.example/chat",
        callback=check, content_type="application/json",
    )
    out = post_json(
        "https://api.example/chat",
        headers={"Authorization": "Bearer tok"},
        json_body={"q": "hi"},
    )
    assert out == {"result": 1}
