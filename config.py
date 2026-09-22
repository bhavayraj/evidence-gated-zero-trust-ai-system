"""
config.py

One place for LLM client setup. planner.py, recovery.py, and judge.py all
import CLIENT and MODEL from here — never instantiate their own client.
"""

import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai import errors

load_dotenv()  # reads .env in the project root, if present

MODEL = "gemini-3.6-flash"  # bump here if Google retires this one too — see error text, it names the replacement
API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY not found. Copy .env.example to .env and fill in your key."
    )

CLIENT = genai.Client(api_key=API_KEY)

# Status codes worth retrying: rate limit + transient server-side failures.
# NOT retried: 400 (bad request), 403 (auth) — retrying those just burns
# time during a live demo since the same request will fail the same way.
_RETRYABLE_CODES = {429, 500, 502, 503, 504}
_MAX_TRANSIENT_RETRIES = 2
_BACKOFF_SECONDS = 1.5


def _generate(contents: str, config: "types.GenerateContentConfig"):
    """
    Every direct call to the Gemini API goes through here so retry behavior
    for transient failures (rate limits, 5xx, dropped connections) lives in
    exactly one place. This is separate from — and sits underneath — the
    JSON-validity retry loop in call_llm_structured(), which handles a
    different failure mode (the API answered fine, but the content was
    malformed). A network blip should not crash a live demo the way a bad
    JSON response is allowed to.
    """
    last_exc = None
    for attempt in range(_MAX_TRANSIENT_RETRIES + 1):
        try:
            return CLIENT.models.generate_content(model=MODEL, contents=contents, config=config)
        except errors.APIError as e:
            last_exc = e
            if getattr(e, "code", None) not in _RETRYABLE_CODES or attempt == _MAX_TRANSIENT_RETRIES:
                raise
        except (ConnectionError, TimeoutError) as e:
            last_exc = e
            if attempt == _MAX_TRANSIENT_RETRIES:
                raise
        time.sleep(_BACKOFF_SECONDS * (attempt + 1))  # 1.5s, then 3s
    raise last_exc  # pragma: no cover — loop always returns or raises above


def call_llm(system: str, user: str, max_tokens: int = 1500) -> str:
    """Thin wrapper so every LLM call in the project goes through one function."""
    response = _generate(
        user,
        types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
        ),
    )
    return response.text or ""


def _strip_code_fences(raw: str) -> str:
    """Models frequently wrap JSON in ```json ... ``` even when told not to."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]          # drop opening fence (and optional "json" tag)
        if text.startswith("json"):
            text = text[4:]
        if "```" in text:
            text = text.rsplit("```", 1)[0]
    return text.strip()


def call_llm_structured(system: str, user: str, model_cls, max_tokens: int = 1500):
    """
    Calls the LLM, parses the response as JSON, and validates it against a
    Pydantic model. On parse OR validation failure, retries ONCE with the
    actual error fed back to the model. On a second failure, raises loudly —
    this is intentional: a silently-corrupted plan/patch/judgment is far
    worse than a visible crash during a hackathon demo.

    Every caller (planner.py, recovery.py, judge.py) should use this instead
    of raw json.loads(call_llm(...)).

    Uses Gemini's native JSON mode (response_mime_type="application/json")
    so the model is constrained to emit JSON at generation time — the
    code-fence stripping and retry loop below stay in place as a defensive
    second layer, since JSON mode still doesn't guarantee schema validity.
    """
    import json
    from pydantic import ValidationError

    attempt_user_prompt = user
    last_error = None
    cleaned = ""

    for attempt in range(2):
        if last_error:
            attempt_user_prompt = (
                f"{user}\n\n"
                f"Your previous response failed with this error:\n{last_error}\n"
                f"Respond again with ONLY corrected valid JSON, no prose, no code fences."
            )

        response = _generate(
            attempt_user_prompt,
            types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
            ),
        )
        raw = response.text or ""
        cleaned = _strip_code_fences(raw)

        try:
            data = json.loads(cleaned)
            return model_cls(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = str(e)
            continue

    raise RuntimeError(
        f"LLM failed to produce valid {model_cls.__name__} after 2 attempts. "
        f"Last error: {last_error}\nLast raw output: {cleaned[:500]}"
    )
