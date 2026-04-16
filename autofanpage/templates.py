"""Post-type templates used by the writing-agent."""
from __future__ import annotations

from typing import TypedDict


class PostTemplate(TypedDict):
    hook_shape: str
    body_shape: str
    cta: str
    hashtag_hint: str
    first_comment_shape: str


TEMPLATES: dict[str, PostTemplate] = {
    "news": {
        "hook_shape": "Lead with the breaking event in one tight sentence. Name the actor and the change.",
        "body_shape": "150-250 words. 2-3 short paragraphs summarizing the news, then one paragraph on what it means for a business audience. No speculation beyond the source.",
        "cta": "Ask how this affects the reader's own work in a single question.",
        "hashtag_hint": "3-5 hashtags. 1 about the topic, 1 about the actor, 1 general (#AI #Automation).",
        "first_comment_shape": "Drop the canonical source URL in the first line. Follow with 2-3 related links if multiple URLs are provided.",
    },
    "guide": {
        "hook_shape": "Lead with a concrete numeric result that the guide will help the reader reproduce.",
        "body_shape": "150-250 words. Numbered 3-5 steps, each actionable, each under 40 words. No motivation filler.",
        "cta": "Ask which step the reader will try first.",
        "hashtag_hint": "3-5 hashtags. Include 1 how-to-flavored tag and 1 topic tag.",
        "first_comment_shape": "Expand each step into 2-3 concrete sub-bullets. This is the place for the long form.",
    },
    "opinion": {
        "hook_shape": "Lead by inverting a widely held belief. State the unpopular view plainly in one sentence.",
        "body_shape": "150-250 words. Steelman the common view in one paragraph, then present the counter-argument in one paragraph. Avoid absolutes.",
        "cta": "Ask which side the reader is on and invite a comment.",
        "hashtag_hint": "3-5 hashtags. 1 topic tag + 1 debate-flavored tag.",
        "first_comment_shape": "Post one follow-up question that sharpens the debate. No links.",
    },
    "case_study": {
        "hook_shape": "Lead with before/after numbers from a named company.",
        "body_shape": "150-250 words. Structure: context, AI solution applied, measured outcome with numbers.",
        "cta": "Ask whether the reader's business has tried this.",
        "hashtag_hint": "3-5 hashtags. Include industry tag + 1 metric tag (#ROI, #Growth).",
        "first_comment_shape": "Link to the source of the case study. Add a 2-3 line breakdown of the headline metric.",
    },
}


POST_TYPE_BY_SLOT: tuple[str, str, str, str] = (
    "news", "guide", "opinion", "case_study",
)


def slot_time(post_times: list[str], slot_index: int) -> str:
    return post_times[slot_index]
