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

from groq import APIConnectionError, APIStatusError, BadRequestError, Groq, RateLimitError
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


# ---- singleton & model resolution ----------------------------------------------
_client: Groq | None = None
_resolved_model_cache: dict[str, str] = {}

PREFERRED_MODELS = [
    "qwen/qwen3.8-27b",
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
]


def resolve_model(preferred: str) -> str:
    """Check if the requested model exists on this Groq account; if not, return the best available alternative."""
    if preferred in _resolved_model_cache:
        return _resolved_model_cache[preferred]
    client = get_groq_client()
    if not client:
        return preferred
    try:
        models_data = client.models.list().data
        available_ids = {m.id for m in models_data}
        if preferred in available_ids:
            _resolved_model_cache[preferred] = preferred
            return preferred
        for cand in PREFERRED_MODELS:
            if cand in available_ids:
                log.info("Groq model '%s' not available; automatically using '%s'", preferred, cand)
                _resolved_model_cache[preferred] = cand
                return cand
        for m_id in available_ids:
            if not any(x in m_id.lower() for x in ["whisper", "guard", "audio"]):
                _resolved_model_cache[preferred] = m_id
                return m_id
    except Exception as exc:
        log.warning("Could not query Groq model list (%s); keeping %s", exc, preferred)
    return preferred


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
    global _client, _resolved_model_cache
    _client = None
    _resolved_model_cache.clear()


def _parse_retry_delay(exc: Exception, default_delay: float) -> float:
    """Extract wait time from RateLimitError headers or message."""
    # 1. First inspect the exception message text which contains the exact wait time from Groq
    msg = str(exc)
    m = re.search(r"try again in ([0-9.]+)\s*(m?s)", msg, re.IGNORECASE)
    if not m:
        m = re.search(r"in ([0-9.]+)\s*(m?s)", msg, re.IGNORECASE)
    if m:
        try:
            val = float(m.group(1))
            unit = m.group(2).lower()
            sec = val / 1000.0 if unit == "ms" else val
            return max(2.0, sec + 1.0)
        except Exception:
            pass

    # 2. Check response headers
    try:
        resp = getattr(exc, "response", None)
        if resp and hasattr(resp, "headers"):
            headers = resp.headers
            if "retry-after" in headers:
                try:
                    return max(2.0, float(headers["retry-after"]) + 1.0)
                except Exception:
                    pass
            if "x-ratelimit-reset-tokens" in headers:
                raw = headers["x-ratelimit-reset-tokens"].strip()
                try:
                    if raw.endswith("ms"):
                        sec = float(raw[:-2]) / 1000.0
                    elif raw.endswith("s"):
                        sec = float(raw[:-1])
                    else:
                        sec = float(raw)
                    return max(2.0, sec + 1.0)
                except Exception:
                    pass
    except Exception:
        pass
    return default_delay


def repair_json(raw: str) -> str:
    """Attempt to repair common JSON syntax issues like unclosed quotes, brackets, or braces."""
    s = raw.strip()
    if not s:
        return "{}"
    start_brace = s.find("{")
    start_bracket = s.find("[")
    if start_brace == -1 and start_bracket == -1:
        return s
    if start_bracket != -1 and (start_brace == -1 or start_bracket < start_brace):
        s = s[start_bracket:]
    else:
        s = s[start_brace:]

    # Remove trailing comma before closing tokens
    s = re.sub(r",\s*([\]\}])", r"\1", s)

    in_quote = False
    escape = False
    stack = []
    for ch in s:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_quote = not in_quote
            continue
        if not in_quote:
            if ch in ("{", "["):
                stack.append("}" if ch == "{" else "]")
            elif ch in ("}", "]"):
                if stack and stack[-1] == ch:
                    stack.pop()

    if in_quote:
        s += '"'
    s = s.rstrip().rstrip(",")
    while stack:
        s += stack.pop()
    return s


def _clean_json_content(content: str) -> str:
    """Strip code fences, whitespace, commentary, or think tags around a JSON object."""
    cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    if "```json" in cleaned:
        parts = cleaned.split("```json", 1)[1].split("```", 1)
        cleaned = parts[0].strip()
    elif "```" in cleaned:
        parts = cleaned.split("```", 1)[1].split("```", 1)
        cleaned = parts[0].strip()

    try:
        json.loads(cleaned)
        return cleaned
    except Exception:
        pass

    m = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
    if m:
        candidate = m.group(1).strip()
        try:
            json.loads(candidate)
            return candidate
        except Exception:
            pass

    return repair_json(cleaned)


def _do_request(
    client: Groq,
    messages: list[dict],
    model: str,
    schema_cls: type[BaseModel] | None,
    temperature: float,
    max_tokens: int = 500,
) -> dict:
    """Make the actual API call. Returns parsed JSON dict from the response."""
    resolved_model = resolve_model(model)
    safe_max_tokens = min(max_tokens, 500)

    if schema_cls is not None:
        raw_schema = schema_cls.model_json_schema()
        props = raw_schema.get("properties", {})
        keys_list = list(props.keys())
        hint_msg = {
            "role": "system",
            "content": (
                f"You must return ONLY a single, valid JSON object with keys: {keys_list}. "
                "Do NOT wrap in markdown code fences. Do NOT include thought tags or extra commentary. Keep values concise."
            ),
        }
        all_messages = [hint_msg] + messages
        try:
            resp = client.chat.completions.create(
                model=resolved_model,
                messages=all_messages,
                temperature=temperature,
                max_tokens=safe_max_tokens,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content or "{}"
            cleaned = _clean_json_content(content)
            return json.loads(cleaned)
        except (BadRequestError, json.JSONDecodeError) as format_err:
            # Check if Groq captured failed_generation in the error body
            body = getattr(format_err, "body", None)
            if isinstance(body, dict):
                fg = body.get("error", {}).get("failed_generation")
                if fg:
                    try:
                        repaired = repair_json(fg)
                        return json.loads(_clean_json_content(repaired))
                    except Exception:
                        pass

            log.debug(
                "json_object mode failed for model %s (%s); trying raw completion",
                resolved_model,
                type(format_err).__name__,
            )
            resp = client.chat.completions.create(
                model=resolved_model,
                messages=all_messages,
                temperature=temperature,
                max_tokens=safe_max_tokens,
            )
            content = resp.choices[0].message.content or "{}"
            cleaned = _clean_json_content(content)
            return json.loads(cleaned)

    # Plain json_object mode when no schema is required
    resp = client.chat.completions.create(
        model=resolved_model,
        messages=messages,
        temperature=temperature,
        max_tokens=safe_max_tokens,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content or "{}"
    cleaned = _clean_json_content(content)
    return json.loads(cleaned)


def _parse(raw: dict, schema_cls: type[T]) -> T:
    """Validate raw dict against the Pydantic schema."""
    return schema_cls.model_validate(raw)


def groq_chat(
    messages: list[dict],
    model: str,
    schema_cls: type[T] | None = None,
    temperature: float | None = None,
    max_tokens: int = 500,
) -> T | dict | None:
    """
    Send a chat completion request to Groq with retry and timeout handling.

    Parameters
    ----------
    messages:    OpenAI-style message list (role / content dicts).
    model:       Groq model identifier.
    schema_cls:  If provided, attempt structured JSON output and validate with Pydantic.
    temperature: Sampling temperature (defaults to settings.groq_temperature).
    max_tokens:  Upper limit on generated tokens to preserve TPM/OTPM quota.

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
    max_retries = max(5, settings.groq_max_retries)
    delay = 3.0

    # Sanitize messages to avoid prompt leakage
    sanitized_messages = [
        {"role": m.get("role", "user"), "content": redact_secrets(m.get("content", ""))}
        for m in messages
    ]

    for attempt in range(1, max_retries + 1):
        try:
            raw = _do_request(client, sanitized_messages, model, schema_cls, temp, max_tokens)
            if schema_cls is not None:
                return _parse(raw, schema_cls)
            return raw
        except RateLimitError as exc:
            if attempt >= max_retries:
                log.error("Groq rate limit reached after %d attempts on model %s", attempt, model)
                return None
            wait_time = _parse_retry_delay(exc, delay)
            wait_time = min(65.0, max(wait_time, delay))
            log.warning("Groq rate limit on attempt %d/%d; waiting %.1fs for token reset", attempt, max_retries, wait_time)
            time.sleep(wait_time)
            delay = min(25.0, delay * 1.5)
        except (BadRequestError, json.JSONDecodeError) as parse_err:
            log.warning("JSON parse issue on attempt %d/%d for model %s: %s", attempt, max_retries, model, str(parse_err)[:150])
            if attempt >= max_retries:
                return None
            time.sleep(delay)
            delay = min(15.0, delay * 1.5)
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
        model = resolve_model(settings.groq_code_model)
        # Send a minimal ping completion
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
            temperature=0.0,
        )
        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "configured": True,
            "connected": True,
            "model": model,
            "latency_ms": latency_ms,
            "message": f"Groq API is reachable and functional (using model: {model}).",
        }
    except Exception as exc:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        err_msg = type(exc).__name__
        detail = str(exc)
        log.warning("Groq connection test failed: %s - %s", err_msg, detail)
        return {
            "configured": True,
            "connected": False,
            "model": settings.groq_code_model,
            "latency_ms": latency_ms,
            "message": f"Connection check failed: {err_msg} ({detail[:120]})",
        }
