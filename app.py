"""Streamlit user interface. Run with: streamlit run app.py"""

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

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Source+Serif+4:wght@500;600;700&display=swap');
:root { --ink:#202923; --muted:#68736b; --paper:#f6f5f0; --green:#315c48; --line:#e3e5dd; --white:#fff; }
.stApp { background:var(--paper); color:var(--ink); font-family:'DM Sans',sans-serif; }
[data-testid="stHeader"] { background:transparent; }
.block-container { max-width:1160px; padding:2.5rem 2rem 5rem; }
h1,h2,h3,h4 { font-family:'Source Serif 4',Georgia,serif !important; color:var(--ink); letter-spacing:-.025em; }
h1,h2,h3,h4 { color:#202923 !important; }
h1 { font-size:3.25rem !important; line-height:1.04 !important; max-width:760px; white-space:pre-line; }
h2 { margin-top:1.1rem !important; }
[data-testid="stSidebar"] { background:#eeede7; border-right:1px solid var(--line); }
[data-testid="stTextArea"] textarea { background:var(--white); border:1px solid var(--line); border-radius:8px; line-height:1.75; padding:1rem; }
[data-testid="stFileUploader"] section { background:#fff !important; border:1px dashed #9eafa2; border-radius:8px; color:var(--ink) !important; }
[data-testid="stFileUploader"] section * { color:var(--ink) !important; }
[data-testid="stFileUploader"] button { background:var(--green) !important; border:1px solid var(--green) !important; color:#fff !important; border-radius:5px !important; }
[data-testid="stFileUploader"] button * { color:#fff !important; }
.stButton>button,.stDownloadButton>button { border-radius:6px; min-height:2.8rem; padding:0 1rem; font-weight:600; }
.stButton>button[kind=primary] { background:var(--green); border-color:var(--green); }
[data-testid="stMetric"] { background:var(--white); border:1px solid var(--line); border-radius:8px; padding:1rem; }
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] *, [data-testid="stMetricValue"], [data-testid="stMetricValue"] * { opacity:1 !important; visibility:visible !important; }
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * { color:#4d5951 !important; }
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * { color:var(--green) !important; font-family:'Source Serif 4',Georgia,serif; }
[data-testid="stExpander"] { background:var(--white); border:1px solid var(--line); border-radius:8px; margin:.4rem 0; }
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * { color:#202923 !important; opacity:1 !important; visibility:visible !important; }
[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:8px; overflow:hidden; }
.eyebrow { color:#587261; font-size:.75rem; font-weight:700; letter-spacing:.14em; text-transform:uppercase; margin-bottom:.5rem; }
.lede { max-width:690px; color:#58635c; font-size:1.05rem; line-height:1.65; }
.score-note { color:#69756d; font-size:.88rem; }
hr { border-color:var(--line); }
@media(max-width:760px) { h1 { font-size:2.45rem !important; } .block-container { padding:1.4rem 1rem 3rem; } }
</style>
""", unsafe_allow_html=True)


with st.sidebar:
    st.caption("EXAM SETTINGS")
    st.header("Choose your task")
    task_type = st.radio(
        "Task type",
        options=["task2", "task1"],
        format_func=lambda t: "Task 2 · Essay" if t == "task2" else "Task 1 · Report",
        label_visibility="collapsed",
    )
    st.caption(f"Recommended minimum: {config['min_words'][task_type]} words")
    if task_type == "task1":
        st.caption("Describe the chart or data in the task prompt. Images are not analysed.")
    st.divider()
    st.caption("SCORING MODEL")
    provider = st.selectbox(
        "LLM provider",
        options=list(config["models"].keys()),
        index=list(config["models"].keys()).index(config["provider"]),
    )
    st.caption(f"Model: `{config['models'][provider]}`")


st.markdown('<p class="eyebrow">IELTS · WRITING WORKSHOP</p>', unsafe_allow_html=True)
st.title("IELTS Writing Assessment")
st.markdown('<p class="lede">Get a criterion by criterion score, useful corrections and a focused plan for your next practice session.</p>', unsafe_allow_html=True)
st.divider()

prompt_col, essay_col = st.columns([0.82, 1.55], gap="large")
with prompt_col:
    st.markdown("#### 01 · The task")
    question = st.text_area(
        "Question / task prompt",
        height=185,
        placeholder="Paste the full question here…",
        label_visibility="collapsed",
    )
    st.caption("Include the full prompt so your response can be checked against it.")
with essay_col:
    st.markdown("#### 02 · Your response")
    uploaded = st.file_uploader("Drop a .txt essay here", type=["txt"], label_visibility="collapsed")
    if uploaded:
        st.caption(f"Selected file: **{uploaded.name}**")
    default_text = uploaded.read().decode("utf-8", errors="ignore") if uploaded else ""
    essay = st.text_area(
        "Your essay",
        value=default_text,
        height=280,
        placeholder="Write or paste your response here…",
        label_visibility="collapsed",
    )
    word_count = evaluator.count_words(essay)
    minimum = config["min_words"][task_type]
    st.markdown(f'<p class="score-note">{word_count} words <span style="padding:0 .45rem">·</span> {minimum} word minimum</p>', unsafe_allow_html=True)

action_col, note_col = st.columns([1, 2.5], vertical_alignment="center")
with action_col:
    run = st.button("Get my review", type="primary", use_container_width=True)
with note_col:
    st.caption("Usually takes under a minute · Download the full report when it’s ready")


def show_results(result: dict) -> None:
    for warning in result["warnings"]:
        st.warning(warning)

    st.divider()
    st.markdown('<p class="eyebrow">YOUR REVIEW</p>', unsafe_allow_html=True)
    st.subheader("Band profile")
    cols = st.columns(5)
    cols[0].metric("Overall", result["overall_band"])
    for col, key in zip(cols[1:], CRITERIA_LABELS):
        col.metric(CRITERIA_LABELS[key], result["criteria"][key]["band"])

    st.subheader("Feedback by criterion")
    for key, label in CRITERIA_LABELS.items():
        block = result["criteria"][key]
        with st.expander(f"{label} · Band {block['band']}"):
            st.write(block["feedback"])
            left, right = st.columns(2)
            left.markdown("**Working well**")
            for item in block["strengths"]:
                left.markdown(f"- {item}")
            right.markdown("**Next to improve**")
            for item in block["weaknesses"]:
                right.markdown(f"- {item}")

    st.subheader("Corrections")
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
        st.subheader("A stronger version of your weakest paragraph")
        before, after = st.columns(2)
        with before:
            st.markdown("**Your paragraph**")
            st.write(paragraph.get("original", ""))
        with after:
            st.markdown("**One possible revision**")
            st.write(paragraph["rewritten"])
        st.caption(paragraph.get("why_better", ""))

    st.subheader("Your next practice steps")
    for i, item in enumerate(result["top_priorities"], start=1):
        st.markdown(f"**{i}.** {item}")

    st.download_button(
        "Download full report (JSON)",
        data=json.dumps(result, indent=2, ensure_ascii=False),
        file_name="ielts_report.json",
        mime="application/json",
    )


if run:
    try:
        with st.spinner("Reviewing your writing…"):
            result = evaluator.evaluate_essay(
                essay=essay, question=question, task_type=task_type, provider=provider
            )
        show_results(result)
    except ValueError as exc:
        st.error(str(exc))
    except LLMError as exc:
        st.error(f"LLM problem: {exc}")
