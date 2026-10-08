import time

import yaml
from dotenv import load_dotenv

load_dotenv()

import llm_client

with open("config.yaml", encoding="utf-8") as f:
    config = yaml.safe_load(f)

model = config["models"]["gemini"]
print("Using model:", model, flush=True)

start = time.time()
try:
    reply = llm_client.generate(
        provider="gemini",
        model=model,
        system_prompt="Reply with JSON only.",
        user_prompt='Return {"ok": true}',
        temperature=0.2,
        max_tokens=200,
    )
    print("Reply:", reply)
except Exception as exc:
    print("ERROR:", exc)
print(f"Took {time.time() - start:.1f} seconds")