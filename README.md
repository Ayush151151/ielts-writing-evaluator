# IELTS Writing Evaluator

An NLP project that uses a Large Language Model (through API calls) to mark IELTS
Writing essays the way an examiner would. You paste an essay and get:

- A band score (0 to 9) for each of the four official criteria, plus the overall band
- A list of specific errors with corrections and the grammar rule behind each one
- Vocabulary upgrades for basic words you used
- Your weakest paragraph rewritten about one band higher
- The three most valuable things to practise next

## How it works

```
essay + question
      |
      v
 evaluator.py  --- checks the input (word count, empty text)
      |         --- fills the prompt template from prompts.yaml
      v
 llm_client.py --- sends the prompt to Gemini or Claude (set in config.yaml)
      |
      v
 evaluator.py  --- parses the JSON reply, validates it, rounds the bands,
      |            calculates the overall band with the official IELTS rule
      v
   app.py      --- shows everything in a Streamlit web page
```

**Why the work is split this way.** The LLM does the language judgement: scoring
against the band descriptors, finding errors, rewriting text. Plain Python does
everything that has to be exact: counting words, validating the JSON structure and
calculating the overall band. LLMs are unreliable at arithmetic, so the prompt tells
the model *not* to calculate the overall band; `calculate_overall_band()` does it.

**NLP tasks involved:** rubric-based text classification (band scoring), grammatical
error detection and correction, vocabulary enrichment, text rewriting (style transfer
to a higher level), and structured information extraction (JSON output).

## Project structure

| File | Purpose |
|------|---------|
| `app.py` | Streamlit user interface |
| `evaluator.py` | Core logic: validation, prompt building, JSON parsing, band calculation |
| `llm_client.py` | The only file that talks to an LLM API (Gemini or Anthropic) |
| `prompts.yaml` | The prompt file: examiner system prompt, band descriptors, JSON schema, user template |
| `config.yaml` | Provider, model names, temperature, token limit, minimum word counts |
| `.env.example` | Template for your API keys |
| `sample_essays/` | A Task 2 essay with deliberate mistakes for testing |
| `tests/` | Unit tests (no API key needed) |

## Setup

1. Install Python 3.10 or newer.
2. Create a virtual environment and install the packages:
   ```
   python -m venv .venv
   .venv\Scripts\activate        # Windows
   source .venv/bin/activate     # Mac / Linux
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and paste in your API key.
   - Gemini (free tier): https://aistudio.google.com/apikey
   - Anthropic: https://console.anthropic.com
4. In `config.yaml`, set `provider` to `gemini` or `anthropic`. If a model name has been
   retired, replace it under `models:` with a current one.
5. Run the app:
   ```
   streamlit run app.py
   ```
6. Paste the question and essay from `sample_essays/task2_sample.txt` to try it.

## Running the tests

```
pytest
```

The tests replace the LLM with a fake, so they run offline and need no API key.

## Prompt design (prompts.yaml)

- **Role and calibration:** the model is told it is an experienced examiner and that most
  candidates land between 5.0 and 7.0, which stops it giving every essay a 7 or 8.
- **Band descriptors inside the prompt:** each criterion has Band 5 / 7 / 9 anchors, so the
  scores follow the real rubric instead of the model's general impression.
- **Evidence rule:** errors must be copied exactly from the essay, so every correction can be
  traced back to the text.
- **Strict JSON schema:** one fixed structure, so the app can parse and display it reliably.
  If the reply is malformed, the code retries once.
- **Prompt-injection guard:** text inside the essay is treated as text to mark, never as
  instructions.
- **Low temperature (0.2):** keeps scoring consistent from run to run.

## Limitations

- This is an AI estimate, not an official IELTS score. Treat bands as guidance.
- Task 1 works from text only; describe the chart or data in the question box.
- Scores can vary by about half a band between runs and between models.
