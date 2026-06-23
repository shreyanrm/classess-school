"""Relationships & communication configuration (B9).

SECURITY INVARIANT 4: secrets are environment-only, read by NAME, never
hardcoded and never invented. Dotted names follow ``clss.<app>.<env>.<purpose>``
and map to ``CLSS_COMMUNICATION_DEV_*`` env vars (uppercased, dots/dashes ->
underscores).

This module holds NO credentials (INVARIANT 8 — agents hold no credentials).
Every cross-service call passes the gateway; this names the gateway URL var but
never stores a key value. With no provider configured the deterministic paths
(the bounded companion, the message hub + task routing, the parent partnership
framing, the safeguarding classifier, the translation interface) all work, and
event emission degrades to a clearly-labelled in-memory sink.

Import-safe: this module reads no environment VALUE and opens no connection at
import. Settings are resolved lazily by :func:`get_settings`, and only env-var
NAMES are ever referenced.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


# Dotted secret/config NAMES (names only — INVARIANT 4). Single source of truth
# shared by the README and the degraded-reasons report.
ENV_GATEWAY_URL = "clss.communication.dev.gateway_url"
ENV_EVENT_SINK_URL = "clss.communication.dev.event_sink_url"
ENV_DATABASE_URL = "clss.communication.dev.database_url"
# The A4 Vidya orchestrator the companion would speak through (always behind the
# gateway, structured-output + confidence gate). Unset -> companion runs its
# deterministic, bounded, scripted path.
ENV_ORCHESTRATOR_URL = "clss.communication.dev.orchestrator_url"
# The A7 child-safety subsystem (moderation / crisis classifier). Unset ->
# safeguarding runs its deterministic on-device lexical classifier (fail-safe:
# it never opens an unmonitored channel).
ENV_SAFETY_URL = "clss.communication.dev.safety_url"
# The A1 consent authority — resolves consent + purpose for cross-context reads.
# Unset -> only explicitly-supplied consent grants are honoured (fail-closed).
ENV_CONSENT_URL = "clss.communication.dev.consent_url"
# The A5 workflow engine that carries an escalation / routed task to a qualified
# human for ownership + approval. Unset -> escalations stay local + pending.
ENV_WORKFLOW_URL = "clss.communication.dev.workflow_url"
# The translation provider (multilingual + code-switching). Unset -> the
# translation interface passes text through, tagged untranslated, never dropping
# subject terminology.
ENV_TRANSLATION_URL = "clss.communication.dev.translation_url"
# The multi-channel delivery providers (the trigger layer). Each is named ONLY by
# its env var; unset -> that channel degrades to a deterministic in-memory outbox
# that records the send intent and transmits nothing externally.
ENV_CHAT_PROVIDER_URL = "clss.communication.dev.chat_provider_url"
ENV_PUSH_PROVIDER_URL = "clss.communication.dev.push_provider_url"
ENV_EMAIL_PROVIDER_URL = "clss.communication.dev.email_provider_url"
ENV_SMS_PROVIDER_URL = "clss.communication.dev.sms_provider_url"
ENV_WHATSAPP_PROVIDER_URL = "clss.communication.dev.whatsapp_provider_url"
# The persistent companion-memory store (consent-gated, PII-free). Unset -> the
# companion memory runs in a deterministic in-process store (per-session only).
ENV_COMPANION_MEMORY_URL = "clss.communication.dev.companion_memory_url"
# The transcription provider for the in-meeting silent assistant. Unset -> the
# assistant accepts only already-captured transcript segments (no live capture)
# and runs its deterministic notes/key-point/action-item extraction on them.
ENV_TRANSCRIPTION_URL = "clss.communication.dev.transcription_url"

_ENV_PREFIX = "CLSS_COMMUNICATION_DEV_"

DOTTED_CONVENTION = "clss.<app>.<env>.<purpose>"


def env_var_name(dotted: str) -> str:
    """Map a dotted secret name to its OS environment variable key.

    ``clss.communication.dev.gateway_url`` -> ``CLSS_COMMUNICATION_DEV_GATEWAY_URL``.
    """
    return dotted.replace(".", "_").replace("-", "_").upper()


@dataclass(frozen=True)
class CommunicationSettings:
    """Resolved configuration. Every field is optional; absence -> graceful
    degradation. No secret value is ever defaulted to a literal here
    (INVARIANT 4) — only ``None``.
    """

    env: str = "dev"
    service_name: str = "communication"

    # The only egress. Every cross-service call (event store, orchestrator,
    # safety subsystem, consent authority, workflow, translation) passes the
    # gateway. Unset -> degraded.
    gateway_url: str | None = None
    event_sink_url: str | None = None
    database_url: str | None = None
    orchestrator_url: str | None = None
    safety_url: str | None = None
    consent_url: str | None = None
    workflow_url: str | None = None
    translation_url: str | None = None
    chat_provider_url: str | None = None
    push_provider_url: str | None = None
    email_provider_url: str | None = None
    sms_provider_url: str | None = None
    whatsapp_provider_url: str | None = None
    companion_memory_url: str | None = None
    transcription_url: str | None = None

    @property
    def has_gateway(self) -> bool:
        return bool(self.gateway_url)

    @property
    def has_event_sink(self) -> bool:
        """True only when BOTH the gateway and the sink are configured — every
        cross-service write passes the gateway, so a sink without a gateway is
        still degraded (we never write directly)."""
        return bool(self.gateway_url and self.event_sink_url)

    @property
    def has_orchestrator(self) -> bool:
        return bool(self.gateway_url and self.orchestrator_url)

    @property
    def has_safety_service(self) -> bool:
        return bool(self.gateway_url and self.safety_url)

    @property
    def has_consent_authority(self) -> bool:
        return bool(self.gateway_url and self.consent_url)

    @property
    def has_workflow(self) -> bool:
        return bool(self.gateway_url and self.workflow_url)

    @property
    def has_translation(self) -> bool:
        return bool(self.gateway_url and self.translation_url)

    @property
    def has_companion_memory_store(self) -> bool:
        return bool(self.gateway_url and self.companion_memory_url)

    @property
    def has_transcription(self) -> bool:
        return bool(self.gateway_url and self.transcription_url)

    def configured_channels(self) -> list[str]:
        """The delivery channels whose provider URL AND the gateway are set (so a
        real send would go out). Names only; absence -> degraded outbox."""
        ready: list[str] = []
        if not self.gateway_url:
            return ready
        if self.chat_provider_url:
            ready.append("chat")
        if self.push_provider_url:
            ready.append("push")
        if self.email_provider_url:
            ready.append("email")
        if self.sms_provider_url:
            ready.append("sms")
        if self.whatsapp_provider_url:
            ready.append("whatsapp_class")
        return ready

    def degraded_reasons(self) -> list[str]:
        """Dotted NAMES (NEVER values) of env vars whose absence keeps the
        module in degraded (deterministic, in-memory) mode."""
        missing: list[str] = []
        if not self.gateway_url:
            missing.append(ENV_GATEWAY_URL)
        if not self.event_sink_url:
            missing.append(ENV_EVENT_SINK_URL)
        if not self.database_url:
            missing.append(ENV_DATABASE_URL)
        if not self.orchestrator_url:
            missing.append(ENV_ORCHESTRATOR_URL)
        if not self.safety_url:
            missing.append(ENV_SAFETY_URL)
        if not self.consent_url:
            missing.append(ENV_CONSENT_URL)
        if not self.workflow_url:
            missing.append(ENV_WORKFLOW_URL)
        if not self.translation_url:
            missing.append(ENV_TRANSLATION_URL)
        if not self.chat_provider_url:
            missing.append(ENV_CHAT_PROVIDER_URL)
        if not self.push_provider_url:
            missing.append(ENV_PUSH_PROVIDER_URL)
        if not self.email_provider_url:
            missing.append(ENV_EMAIL_PROVIDER_URL)
        if not self.sms_provider_url:
            missing.append(ENV_SMS_PROVIDER_URL)
        if not self.whatsapp_provider_url:
            missing.append(ENV_WHATSAPP_PROVIDER_URL)
        if not self.companion_memory_url:
            missing.append(ENV_COMPANION_MEMORY_URL)
        if not self.transcription_url:
            missing.append(ENV_TRANSCRIPTION_URL)
        return missing


def _read_env(dotted: str) -> str | None:
    value = os.environ.get(env_var_name(dotted))
    if value is None:
        return None
    value = value.strip()
    return value or None


_cached: CommunicationSettings | None = None


def get_settings(*, refresh: bool = False) -> CommunicationSettings:
    """Resolve settings from the environment (by NAME) once, then cache.

    Reads only environment variables — no file, no network, no secret literal.
    Pass ``refresh=True`` to re-read (e.g. after the environment changes in a
    test).
    """
    global _cached
    if _cached is not None and not refresh:
        return _cached
    _cached = CommunicationSettings(
        env=os.environ.get(_ENV_PREFIX + "ENV", "dev"),
        gateway_url=_read_env(ENV_GATEWAY_URL),
        event_sink_url=_read_env(ENV_EVENT_SINK_URL),
        database_url=_read_env(ENV_DATABASE_URL),
        orchestrator_url=_read_env(ENV_ORCHESTRATOR_URL),
        safety_url=_read_env(ENV_SAFETY_URL),
        consent_url=_read_env(ENV_CONSENT_URL),
        workflow_url=_read_env(ENV_WORKFLOW_URL),
        translation_url=_read_env(ENV_TRANSLATION_URL),
        chat_provider_url=_read_env(ENV_CHAT_PROVIDER_URL),
        push_provider_url=_read_env(ENV_PUSH_PROVIDER_URL),
        email_provider_url=_read_env(ENV_EMAIL_PROVIDER_URL),
        sms_provider_url=_read_env(ENV_SMS_PROVIDER_URL),
        whatsapp_provider_url=_read_env(ENV_WHATSAPP_PROVIDER_URL),
        companion_memory_url=_read_env(ENV_COMPANION_MEMORY_URL),
        transcription_url=_read_env(ENV_TRANSCRIPTION_URL),
    )
    return _cached
