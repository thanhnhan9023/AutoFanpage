"""Pure scoring and type-assignment heuristics for the review-agent.

Scoring is deliberately deterministic. Every insight gets four integer scores
(1..5) on Relevance / Novelty / Viral / Actionable, summed into ``total``.
Insights with ``total >= APPROVAL_THRESHOLD`` (14) move to Writing.

Type assignment uses keyword heuristics — news / guide / opinion / case_study —
with ``news`` as the safe default for insights that don't match any bucket.
"""
from __future__ import annotations

import re
from typing import TypedDict


class Scores(TypedDict):
    relevance: int
    novelty: int
    viral: int
    actionable: int


APPROVAL_THRESHOLD = 14


_ACTIONABLE_VERBS = re.compile(
    r"\b(try|use|implement|build|set up|adopt|switch|apply|measure|track|"
    r"automate|deploy|run|configure|start|install|test)\b",
    re.IGNORECASE,
)
_NOVELTY_MARKERS = re.compile(
    r"\b(announced|launched|released|unveiled|new|first|breakthrough|"
    r"surpris(ed|ing)|counterintuitive)\b",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"\b\d+(\.\d+)?\s?%?\b")
_OPINION_MARKERS = re.compile(
    r"\b(why|opinion|unpopular|hot take|debate|controvers(y|ial)|myth)\b",
    re.IGNORECASE,
)
_GUIDE_MARKERS = re.compile(
    r"\b(how to|step(s)?|tutorial|guide|checklist|\d+\s+(ways?|steps?|tips?))\b",
    re.IGNORECASE,
)
_CASE_MARKERS = re.compile(
    r"\b(case study|real[- ]world|company|corp\.?|inc\.?|ltd\.?|"
    r"reduced|increased|cut\b|saved|grew)\b.*\b\d+\s?%",
    re.IGNORECASE,
)
_CASE_KEYWORDS = re.compile(
    r"\b(case study|real[- ]world)\b",
    re.IGNORECASE,
)
_NEWS_MARKERS = re.compile(
    r"\b(today|yesterday|this week|announce(d)?|releases?|launches?)\b",
    re.IGNORECASE,
)


def _topic_relevance(insight: str, topic: str) -> int:
    if not insight:
        return 1
    tokens = {t for t in re.findall(r"\w+", topic.lower()) if len(t) >= 2}
    if not tokens:
        return 3
    text = insight.lower()
    hits = sum(1 for t in tokens if t in text)
    if hits == 0:
        return 2
    if hits == 1:
        return 3
    if hits == 2:
        return 4
    return 5


def _novelty(insight: str) -> int:
    if not insight:
        return 1
    if _NOVELTY_MARKERS.search(insight):
        return 5
    if _NUMBER.search(insight):
        return 4
    return 2 if len(insight) < 50 else 3


def _viral(insight: str) -> int:
    if not insight:
        return 1
    if _NUMBER.search(insight) and len(insight) > 40:
        return 5
    if _NUMBER.search(insight):
        return 4
    if "?" in insight or "!" in insight:
        return 3
    return 2


def _actionable(insight: str) -> int:
    if not insight:
        return 1
    verb = bool(_ACTIONABLE_VERBS.search(insight))
    has_step = bool(re.search(r"\b(first|step|then|after|next)\b", insight, re.IGNORECASE))
    if verb and has_step:
        return 5
    if verb:
        return 4
    if has_step:
        return 3
    return 2


def score_insight(insight: str, *, topic: str) -> Scores:
    return {
        "relevance":  _topic_relevance(insight, topic),
        "novelty":    _novelty(insight),
        "viral":      _viral(insight),
        "actionable": _actionable(insight),
    }


def total(scores: Scores) -> int:
    return sum(scores.values())


def assign_type(insight: str) -> str:
    if _CASE_MARKERS.search(insight):
        return "case_study"
    if _CASE_KEYWORDS.search(insight):
        return "case_study"
    if _GUIDE_MARKERS.search(insight):
        return "guide"
    if _OPINION_MARKERS.search(insight):
        return "opinion"
    if _NEWS_MARKERS.search(insight):
        return "news"
    return "news"
