import json

import pytest

from autofanpage.errors import AutofanpageError
from autofanpage.mixpost import (
    _build_store_payload,
    _looks_like_scheduled_editor,
    _pick_account,
    _read_storage_state,
    parse_create_page,
    schedule_slot_via_mixpost,
)


def test_read_storage_state_rejects_missing_file(tmp_path):
    with pytest.raises(AutofanpageError, match="storage state"):
        _read_storage_state(tmp_path / "missing.json")


def test_parse_create_page_extracts_csrf_and_accounts():
    html = """
    <html>
      <head><meta name="csrf-token" content="csrf-123"></head>
      <body>
        <div id="app" data-page="{&quot;props&quot;:{&quot;accounts&quot;:[{&quot;id&quot;:1,&quot;name&quot;:&quot;Test&quot;,&quot;authorized&quot;:true,&quot;provider&quot;:&quot;facebook_page&quot;},{&quot;id&quot;:2,&quot;name&quot;:&quot;X&quot;,&quot;authorized&quot;:false,&quot;provider&quot;:&quot;facebook_page&quot;}]}}"></div>
      </body>
    </html>
    """

    parsed = parse_create_page(html)

    assert parsed.csrf_token == "csrf-123"
    assert parsed.accounts[0]["name"] == "Test"
    assert parsed.accounts[0]["authorized"] is True


def test_pick_account_prefers_named_match():
    account = _pick_account(
        [
            {"id": 2, "name": "Other", "authorized": True, "provider": "facebook_page"},
            {"id": 1, "name": "Test", "authorized": True, "provider": "facebook_page"},
        ],
        page_name="Test",
    )

    assert account["id"] == 1


def test_build_store_payload_sets_date_and_time_for_selected_account():
    payload = _build_store_payload(
        account_id=1,
        content="Xin chao",
        publish_date="2026-04-25",
        publish_time="09:30",
    )

    assert payload == {
        "accounts": [1],
        "versions": [
            {
                "account_id": 1,
                "is_original": True,
                "content": [{"body": "<div>Xin chao</div>", "media": []}],
            }
        ],
        "tags": [],
        "date": "2026-04-25",
        "time": "09:30",
    }


def test_looks_like_scheduled_editor_accepts_saved_editor_url():
    class _Locator:
        def __init__(self, count):
            self._count = count

        def count(self):
            return self._count

    class _Page:
        url = "https://mixpost.example.test/mixpost/posts/f204f79a-99c5-4b55-8a28-82793441ea21"

        def locator(self, selector):
            counts = {
                "text=Saved": 1,
                "text=Scheduled": 1,
            }
            return _Locator(counts.get(selector, 0))

    assert _looks_like_scheduled_editor(_Page()) is True


def test_looks_like_scheduled_editor_rejects_unscheduled_editor_url():
    class _Locator:
        def __init__(self, count):
            self._count = count

        def count(self):
            return self._count

    class _Page:
        url = "https://mixpost.example.test/mixpost/posts/create/2026-04-24%2008%3A00"

        def locator(self, selector):
            counts = {
                "text=Saved": 1,
                "text=Scheduled": 0,
            }
            return _Locator(counts.get(selector, 0))

    assert _looks_like_scheduled_editor(_Page()) is False


def test_schedule_slot_via_mixpost_with_image_raises_on_schedule_http_failure(
    monkeypatch,
    tmp_path,
):
    storage_state = tmp_path / "storage_state.json"
    storage_state.write_text('{"cookies": []}', encoding="utf-8")

    class _Response:
        status = 422
        url = "https://mixpost.example.test/mixpost/posts/schedule/post-123"

        def text(self):
            return '{"message":"This post cannot be scheduled! The date is in the past."}'

    class _ExpectResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        @property
        def value(self):
            return _Response()

    class _Page:
        url = "https://mixpost.example.test/mixpost/posts/post-123"

        def goto(self, *_args, **_kwargs):
            return None

        def click(self, *_args, **_kwargs):
            return None

        def set_input_files(self, *_args, **_kwargs):
            return None

        def wait_for_selector(self, *_args, **_kwargs):
            return None

        def fill(self, *_args, **_kwargs):
            return None

        def wait_for_url(self, *_args, **_kwargs):
            return None

        def expect_response(self, *_args, **_kwargs):
            return _ExpectResponse()

    class _Context:
        def new_page(self):
            return _Page()

        def close(self):
            return None

    class _Browser:
        def new_context(self, **_kwargs):
            return _Context()

        def close(self):
            return None

    class _Playwright:
        chromium = type("_Chromium", (), {"launch": lambda self, **_kwargs: _Browser()})()

    class _PlaywrightManager:
        def __enter__(self):
            return _Playwright()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "autofanpage.mixpost._load_playwright",
        lambda: _PlaywrightManager,
    )

    with pytest.raises(AutofanpageError, match="Mixpost schedule failed with HTTP 422"):
        schedule_slot_via_mixpost(
            base_url="https://mixpost.example.test",
            storage_state_path=storage_state,
            headless=True,
            page_name="Test",
            content="Xin chao",
            publish_date="2026-04-24",
            publish_time="08:00",
            timezone="Asia/Ho_Chi_Minh",
            image_path=str(tmp_path / "image.png"),
        )
