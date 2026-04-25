from autofanpage.hourly_repost_selector import select_source_post


def test_select_source_post_prefers_newest_today_in_profile_timezone():
    result = select_source_post(
        source_posts={
            "source_page_url": "https://www.facebook.com/0xSojalSec",
            "backend": "agent_browser",
            "fetched_at": "2026-04-24T03:00:00Z",
            "search_status": "selection_ready",
            "end_of_feed_reached": False,
            "scan_stopped_reason": "selection_ready",
            "posts_scanned": 3,
            "posts": [
                {
                    "source_page_url": "https://www.facebook.com/0xSojalSec",
                    "source_post_id": "today-older",
                    "source_post_url": "https://www.facebook.com/0xSojalSec/posts/today-older",
                    "author": "0xSojalSec",
                    "published_at": "2026-04-24T07:30:00+07:00",
                    "published_at_resolved": "2026-04-24T07:30:00+07:00",
                    "content_text": "today older",
                    "media_urls": [],
                    "backend": "agent_browser",
                    "fetched_at": "2026-04-24T03:00:00Z",
                },
                {
                    "source_page_url": "https://www.facebook.com/0xSojalSec",
                    "source_post_id": "today-newest",
                    "source_post_url": "https://www.facebook.com/0xSojalSec/posts/today-newest",
                    "author": "0xSojalSec",
                    "published_at": "2026-04-24T09:15:00+07:00",
                    "published_at_resolved": "2026-04-24T09:15:00+07:00",
                    "content_text": "today newest",
                    "media_urls": [],
                    "backend": "agent_browser",
                    "fetched_at": "2026-04-24T03:00:00Z",
                },
                {
                    "source_page_url": "https://www.facebook.com/0xSojalSec",
                    "source_post_id": "backlog-newest",
                    "source_post_url": "https://www.facebook.com/0xSojalSec/posts/backlog-newest",
                    "author": "0xSojalSec",
                    "published_at": "2026-04-23T23:45:00+07:00",
                    "published_at_resolved": "2026-04-23T23:45:00+07:00",
                    "content_text": "backlog newest",
                    "media_urls": [],
                    "backend": "agent_browser",
                    "fetched_at": "2026-04-24T03:00:00Z",
                },
            ],
        },
        repost_history={"items": []},
        profile_timezone="Asia/Ho_Chi_Minh",
        now_iso="2026-04-24T10:00:00+07:00",
    )

    assert result["action"] == "publish"
    assert result["selected_post"]["source_post_id"] == "today-newest"


def test_select_source_post_returns_partial_scope_error_when_selection_ready_dedupes_to_empty():
    result = select_source_post(
        source_posts={
            "source_page_url": "https://www.facebook.com/0xSojalSec",
            "backend": "agent_browser",
            "fetched_at": "2026-04-24T03:00:00Z",
            "search_status": "selection_ready",
            "end_of_feed_reached": False,
            "scan_stopped_reason": "selection_ready",
            "posts_scanned": 1,
            "posts": [
                {
                    "source_page_url": "https://www.facebook.com/0xSojalSec",
                    "source_post_id": "123",
                    "source_post_url": "https://www.facebook.com/0xSojalSec/posts/123",
                    "author": "0xSojalSec",
                    "published_at": "2026-04-24T09:15:00+07:00",
                    "published_at_resolved": "2026-04-24T09:15:00+07:00",
                    "content_text": "duplicate newest",
                    "media_urls": [],
                    "backend": "agent_browser",
                    "fetched_at": "2026-04-24T03:00:00Z",
                }
            ],
        },
        repost_history={
            "items": [
                {
                    "source_post_id": None,
                    "source_post_url": "https://www.facebook.com/0xSojalSec/posts/123",
                    "published_at": "2026-04-24T09:15:00+07:00",
                    "published_at_resolved": "2026-04-24T09:15:00+07:00",
                    "reposted_at": "2026-04-24T09:30:00+07:00",
                    "run_dir": "/tmp/old-run",
                }
            ]
        },
        profile_timezone="Asia/Ho_Chi_Minh",
        now_iso="2026-04-24T10:00:00+07:00",
    )

    assert result["action"] == "error"
    assert result["reason"] == "error_partial_search_scope"


def test_select_source_post_errors_when_only_unresolved_unreposted_candidates_remain():
    result = select_source_post(
        source_posts={
            "source_page_url": "https://www.facebook.com/0xSojalSec",
            "backend": "agent_browser",
            "fetched_at": "2026-04-24T03:00:00Z",
            "search_status": "full_search_complete",
            "end_of_feed_reached": True,
            "scan_stopped_reason": "end_of_feed",
            "posts_scanned": 1,
            "posts": [
                {
                    "source_page_url": "https://www.facebook.com/0xSojalSec",
                    "source_post_id": "bad-ts",
                    "source_post_url": "https://www.facebook.com/0xSojalSec/posts/bad-ts",
                    "author": "0xSojalSec",
                    "published_at": "today",
                    "published_at_resolved": "not-a-timestamp",
                    "content_text": "unresolved candidate",
                    "media_urls": [],
                    "backend": "agent_browser",
                    "fetched_at": "2026-04-24T03:00:00Z",
                }
            ],
        },
        repost_history={"items": []},
        profile_timezone="Asia/Ho_Chi_Minh",
        now_iso="2026-04-24T10:00:00+07:00",
    )

    assert result["action"] == "error"
    assert result["reason"] == "error_unresolved_candidate_timestamps"
