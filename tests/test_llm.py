import json

import pytest
import responses

from autofanpage.errors import SourceFailedError
from autofanpage.llm import ClaudeClient


API = "https://api.anthropic.com/v1/messages"


@responses.activate
def test_generate_posts_payload_and_returns_text():
    responses.add(
        responses.POST, API,
        json={"content": [{"type": "text", "text": "hello from claude"}]},
        status=200,
    )
    c = ClaudeClient(api_key="sk-ant-xxx", model="claude-opus-4-6")
    out = c.generate(
        system="you are a writer",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=500,
        temperature=0.7,
    )
    assert out == "hello from claude"

    call = responses.calls[0]
    body = json.loads(call.request.body)
    assert body["model"] == "claude-opus-4-6"
    assert body["system"] == "you are a writer"
    assert body["max_tokens"] == 500
    assert body["temperature"] == 0.7
    assert call.request.headers["x-api-key"] == "sk-ant-xxx"
    assert call.request.headers["anthropic-version"] == "2023-06-01"


@responses.activate
def test_generate_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setattr("autofanpage.http.time.sleep", lambda _: None)
    responses.add(responses.POST, API, status=429)
    responses.add(responses.POST, API, status=429)
    responses.add(
        responses.POST, API,
        json={"content": [{"type": "text", "text": "ok"}]},
        status=200,
    )
    c = ClaudeClient(api_key="k", model="claude-opus-4-6")
    assert c.generate(
        system="", messages=[{"role": "user", "content": "x"}],
        max_tokens=10, temperature=0,
    ) == "ok"


@responses.activate
def test_generate_raises_after_exhausted_retries(monkeypatch):
    monkeypatch.setattr("autofanpage.http.time.sleep", lambda _: None)
    for _ in range(5):
        responses.add(responses.POST, API, status=500)
    c = ClaudeClient(api_key="k", model="claude-opus-4-6")
    with pytest.raises(SourceFailedError):
        c.generate(
            system="", messages=[{"role": "user", "content": "x"}],
            max_tokens=10, temperature=0,
        )


@responses.activate
def test_generate_raises_on_4xx_non_429():
    responses.add(responses.POST, API, status=400,
                  json={"error": {"message": "bad request"}})
    c = ClaudeClient(api_key="k", model="claude-opus-4-6")
    with pytest.raises(SourceFailedError):
        c.generate(
            system="", messages=[{"role": "user", "content": "x"}],
            max_tokens=10, temperature=0,
        )


@responses.activate
def test_generate_joins_multiple_text_blocks():
    responses.add(
        responses.POST, API,
        json={"content": [
            {"type": "text", "text": "hello "},
            {"type": "text", "text": "world"},
        ]},
        status=200,
    )
    c = ClaudeClient(api_key="k", model="claude-opus-4-6")
    assert c.generate(
        system="", messages=[{"role": "user", "content": "x"}],
        max_tokens=10, temperature=0,
    ) == "hello world"
