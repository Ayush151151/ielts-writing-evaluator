"""Streamlit user interface. Run with:  streamlit run app.py"""

import json

import streamlit as st
from dotenv import load_dotenv

import evaluator
from llm_client import LLMError

load_dotenv()

st.set_page_config(page_title="IELTS Writing Evaluator", page_icon="✍️", layout="wide")

CRITERIA_LABELS = {
    "task_response": "Task Response",
    "coherence_cohesion": "Coherence & Cohesion",
    "lexical_resource": "Lexical Resource",
    "grammatical_range_accuracy": "Grammar Range & Accuracy",
}

config = evaluator.load_yaml("config.yaml")


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("Settings")
    provider = st.selectbox(
        "LLM provider",
        options=list(config["models"].keys()),
        index=list(config["models"].keys()).index(config["provider"]),
    )
    st.caption(f"Model: `{config['models'][provider]}`")
    task_type = st.radio(
        "Task type",
        options=["task2", "task1"],
        format_func=lambda t: "Task 2 (essay)" if t == "task2" else "Task 1 (report)",
    )
    st.caption(f"Minimum words: {config['min_words'][task_type]}")
    if task_type == "task1":
        st.info(
            "Text only: for Task 1, describe the chart or data in the question box, "
            "since images are not analysed."
        )


# --------------------------------------------------------------------- input
st.title("✍️ IELTS Writing Evaluator")
st.write("Paste your essay to get a band score, error corrections and a study plan.")

question = st.text_area(
    "Question / task prompt",
    height=100,
    placeholder="Some people think that ... To what extent do you agree or disagree?",
)

uploaded = st.file_uploader("Or upload your essay as a .txt file", type=["txt"])
default_text = uploaded.read().decode("utf-8", errors="ignore") if uploaded else ""
essay = st.text_area("Your essay", value=default_text, height=300)
st.caption(f"Word count: {evaluator.count_words(essay)}")

run = st.button("Evaluate my essay", type="primary")


# ------------------------------------------------------------------- results
def show_results(result: dict) -> None:
    for warning in result["warnings"]:
        st.warning(warning)

    st.subheader("Band scores")
    cols = st.columns(5)
    cols[0].metric("Overall", result["overall_band"])
    for col, key in zip(cols[1:], CRITERIA_LABELS):
        col.metric(CRITERIA_LABELS[key], result["criteria"][key]["band"])

    st.subheader("Criterion feedback")
    for key, label in CRITERIA_LABELS.items():
        block = result["criteria"][key]
        with st.expander(f"{label}: Band {block['band']}"):
            st.write(block["feedback"])
            left, right = st.columns(2)
            left.markdown("**Strengths**")
            for item in block["strengths"]:
                left.markdown(f"- {item}")
            right.markdown("**To improve**")
            for item in block["weaknesses"]:
                right.markdown(f"- {item}")

    st.subheader("Errors found")
    if result["errors"]:
        st.dataframe(
            [
                {
                    "Your text": e.get("original", ""),
                    "Correction": e.get("correction", ""),
                    "Type": e.get("type", ""),
                    "Why": e.get("explanation", ""),
                }
                for e in result["errors"]
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write("No major errors found.")

    if result["vocabulary_upgrades"]:
        st.subheader("Vocabulary upgrades")
        for item in result["vocabulary_upgrades"]:
            better = ", ".join(item.get("better", []))
            st.markdown(f"- **{item.get('original', '')}** → {better}")

    paragraph = result["improved_paragraph"]
    if paragraph.get("rewritten"):
        st.subheader("Weakest paragraph, rewritten one band higher")
        before, after = st.columns(2)
        before.markdown("**Original**")
        before.write(paragraph.get("original", ""))
        after.markdown("**Improved**")
        after.write(paragraph["rewritten"])
        st.caption(paragraph.get("why_better", ""))

    st.subheader("Top priorities to practise")
    for i, item in enumerate(result["top_priorities"], start=1):
        st.markdown(f"{i}. {item}")

    st.download_button(
        "Download full report (JSON)",
        data=json.dumps(result, indent=2, ensure_ascii=False),
        file_name="ielts_report.json",
        mime="application/json",
    )


if run:
    try:
        with st.spinner("The examiner is marking your essay..."):
            result = evaluator.evaluate_essay(
                essay=essay, question=question, task_type=task_type, provider=provider
            )
        show_results(result)
    except ValueError as exc:
        st.error(str(exc))
    except LLMError as exc:
        st.error(f"LLM problem: {exc}")
