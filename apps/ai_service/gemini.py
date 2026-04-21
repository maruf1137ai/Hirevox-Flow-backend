"""AI provider wrapper for Hirevox.

Prefers OpenAI when OPENAI_API_KEY is set, falls back to Gemini.
Every AI call goes through `generate_json` or `generate_text`.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger("hirevox.ai")


class AIConfigurationError(RuntimeError):
    """Raised when no AI backend is configured."""


class AIResponseError(RuntimeError):
    """Raised when the AI returns an unusable response."""


class AIQuotaError(RuntimeError):
    """Raised when the AI provider returns a quota/rate-limit error (HTTP 429)."""


# ─── Provider selection ──────────────────────────────────────────────────

def _use_openai() -> bool:
    return bool(settings.OPENAI_API_KEY)


def is_configured() -> bool:
    return _use_openai() or bool(settings.GEMINI_API_KEY)


# ─── OpenAI implementation ───────────────────────────────────────────────

def _openai_client():
    import openai  # type: ignore
    return openai.OpenAI(api_key=settings.OPENAI_API_KEY)


def _openai_model(mode: str) -> str:
    if mode == "fast":
        return settings.OPENAI_FAST_MODEL
    return settings.OPENAI_REASONING_MODEL


def _openai_generate_text(
    prompt: str,
    *,
    system: str | None = None,
    history: list[dict] | None = None,
    mode: str = "reasoning",
    temperature: float = 0.7,
) -> str:
    import openai  # type: ignore

    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        for h in history:
            role = "assistant" if h["role"] == "model" else h["role"]
            messages.append({"role": role, "content": h["parts"][0]})
    messages.append({"role": "user", "content": prompt})

    try:
        client = _openai_client()
        response = client.chat.completions.create(
            model=_openai_model(mode),
            messages=messages,
            temperature=temperature,
        )
    except openai.RateLimitError as exc:
        raise AIQuotaError(str(exc)) from exc
    except openai.AuthenticationError as exc:
        raise AIConfigurationError(str(exc)) from exc

    text = response.choices[0].message.content if response.choices else None
    if not text:
        raise AIResponseError("OpenAI returned an empty response.")
    return text.strip()


def _openai_generate_json(
    prompt: str,
    *,
    system: str | None = None,
    mode: str = "reasoning",
    temperature: float = 0.4,
) -> Any:
    import openai  # type: ignore

    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system + "\nAlways respond with valid JSON only."})
    messages.append({"role": "user", "content": prompt})

    try:
        client = _openai_client()
        response = client.chat.completions.create(
            model=_openai_model(mode),
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
    except openai.RateLimitError as exc:
        raise AIQuotaError(str(exc)) from exc
    except openai.AuthenticationError as exc:
        raise AIConfigurationError(str(exc)) from exc

    text = response.choices[0].message.content if response.choices else None
    if not text:
        raise AIResponseError("OpenAI returned an empty JSON response.")

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("OpenAI returned non-JSON: %s", text[:500])
        raise AIResponseError("OpenAI did not return valid JSON.") from exc


# ─── Gemini implementation ───────────────────────────────────────────────

def _gemini_client():
    if not settings.GEMINI_API_KEY:
        raise AIConfigurationError(
            "No AI key configured. Add OPENAI_API_KEY or GEMINI_API_KEY to backend/.env."
        )
    import google.generativeai as genai  # type: ignore
    genai.configure(api_key=settings.GEMINI_API_KEY)
    return genai


def _gemini_model(mode: str) -> str:
    if mode == "fast":
        return settings.GEMINI_FAST_MODEL
    return settings.GEMINI_REASONING_MODEL


def _reraise_gemini_quota(exc: Exception) -> None:
    try:
        from google.api_core.exceptions import ResourceExhausted  # type: ignore
        if isinstance(exc, ResourceExhausted):
            raise AIQuotaError(str(exc)) from exc
    except ImportError:
        pass
    if type(exc).__name__ == "ResourceExhausted":
        raise AIQuotaError(str(exc)) from exc


def _gemini_generate_text(
    prompt: str,
    *,
    system: str | None = None,
    history: list[dict] | None = None,
    mode: str = "reasoning",
    temperature: float = 0.7,
) -> str:
    genai = _gemini_client()
    model = genai.GenerativeModel(model_name=_gemini_model(mode), system_instruction=system)
    generation_config = {"temperature": temperature}
    try:
        if history:
            chat = model.start_chat(history=history)
            response = chat.send_message(prompt, generation_config=generation_config)
        else:
            response = model.generate_content(prompt, generation_config=generation_config)
    except Exception as exc:
        _reraise_gemini_quota(exc)
        raise
    text = getattr(response, "text", None)
    if not text:
        raise AIResponseError("Gemini returned an empty response.")
    return text.strip()


def _gemini_generate_json(
    prompt: str,
    *,
    system: str | None = None,
    mode: str = "reasoning",
    temperature: float = 0.4,
) -> Any:
    genai = _gemini_client()
    model = genai.GenerativeModel(model_name=_gemini_model(mode), system_instruction=system)
    try:
        response = model.generate_content(
            prompt,
            generation_config={"temperature": temperature, "response_mime_type": "application/json"},
        )
    except Exception as exc:
        _reraise_gemini_quota(exc)
        raise
    text = getattr(response, "text", None)
    if not text:
        raise AIResponseError("Gemini returned an empty JSON response.")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("Gemini returned non-JSON: %s", text[:500])
        raise AIResponseError("Gemini did not return valid JSON.") from exc


# ─── Public API ──────────────────────────────────────────────────────────

def generate_text(
    prompt: str,
    *,
    system: str | None = None,
    history: list[dict] | None = None,
    mode: str = "reasoning",
    temperature: float = 0.7,
) -> str:
    if not is_configured():
        raise AIConfigurationError("No AI key configured. Add OPENAI_API_KEY to backend/.env.")
    if _use_openai():
        return _openai_generate_text(prompt, system=system, history=history, mode=mode, temperature=temperature)
    return _gemini_generate_text(prompt, system=system, history=history, mode=mode, temperature=temperature)


def generate_json(
    prompt: str,
    *,
    system: str | None = None,
    mode: str = "reasoning",
    temperature: float = 0.4,
) -> Any:
    if not is_configured():
        raise AIConfigurationError("No AI key configured. Add OPENAI_API_KEY to backend/.env.")
    if _use_openai():
        return _openai_generate_json(prompt, system=system, mode=mode, temperature=temperature)
    return _gemini_generate_json(prompt, system=system, mode=mode, temperature=temperature)


def transcribe_audio(audio_file: Any) -> str:
    """Convert speech to text using Whisper (OpenAI) or Gemini."""
    if not is_configured():
        raise AIConfigurationError("No AI key configured.")

    if _use_openai():
        client = _openai_client()
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
        return transcript.text

    # Gemini native multimodal transcription
    genai = _gemini_client()
    model = genai.GenerativeModel("gemini-1.5-flash")
    # For Gemini, we'd typically need to handle file uploads or pass bytes with mime_type.
    # Defaulting to OpenAI first as requested by user.
    raise NotImplementedError("Gemini STT implementation pending.")


def generate_speech(text: str, voice: str = "alloy") -> bytes:
    """Convert text to speech using OpenAI TTS."""
    if not _use_openai():
        # Fallback/Placeholder if only Gemini is configured
        raise AIConfigurationError("OpenAI TTS requires OPENAI_API_KEY.")

    client = _openai_client()
    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,  # alloy, echo, fable, onyx, nova, shimmer
        input=text,
    )
    return response.content
