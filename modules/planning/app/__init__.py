"""d6 planning app package.

Teacher planning & instruction design. Builds adaptive annual/unit/weekly/daily
plans mapped to the ontology, readiness-aware differentiation, a planned-vs-delivered
teacher diary, and a pacing-protection feed.

All cross-context behavioral data carries ONLY an opaque canonical_uuid (never PII).
Every outbound dependency (scheduling, intelligence) is injected so this package
imports safely with no network or DB and is fully unit-testable.
"""

from .plans import (
    PlanScope,
    OutcomeRef,
    PlanItem,
    Plan,
    PlanGenerator,
    PriorPerformance,
)
from .differentiation import (
    MasteryBand,
    LearnerReadiness,
    DifferentiatedTask,
    DifferentiationPlan,
    Differentiator,
)
from .diary import (
    DeliveryStatus,
    DiaryEntry,
    TeacherDiary,
)
from .pacing_link import (
    PacingSignal,
    PacingProtectionFeed,
)
from .events import (
    PlanningEvent,
    EventType,
    EventLog,
)

__all__ = [
    "PlanScope",
    "OutcomeRef",
    "PlanItem",
    "Plan",
    "PlanGenerator",
    "PriorPerformance",
    "MasteryBand",
    "LearnerReadiness",
    "DifferentiatedTask",
    "DifferentiationPlan",
    "Differentiator",
    "DeliveryStatus",
    "DiaryEntry",
    "TeacherDiary",
    "PacingSignal",
    "PacingProtectionFeed",
    "PlanningEvent",
    "EventType",
    "EventLog",
]
