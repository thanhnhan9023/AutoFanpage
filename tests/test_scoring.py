import pytest

from autofanpage.scoring import (
    score_insight, total, assign_type, APPROVAL_THRESHOLD,
)


def test_total_sums_the_four_axes():
    assert total({"relevance": 5, "novelty": 4, "viral": 4, "actionable": 3}) == 16


def test_score_empty_string_returns_low_scores():
    s = score_insight("", topic="AI automation")
    assert all(v == 1 for v in s.values())
    assert total(s) < APPROVAL_THRESHOLD


def test_score_on_topic_with_numbers_and_actionable_verbs_is_high():
    s = score_insight(
        "Using AI automation, teams reduced ticket backlog by 40% in 6 weeks — try batching similar tickets first.",
        topic="AI automation",
    )
    assert s["relevance"] >= 4
    assert s["actionable"] >= 4
    assert s["viral"] >= 4
    assert total(s) >= APPROVAL_THRESHOLD


def test_score_generic_opinion_is_below_threshold():
    s = score_insight("AI is the future.", topic="AI automation")
    assert total(s) < APPROVAL_THRESHOLD


def test_assign_type_maps_breaking_news_language():
    assert assign_type("OpenAI announced GPT-5 yesterday") == "news"
    assert assign_type("Google launches a new Gemini release today") == "news"


def test_assign_type_maps_howto_language():
    assert assign_type("How to set up an AI chatbot in 5 minutes") == "guide"
    assert assign_type("3 steps to automate invoice processing") == "guide"


def test_assign_type_maps_opinion_language():
    assert assign_type("Why most AI agents still fail in production") == "opinion"
    assert assign_type("Unpopular opinion: LLMs aren't ready for ops") == "opinion"


def test_assign_type_maps_case_study_language():
    assert assign_type("How Acme Corp cut support cost 60% with AI") == "case_study"
    assert assign_type("A real-world case of AI in manufacturing") == "case_study"


def test_assign_type_falls_back_to_news():
    assert assign_type("The token cost of large context windows") == "news"
