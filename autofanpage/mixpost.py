"""Mixpost publishing helpers backed by persisted browser session state."""
from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from autofanpage.errors import AutofanpageError


@dataclass(frozen=True)
class CreatePage:
    csrf_token: str
    accounts: list[dict[str, Any]]


def _load_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise AutofanpageError("Playwright is required for Mixpost image publishing") from exc
    return sync_playwright


def _normalize_mixpost_root(base_url: str) -> str:
    root = base_url.rstrip("/")
    if not root.endswith("/mixpost"):
        root = f"{root}/mixpost"
    return root


def _page_button_selector(page_name: str) -> str:
    return f"button:has(span[name={json.dumps(page_name)}])"


def _media_button_selector() -> str:
    return (
        "button:has(svg path[d="
        "\"M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z\""
        "])"
    )


def _looks_like_scheduled_editor(page: Any) -> bool:
    url = str(getattr(page, "url", "") or "")
    if not re.search(r"/mixpost/posts/[0-9a-f-]+$", url):
        return False
    try:
        saved_count = page.locator("text=Saved").count()
        scheduled_count = page.locator("text=Scheduled").count()
    except Exception:  # noqa: BLE001
        return False
    return saved_count > 0 and scheduled_count > 0


def _read_storage_state(path: str | Path) -> dict[str, Any]:
    p = Path(path).expanduser()
    if not p.exists():
        raise AutofanpageError(
            f"Mixpost storage state not found: {p}. Refresh the Mixpost session first."
        )
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise AutofanpageError(f"invalid Mixpost storage state JSON: {p}") from e


def _build_session(storage_state: dict[str, Any]) -> requests.Session:
    session = requests.Session()
    for cookie in storage_state.get("cookies", []):
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain"),
            path=cookie.get("path", "/"),
        )
    return session


def parse_create_page(page_html: str) -> CreatePage:
    csrf_match = re.search(r'<meta name="csrf-token" content="([^"]+)"', page_html)
    if not csrf_match:
        raise AutofanpageError("Mixpost create page is missing CSRF token.")

    data_page_match = re.search(r'data-page="([^"]+)"', page_html)
    if not data_page_match:
        raise AutofanpageError("Mixpost create page is missing Inertia payload.")

    try:
        payload = json.loads(html.unescape(data_page_match.group(1)))
    except json.JSONDecodeError as e:
        raise AutofanpageError("Mixpost create page payload is malformed.") from e

    props = payload.get("props", {})
    accounts = props.get("accounts", [])
    if not isinstance(accounts, list):
        raise AutofanpageError("Mixpost create page returned invalid accounts payload.")

    return CreatePage(csrf_token=csrf_match.group(1), accounts=accounts)


def _pick_account(accounts: list[dict[str, Any]], *, page_name: str) -> dict[str, Any]:
    candidates = [
        account
        for account in accounts
        if account.get("authorized") is True and account.get("provider") == "facebook_page"
    ]
    if not candidates:
        raise AutofanpageError("No authorized Facebook page account found in Mixpost.")

    for account in candidates:
        if account.get("name") == page_name:
            return account

    if len(candidates) == 1:
        return candidates[0]

    raise AutofanpageError(
        f"Mixpost account '{page_name}' not found. Available accounts: "
        + ", ".join(str(account.get("name")) for account in candidates)
    )


def _build_store_payload(
    *,
    account_id: int,
    content: str,
    publish_date: str,
    publish_time: str,
) -> dict[str, Any]:
    safe_content = html.escape(content).replace("\n", "<br>")
    return {
        "accounts": [account_id],
        "versions": [
            {
                "account_id": account_id,
                "is_original": True,
                "content": [{"body": f"<div>{safe_content}</div>", "media": []}],
            }
        ],
        "tags": [],
        "date": publish_date,
        "time": publish_time,
    }


def _ensure_authenticated(response: requests.Response) -> None:
    if "/mixpost/login" in response.url or response.status_code in (401, 403):
        raise AutofanpageError(
            "Mixpost session expired. Refresh storage state with the login bootstrap."
        )


def _post_uuid_from_location(location: str | None) -> str:
    if not location:
        raise AutofanpageError("Mixpost did not return a draft post location.")
    return location.rstrip("/").split("/")[-1]


def _ensure_schedule_response_ok(status_code: int, body: str) -> None:
    if status_code != 200:
        raise AutofanpageError(
            f"Mixpost schedule failed with HTTP {status_code}: "
            f"{body[:400]}"
        )


def schedule_slot_via_mixpost(
    *,
    base_url: str,
    storage_state_path: str | Path,
    headless: bool,
    page_name: str,
    content: str,
    publish_date: str,
    publish_time: str,
    timezone: str,
    image_path: str | None = None,
) -> dict[str, int | None]:
    del timezone

    storage_state = _read_storage_state(storage_state_path)
    if image_path:
        sync_playwright = _load_playwright()
        mixpost_root = _normalize_mixpost_root(base_url)
        create_post_url = (
            f"{mixpost_root}/posts/create/{quote(f'{publish_date} {publish_time}', safe='')}"
        )
        with sync_playwright() as playwright:
            browser = None
            context = None
            try:
                browser = playwright.chromium.launch(headless=headless)
                context = browser.new_context(storage_state=str(Path(storage_state_path).expanduser()))
                page = context.new_page()
                try:
                    page.goto(create_post_url, wait_until="domcontentloaded")
                except Exception as exc:
                    raise AutofanpageError(
                        f"Mixpost interaction failed during page load: {exc}"
                    ) from exc
                if "/login" in getattr(page, "url", ""):
                    raise AutofanpageError("Mixpost session expired; please refresh login")
                try:
                    page.click(_page_button_selector(page_name))
                    page.click(_media_button_selector())
                    page.set_input_files("input[type='file']", image_path)
                    page.wait_for_selector("button:has-text('INSERT 1 ITEMS')", timeout=10000)
                    page.click("button:has-text('INSERT 1 ITEMS')")
                    page.fill("[contenteditable='true']", content)
                    page.wait_for_selector("text=Saved", timeout=5000)
                    with page.expect_response(
                        lambda response: "/mixpost/posts/schedule/" in response.url
                    ) as schedule_response_info:
                        page.click("button:has-text('SCHEDULE')")
                    schedule_response = schedule_response_info.value
                    _ensure_schedule_response_ok(
                        int(schedule_response.status),
                        schedule_response.text(),
                    )
                    try:
                        page.wait_for_url("**/mixpost/posts", timeout=15000)
                    except Exception:
                        if not _looks_like_scheduled_editor(page):
                            raise
                except Exception as exc:
                    raise AutofanpageError(f"Mixpost interaction failed during image upload: {exc}") from exc
            finally:
                if context is not None:
                    context.close()
                if browser is not None:
                    browser.close()
        return {"post_id": None, "comment_id": None, "status": 200}

    session = _build_session(storage_state)
    root = base_url.rstrip("/")

    create_response = session.get(f"{root}/mixpost/posts/create", timeout=60)
    _ensure_authenticated(create_response)
    create_page = parse_create_page(create_response.text)
    account = _pick_account(create_page.accounts, page_name=page_name)

    headers = {
        "X-CSRF-TOKEN": create_page.csrf_token,
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/json",
    }
    store_response = session.post(
        f"{root}/mixpost/posts/store",
        headers=headers,
        json=_build_store_payload(
            account_id=int(account["id"]),
            content=content,
            publish_date=publish_date,
            publish_time=publish_time,
        ),
        timeout=60,
        allow_redirects=False,
    )
    if store_response.status_code not in (302, 303):
        raise AutofanpageError(
            f"Mixpost store failed with HTTP {store_response.status_code}: "
            f"{store_response.text[:400]}"
        )

    post_uuid = _post_uuid_from_location(store_response.headers.get("location"))
    schedule_response = session.post(
        f"{root}/mixpost/posts/schedule/{post_uuid}",
        headers=headers,
        json={"postNow": False},
        timeout=60,
        allow_redirects=False,
    )
    _ensure_schedule_response_ok(schedule_response.status_code, schedule_response.text)

    return {"post_id": None, "comment_id": None, "status": 200}
