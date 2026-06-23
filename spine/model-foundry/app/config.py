"""Settings for the model foundry (spine A4 — Track 2 BASE).

INVARIANT 4 — SECRETS ARE ENV-ONLY, READ BY NAME, NEVER HARDCODED.

Settings resolve from the environment under the secret convention
``clss.<app>.<env>.<purpose>``, which maps to OS env keys by uppercasing and
replacing ``.``/``-`` with ``_``. The shared prefix for this app/env is
``CLSS_MODELFOUNDRY_DEV_``; a field ``training_endpoint`` therefore resolves
from the OS env var ``CLSS_MODELFOUNDRY_DEV_TRAINING_ENDPOINT`` (secret name
``clss.modelfoundry.dev.training_endpoint``).

Key VALUES are never defaulted to anything but ``None`` and never written to
this repository. A field that is ``None`` means the secret is unset, and the
caller degrades to a clearly-marked *no-compute* / *unavailable* result rather
than fabricating a value (in particular: the fine-tune runner NEVER fabricates a
trained model).

This module is dependency-free and import-safe: a standard-library loader reads
each field from the environment with the shared prefix and field names. It
mirrors the AI fabric's ``config`` style so the two spine packages read secrets
identically.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# The shared env prefix for this app/env. Secret names are
# ``clss.modelfoundry.dev.<purpose>``; mapped to OS env keys this is the prefix.
ENV_PREFIX = "CLSS_MODELFOUNDRY_DEV_"

# Named secrets (NAMES ONLY — never values). The training BACKEND seam.
# Secret name: clss.modelfoundry.dev.training_endpoint
# OS env var:  CLSS_MODELFOUNDRY_DEV_TRAINING_ENDPOINT
TRAINING_ENDPOINT_SECRET_NAME = "clss.modelfoundry.dev.training_endpoint"
TRAINING_ENDPOINT_ENV_VAR = ENV_PREFIX + "TRAINING_ENDPOINT"
# Secret name: clss.modelfoundry.dev.training_key
# OS env var:  CLSS_MODELFOUNDRY_DEV_TRAINING_KEY
TRAINING_KEY_SECRET_NAME = "clss.modelfoundry.dev.training_key"
TRAINING_KEY_ENV_VAR = ENV_PREFIX + "TRAINING_KEY"

# The Track-1 frontier TEACHER seam (distillation source only — never conflated
# with Track 2). The teacher key is the SAME named secret the AI fabric reads for
# Gemini, so the two spine packages read it identically (INVARIANT 4): the value
# is read by NAME from the AI fabric's env prefix, never hardcoded, never logged.
# Secret name: clss.aifabric.dev.gemini_api_key
# OS env var:  CLSS_AIFABRIC_DEV_GEMINI_API_KEY
TEACHER_KEY_SECRET_NAME = "clss.aifabric.dev.gemini_api_key"
TEACHER_KEY_ENV_VAR = "CLSS_AIFABRIC_DEV_GEMINI_API_KEY"


def _read(field_name: str, env: dict[str, str] | None = None) -> str | None:
    """Read a field's value from the environment by its prefixed, upper-cased key.

    Never returns an empty/whitespace string as a value — that is treated as
    unset (``None``), matching the AI fabric's ``_has_key`` semantics so an
    unset secret degrades rather than fabricating.
    """
    source = env if env is not None else os.environ
    raw = source.get(ENV_PREFIX + field_name.upper())
    if raw is None or not raw.strip():
        return None
    return raw


def _read_env_var(env_var: str, env: dict[str, str] | None = None) -> str | None:
    """Read a fully-qualified OS env var by name (no prefix added).

    Used for cross-package named secrets — the Track-1 teacher key lives under
    the AI fabric's prefix (``CLSS_AIFABRIC_DEV_GEMINI_API_KEY``), so the foundry
    reads it BY NAME exactly as the fabric does. Empty/whitespace is unset.
    """
    source = env if env is not None else os.environ
    raw = source.get(env_var)
    if raw is None or not raw.strip():
        return None
    return raw


@dataclass
class Settings:
    """Env-resolved settings under the ``CLSS_MODELFOUNDRY_DEV_`` prefix.

    Defaults are ``None`` so an unset secret degrades, never fabricates. With NO
    training endpoint/key the fine-tune runner returns a no-compute plan.
    """

    # The training backend HTTP endpoint (the GPU compute seam).
    training_endpoint: str | None = None
    # The training backend key. Read by NAME only; the raw value is never
    # returned in a result object and never logged.
    training_key: str | None = None
    # The Track-1 frontier TEACHER (Gemini) key — read by NAME from the AI
    # fabric's env var (CLSS_AIFABRIC_DEV_GEMINI_API_KEY). Distillation SOURCE
    # only; with no key the teacher degrades and never fabricates a target.
    teacher_key: str | None = None

    def __init__(self, _env: dict[str, str] | None = None, **overrides: object) -> None:
        self.training_endpoint = overrides.get(  # type: ignore[assignment]
            "training_endpoint", _read("training_endpoint", _env)
        )
        self.training_key = overrides.get(  # type: ignore[assignment]
            "training_key", _read("training_key", _env)
        )
        self.teacher_key = overrides.get(  # type: ignore[assignment]
            "teacher_key", _read_env_var(TEACHER_KEY_ENV_VAR, _env)
        )

    def training_configured(self) -> bool:
        """True only when BOTH the endpoint and the key are present.

        A partial configuration (one without the other) is treated as unset so
        the runner degrades to a no-compute plan rather than attempting a call
        it cannot authenticate or address.
        """
        return bool(self.training_endpoint) and bool(self.training_key)

    def teacher_configured(self) -> bool:
        """True only when the Track-1 teacher key is present.

        With no key the teacher distillation builder degrades to an offline plan
        rather than fabricating a teacher target.
        """
        return bool(self.teacher_key)


def get_settings(env: dict[str, str] | None = None) -> "Settings":
    """Construct settings, optionally from an injected env mapping (for tests)."""
    return Settings(_env=env)
