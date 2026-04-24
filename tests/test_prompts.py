from autofanpage.prompts import (
    build_first_comment_prompt,
    build_hourly_repost_prompt,
    build_hourly_repost_rewrite_prompt,
    build_hourly_repost_review_prompt,
    build_writing_prompt,
)
from autofanpage.templates import TEMPLATES


APPROVED = {
    "insight": "OpenAI launched GPT-5 — latency dropped 35% vs 4.5.",
    "scores": {"relevance": 5, "novelty": 5, "viral": 5, "actionable": 2},
    "total": 17,
    "suggested_post_type": "news",
    "hook_angle": "latency dropped 35%",
    "source_url": "https://news.example/gpt5",
}


def test_build_writing_prompt_returns_system_and_messages():
    system, messages = build_writing_prompt(
        insight=APPROVED, template=TEMPLATES["news"], language="vi",
    )
    assert isinstance(system, str) and system
    assert isinstance(messages, list) and len(messages) == 1
    assert messages[0]["role"] == "user"
    content = messages[0]["content"]
    assert "vi" in content or "Vietnamese" in content
    assert APPROVED["insight"] in content
    assert "hook" in content.lower()


def test_build_writing_prompt_forbids_fabrication():
    system, _ = build_writing_prompt(
        insight=APPROVED, template=TEMPLATES["news"], language="vi",
    )
    assert "do not invent" in system.lower() or \
           "do not fabricate" in system.lower()


def test_build_writing_prompt_includes_word_count_window():
    _, messages = build_writing_prompt(
        insight=APPROVED, template=TEMPLATES["news"], language="vi",
    )
    content = messages[0]["content"]
    assert "150" in content and "250" in content


def test_build_first_comment_prompt_includes_source_url_for_news():
    system, messages = build_first_comment_prompt(
        insight=APPROVED, template=TEMPLATES["news"], language="vi",
        post_body="POST BODY",
    )
    assert APPROVED["source_url"] in messages[0]["content"]


def test_build_prompt_different_languages_produce_different_instructions():
    _, m_vi = build_writing_prompt(
        insight=APPROVED, template=TEMPLATES["news"], language="vi",
    )
    _, m_en = build_writing_prompt(
        insight=APPROVED, template=TEMPLATES["news"], language="en",
    )
    assert m_vi[0]["content"] != m_en[0]["content"]


def test_build_hourly_repost_prompt_includes_ai5phut_style_and_grounding():
    source_post = {
        "content_text": "OpenAI launched a new model.",
        "source_post_url": "https://facebook.com/post/123",
    }

    _, messages = build_hourly_repost_prompt(
        source_post=source_post,
        language="vi",
        style="ai5phut",
    )

    content = messages[0]["content"]
    assert "ai5phut" in content.lower()
    assert source_post["source_post_url"] in content
    assert source_post["content_text"] in content
    assert "khong duoc" in content.lower() or "do not invent" in content.lower()


def test_build_hourly_repost_review_prompt_requests_json_feedback():
    source_post = {
        "content_text": "OpenAI launched a new model.",
        "source_post_url": "https://facebook.com/post/123",
    }

    _, messages = build_hourly_repost_review_prompt(
        source_post=source_post,
        draft_post="Ban nhap bai viet",
        language="vi",
        style="ai5phut",
    )

    content = messages[0]["content"]
    assert "json" in content.lower()
    assert "approved" in content
    assert "feedback" in content
    assert "Ban nhap bai viet" in content


def test_build_hourly_repost_rewrite_prompt_includes_feedback():
    source_post = {
        "content_text": "OpenAI launched a new model.",
        "source_post_url": "https://facebook.com/post/123",
    }

    _, messages = build_hourly_repost_rewrite_prompt(
        source_post=source_post,
        current_draft="Ban nhap cu",
        feedback="Can mo hook manh hon",
        language="vi",
        style="ai5phut",
    )

    content = messages[0]["content"]
    assert "Ban nhap cu" in content
    assert "Can mo hook manh hon" in content
    assert source_post["content_text"] in content
