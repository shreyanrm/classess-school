"""Settings for governance & safety (spine A7).

INVARIANT 4 — SECRETS ARE ENV-ONLY, READ BY NAME, NEVER HARDCODED.

Settings resolve from the environment under the secret convention
``clss.<app>.<env>.<purpose>``, mapped to OS env keys by uppercasing and
replacing ``.``/``-`` with ``_``. The shared prefix for this app/env is
``CLSS_GOVERNANCE_DEV_``; a field ``audit_database_url`` resolves from
``CLSS_GOVERNANCE_DEV_AUDIT_DATABASE_URL`` (secret name
``clss.governance.dev.audit_database_url``).

Key VALUES are never defaulted to anything but ``None`` and never written to
this repository. A field that is ``None`` means the secret is unset, and the
caller degrades to a clearly-marked *unavailable* / in-memory result rather
than fabricating a value or a key.

INVARIANT 11 — Track 1 and Track 2 stay separate. Their endpoint keys are
distinct, distinctly named fields here and are never read into a single
shared slot.

Prefers ``pydantic-settings`` when installed; degrades to a stdlib loader with
the SAME prefix and field names so the package is import-safe with no
third-party dependency.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, fields

# The shared env prefix for this app/env. Secret names are
# ``clss.governance.dev.<purpose>``; mapped to OS env keys this is the prefix.
ENV_PREFIX = "CLSS_GOVERNANCE_DEV_"

# Field names <-> dotted secret names. Listed so the README and the loader agree.
_FIELD_NAMES = (
    "audit_database_url",        # immutable audit sink (append-only, INSERT-only grants)
    "breakglass_database_url",   # break-glass record sink (immutable, reviewable)
    "consent_database_url",      # consent/retention/lineage store
    "child_safety_classifier_url",   # moderation/crisis classifier endpoint (Track 1)
    "child_safety_classifier_key",   # moderation/crisis classifier key (Track 1)
    "child_safety_edge_model_url",   # on-edge classifier endpoint (Track 2 — separate)
    "child_safety_edge_model_key",   # on-edge classifier key (Track 2 — separate)
    "escalation_webhook_url",    # qualified-human escalation channel endpoint
    "escalation_webhook_key",    # qualified-human escalation channel key
)


def _read(field_name: str, env: dict[str, str] | None = None) -> str | None:
    """Read a field's value from the environment by its prefixed, upper-cased key.

    An empty/whitespace value is treated as unset (``None``).
    """
    source = env if env is not None else os.environ
    raw = source.get(ENV_PREFIX + field_name.upper())
    if raw is None or not raw.strip():
        return None
    return raw


try:  # Prefer pydantic-settings when present.
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):  # type: ignore[misc]
        """Env-resolved settings under the ``CLSS_GOVERNANCE_DEV_`` prefix.

        Each field resolves from ``CLSS_GOVERNANCE_DEV_<FIELD>``. Defaults are
        ``None`` so an unset secret degrades, never fabricates.
        """

        model_config = SettingsConfigDict(
            env_prefix=ENV_PREFIX,
            case_sensitive=False,
            extra="ignore",
        )

        audit_database_url: str | None = None
        breakglass_database_url: str | None = None
        consent_database_url: str | None = None
        # Track 1 (external) child-safety classifier.
        child_safety_classifier_url: str | None = None
        child_safety_classifier_key: str | None = None
        # Track 2 (proprietary / edge) child-safety classifier — kept separate.
        child_safety_edge_model_url: str | None = None
        child_safety_edge_model_key: str | None = None
        # Qualified-human escalation channel.
        escalation_webhook_url: str | None = None
        escalation_webhook_key: str | None = None

except ImportError:  # pragma: no cover - exercised when pydantic-settings absent
    @dataclass
    class Settings:  # type: ignore[no-redef]
        """Standard-library fallback with the SAME prefix + field names."""

        audit_database_url: str | None = None
        breakglass_database_url: str | None = None
        consent_database_url: str | None = None
        child_safety_classifier_url: str | None = None
        child_safety_classifier_key: str | None = None
        child_safety_edge_model_url: str | None = None
        child_safety_edge_model_key: str | None = None
        escalation_webhook_url: str | None = None
        escalation_webhook_key: str | None = None

        def __init__(self, _env: dict[str, str] | None = None, **overrides: object) -> None:
            for f in fields(self):
                if f.name in overrides:
                    setattr(self, f.name, overrides[f.name])  # type: ignore[arg-type]
                else:
                    setattr(self, f.name, _read(f.name, _env))


def get_settings(env: dict[str, str] | None = None) -> "Settings":
    """Construct settings, optionally from an injected env mapping (for tests).

    With pydantic-settings, an injected ``env`` is applied as explicit field
    overrides so the prefix logic is identical to the fallback path.
    """
    if env is None:
        return Settings()  # type: ignore[call-arg]
    overrides = {name: _read(name, env) for name in _FIELD_NAMES}
    return Settings(**overrides)  # type: ignore[arg-type]
