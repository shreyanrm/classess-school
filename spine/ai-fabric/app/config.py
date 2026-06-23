"""Settings for the AI fabric (spine A4).

INVARIANT 4 — SECRETS ARE ENV-ONLY, READ BY NAME, NEVER HARDCODED.

Settings resolve from the environment under the secret convention
``clss.<app>.<env>.<purpose>``, which maps to OS env keys by uppercasing and
replacing ``.``/``-`` with ``_``. The shared prefix for this app/env is
``CLSS_AIFABRIC_DEV_``; a field ``gemini_api_key`` therefore resolves from the
OS env var ``CLSS_AIFABRIC_DEV_GEMINI_API_KEY`` (secret name
``clss.aifabric.dev.gemini_api_key``).

Key VALUES are never defaulted to anything but ``None`` and never written to
this repository. A field that is ``None`` means the secret is unset, and the
caller degrades to a clearly-marked *unavailable* result rather than fabricating
a value.

This module prefers ``pydantic-settings`` (the env-prefix loader) when it is
installed, but degrades gracefully to a standard-library loader with the SAME
prefix and field names when it is absent — so the package stays import-safe with
no third-party dependency required for the deterministic paths or the tests.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# The shared env prefix for this app/env. Secret names are
# ``clss.aifabric.dev.<purpose>``; mapped to OS env keys this is the prefix.
ENV_PREFIX = "CLSS_AIFABRIC_DEV_"


def _read(field_name: str, env: dict[str, str] | None = None) -> str | None:
    """Read a field's value from the environment by its prefixed, upper-cased key.

    Never returns an empty/whitespace string as a value — that is treated as
    unset (``None``), matching the router's ``_has_key`` semantics.
    """
    source = env if env is not None else os.environ
    raw = source.get(ENV_PREFIX + field_name.upper())
    if raw is None or not raw.strip():
        return None
    return raw


try:  # Prefer pydantic-settings when present (the env-prefix loader).
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):  # type: ignore[misc]
        """Env-resolved settings under the ``CLSS_AIFABRIC_DEV_`` prefix.

        Add fields here as named secrets are introduced; each field resolves
        from ``CLSS_AIFABRIC_DEV_<FIELD>``. Defaults are ``None`` so an unset
        secret degrades, never fabricates.
        """

        model_config = SettingsConfigDict(
            env_prefix=ENV_PREFIX,
            case_sensitive=False,
            extra="ignore",
        )

        # Gemini Live (speech-to-speech) provider key.
        # Secret name: clss.aifabric.dev.gemini_api_key
        # OS env var:  CLSS_AIFABRIC_DEV_GEMINI_API_KEY
        gemini_api_key: str | None = None

        # TRACK 1 — second-model cross-check provider key (INVARIANT 7). The
        # independent model that confirms/refutes generated content in the
        # generate-and-verify pipeline. Read by NAME only; the raw value is never
        # returned or logged. Unset => the cross-checker abstains (gate stays
        # closed) rather than serving unverified content.
        # Secret name: clss.aifabric.dev.crosscheck_model_key
        # OS env var:  CLSS_AIFABRIC_DEV_CROSSCHECK_MODEL_KEY
        crosscheck_model_key: str | None = None

        # TRACK 2 — proprietary / edge SLM models (INVARIANT 11, kept SEPARATE
        # from Track 1 in config and ownership). Defaults are ``None`` so an
        # unset Track 2 degrades to a clearly-marked unavailable result and is
        # never conflated with Track 1's keys.
        # Secret name: clss.aifabric.dev.track2_endpoint_url
        # OS env var:  CLSS_AIFABRIC_DEV_TRACK2_ENDPOINT_URL
        track2_endpoint_url: str | None = None
        # Secret name: clss.aifabric.dev.track2_endpoint_key
        # OS env var:  CLSS_AIFABRIC_DEV_TRACK2_ENDPOINT_KEY
        track2_endpoint_key: str | None = None

except ImportError:  # pragma: no cover - exercised when pydantic-settings absent
    @dataclass
    class Settings:  # type: ignore[no-redef]
        """Standard-library fallback with the SAME prefix + field names.

        Reads each field from ``CLSS_AIFABRIC_DEV_<FIELD>`` at construction.
        Keeps the package import-safe and dependency-free for the deterministic
        paths and tests when ``pydantic-settings`` is not installed.
        """

        # Gemini Live (speech-to-speech) provider key.
        # Secret name: clss.aifabric.dev.gemini_api_key
        # OS env var:  CLSS_AIFABRIC_DEV_GEMINI_API_KEY
        gemini_api_key: str | None = None

        # TRACK 1 — second-model cross-check provider key (INVARIANT 7). The
        # independent model that confirms/refutes generated content in the
        # generate-and-verify pipeline. Read by NAME only; the raw value is never
        # returned or logged. Unset => the cross-checker abstains (gate stays
        # closed) rather than serving unverified content.
        # Secret name: clss.aifabric.dev.crosscheck_model_key
        # OS env var:  CLSS_AIFABRIC_DEV_CROSSCHECK_MODEL_KEY
        crosscheck_model_key: str | None = None

        # TRACK 2 — proprietary / edge SLM models (INVARIANT 11, kept SEPARATE
        # from Track 1 in config and ownership). Defaults are ``None`` so an
        # unset Track 2 degrades to a clearly-marked unavailable result and is
        # never conflated with Track 1's keys.
        # Secret name: clss.aifabric.dev.track2_endpoint_url
        # OS env var:  CLSS_AIFABRIC_DEV_TRACK2_ENDPOINT_URL
        track2_endpoint_url: str | None = None
        # Secret name: clss.aifabric.dev.track2_endpoint_key
        # OS env var:  CLSS_AIFABRIC_DEV_TRACK2_ENDPOINT_KEY
        track2_endpoint_key: str | None = None

        def __init__(self, _env: dict[str, str] | None = None, **overrides: object) -> None:
            self.gemini_api_key = overrides.get(  # type: ignore[assignment]
                "gemini_api_key", _read("gemini_api_key", _env)
            )
            self.crosscheck_model_key = overrides.get(  # type: ignore[assignment]
                "crosscheck_model_key", _read("crosscheck_model_key", _env)
            )
            self.track2_endpoint_url = overrides.get(  # type: ignore[assignment]
                "track2_endpoint_url", _read("track2_endpoint_url", _env)
            )
            self.track2_endpoint_key = overrides.get(  # type: ignore[assignment]
                "track2_endpoint_key", _read("track2_endpoint_key", _env)
            )


def get_settings(env: dict[str, str] | None = None) -> "Settings":
    """Construct settings, optionally from an injected env mapping (for tests).

    With pydantic-settings, an injected ``env`` is applied as explicit field
    overrides so the prefix logic stays identical to the fallback path.
    """
    if env is None:
        return Settings()  # type: ignore[call-arg]
    # Resolve each known field from the injected env via the shared prefix.
    return Settings(  # type: ignore[call-arg]
        gemini_api_key=_read("gemini_api_key", env),
        crosscheck_model_key=_read("crosscheck_model_key", env),
        track2_endpoint_url=_read("track2_endpoint_url", env),
        track2_endpoint_key=_read("track2_endpoint_key", env),
    )
