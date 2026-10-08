"""Thin wrapper around the LLM providers.

The rest of the project only calls `generate()`. It does not know which
provider is being used, so switching providers is a config change, not a
code change.
"""

import os
import time

# Error text that means "temporary problem, try again" (busy server, rate limit).
RETRYABLE = ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED")
MAX_ATTEMPTS = 4

# Give up on a single API request after this many seconds instead of waiting forever.
REQUEST_TIMEOUT_SECONDS = 120


class LLMError(Exception):
    """Raised when the LLM call fails or the API key is missing."""


def _require_key(env_var: str) -> str:
    key = os.environ.get(env_var)
    if not key:
        raise LLMError(
            f"{env_var} is not set. Copy .env.example to .env and add your key."
        )
    return key


def _call_gemini(model, system_prompt, user_prompt, temperature, max_tokens) -> str:
    # Imported here so you only need the SDK of the provider you actually use.
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=_require_key("GEMINI_API_KEY"),
        http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_SECONDS * 1000),  # needs milliseconds
    )
    response = client.models.generate_content(
        model=model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",  # ask Gemini for JSON directly
        ),
    )
    return response.text


def _call_anthropic(model, system_prompt, user_prompt, temperature, max_tokens) -> str:
    import anthropic

    client = anthropic.Anthropic(
        api_key=_require_key("ANTHROPIC_API_KEY"),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text


_PROVIDERS = {
    "gemini": _call_gemini,
    "anthropic": _call_anthropic,
}


def generate(
    provider: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 3000,
) -> str:
    """Send a prompt to the chosen provider and return the raw text reply.

    Temporary errors (busy server, rate limit) are retried automatically with
    a growing wait. Permanent errors (wrong key, wrong model) fail immediately.
    Every failed attempt is printed to the terminal so you can see what happened.
    """
    if provider not in _PROVIDERS:
        raise LLMError(
            f"Unknown provider '{provider}'. Choose from: {', '.join(_PROVIDERS)}"
        )

    last_exc = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return _PROVIDERS[provider](
                model, system_prompt, user_prompt, temperature, max_tokens
            )
        except LLMError:
            raise
        except Exception as exc:  # network errors, quota errors, bad model name...
            last_exc = exc
            print(
                f"[attempt {attempt + 1}/{MAX_ATTEMPTS}] "
                f"{type(exc).__name__}: {str(exc)[:150]}",
                flush=True,
            )
            temporary = any(code in str(exc) for code in RETRYABLE)
            if not temporary or attempt == MAX_ATTEMPTS - 1:
                break
            time.sleep(2 * 2**attempt)  # waits 2s, 4s, 8s between tries

    raise LLMError(f"{provider} API call failed: {last_exc}") from last_exc