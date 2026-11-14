"""
Centralised Groq client for ScaleAI.

Usage:
    from .groq_client import groq_chat, test_groq_connection
    result = groq_chat(messages, model, schema_cls=MyModel, temperature=0.2)

groq_chat() tries Groq's structured JSON output first (json_schema mode).
If the model does not support it, or the response cannot be parsed, it falls back
to JSON object mode with system schema guidance and validates the payload with Pydantic.

API key: read from settings.groq_api_key - never logged, never exposed to frontend.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, TypeVar

from groq import APIConnectionError, APIStatusError, Groq, RateLimitError
from pydantic import BaseModel, ValidationError

from ..config import settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# ---- Secret Redaction Patterns ----
SECRET_PATTERNS = [
    (re.compile(r"gsk_[a-zA-Z0-9]{20,}", re.I), "[REDACTED_GROQ_KEY]"),
    (re.compile(r"sk-[a-zA-Z0-9]{20,}", re.I), "[REDACTED_KEY]"),
    (re.compile(r"AIza[0-9A-Za-z-_]{35}", re.I), "[REDACTED_KEY]"),
    (re.compile(r"ghp_[a-zA-Z0-9]{36}", re.I), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"bearer\s+[a-zA-Z0-9_.\-]{20,}", re.I), "Bearer [REDACTED_TOKEN]"),
    (re.compile(r"(['\"]?password['\"]?\s*[:=]\s*['\"])[^'\"]+(['\"])", re.I), r"\1[REDACTED]\2"),
]


def redact_secrets(text: str) -> str:
    """Mask sensitive tokens and credentials from logs or prompts."""
    if not text:
        return text
    sanitized = text
    for pattern, replacement in SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


# ---- singleton -------------------------------------------------------------------
_client: Groq | None = None


def get_groq_client() -> Groq | None:
    """Return a shared Groq client, or None when the API key is not configured."""
    global _client
    if _client is not None:
        return _client
    if not settings.groq_api_key:
        return None
    _client = Groq(
        api_key=settings.groq_api_key,
        timeout=float(settings.groq_timeout),
        max_retries=0,  # we handle retries ourselves for fine-grained backoff and logging
    )
    return _client


def reset_groq_client() -> None:
    """Reset the singleton instance (useful for testing or config reload)."""
    global _client
    _client = None


def groq_chat(
    messages: list[dict],
    model: str,
    schema_cls: type[T] | None = None,
    temperature: float | None = None,
) -> T | dict | None:
    """
    Send a chat completion request to Groq with retry and timeout handling.

    Parameters
    ----------
    messages:    OpenAI-style message list (role / content dicts).
    model:       Groq model identifier.
    schema_cls:  If provided, attempt structured JSON output and validate with Pydantic.
    temperature: Sampling temperature (defaults to settings.groq_temperature).

    Returns
    -------
    Validated Pydantic instance when schema_cls is given, raw dict otherwise.
    Returns None on unrecoverable failure.
    """
    client = get_groq_client()
    if client is None:
        log.warning("Groq API key not configured; skipping AI call")
        return None

    temp = temperature if temperature is not None else settings.groq_temperature
    max_retries = max(1, settings.groq_max_retries)
    delay = 2.0

    # Sanitize messages to avoid prompt leakage
    sanitized_messages = [
        {"role": m.get("role", "user"), "content": redact_secrets(m.get("content", ""))}
        for m in messages
    ]

    for attempt in range(1, max_retries + 1):
        try:
            raw = _do_request(client, sanitized_messages, model, schema_cls, temp)
            if schema_cls is not None:
                return _parse(raw, schema_cls)
            return raw
        except RateLimitError as exc:
            if attempt >= max_retries:
                log.error("Groq rate limit reached after %d attempts on model %s", attempt, model)
                return None
            log.warning("Groq rate limit on attempt %d/%d; waiting %.1fs", attempt, max_retries, delay)
            time.sleep(delay)
            delay *= 2
        except (APIConnectionError, APIStatusError) as exc:
            if attempt >= max_retries:
                log.error("Groq API error after %d attempts on model %s: %s", attempt, model, type(exc).__name__)
                return None
            log.warning("Groq API error attempt %d/%d (%s); retrying in %.1fs", attempt, max_retries, type(exc).__name__, delay)
            time.sleep(delay)
            delay *= 2
        except ValidationError as val_err:
            log.warning("Schema validation failed on attempt %d/%d for model %s: %s", attempt, max_retries, model, str(val_err)[:200])
            if attempt >= max_retries:
                return None
            time.sleep(1.0)
        except Exception as exc:
            log.exception("Unexpected error in groq_chat (model=%s): %s", model, redact_secrets(str(exc)))
            return None
    return None


def _clean_json_content(content: str) -> str:
    """Strip code fences, whitespace, or commentary around a JSON object."""
    cleaned = content.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def _do_request(
    client: Groq,
    messages: list[dict],
    model: str,
    schema_cls: type[BaseModel] | None,
    temperature: float,
) -> dict:
    """Make the actual API call. Returns parsed JSON dict from the response."""
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    if schema_cls is not None:
        json_schema = schema_cls.model_json_schema()
        # 1. First attempt: Groq json_schema strict mode
        try:
            resp = client.chat.completions.create(
                **kwargs,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema_cls.__name__,
                        "schema": json_schema,
                        "strict": True,
                    },
                },
            )
            content = resp.choices[0].message.content or "{}"
            return json.loads(_clean_json_content(content))
        except (APIStatusError, json.JSONDecodeError, KeyError, Exception) as schema_err:
            log.debug(
                "json_schema mode unsupported or failed for model %s (%s); falling back to json_object",
                model,
                type(schema_err).__name__,
            )

        # 2. Fallback: JSON object mode with schema specification in system message
        schema_hint = json.dumps(json_schema, indent=2)
        hint_msg = {
            "role": "system",
            "content": (
                "Return ONLY a valid JSON object conforming exactly to this JSON Schema. "
                "Do NOT wrap in markdown code fences. Do NOT add any extra commentary.\n\n"
                f"{schema_hint}"
            ),
        }
        resp = client.chat.completions.create(
            **kwargs,
            messages=[hint_msg] + messages,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        return json.loads(_clean_json_content(content))

    # Plain json_object mode when no schema is required
    resp = client.chat.completions.create(**kwargs, response_format={"type": "json_object"})
    content = resp.choices[0].message.content or "{}"
    return json.loads(_clean_json_content(content))


def _parse(raw: dict, schema_cls: type[T]) -> T:
    """Validate raw dict against the Pydantic schema."""
    return schema_cls.model_validate(raw)


def test_groq_connection() -> dict:
    """
    Check whether the Groq API is configured and reachable.
    Never exposes secrets or private keys in the response.
    """
    configured = bool(settings.groq_api_key)
    if not configured:
        return {
            "configured": False,
            "connected": False,
            "model": settings.groq_code_model,
            "latency_ms": None,
            "message": "Groq API key is not configured.",
        }

    client = get_groq_client()
    if client is None:
        return {
            "configured": True,
            "connected": False,
            "model": settings.groq_code_model,
            "latency_ms": None,
            "message": "Failed to initialize Groq client.",
        }

    start_time = time.time()
    try:
        # Send a minimal ping completion
        resp = client.chat.completions.create(
            model=settings.groq_code_model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
            temperature=0.0,
        )
        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "configured": True,
            "connected": True,
            "model": settings.groq_code_model,
            "latency_ms": latency_ms,
            "message": "Groq API is reachable and functional.",
        }
    except Exception as exc:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        err_msg = type(exc).__name__
        log.warning("Groq connection test failed: %s", err_msg)
        return {
            "configured": True,
            "connected": False,
            "model": settings.groq_code_model,
            "latency_ms": latency_ms,
            "message": f"Connection check failed: {err_msg}",
        }
