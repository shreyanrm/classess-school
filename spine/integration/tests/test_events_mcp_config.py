"""Event seam (consent-gated, PII-free), MCP surface (ladder + child-safety),
and config degradation (env names only)."""

from __future__ import annotations

from app import (
    ActivityEventContext,
    CanonicalRef,
    EmitRefused,
    IntegrationSettings,
    LearningActivityStatement,
    Standard,
    Verb,
    build_activity_event,
    emit_activity,
)
from app.adapters.mcp import MCPCallError, default_surface
from app.config import env_var_name


def _resolved_actor() -> CanonicalRef:
    return CanonicalRef(Standard.XAPI, "xapi:abc", "uuid-1")


def _context() -> ActivityEventContext:
    return ActivityEventContext(purpose="instruction", consent_ref="consent-1")


# ---------------------------------------------------------------------------
# Event seam
# ---------------------------------------------------------------------------
def test_build_activity_event_is_attributed_and_pii_free():
    stmt = LearningActivityStatement(
        actor=_resolved_actor(), verb=Verb.SCORED,
        object_id="act:1", result_score_scaled=0.9, result_success=True,
    )
    event = build_activity_event(stmt, _context(), source_standard="xapi")
    assert event["canonical_uuid"] == "uuid-1"
    assert event["consent_ref"] == "consent-1"
    assert event["purpose"] == "instruction"
    assert event["payload"]["score_scaled"] == 0.9
    assert event["type"] == "attempt.recorded"


def test_event_refuses_without_consent():
    stmt = LearningActivityStatement(actor=_resolved_actor(), verb=Verb.VIEWED, object_id="a")
    ctx = ActivityEventContext(purpose="instruction", consent_ref="")
    raised = False
    try:
        build_activity_event(stmt, ctx, source_standard="xapi")
    except EmitRefused:
        raised = True
    assert raised


def test_event_refuses_unresolved_actor():
    stmt = LearningActivityStatement(
        actor=CanonicalRef(Standard.XAPI, "xapi:abc", None),  # unresolved
        verb=Verb.VIEWED, object_id="a",
    )
    raised = False
    try:
        build_activity_event(stmt, _context(), source_standard="xapi")
    except EmitRefused:
        raised = True
    assert raised


def test_emit_activity_degraded_without_emitter():
    stmt = LearningActivityStatement(actor=_resolved_actor(), verb=Verb.VIEWED, object_id="a")
    out = emit_activity(stmt, _context(), source_standard="xapi")
    assert out["degraded"] is True
    assert out["event_id"] is None
    assert out["event"]["canonical_uuid"] == "uuid-1"


def test_emit_activity_with_emitter_returns_id():
    class _Emitter:
        def emit(self, event_input):
            assert event_input["consent_ref"] == "consent-1"
            return "evt-77"

    stmt = LearningActivityStatement(actor=_resolved_actor(), verb=Verb.COMPLETED, object_id="a")
    out = emit_activity(stmt, _context(), source_standard="xapi", emitter=_Emitter())
    assert out["degraded"] is False
    assert out["event_id"] == "evt-77"


# ---------------------------------------------------------------------------
# MCP surface
# ---------------------------------------------------------------------------
def test_mcp_lists_tools_and_runs_safe_inline():
    surface = default_surface()
    names = {t["name"] for t in surface.list_tools()}
    assert "fluid.qti.parse" in names
    assert "fluid.lti.ags.scores" in names
    out = surface.call("fluid.connectors.health", {})
    assert out["prepared"] is False
    assert out["result"] == {"ok": True}


def test_mcp_consequential_tool_is_prepared_not_executed():
    surface = default_surface()
    out = surface.call("fluid.lti.ags.scores", {"line_item_url": "u", "score_given": 5})
    assert out["prepared"] is True
    assert out["requires_human_approval"] is True


def test_mcp_unknown_tool_raises():
    surface = default_surface()
    raised = False
    try:
        surface.call("does.not.exist")
    except MCPCallError:
        raised = True
    assert raised


def test_mcp_free_text_refused_without_guard():
    from app.adapters.mcp import MCPServerSurface, MCPTool

    surface = MCPServerSurface()  # no text_guard wired
    surface.register(MCPTool(
        name="fluid.note",
        description="free text note",
        input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
        handler=lambda a: {"ok": True},
        free_text_fields=("text",),
    ))
    raised = False
    try:
        surface.call("fluid.note", {"text": "hello"})
    except MCPCallError:
        raised = True
    assert raised, "free-text must be refused when no child-safety guard is wired"


def test_mcp_free_text_blocked_by_guard():
    from app.adapters.mcp import MCPServerSurface, MCPTool

    class _Guard:
        def is_safe(self, text):
            return "unsafe" not in text

    surface = MCPServerSurface(text_guard=_Guard())
    surface.register(MCPTool(
        name="fluid.note",
        description="free text note",
        input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
        handler=lambda a: {"ok": True},
        free_text_fields=("text",),
    ))
    safe = surface.call("fluid.note", {"text": "all good"})
    assert safe.get("result") == {"ok": True}
    blocked = surface.call("fluid.note", {"text": "this is unsafe"})
    assert blocked.get("blocked") is True
    assert blocked.get("reason") == "child-safety"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def test_config_degrades_with_names_only(monkeypatch):
    for key in list(__import__("os").environ):
        if key.startswith("CLSS_INTEGRATION_DEV_"):
            monkeypatch.delenv(key, raising=False)
    s = IntegrationSettings()
    assert s.degraded is True
    reasons = s.degraded_reasons()
    # reasons are NAMES only, never values
    assert "clss.integration.dev.gateway_base_url" in reasons
    assert all(r.startswith("clss.integration.dev.") for r in reasons)


def test_env_var_name_mapping():
    assert env_var_name("clss.integration.dev.gateway_base_url") == \
        "CLSS_INTEGRATION_DEV_GATEWAY_BASE_URL"


def test_track1_track2_are_separate_fields():
    s = IntegrationSettings()
    # Track 2 slot exists from the start as a distinct field (INVARIANT 11).
    assert hasattr(s, "track2_connector_url")
    assert hasattr(s, "oneroster_base_url")  # a Track 1 external endpoint name
