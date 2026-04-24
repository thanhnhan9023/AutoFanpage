import re

import pytest
import responses
from requests import Response

from autofanpage.errors import AutofanpageError
from autofanpage.useapi_flow import UseApiFlowClient


def _make_client(**kwargs):
    return UseApiFlowClient(
        base_url="https://api.useapi.net",
        api_token="token",
        account_id="acct@example.com",
        **kwargs,
    )


@responses.activate
def test_submit_image_job_returns_job_id_and_status():
    def callback(request):
        assert request.headers["Authorization"] == "Bearer token"
        assert request.headers["Content-Type"] == "application/json"
        body = request.body
        if isinstance(body, (bytes, bytearray)):
            body = body.decode()
        assert '"email": "acct@example.com"' in body
        assert '"prompt": "A clean AI workspace"' in body
        assert '"aspectRatio": "3:4"' in body
        assert '"count": 1' in body
        assert '"captchaRetry": 3' in body
        assert '"model": "imagen-4"' in body
        return (
            200,
            {},
            '{"jobId": "job_123", "media": [{"image": {"generatedImage": {"fifeUrl": "https://cdn.example/raw.png"}}}]}',
        )

    responses.add_callback(
        responses.POST,
        "https://api.useapi.net/v1/google-flow/images",
        callback=callback,
        content_type="application/json",
    )

    result = _make_client().submit_image_job(
        prompt="A clean AI workspace",
        aspect_ratio="3:4",
    )

    assert result == {
        "job_id": "job_123",
        "status": "completed",
        "raw_image_url": "https://cdn.example/raw.png",
    }


@responses.activate
def test_wait_for_image_job_returns_completed_payload():
    responses.add(
        responses.GET,
        "https://api.useapi.net/v1/google-flow/jobs/job_123",
        json={"jobid": "job_123", "status": "running"},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.useapi.net/v1/google-flow/jobs/job_123",
        json={
            "jobid": "job_123",
            "status": "completed",
            "response": {
                "media": [
                    {
                        "image": {
                            "generatedImage": {
                                "fifeUrl": "https://cdn.example/raw.png",
                            }
                        }
                    }
                ]
            },
        },
        status=200,
    )

    result = _make_client(
        poll_interval_seconds=0,
        max_polls=2,
    ).wait_for_image_job("job_123")

    assert result == {
        "job_id": "job_123",
        "raw_image_url": "https://cdn.example/raw.png",
    }
    assert len(responses.calls) == 2


@responses.activate
def test_wait_for_image_job_raises_on_timeout():
    responses.add(
        responses.GET,
        "https://api.useapi.net/v1/google-flow/jobs/job_123",
        json={"jobid": "job_123", "status": "running"},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.useapi.net/v1/google-flow/jobs/job_123",
        json={"jobid": "job_123", "status": "running"},
        status=200,
    )

    with pytest.raises(AutofanpageError, match=re.escape("useapi google flow timed out")):
        _make_client(
            poll_interval_seconds=0,
            max_polls=2,
        ).wait_for_image_job("job_123")


def test_submit_image_job_uses_extended_timeout(monkeypatch):
    seen = {}

    def fake_post(url, *, headers, json, timeout):
        seen["url"] = url
        seen["timeout"] = timeout
        response = Response()
        response.status_code = 200
        response._content = (
            b'{"jobId": "job_123", "media": [{"image": {"generatedImage": '
            b'{"fifeUrl": "https://cdn.example/raw.png"}}}]}'
        )
        response.headers["Content-Type"] = "application/json"
        return response

    monkeypatch.setattr("autofanpage.useapi_flow.requests.post", fake_post)

    result = _make_client().submit_image_job(
        prompt="A clean AI workspace",
        aspect_ratio="3:4",
    )

    assert seen["url"] == "https://api.useapi.net/v1/google-flow/images"
    assert seen["timeout"] == 25
    assert result["job_id"] == "job_123"


@responses.activate
def test_configure_captcha_providers_posts_capsolver_key():
    def callback(request):
        body = request.body
        if isinstance(body, (bytes, bytearray)):
            body = body.decode()
        assert '"CapSolver": "capsolver-key"' in body
        return (200, {}, '{"CapSolver": true}')

    responses.add_callback(
        responses.POST,
        "https://api.useapi.net/v1/google-flow/accounts/captcha-providers",
        callback=callback,
        content_type="application/json",
    )

    result = _make_client().configure_captcha_providers(
        capsolver_api_key="capsolver-key",
    )

    assert result == {"CapSolver": True}
