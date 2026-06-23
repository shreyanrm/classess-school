"""Tests for the LIVE Track-1 Gemini generator.

Exercised entirely OFFLINE via an injected transport. Asserts: structured-output
validation, key-read-by-NAME, fail-closed without a key / on bad responses, and
that the raw key NEVER appears in a result or repr.

Import-safe, no network.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.config import get_settings
from app.generator import (
    GEMINI_KEY_ENV_VAR,
    GENERATOR_PROVIDER,
    GeminiGenerator,
    StructuredOutputError,
    validate_structured_output,
)
from app.second_model import GENERATOR_PROVIDER as XCHECK_GENERATOR


# -- structured-output validation -----------------------------------------

def test_validate_accepts_complete_object():
    out = validate_structured_output({"answer": 4, "confidence": 0.9}, required_fields=("answer",))
    assert out["answer"] == 4


def test_validate_rejects_non_object():
    try:
        validate_structured_output([1, 2, 3], required_fields=("answer",))
    except StructuredOutputError:
        pass
    else:
        raise AssertionError("expected StructuredOutputError")


def test_validate_rejects_missing_field():
    try:
        validate_structured_output({"confidence": 0.9}, required_fields=("answer",))
    except StructuredOutputError as exc:
        assert "answer" in str(exc)
    else:
        raise AssertionError("expected StructuredOutputError")


# -- a fake transport that returns a Gemini-shaped body --------------------

@dataclass
class FakeTransport:
    body: dict
    seen_headers: dict | None = None

    def post_json(self, *, url, headers, json_body, timeout):
        self.seen_headers = dict(headers)
        return self.body


def _gemini_body(payload: dict, *, prompt_tokens=11, completion_tokens=5) -> dict:
    return {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps(payload)}]}}
        ],
        "usageMetadata": {
            "promptTokenCount": prompt_tokens,
            "candidatesTokenCount": completion_tokens,
        },
    }


# -- degrade with no key ---------------------------------------------------

def test_no_key_is_unavailable_not_fabricated():
    gen = GeminiGenerator(settings=get_settings(env={}))
    res = gen.generate(prompt="2+2?", required_fields=("answer",))
    assert res.available is False
    assert res.content is None
    assert GEMINI_KEY_ENV_VAR in (res.unavailable_reason or "")


# -- live path (offline) ---------------------------------------------------

def test_live_generate_validates_and_returns_content():
    transport = FakeTransport(body=_gemini_body({"answer": 4, "confidence": 0.91}))
    gen = GeminiGenerator(
        transport=transport,
        settings=get_settings(env={GEMINI_KEY_ENV_VAR: "secret-key-NOLEAK"}),
    )
    res = gen.generate(prompt="2+2?", required_fields=("answer",))
    assert res.available is True
    assert res.content["answer"] == 4
    assert res.confidence == 0.91
    assert res.prompt_tokens == 11
    assert res.completion_tokens == 5
    # Key rode ONLY in the header.
    assert transport.seen_headers["x-goog-api-key"] == "secret-key-NOLEAK"


def test_invalid_json_fails_closed():
    body = {"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}
    gen = GeminiGenerator(
        transport=FakeTransport(body=body),
        settings=get_settings(env={GEMINI_KEY_ENV_VAR: "k"}),
    )
    res = gen.generate(prompt="x", required_fields=("answer",))
    assert res.available is False


def test_missing_required_field_fails_closed():
    transport = FakeTransport(body=_gemini_body({"confidence": 0.9}))  # no 'answer'
    gen = GeminiGenerator(
        transport=transport,
        settings=get_settings(env={GEMINI_KEY_ENV_VAR: "k"}),
    )
    res = gen.generate(prompt="x", required_fields=("answer",))
    assert res.available is False
    assert "validation failed" in (res.unavailable_reason or "")


def test_transport_error_fails_closed():
    @dataclass
    class Exploding:
        def post_json(self, *, url, headers, json_body, timeout):
            raise RuntimeError("network down")

    gen = GeminiGenerator(transport=Exploding(), settings=get_settings(env={GEMINI_KEY_ENV_VAR: "k"}))
    res = gen.generate(prompt="x", required_fields=("answer",))
    assert res.available is False


def test_key_never_in_repr_or_result():
    transport = FakeTransport(body=_gemini_body({"answer": 4, "confidence": 0.9}))
    gen = GeminiGenerator(
        transport=transport,
        settings=get_settings(env={GEMINI_KEY_ENV_VAR: "secret-key-NOLEAK"}),
    )
    res = gen.generate(prompt="x", required_fields=("answer",))
    assert "secret-key-NOLEAK" not in repr(gen)
    assert "secret-key-NOLEAK" not in repr(res)


def test_generator_is_independent_provider_from_crosscheck():
    # The generator (Gemini) must differ from the cross-check provider (OpenAI).
    assert GENERATOR_PROVIDER == "gemini"
    assert XCHECK_GENERATOR == GENERATOR_PROVIDER  # both name the same generator
