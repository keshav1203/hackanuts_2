import pytest
from pydantic import BaseModel

from app.config import settings
from app.services.groq_client import (
    _clean_json_content,
    get_groq_client,
    redact_secrets,
    repair_json,
    reset_groq_client,
    resolve_model,
    test_groq_connection as check_groq_connection,
)


class SampleModel(BaseModel):
    name: str
    score: int


def test_secret_redaction():
    text = "Error with key gsk_1234567890abcdef1234567890 and Bearer eyJhbGciOiJIUzI1NiJ9.test and password: 'secretpassword'"
    redacted = redact_secrets(text)
    assert "gsk_1234567890abcdef1234567890" not in redacted
    assert "secretpassword" not in redacted
    assert "[REDACTED" in redacted


def test_clean_json_content():
    raw_md = "```json\n{\"score\": 90, \"name\": \"ScaleAI\"}\n```"
    cleaned = _clean_json_content(raw_md)
    assert cleaned == '{"score": 90, "name": "ScaleAI"}'

    plain = '  {"score": 90}  '
    assert _clean_json_content(plain) == '{"score": 90}'


def test_repair_json():
    # Test truncated JSON repair
    truncated = '{"name": "ScaleAI", "score": 95, "tags": ["fast", "reliable"'
    repaired = repair_json(truncated)
    import json
    data = json.loads(repaired)
    assert data["name"] == "ScaleAI"
    assert data["score"] == 95
    assert "fast" in data["tags"]

    # Test trailing comma
    with_comma = '{"score": 90,}'
    assert json.loads(repair_json(with_comma)) == {"score": 90}


def test_resolve_model_fallback():
    # If a decommissioned or unavailable model is requested, it falls back to an available model
    resolved = resolve_model("llama-3.3-70b-versatile")
    assert resolved in ("qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "llama-3.3-70b-versatile")


def test_groq_connection_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "")
    reset_groq_client()
    res = check_groq_connection()
    assert res["configured"] is False
    assert res["connected"] is False
    assert "API key" in res["message"]


def test_groq_client_singleton(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "gsk_testdummykey12345678901234567890")
    reset_groq_client()
    client1 = get_groq_client()
    client2 = get_groq_client()
    assert client1 is not None
    assert client1 is client2
    reset_groq_client()
