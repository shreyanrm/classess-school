"""The LIVE generate-and-verify path through the orchestrator (INVARIANT 7 + 11).

Proves the REAL call path is taken WHEN CONFIGURED and DEGRADES cleanly when not:

  - With a Track-1 router key AND a Gemini generator key present (both by NAME),
    a non-deterministic capability actually CALLS the live Gemini generator
    through :class:`~app.orchestrator.LiveTrack1Provider`. The model + the
    independent second-model cross-check are both mocked offline (no paid call,
    no network), and the confidence gate serves only when both agree.
  - With NO router key, the route is unavailable and there is no deterministic
    handle, so the orchestrator REFUSES — it never fabricates content.
  - The live model failing closed (no content) keeps the gate shut.

Entirely OFFLINE: the Gemini transport and the second model are injected.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from app.config import get_settings
from app.generator import GEMINI_KEY_ENV_VAR, GeminiGenerator
from app.orchestrator import Intent, LiveTrack1Provider, Orchestrator
from app.router import ModelRouter, Track1Config, env_var_name


def _rid() -> str:
    return str(uuid.uuid4())


# -- offline fakes ---------------------------------------------------------

@dataclass
class FakeGeminiTransport:
    """A Gemini-shaped response for the injected generator transport."""

    payload: dict
    seen_headers: dict | None = None

    def post_json(self, *, url, headers, json_body, timeout):
        self.seen_headers = dict(headers)
        return {
            "candidates": [{"content": {"parts": [{"text": json.dumps(self.payload)}]}}],
            "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 6},
        }


class _AgreeingSecondModel:
    def cross_check(self, *, task_class, content):
        return (True, 0.95)


def _router_with_track1_key() -> ModelRouter:
    key = env_var_name(Track1Config().provider_key_env)
    return ModelRouter(env={key: "router-key-present-by-name"})


def _live_provider_with_key(payload: dict) -> tuple[LiveTrack1Provider, FakeGeminiTransport]:
    transport = FakeGeminiTransport(payload=payload)
    gen = GeminiGenerator(
        transport=transport,
        settings=get_settings(env={GEMINI_KEY_ENV_VAR: "gemini-key-NOLEAK"}),
    )
    return LiveTrack1Provider(generator=gen), transport


# -- the live path is TAKEN when configured --------------------------------

def test_live_track1_path_is_taken_when_configured_and_served():
    """Router key present => route available => the orchestrator calls the LIVE
    Gemini provider; the mocked second model agrees => the gate serves."""
    provider, transport = _live_provider_with_key(
        {"answer": "Mitosis has four phases.", "confidence": 0.93}
    )
    orch = Orchestrator(
        router=_router_with_track1_key(),
        provider=provider,
        second_model=_AgreeingSecondModel(),
    )
    res = orch.handle(Intent(
        request_id=_rid(),
        capability="conversation.companion-turn",
        purpose="companion_dialogue",
        payload={"prompt": "How many phases in mitosis?"},
    ))
    assert res.provider_available is True
    assert res.verification is not None
    assert res.verification.served is True
    assert res.refused is False
    assert res.content["answer"] == "Mitosis has four phases."
    assert res.track == 1
    # The live model was actually called: the key rode ONLY in the header.
    assert transport.seen_headers["x-goog-api-key"] == "gemini-key-NOLEAK"


def test_live_path_selected_by_orchestrator_without_explicit_provider():
    """Even with NO explicit provider wired, an available Track-1 route makes the
    orchestrator pick the live provider (it builds GeminiGenerator under the
    hood). With no Gemini key the generator fails closed => the gate withholds —
    proving the path is wired AND fails safe."""
    # Router has a key, but the Gemini GENERATOR key is absent in this process,
    # so the live generator the orchestrator builds returns no content.
    orch = Orchestrator(
        router=_router_with_track1_key(),
        second_model=_AgreeingSecondModel(),
    )
    res = orch.handle(Intent(
        request_id=_rid(),
        capability="conversation.companion-turn",
        purpose="companion_dialogue",
        payload={"prompt": "hello"},
    ))
    # The provider was the live one (route available => selected), but with no
    # generator key it produced no candidate => withheld, never fabricated.
    assert res.verification is not None
    assert res.verification.served is False
    assert res.content is None


# -- DEGRADES cleanly when NOT configured ----------------------------------

def test_no_router_key_degrades_to_refusal_never_fabricates():
    """No Track-1 router key => route unavailable AND no deterministic handle =>
    the orchestrator refuses; it does not invent content."""
    orch = Orchestrator(
        router=ModelRouter(env={}),  # no key
        second_model=_AgreeingSecondModel(),
    )
    res = orch.handle(Intent(
        request_id=_rid(),
        capability="conversation.companion-turn",
        purpose="companion_dialogue",
        payload={"prompt": "hello"},
    ))
    assert res.refused is True
    assert res.provider_available is False
    assert res.content is None
    # The refusal names the env var to set, never a fabricated answer.
    assert "CLSS_AIFABRIC_DEV_TRACK1_PROVIDER_KEY" in (res.detail or "")


def test_live_content_withheld_when_second_model_abstains():
    """Configured live model + content, but the DEFAULT second model abstains
    (no cross-check key) => the gate stays closed (INVARIANT 7)."""
    provider, _ = _live_provider_with_key({"answer": "anything", "confidence": 0.99})
    orch = Orchestrator(
        router=_router_with_track1_key(),
        provider=provider,
        # No second_model => make_second_model() returns the abstaining default.
    )
    res = orch.handle(Intent(
        request_id=_rid(),
        capability="conversation.companion-turn",
        purpose="companion_dialogue",
        payload={"prompt": "x"},
    ))
    assert res.verification.served is False
    assert res.refused is True
