from autofanpage.telegram import format_message


def test_success_template_includes_page_and_count():
    msg = format_message(
        status="success",
        page="page_vn_ai",
        details={"date": "2026-04-15", "posts_scheduled": 4,
                 "elapsed_sec": 287},
    )
    assert "✅" in msg
    assert "page_vn_ai" in msg
    assert "2026-04-15" in msg
    assert "4" in msg


def test_error_template_includes_phase_and_cause():
    msg = format_message(
        status="error",
        page="p",
        details={"phase": "notebooklm-analyzer", "cause": "cookie expired",
                 "log_tail": "line1\nline2"},
    )
    assert "🚨" in msg
    assert "notebooklm-analyzer" in msg
    assert "cookie expired" in msg
    assert "line1" in msg


def test_partial_template():
    msg = format_message(
        status="partial",
        page="p",
        details={"reason": "Review approved 2/4 insights",
                 "post_ids": ["123_1", "123_2"]},
    )
    assert "⚠️" in msg
    assert "2/4" in msg


def test_info_template():
    msg = format_message(status="info", page="p",
                         details={"message": "already ran today"})
    assert "ℹ️" in msg
    assert "already ran today" in msg


def test_success_template_includes_phase1_counts():
    msg = format_message(
        status="success", page="p",
        details={
            "date": "2026-04-15", "posts_scheduled": 0, "elapsed_sec": 12,
            "phase1_counts": {"youtube": 3, "hackernews": 5},
            "phase1_failed_sources": ["reddit"],
        },
    )
    assert "sources: youtube=3, hackernews=5" in msg
    assert "failed: reddit" in msg


def test_success_template_without_phase1_keys_is_backward_compatible():
    msg = format_message(
        status="success", page="p",
        details={"date": "2026-04-15", "posts_scheduled": 4, "elapsed_sec": 12},
    )
    assert "sources:" not in msg
    assert "failed:" not in msg


def test_partial_template_includes_approved_and_generated_counts():
    from autofanpage.telegram import format_message
    msg = format_message(
        status="partial", page="p",
        details={
            "date": "2026-04-16", "approved_count": 1, "posts_generated": 1,
            "phase1_counts": {"youtube": 3}, "phase": "review",
        },
    )
    assert "1 insights approved" in msg
    assert "1/4 posts generated" in msg
    assert "sources:" in msg


def test_success_template_renders_posts_generated_value():
    from autofanpage.telegram import format_message
    msg = format_message(
        status="success", page="p",
        details={"date": "2026-04-16", "posts_scheduled": 0,
                 "posts_generated": 4, "elapsed_sec": 60},
    )
    assert "4 posts generated" in msg


def test_success_template_includes_hourly_source_context():
    msg = format_message(
        status="success",
        page="page_hourly_repost",
        details={
            "posts_scheduled": 1,
            "date": "2026-04-23",
            "elapsed_sec": 12,
            "source_page_url": "https://www.facebook.com/0xSojalSec",
            "source_post_url": "https://www.facebook.com/0xSojalSec/posts/123",
            "source_published_at": "2026-04-23T09:15:00Z",
            "fetch_backend": "browser_use_mcp",
        },
    )
    assert "https://www.facebook.com/0xSojalSec/posts/123" in msg
    assert "browser_use_mcp" in msg


def test_info_template_renders_dry_run_preview():
    msg = format_message(
        status="info", page="p",
        details={"message": "Dry-run preview:\n\n## 08:00 — news\nContent here"},
    )
    assert "ℹ️" in msg
    assert "Dry-run preview" in msg
    assert "Content here" in msg
