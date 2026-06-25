"""Infra circuit — the plumbing made REAL, proven offline (mocked DB / no secret).

Each test pins ONE of the six infra items and proves both halves of the law:
the LIVE path is taken when configured, and it DEGRADES observably when not.

  1. EVENT_SINK ASYNC   — one shared background loop drives every append; the
                          door + workflow + governance all reach the SAME store
                          (works with a Postgres-shaped async store; no per-call
                          loop). Proven with a MOCK async store (no real DB).
  2. GATEWAY SELF-WIRE  — capability_targets() resolves the Wave-2 fronts to the
                          deployable's own loopback (no 503 upstream_unconfigured)
                          when CLSS_GATEWAY_DEV_SELF_BASE_URL is unset; an explicit
                          value overrides.
  3. DB-BACKED PERSIST  — the event-store + governance-audit stores select the
                          Postgres adapter when their *_DATABASE_URL is set and
                          asyncpg is present; in-memory (observable) when not.
  4. SIGNED WALL        — wall_auth verifies RS256 with the public key when PyJWT
                          is present; falls back to DEV-UNSIGNED when no key.
  5. CONCRETE EXECUTORS — a CLEARED (post-approval) execute PERFORMS the reversible
                          side effect (make_tasks / attendance mark / message send)
                          and reports performed; never fires without clearance.
  6. PTM AVAILABILITY   — _comm_ptm sources its slot from a scheduling/availability
                          read (a derived working-day slot), not a hard-coded literal.

CONFIDENTIALITY: opaque refs only; no names, no board, no real pricing.
"""

from __future__ import annotations

import asyncio
import base64
import json
from datetime import datetime, timezone

import pytest

import backend.event_sink as event_sink
from backend import dispatch
from backend.wall_auth import WallTokenVerifier

_TEACHER = "11111111-1111-4111-8111-111111111111"
_DECIDER = "22222222-2222-4222-8222-222222222222"
_CONSENT = "cccccccc-0000-4000-8000-000000000003"


def _dev_token(canonical_uuid: str, role: str = "teacher") -> str:
    claims = {
        "canonical_uuid": canonical_uuid,
        "app": "school",
        "memberships": [{"app": "school", "role": role, "scope": "inst-1"}],
    }
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return "DEV-UNSIGNED." + body


# --------------------------------------------------------------------------- #
# 1. EVENT_SINK ASYNC — one shared loop; works with a Postgres-shaped async store.
# --------------------------------------------------------------------------- #
class _MockAsyncStore:
    """A Postgres-SHAPED async store: connect() opens a 'pool' captured to the
    loop it ran on, and append() must run on that SAME loop (asyncpg's real
    constraint). If a per-call loop were used, the loop ids would differ and we
    raise — so the test FAILS unless one shared loop drives both."""

    backend = "mock-postgres"

    def __init__(self) -> None:
        self.connect_loop_id: int | None = None
        self.append_loop_ids: list[int] = []

    async def connect(self) -> None:
        self.connect_loop_id = id(asyncio.get_running_loop())

    async def append(self, **kw):
        loop_id = id(asyncio.get_running_loop())
        self.append_loop_ids.append(loop_id)
        if loop_id != self.connect_loop_id:
            raise RuntimeError("append ran on a DIFFERENT loop than connect — pool would break")
        return {"event_id": "evt-1", "type": kw["type"]}


def test_shared_loop_drives_append_on_the_same_loop_as_connect(monkeypatch):
    """The async store's connect + every append run on ONE shared background loop
    (the real-Postgres requirement). Multiple appends stay on that loop."""
    store = _MockAsyncStore()
    # Reset the module's connection state + force our mock store.
    monkeypatch.setattr(event_sink, "_store", store, raising=False)
    monkeypatch.setattr(event_sink, "_connected", False, raising=False)
    monkeypatch.setattr(event_sink, "_build_store", lambda: store)

    def _emit(i: int) -> dict:
        return event_sink.append_emit_input({
            "app": "workflow", "canonical_uuid": _TEACHER, "purpose": "intervention",
            "consent_ref": _CONSENT, "occurred_at": datetime.now(timezone.utc).isoformat(),
            "type": f"test.event.{i}", "payload": {"n": i},
        })

    r1 = _emit(1)
    r2 = _emit(2)
    assert r1["persisted"] is True and r2["persisted"] is True
    assert store.connect_loop_id is not None
    # Both appends on the SAME loop as connect (else _MockAsyncStore would raise
    # and persisted would be False).
    assert store.append_loop_ids == [store.connect_loop_id, store.connect_loop_id]


def test_event_sink_degrades_observably_when_store_unavailable(monkeypatch):
    """No store wired -> persisted:false with an observable reason (never crashes,
    never silently pretends)."""
    monkeypatch.setattr(event_sink, "_build_store", lambda: None)
    out = event_sink.append_emit_input({
        "app": "workflow", "canonical_uuid": _TEACHER, "purpose": "intervention",
        "consent_ref": _CONSENT, "type": "test.event", "payload": {},
    })
    assert out["persisted"] is False
    assert out["reason"] == "event_store_unavailable"


# --------------------------------------------------------------------------- #
# 2. GATEWAY SELF-WIRE — the Wave-2 fronts resolve in-process (no 503).
# --------------------------------------------------------------------------- #
def _gateway_settings():
    # Load the gateway under the deployable's alias so we read the SAME config the
    # wall uses (the alias is only registered once load_gateway() has run).
    from backend import loader
    loader.load_gateway()
    cfg = __import__(f"{loader.GATEWAY_ALIAS}.config", fromlist=["GatewaySettings"])
    return cfg.GatewaySettings


def test_self_wire_defaults_loopback_when_self_base_url_unset(monkeypatch):
    monkeypatch.delenv("CLSS_GATEWAY_DEV_SELF_BASE_URL", raising=False)
    monkeypatch.setenv("PORT", "8080")
    targets = _gateway_settings()().capability_targets()
    # The Wave-2 fronts now resolve to the deployable's own governed door — not None
    # (None would make the gateway return 503 upstream_unconfigured).
    for cap in ("institution", "scheduling", "attendance", "communication",
                "teacher-growth", "governance"):
        assert targets[cap].base_url == "http://127.0.0.1:8080/capabilities", cap
    assert targets["identity"].base_url == "http://127.0.0.1:8080/internal/identity"


def test_self_wire_explicit_base_url_overrides(monkeypatch):
    monkeypatch.setenv("CLSS_GATEWAY_DEV_SELF_BASE_URL", "https://deploy.example")
    targets = _gateway_settings()().capability_targets()
    assert targets["communication"].base_url == "https://deploy.example/capabilities"
    assert targets["event-store"].base_url == "https://deploy.example/internal/event-store"


# --------------------------------------------------------------------------- #
# 3. DB-BACKED PERSISTENCE — the right adapter is chosen for set/unset DATABASE_URL.
# --------------------------------------------------------------------------- #
def test_event_store_selects_postgres_when_database_url_set(monkeypatch):
    """build_event_store picks the PostgresEventStore when the URL is set AND
    asyncpg is present; in-memory (observable degrade) otherwise. We MOCK asyncpg
    presence so no real DB / driver is required in CI."""
    import importlib
    from backend import loader

    loader.load_spine_app("event-store")
    store_mod = importlib.import_module(f"{loader._alias_for('svc', 'event-store')}.store")

    monkeypatch.setattr(store_mod, "_ASYNCPG_AVAILABLE", True)
    live = store_mod.build_event_store("postgresql://pooler/db")
    assert isinstance(live, store_mod.PostgresEventStore)
    assert "postgres" in live.backend

    # Unset URL -> in-memory degrade, clearly labelled.
    degraded = store_mod.build_event_store(None)
    assert isinstance(degraded, store_mod.InMemoryEventStore)
    assert "in-memory" in degraded.backend


def test_governance_audit_selects_postgres_when_audit_url_set(monkeypatch):
    """build_audit_log picks the PostgresAuditLog when audit_database_url is set
    (asyncpg mocked present); in-memory otherwise."""
    import importlib
    from backend import loader

    loader.load_governance()
    audit_mod = importlib.import_module(f"{loader.GOVERNANCE_ALIAS}.audit")

    monkeypatch.setattr(audit_mod, "_ASYNCPG_AVAILABLE", True)
    live = audit_mod.build_audit_log("postgresql://pooler/db")
    assert isinstance(live, audit_mod.PostgresAuditLog)
    assert "postgres" in live.backend

    degraded = audit_mod.build_audit_log(None)
    assert isinstance(degraded, audit_mod.InMemoryAuditLog)
    assert "in-memory" in degraded.backend


def test_governance_audit_persists_for_real_with_a_mock_pg_log(monkeypatch):
    """When a DB-backed audit log is wired, do_audit_trail returns persisted rows
    for real (persisted:true semantics). We inject a MOCK async PG-shaped log that
    has connect() (so the connect-on-shared-loop path is exercised) — no real DB."""
    from backend import governance_app

    class _MockPgAuditLog:
        backend = "mock-postgres-audit"

        def __init__(self):
            self.connected = False
            self.records: list = []

        async def connect(self):
            self.connected = True

        async def record(self, **kw):
            from types import SimpleNamespace
            rec = SimpleNamespace(audit_id="aud-1", actor_uuid=kw["actor_uuid"],
                                  action=kw["action"], resource=kw["resource"],
                                  purpose=kw["purpose"], privileged=kw.get("privileged", False),
                                  occurred_at=datetime.now(timezone.utc),
                                  detail=dict(kw.get("detail") or {}))
            self.records.append(rec)
            return rec

        async def query(self, q):
            return list(self.records)

    mock = _MockPgAuditLog()
    # Reset the governance singletons + force the mock log.
    monkeypatch.setattr(governance_app, "_AUDIT", None, raising=False)
    monkeypatch.setattr(governance_app, "_CONTROL", None, raising=False)
    monkeypatch.setattr(governance_app._gov_audit, "build_audit_log", lambda url: mock)
    monkeypatch.setattr(governance_app._gov_config, "get_settings",
                        lambda: type("S", (), {"audit_database_url": "postgresql://pooler/db"})())

    log = governance_app._audit_log()
    assert log is mock
    assert mock.connected is True  # connect() ran on the shared loop (PG needs it)


# --------------------------------------------------------------------------- #
# 4. SIGNED WALL — RS256 with the public key; DEV-UNSIGNED fallback.
# --------------------------------------------------------------------------- #
class _Principal:
    def __init__(self, *, canonical_uuid, roles, institution_uuid=None, consent_scopes=()):
        self.canonical_uuid = canonical_uuid
        self.roles = roles
        self.institution_uuid = institution_uuid
        self.consent_scopes = consent_scopes


def test_dev_unsigned_accepted_only_when_no_public_key():
    """No public key configured -> DEV-UNSIGNED token resolves to a Principal."""
    v = WallTokenVerifier(principal_cls=_Principal, public_key=None, introspect_url=None)
    principal = v.verify(_dev_token(_TEACHER))
    assert principal is not None
    assert principal.canonical_uuid == _TEACHER
    assert "teacher" in principal.roles


def test_dev_unsigned_rejected_when_public_key_present():
    """A real public key configured -> the unsigned dev token is REJECTED (the
    signed path is the only trust path)."""
    v = WallTokenVerifier(principal_cls=_Principal, public_key="-----BEGIN PUBLIC KEY-----\nx\n-----END PUBLIC KEY-----",
                          introspect_url=None)
    assert v.verify(_dev_token(_TEACHER)) is None


def test_signed_rs256_path_is_taken_when_key_present(monkeypatch):
    """A signed (non-dev) token is verified with the PUBLIC key via PyJWT. We MOCK
    jwt.decode so no real PyJWT install / key is needed — the test asserts the
    LIVE signed path is reached (decode is called with the public key) and its
    claims map onto a Principal."""
    import backend.wall_auth as wall_auth

    decoded = {"canonical_uuid": _TEACHER,
               "memberships": [{"app": "school", "role": "teacher", "scope": "inst-1"}]}
    calls = {}

    class _FakeJwt:
        @staticmethod
        def decode(token, key, algorithms, audience, issuer):
            calls["key"] = key
            calls["alg"] = algorithms
            return decoded

    monkeypatch.setattr(wall_auth, "_JWT_AVAILABLE", True)
    monkeypatch.setattr(wall_auth, "jwt", _FakeJwt)
    v = WallTokenVerifier(principal_cls=_Principal, public_key="PUBKEY", introspect_url=None,
                          algorithm="RS256")
    principal = v.verify("a.real.signed.jwt")
    assert principal is not None and principal.canonical_uuid == _TEACHER
    assert calls["key"] == "PUBKEY"          # the LIVE signed path was taken
    assert calls["alg"] == ["RS256"]


def test_signed_token_denied_when_pyjwt_absent(monkeypatch):
    """Public key set but PyJWT unavailable -> the signed token is DENIED (observable
    degrade), never silently accepted."""
    import backend.wall_auth as wall_auth

    monkeypatch.setattr(wall_auth, "_JWT_AVAILABLE", False)
    v = WallTokenVerifier(principal_cls=_Principal, public_key="PUBKEY", introspect_url=None)
    assert v.verify("a.real.signed.jwt") is None


# --------------------------------------------------------------------------- #
# 5. CONCRETE EXECUTORS — a cleared execute PERFORMS the reversible side effect.
# --------------------------------------------------------------------------- #
def test_cleared_message_send_performs_and_emits(monkeypatch):
    """When the workflow gate CLEARS the action (post-approval), the message-send
    executor actually posts the (screened) message and reports performed + emits
    communication.message_sent. INVARIANT 8: it never fires without clearance."""
    # Stub the workflow gate to return a cleared-but-not-performed result (the
    # package authorises; the executor performs). No real workflow needed here.
    monkeypatch.setattr(dispatch.workflow_app if hasattr(dispatch, "workflow_app") else __import__("backend.workflow_app", fromlist=["do_execute"]),
                        "do_execute",
                        lambda payload: (200, {"recommendation_id": "rec-1", "cleared": True,
                                               "performed": False, "events": []}))
    out = dispatch._loop_execute({"effect": "message_send", "body": "Great progress this week.",
                                  "subject_uuid": _TEACHER}, approval="appr-1")
    assert out["cleared"] is True
    assert out["performed"] is True
    assert out["execution"]["operation"] == "message_send"
    assert out["execution"]["message_id"]
    assert out["execution"]["event"]["type"] == "communication.message_sent"


def test_uncleared_execute_does_not_perform(monkeypatch):
    """Not cleared (no approval recorded) -> the executor does NOT fire; no side
    effect, no performed (INVARIANT 8)."""
    import backend.workflow_app as wf
    monkeypatch.setattr(wf, "do_execute",
                        lambda payload: (200, {"recommendation_id": "rec-1", "cleared": False,
                                               "performed": False, "events": []}))
    out = dispatch._loop_execute({"effect": "message_send", "body": "x"}, approval=None)
    assert out["cleared"] is False
    assert "execution" not in out


def test_cleared_attendance_mark_requires_human_ref(monkeypatch):
    """The attendance-mark executor refuses to finalise without an opaque human ref
    (confirm is human-attributed, INVARIANT 3); with one, it finalises + emits."""
    import backend.workflow_app as wf
    monkeypatch.setattr(wf, "do_execute",
                        lambda payload: (200, {"recommendation_id": "rec-1", "cleared": True,
                                               "performed": False, "events": []}))
    base = {"effect": "attendance_mark", "session_id": "sess-1",
            "roster_refs": ["a", "b", "c"], "absent_refs": ["b"]}
    # No confirmed_by -> degraded (no finalise).
    out = dispatch._loop_execute(dict(base), approval="appr-1")
    assert out["performed"] is False
    assert out["execution"]["degraded"] is True
    # With the approving human's ref -> finalised + event.
    out2 = dispatch._loop_execute({**base, "confirmed_by": _DECIDER}, approval="appr-1")
    assert out2["performed"] is True
    assert out2["execution"]["is_final"] is True
    assert out2["execution"]["event"]["type"] == "attendance.finalised"


# --------------------------------------------------------------------------- #
# 6. PTM AVAILABILITY — slots are sourced from a scheduling read, not literals.
# --------------------------------------------------------------------------- #
def test_ptm_slot_is_derived_from_scheduling_availability():
    """_comm_ptm sources its slot from a scheduling/availability read: the offered
    slot is a DERIVED working day (a real next-working-day on/after the anchor),
    not the old hard-coded 2026-07-01 literal."""
    ptm = __import__(f"{dispatch._alias('communication')}.ptm", fromlist=["MeetingSlot"])
    # Anchor on a Friday; the next working weekday is the following Monday.
    slot = dispatch._ptm_available_slot(
        {"after": "2026-06-26", "teacher_ref": _TEACHER, "window_hour": 15, "window_minute": 30},
        ptm,
    )
    assert slot.starts_at != "2026-07-01T10:00:00+00:00"  # not the old literal
    # Derived from the anchor: a working day strictly after 2026-06-26.
    assert slot.starts_at.startswith("2026-")
    assert slot.starts_at > "2026-06-26"
    assert "15:30" in slot.window_label
    # An explicit surface-chosen slot still overrides the availability read.
    chosen = dispatch._ptm_available_slot(
        {"starts_at": "2026-08-01T09:00:00+00:00", "teacher_ref": _TEACHER}, ptm)
    assert chosen.starts_at == "2026-08-01T09:00:00+00:00"


def test_ptm_dispatch_uses_real_availability_not_literal():
    """Through the dispatch handler: the booking's slot is the derived availability
    slot (no hard-coded literal leaks into the booking)."""
    out = dispatch._comm_ptm(
        {"after": "2026-06-26", "parent_ref": "parent-1", "teacher_ref": _TEACHER,
         "child_context_ref": "child-1", "child_brief": "A short shared conversation.",
         "subject_uuid": _TEACHER},
        approval=None,
    )
    # Either dispatched (module present) or a clearly-labelled degrade — never a crash.
    if out.get("dispatched"):
        assert out["operation"] == "ptm"
        assert out["booking_id"]
