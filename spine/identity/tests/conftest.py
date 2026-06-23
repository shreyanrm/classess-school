"""Offline, PII-free fixtures for the identity service tests.

The app boots with the in-memory store and the unsigned-DEV token fallback (no
signing key, no asyncpg, no live network) so the full contract is exercisable
offline. The client overrides the lifespan-built dependencies with a fresh
in-memory store per test for isolation.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest

# Import the package without installation.
_PKG_ROOT = Path(__file__).resolve().parents[1]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app import main as main_mod  # noqa: E402
from app.config import IdentitySettings  # noqa: E402
from app.store import InMemoryIdentityStore  # noqa: E402
from app.tokens import TokenService  # noqa: E402

# Deterministic opaque ids — random-shaped, never derived from PII.
ADMIN = UUID("aaaaaaaa-0000-4000-8000-000000000001")
TEACHER = UUID("bbbbbbbb-0000-4000-8000-000000000002")
SUBSTITUTE = UUID("cccccccc-0000-4000-8000-000000000003")
COORDINATOR = UUID("dddddddd-0000-4000-8000-000000000004")
STUDENT = UUID("eeeeeeee-0000-4000-8000-000000000005")

NOW = datetime.now(timezone.utc)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def store() -> InMemoryIdentityStore:
    return InMemoryIdentityStore()


@pytest.fixture
def tokens() -> TokenService:
    # No private key -> loud unsigned DEV fallback (offline contract testing).
    return TokenService(
        private_key=None, public_key=None, issuer="clss.identity",
        audience="clss.gateway", algorithm="RS256", ttl_seconds=3600,
    )


@pytest.fixture
def client(store, tokens):
    settings = IdentitySettings()
    app = main_mod.app
    # Reset the in-process challenge/state maps for isolation.
    main_mod._otp_challenges.clear()
    main_mod._sso_states.clear()
    with TestClient(app) as c:
        # Override the lifespan-built (degraded) dependencies AFTER startup so each
        # test gets a fresh, isolated in-memory store and the unsigned-DEV tokens.
        app.state.store = store
        app.state.tokens = tokens
        app.state.settings = settings
        yield c


@pytest.fixture
def bearer(tokens):
    """A valid bearer token for an arbitrary caller (gateway-style)."""
    token, _ttl, _exp = tokens.mint(canonical_uuid=ADMIN, app="school", memberships=[])
    return _bearer(token)


@pytest.fixture
def future():
    return (NOW + timedelta(hours=2)).isoformat()


@pytest.fixture
def past():
    return (NOW - timedelta(hours=2)).isoformat()
