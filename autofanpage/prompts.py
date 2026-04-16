"""Prompt builders for the writing-agent."""
from __future__ import annotations

from autofanpage.templates import PostTemplate


_SYSTEM = (
    "You are a senior Facebook content editor. Use only the insight and "
    "source URL provided. Do not invent statistics, company names, or "
    "events that are not in the insight text. If a requested numeric hook "
    "isn't supported, rephrase the hook qualitatively — never fabricate "
    "numbers."
)


def build_writing_prompt(
    *,
    insight: dict,
    template: PostTemplate,
    language: str,
) -> tuple[str, list[dict]]:
    msg = (
        f"Write one Facebook post in {language}. Target 150-250 words.\n\n"
        f"Post type: {insight['suggested_post_type']}.\n"
        f"Insight: {insight['insight']}\n"
        f"Suggested hook angle: {insight['hook_angle']}\n"
        f"Source URL (for reference only, do not inline): {insight['source_url']}\n\n"
        f"Hook shape: {template['hook_shape']}\n"
        f"Body shape: {template['body_shape']}\n"
        f"CTA shape: {template['cta']} Translate naturally into {language}.\n"
        f"Hashtags: {template['hashtag_hint']} Translate or keep in English.\n\n"
        f"Output only the post text. No preamble. No meta-commentary."
    )
    return _SYSTEM, [{"role": "user", "content": msg}]


def build_first_comment_prompt(
    *,
    insight: dict,
    template: PostTemplate,
    language: str,
    post_body: str,
) -> tuple[str, list[dict]]:
    msg = (
        f"Write the first comment in {language} to attach to the post below. "
        f"Shape: {template['first_comment_shape']}\n\n"
        f"Source URL: {insight['source_url']}\n"
        f"Insight: {insight['insight']}\n\n"
        f"--- POST ---\n{post_body}\n--- END ---\n\n"
        f"Output only the comment text. No preamble."
    )
    return _SYSTEM, [{"role": "user", "content": msg}]
