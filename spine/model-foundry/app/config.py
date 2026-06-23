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

    def __init__(self, _env: dict[str, str] | None = None, **overrides: object) -> None:
        self.training_endpoint = overrides.get(  # type: ignore[assignment]
            "training_endpoint", _read("training_endpoint", _env)
        )
        self.training_key = overrides.get(  # type: ignore[assignment]
            "training_key", _read("training_key", _env)
        )

    def training_configured(self) -> bool:
        """True only when BOTH the endpoint and the key are present.

        A partial configuration (one without the other) is treated as unset so
        the runner degrades to a no-compute plan rather than attempting a call
        it cannot authenticate or address.
        """
        return bool(self.training_endpoint) and bool(self.training_key)


def get_settings(env: dict[str, str] | None = None) -> "Settings":
    """Construct settings, optionally from an injected env mapping (for tests)."""
    return Settings(_env=env)
