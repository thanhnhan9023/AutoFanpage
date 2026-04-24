import pytest
import responses

from autofanpage.errors import AutofanpageError
from autofanpage.zai_image import ZaiImageClient


def _make_client(**kwargs):
    return ZaiImageClient(
        base_url="https://api.z.ai/api/paas/v4",
        api_key="zai-key",
        **kwargs,
    )


@responses.activate
def test_generate_image_returns_first_url():
    def callback(request):
        assert request.headers["Authorization"] == "Bearer zai-key"
        assert request.headers["Content-Type"] == "application/json"
        body = request.body
        if isinstance(body, (bytes, bytearray)):
            body = body.decode()
        assert '"model": "glm-image"' in body
        assert '"prompt": "A premium editorial scene"' in body
        assert '"size": "1088x1344"' in body
        assert '"quality": "standard"' in body
        return (
            200,
            {},
            '{"created": 1713950000, "data": [{"url": "https://cdn.z.ai/image.png"}]}',
        )

    responses.add_callback(
        responses.POST,
        "https://api.z.ai/api/paas/v4/images/generations",
        callback=callback,
        content_type="application/json",
    )

    result = _make_client().generate_image(
        prompt="A premium editorial scene",
        size="1088x1344",
    )

    assert result == {
        "raw_image_url": "https://cdn.z.ai/image.png",
        "model": "glm-image",
    }


@responses.activate
def test_generate_image_raises_on_missing_url():
    responses.add(
        responses.POST,
        "https://api.z.ai/api/paas/v4/images/generations",
        json={"created": 1713950000, "data": [{}]},
        status=200,
    )

    with pytest.raises(AutofanpageError, match="missing required fields"):
        _make_client().generate_image(
            prompt="A premium editorial scene",
            size="1088x1344",
        )
