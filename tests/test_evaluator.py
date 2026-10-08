"""Tests for the pure logic. They never call a real LLM (it is replaced by a fake)."""

import json

import pytest

import evaluator

MIN_WORDS = {"task1": 150, "task2": 250}


def make_reply(bands=(6.0, 6.5, 6.0, 5.5)):
    names = evaluator.CRITERIA
    return {
        "criteria": {
            name: {"band": band, "feedback": "ok", "strengths": ["a"], "weaknesses": ["b"]}
            for name, band in zip(names, bands)
        },
        "errors": [],
        "vocabulary_upgrades": [],
        "improved_paragraph": {},
        "top_priorities": ["x", "y", "z"],
    }


# ------------------------------------------------------------ band maths
@pytest.mark.parametrize(
    "bands, expected",
    [
        ([6.0, 6.0, 6.0, 6.0], 6.0),
        ([6.0, 6.5, 6.0, 6.5], 6.5),  # average 6.25 -> 6.5
        ([7.0, 7.0, 6.5, 6.5], 7.0),  # average 6.75 -> 7.0
        ([6.0, 6.0, 6.5, 6.0], 6.0),  # average 6.125 -> 6.0
        ([9.0, 9.0, 9.0, 9.0], 9.0),
    ],
)
def test_overall_band_rounding(bands, expected):
    assert evaluator.calculate_overall_band(bands) == expected


def test_round_half_band_is_clamped():
    assert evaluator.round_half_band(11) == 9.0
    assert evaluator.round_half_band(-2) == 0.0


# ------------------------------------------------------------ input checks
def test_count_words():
    assert evaluator.count_words("It's a well-known fact.") == 4


def test_empty_essay_rejected():
    with pytest.raises(ValueError):
        evaluator.check_essay("   ", "task2", MIN_WORDS)


def test_very_short_essay_rejected():
    with pytest.raises(ValueError):
        evaluator.check_essay("Too short.", "task2", MIN_WORDS)


def test_under_limit_gives_warning():
    essay = "word " * 100
    warnings = evaluator.check_essay(essay, "task2", MIN_WORDS)
    assert len(warnings) == 1


def test_long_enough_has_no_warning():
    essay = "word " * 260
    assert evaluator.check_essay(essay, "task2", MIN_WORDS) == []


# ------------------------------------------------------------ JSON parsing
def test_parse_plain_json():
    assert evaluator.parse_json_response('{"a": 1}') == {"a": 1}


def test_parse_json_with_code_fence():
    assert evaluator.parse_json_response('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_with_chatter():
    assert evaluator.parse_json_response('Sure! {"a": 1} Hope this helps.') == {"a": 1}


def test_parse_without_json_raises():
    with pytest.raises(ValueError):
        evaluator.parse_json_response("no json here")


# ------------------------------------------------------------ validation
def test_validate_adds_overall_band():
    result = evaluator.validate_result(make_reply())
    assert result["overall_band"] == 6.0  # (6 + 6.5 + 6 + 5.5) / 4 = 6.0


def test_validate_rounds_odd_bands_from_model():
    result = evaluator.validate_result(make_reply(bands=(6.3, 6.3, 6.3, 6.3)))
    assert result["criteria"]["task_response"]["band"] == 6.5


def test_validate_rejects_missing_criterion():
    reply = make_reply()
    del reply["criteria"]["lexical_resource"]
    with pytest.raises(ValueError):
        evaluator.validate_result(reply)


# ------------------------------------------------------------ full flow
ESSAY = "This is a test sentence for the evaluator. " * 40  # > 250 words


def test_evaluate_essay_with_fake_llm(monkeypatch):
    monkeypatch.setattr(
        evaluator.llm_client, "generate", lambda **kwargs: json.dumps(make_reply())
    )
    result = evaluator.evaluate_essay(ESSAY, "Some question", "task2", provider="gemini")
    assert result["overall_band"] == 6.0
    assert result["warnings"] == []
    assert result["word_count"] > 250


def test_evaluate_essay_retries_after_bad_reply(monkeypatch):
    replies = iter(["not json at all", json.dumps(make_reply())])
    monkeypatch.setattr(
        evaluator.llm_client, "generate", lambda **kwargs: next(replies)
    )
    result = evaluator.evaluate_essay(ESSAY, "Q", "task2", provider="gemini")
    assert result["overall_band"] == 6.0


def test_evaluate_essay_gives_up_after_retries(monkeypatch):
    monkeypatch.setattr(evaluator.llm_client, "generate", lambda **kwargs: "garbage")
    with pytest.raises(ValueError):
        evaluator.evaluate_essay(ESSAY, "Q", "task2", provider="gemini", retries=1)


def test_prompt_template_fills_in_correctly():
    prompts = evaluator.load_yaml("prompts.yaml")
    text = evaluator.build_user_prompt(prompts["user_template"], "task2", "My question", "My essay text")
    assert "My question" in text and "My essay text" in text and "{" not in text
