"""Classroom delivery / live-class configuration (D7).

SECURITY INVARIANT 4: secrets are environment-only, read by NAME, never
hardcoded or logged. The dotted convention is ``clss.<app>.<env>.<purpose>``;
``env_var_name`` maps a dotted secret name to its OS environment key. This module
NEVER reads a secret VALUE at import; it only knows the NAMES, and degrades
gracefully (clear interfaces, deterministic paths) when a provider is absent.

No live realtime channel, no on-device vision runtime, no recording/transcription
provider, and no event store are required to run. With none wired the module runs
fully in-process and deterministic: board state lives in memory, presence/breakout
are computed locally, polls tally locally, the device-free check decodes its card
codes deterministically, attention signals are produced locally as ASSISTIVE
hints, and event emission returns the well-formed envelope object.

On-device vision NEVER leaves the device and NEVER grades a student from a face —
the vision seam carries only assistive, non-identity signals (see ``board`` and
``attention``). No raw frames or face data are ever sent to this module.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV = Literal["dev", "staging", "prod"]

# The canonical secret-name convention. The dotted name is the source of truth;
# env_var_name() maps it to an OS-safe key.
DOTTED_CONVENTION = "clss.<app>.<env>.<purpose>"


def env_var_name(dotted: str) -> str:
    """Map a dotted secret name to its OS environment variable key.

    ``clss.classroom.dev.event_store_url`` -> ``CLSS_CLASSROOM_DEV_EVENT_STORE_URL``.
    """
    return dotted.replace(".", "_").replace("-", "_").upper()


class ClassroomSettings(BaseSettings):
    """Classroom module settings.

    Every field that would carry a secret is OPTIONAL and defaults to ``None``;
    the module runs fully in a degraded, deterministic mode without any of them.
    """

    model_config = SettingsConfigDict(
        env_prefix="CLSS_CLASSROOM_DEV_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    env: ENV = Field(default="dev")
    service_name: str = Field(default="classroom")

    # --- Event store (emit via its interface; degrade to returning the event) ---
    # clss.classroom.dev.event_store_url
    event_store_url: str | None = Field(default=None)

    # --- Gateway (every cross-service call passes the gateway; INVARIANT 3) ----
    # clss.classroom.dev.gateway_url
    gateway_url: str | None = Field(default=None)
    # clss.classroom.dev.gateway_token  (bearer issued by identity; NEVER hardcoded)
    gateway_token: str | None = Field(default=None)

    # --- Realtime channel (board sync, presence, live tally fan-out) -----------
    # clss.classroom.dev.realtime_url
    realtime_url: str | None = Field(default=None)

    # --- Recording + transcription (only where consent permits) ---------------
    # clss.classroom.dev.recording_bucket
    recording_bucket: str | None = Field(default=None)
    # clss.classroom.dev.transcription_provider_key
    transcription_provider_key: str | None = Field(default=None)

    # --- AI fabric (poll/quiz authoring + transcript summary, generate-verify) -
    # clss.classroom.dev.ai_fabric_url
    ai_fabric_url: str | None = Field(default=None)

    @property
    def has_event_store(self) -> bool:
        return bool(self.event_store_url)

    @property
    def has_realtime(self) -> bool:
        return bool(self.realtime_url)

    @property
    def has_recording(self) -> bool:
        return bool(self.recording_bucket)

    @property
    def has_transcription(self) -> bool:
        return bool(self.transcription_provider_key)

    def degraded_reasons(self) -> list[str]:
        """Dotted NAMES of the secrets that are absent — for clear logging.

        Never returns a value, only the name a deployer must set.
        """
        missing: list[str] = []
        if not self.event_store_url:
            missing.append("clss.classroom.dev.event_store_url")
        if not self.gateway_url:
            missing.append("clss.classroom.dev.gateway_url")
        if not self.realtime_url:
            missing.append("clss.classroom.dev.realtime_url")
        if not self.recording_bucket:
            missing.append("clss.classroom.dev.recording_bucket")
        if not self.transcription_provider_key:
            missing.append("clss.classroom.dev.transcription_provider_key")
        if not self.ai_fabric_url:
            missing.append("clss.classroom.dev.ai_fabric_url")
        return missing


@lru_cache
def get_settings() -> ClassroomSettings:
    return ClassroomSettings()
