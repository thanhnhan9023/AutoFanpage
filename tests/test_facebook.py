from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from autofanpage.facebook import (
    add_first_comment,
    compute_publish_time,
    render_preview,
    schedule_post,
)


def test_compute_publish_time_normal_case():
    wall = datetime(2026, 4, 16, 6, 30, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    ts = compute_publish_time(
        post_time="12:00", date="2026-04-16",
        tz_name="Asia/Ho_Chi_Minh", wall_now=wall,
    )
    assert ts == int(datetime(2026, 4, 16, 5, 0, tzinfo=timezone.utc).timestamp())


def test_compute_publish_time_shifts_when_within_10_min():
    wall = datetime(2026, 4, 16, 7, 55, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    ts = compute_publish_time(
        post_time="08:00", date="2026-04-16",
        tz_name="Asia/Ho_Chi_Minh", wall_now=wall,
    )
    expected = datetime(2026, 4, 16, 1, 15, tzinfo=timezone.utc)
    assert ts == int(expected.timestamp())


def test_compute_publish_time_shifts_when_in_past():
    wall = datetime(2026, 4, 16, 8, 5, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    ts = compute_publish_time(
        post_time="08:00", date="2026-04-16",
        tz_name="Asia/Ho_Chi_Minh", wall_now=wall,
    )
    expected = datetime(2026, 4, 16, 1, 15, tzinfo=timezone.utc)
    assert ts == int(expected.timestamp())


def test_compute_publish_time_no_shift_when_exactly_10_min_away():
    wall = datetime(2026, 4, 16, 7, 50, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    ts = compute_publish_time(
        post_time="08:00", date="2026-04-16",
        tz_name="Asia/Ho_Chi_Minh", wall_now=wall,
    )
    expected = datetime(2026, 4, 16, 1, 0, tzinfo=timezone.utc)
    assert ts == int(expected.timestamp())


def test_render_preview_formats_posts_as_markdown():
    posts = {
        "posts": [
            {"time": "08:00", "type": "news", "content": "Breaking news content",
             "first_comment": "Source: https://example.com"},
            {"time": "12:00", "type": "guide", "content": None, "first_comment": None},
            {"time": "16:00", "type": "opinion", "content": "Hot take here",
             "first_comment": "What do you think?"},
            {"time": "20:00", "type": "case_study", "content": None, "first_comment": None},
        ],
        "language": "vi",
    }
    md = render_preview(posts, page="page_test", date="2026-04-16")
    assert "# Preview: page_test" in md
    assert "## 08:00 — news" in md
    assert "Breaking news content" in md
    assert "Source: https://example.com" in md
    assert "## 12:00 — guide" in md
    assert "(no content)" in md
    assert "## 16:00 — opinion" in md
    assert "Hot take here" in md


def test_schedule_post_delegates_to_post_json(mocker):
    post_json = mocker.patch(
        "autofanpage.facebook.post_json",
        return_value={"id": "123_456"},
    )

    post_id = schedule_post(
        page_id="123",
        access_token="token",
        message="Hello world",
        publish_time=1713229200,
    )

    assert post_id == "123_456"
    post_json.assert_called_once_with(
        "https://graph.facebook.com/v19.0/123/feed",
        json_body={
            "message": "Hello world",
            "scheduled_publish_time": 1713229200,
            "published": False,
            "access_token": "token",
        },
        timeout=60,
        max_retries=3,
    )


def test_add_first_comment_delegates_to_post_json(mocker):
    post_json = mocker.patch(
        "autofanpage.facebook.post_json",
        return_value={"id": "123_789"},
    )

    comment_id = add_first_comment(
        post_id="123_456",
        access_token="token",
        message="First comment",
    )

    assert comment_id == "123_789"
    post_json.assert_called_once_with(
        "https://graph.facebook.com/v19.0/123_456/comments",
        json_body={
            "message": "First comment",
            "access_token": "token",
        },
        timeout=30,
        max_retries=3,
    )
