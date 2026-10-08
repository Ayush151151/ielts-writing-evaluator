"""Core logic: build the prompt, call the LLM, validate and score the result.

Design choice: the LLM does the language judgement (it scores the four IELTS
criteria and finds errors). Plain Python does everything that must be exact:
word counting, JSON validation, and the official band-rounding rule.
LLMs are unreliable at arithmetic, so we never ask the model for the overall band.
"""

import json
import math
import re
from pathlib import Path

import yaml

import llm_client

BASE_DIR = Path(__file__).parent

CRITERIA = (
    "task_response",
    "coherence_cohesion",
    "lexical_resource",
    "grammatical_range_accuracy",
)


# ---------------------------------------------------------------- loading
def load_yaml(filename: str) -> dict:
    with open(BASE_DIR / filename, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ------------------------------------------------------------- input checks
def count_words(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def check_essay(essay: str, task_type: str, min_words: dict) -> list:
    """Return a list of warning strings. Raise ValueError if the essay is unusable."""
    if not essay or not essay.strip():
        raise ValueError("The essay is empty.")
    words = count_words(essay)
    if words < 30:
        raise ValueError(
            f"The essay has only {words} words, which is too short to evaluate."
        )
    warnings = []
    required = min_words[task_type]
    if words < required:
        warnings.append(
            f"Under the word limit: {words} words, but {task_type.replace('task', 'Task ')} "
            f"needs at least {required}. This lowers the Task Response band in real IELTS."
        )
    return warnings


# ------------------------------------------------------------ prompt building
def build_user_prompt(template: str, task_type: str, question: str, essay: str) -> str:
    return template.format(
        task_type=task_type,
        question=question.strip() or "(No question provided)",
        essay=essay.strip(),
        word_count=count_words(essay),
    )


# ----------------------------------------------------------- response parsing
def parse_json_response(text: str) -> dict:
    """Extract a JSON object from the model reply, even if it added ``` fences or chatter."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("The model reply did not contain a JSON object.")
        return json.loads(cleaned[start : end + 1])


def round_half_band(value: float) -> float:
    """Round to the nearest 0.5 (clamped to 0-9)."""
    return min(9.0, max(0.0, math.floor(value * 2 + 0.5) / 2))


def calculate_overall_band(bands: list) -> float:
    """Official IELTS rule: average of the four criteria, rounded to the nearest half band.

    6.25 rounds up to 6.5, 6.75 rounds up to 7.0, 6.2 rounds down to 6.0.
    """
    return round_half_band(sum(bands) / len(bands))


def validate_result(data: dict) -> dict:
    """Make sure the structure is what the UI expects; clean up bands; add overall band."""
    if "criteria" not in data:
        raise ValueError("Missing 'criteria' in model reply.")

    bands = []
    for name in CRITERIA:
        block = data["criteria"].get(name)
        if not isinstance(block, dict) or "band" not in block:
            raise ValueError(f"Missing criterion '{name}' in model reply.")
        block["band"] = round_half_band(float(block["band"]))
        block.setdefault("feedback", "")
        block.setdefault("strengths", [])
        block.setdefault("weaknesses", [])
        bands.append(block["band"])

    data.setdefault("errors", [])
    data.setdefault("vocabulary_upgrades", [])
    data.setdefault("improved_paragraph", {})
    data.setdefault("top_priorities", [])
    data["overall_band"] = calculate_overall_band(bands)
    return data


# ------------------------------------------------------------------ main API
def evaluate_essay(
    essay: str,
    question: str,
    task_type: str,
    provider: str | None = None,
    retries: int = 1,
) -> dict:
    """Evaluate one essay. Returns the validated result dict (with 'warnings' added)."""
    config = load_yaml("config.yaml")
    prompts = load_yaml("prompts.yaml")

    provider = provider or config["provider"]
    warnings = check_essay(essay, task_type, config["min_words"])
    user_prompt = build_user_prompt(
        prompts["user_template"], task_type, question, essay
    )

    last_error = None
    for _ in range(retries + 1):
        raw = llm_client.generate(
            provider=provider,
            model=config["models"][provider],
            system_prompt=prompts["system_prompt"],
            user_prompt=user_prompt,
            temperature=config["temperature"],
            max_tokens=config["max_tokens"],
        )
        try:
            result = validate_result(parse_json_response(raw))
            result["warnings"] = warnings
            result["word_count"] = count_words(essay)
            return result
        except (ValueError, json.JSONDecodeError, TypeError, KeyError) as exc:
            last_error = exc  # malformed reply: ask again

    raise ValueError(f"Could not get a valid evaluation from the model: {last_error}")
