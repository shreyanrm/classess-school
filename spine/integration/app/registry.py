"""The connector registry (spine A6).

Builds and tracks the set of connectors for a deployment, wiring each into the
shared ``HealthRegistry``. Connector configuration is resolved by env var NAME
(INVARIANT 4): a connector whose route NAME is absent registers as UNCONFIGURED
so an operator sees exactly which standards are live vs degraded — by name, never
by value.
"""

from __future__ import annotations

from .adapters import (
    CaliperAdapter,
    CASEAdapter,
    ClassLinkAdapter,
    CleverAdapter,
    EdFiAdapter,
    LTIAdapter,
    OneRosterAdapter,
    QTIAdapter,
    SCORMAdapter,
    XAPIAdapter,
)
from .config import IntegrationSettings, get_settings
from .connector import Connector
from .health import HealthRegistry
from .models import Standard


class ConnectorRegistry:
    """Holds the live connectors and their health for one deployment."""

    def __init__(self, settings: IntegrationSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self.health = HealthRegistry()
        self._connectors: dict[Standard, Connector] = {}
        self._build()

    def _add(self, connector: Connector) -> None:
        self._connectors[connector.standard] = connector
        self.health.register(connector.health)

    def _build(self) -> None:
        s = self.settings
        # Route NAME presence flips a connector out of UNCONFIGURED. The route is
        # a NAME, never a secret value.
        self._add(LTIAdapter("lti:default", endpoint_route=s.lti_jwks_url))
        self._add(OneRosterAdapter("oneroster:default", endpoint_route=s.oneroster_base_url))
        self._add(XAPIAdapter("xapi:default", endpoint_route=s.xapi_lrs_url))
        self._add(CaliperAdapter("caliper:default", endpoint_route=s.caliper_endpoint_url))
        self._add(CleverAdapter("clever:default", endpoint_route=s.clever_base_url))
        self._add(ClassLinkAdapter("classlink:default", endpoint_route=s.classlink_base_url))
        self._add(EdFiAdapter("edfi:default", endpoint_route=s.edfi_base_url))
        self._add(CASEAdapter("case:default", endpoint_route=s.case_registry_url))
        # QTI and SCORM are content-parsing connectors with no live endpoint.
        self._add(QTIAdapter("qti:default", endpoint_route="bundled"))
        self._add(SCORMAdapter("scorm:default", endpoint_route="bundled"))

    def get(self, standard: Standard) -> Connector | None:
        return self._connectors.get(standard)

    def all(self) -> list[Connector]:
        return list(self._connectors.values())

    def health_summary(self) -> list[dict]:
        return self.health.summary()

    def configured_standards(self) -> list[str]:
        return [c.standard.value for c in self._connectors.values() if c.configured]

    def degraded_standards(self) -> list[str]:
        return [c.standard.value for c in self._connectors.values() if c.degraded]
