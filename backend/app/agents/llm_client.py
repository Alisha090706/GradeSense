"""
LLM Client — provider-agnostic wrapper.

Every agent that needs an LLM (Assignment, Rubric, Feedback, Class Insight /
Analytics, Tutor) calls `complete()` from here rather than importing a
provider SDK directly — this is the one place that knows which provider is
configured, so swapping providers (or adding a second one for fallback
when a free-tier quota is hit) never touches agent logic.

Resolution order: GEMINI_API_KEY (spec's primary choice) -> GROQ_API_KEY
(kept for continuity with the original prototype, and as a fallback with a
more generous free tier for heavy local testing) -> offline mode.

Offline mode returns None, which every caller treats as "use your own
deterministic fallback logic" — this is deliberate: it's what let the
original prototype run zero-config, and it's worth preserving here so the
whole platform stays demoable without any API key configured.
"""
from app.core.config import get_settings

settings = get_settings()

GEMINI_MODEL = "gemini-2.0-flash"
GROQ_MODEL = "llama-3.3-70b-versatile"


def _provider() -> str | None:
    if settings.GEMINI_API_KEY:
        return "gemini"
    if settings.GROQ_API_KEY:
        return "groq"
    return None


def is_live() -> bool:
    return _provider() is not None


def _complete_gemini(system_prompt: str, user_prompt: str, max_tokens: int) -> str:
    import google.generativeai as genai

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL, system_instruction=system_prompt)
    resp = model.generate_content(
        user_prompt, generation_config={"max_output_tokens": max_tokens}
    )
    return resp.text


def _complete_groq(system_prompt: str, user_prompt: str, max_tokens: int) -> str:
    from groq import Groq

    client = Groq(api_key=settings.GROQ_API_KEY)
    resp = client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return resp.choices[0].message.content


def complete(system_prompt: str, user_prompt: str, max_tokens: int = 800) -> str | None:
    """Returns plain text completion, or None if no provider is configured
    (signals the caller to use its own offline fallback logic)."""
    provider = _provider()
    if provider == "gemini":
        return _complete_gemini(system_prompt, user_prompt, max_tokens)
    if provider == "groq":
        return _complete_groq(system_prompt, user_prompt, max_tokens)
    return None
