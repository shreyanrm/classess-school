"""Institution & policy module (B1, capability module behind the gateway).

The Ring 0 minimal-provisioning prerequisite made real: an institution, its
structure, and its roster are the canonical schema every other module hangs off,
even while the UI is thin.

This is a capability module over the secure core. It NEVER owns a spine concern
(identity, the event contract, the ontology, the evidence/mastery engine). It
holds the org hierarchy, the blueprint wizard, policy inheritance,
hyperlocalization, and logical multi-tenancy, and it EMITS structure / roster /
policy events on the contract envelope shape, keyed to the opaque
``canonical_uuid`` only.

Package surface:

  - ``hierarchy``  — the configurable org hierarchy + scoped, time-bound
                     many-to-many relationship graph (board-agnostic nodes:
                     group -> region -> campus -> school -> department -> grade ->
                     section).
  - ``blueprint``  — the institution blueprint wizard (structure + roster +
                     policy) producing a validated, tenant-scoped config.
  - ``policy``     — policy inheritance down the hierarchy (a child inherits and
                     may override a parent) plus hyperlocalization (language,
                     region, calendar).
  - ``tenancy``    — logical multi-tenancy: every record carries a tenant scope;
                     cross-tenant reads are denied by default.
  - ``events``     — emit structure/roster/policy events on the contract shapes
                     (degrades to returning the event object with no store).
  - ``config``     — env-var NAMES only; degrades gracefully with none set.

Import-safe: importing the package, or any submodule, performs no I/O, reads no
secret value, opens no connection, and never requires a live provider.
"""

from __future__ import annotations

from .config import InstitutionSettings, get_settings

__all__ = [
    "InstitutionSettings",
    "get_settings",
    # Submodules import by name (``from app import hierarchy``); listed for
    # discoverability rather than eagerly imported, so a missing optional
    # dependency in one path never breaks importing another.
    "hierarchy",
    "blueprint",
    "policy",
    "tenancy",
    "events",
]

__version__ = "0.1.0"
