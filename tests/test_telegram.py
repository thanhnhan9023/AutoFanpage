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
