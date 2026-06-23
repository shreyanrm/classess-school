"""The capability registry (A4).

Governed, least-privilege capabilities. Agents invoke capabilities here; they
hold NO credentials (INVARIANT 8 — the permission ladder). Each capability
declares:

  - its input / output schema refs (contract ids, resolved elsewhere),
  - the TRACK it runs on (1 = external, 2 = proprietary/edge — never conflated),
  - a least-privilege scope (a single purpose code + the minimal data scopes),
  - whether its output must pass the confidence gate (``requires_verification``),
  - its CONSEQUENCE (the permission-ladder rung — see ``orchestrator``).

Schema refs are contract ids, not inlined, so the registry stays a thin index
over the contract surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Consequence(str, Enum):
    """The permission-ladder rung a capability sits on (INVARIANT 8).

    Anything that SENDS / SUBMITS / PUBLISHES / DELETES / CHARGES / GRADES is
    consequential and requires explicit human approval — the orchestrator
    returns ``requires_approval`` rather than executing.
    """

    # Safe-automatic: read/analyse, produces a recommendation or draft only.
    RECOMMEND = "recommend"
    PREPARE = "prepare"
    # Consequential: needs explicit human approval before it can run.
    EXECUTE_WITH_PERMISSION = "execute_with_permission"


CONSEQUENTIAL = {Consequence.EXECUTE_WITH_PERMISSION}


@dataclass(frozen=True)
class CapabilityScope:
    """A least-privilege scope grant. Never broader than needed."""

    purpose: str
    data_scopes: tuple[str, ...]
    emits_events: bool


@dataclass(frozen=True)
class Capability:
    """A capability descriptor in the registry."""

    name: str
    description: str
    input_schema_ref: str
    output_schema_ref: str
    track: int  # 1 or 2 — INVARIANT 11, never conflated
    least_privilege: CapabilityScope
    requires_verification: bool
    task_class: str
    consequence: Consequence = Consequence.RECOMMEND

    @property
    def is_consequential(self) -> bool:
        return self.consequence in CONSEQUENTIAL


class CapabilityRegistry:
    """An in-process registry of governed capabilities."""

    def __init__(self) -> None:
        self._by_name: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        if capability.track not in (1, 2):
            raise ValueError(f"capability '{capability.name}' has invalid track {capability.track}")
        if capability.name in self._by_name:
            raise ValueError(f"capability '{capability.name}' already registered")
        self._by_name[capability.name] = capability

    def get(self, name: str) -> Capability | None:
        return self._by_name.get(name)

    def require(self, name: str) -> Capability:
        cap = self._by_name.get(name)
        if cap is None:
            raise KeyError(f"unknown capability: {name!r}")
        return cap

    def all(self) -> tuple[Capability, ...]:
        return tuple(self._by_name.values())

    def for_track(self, track: int) -> tuple[Capability, ...]:
        return tuple(c for c in self._by_name.values() if c.track == track)


def default_registry() -> CapabilityRegistry:
    """The default set of governed capabilities the fabric exposes.

    All generation/evaluation/conversation capabilities require verification
    (INVARIANT 7). Tracks are explicit (INVARIANT 11). Consequence rungs are set
    so the orchestrator can enforce the permission ladder.
    """
    reg = CapabilityRegistry()

    reg.register(Capability(
        name="content.generate-practice-item",
        description="Generate a single practice item against the mapped curriculum.",
        input_schema_ref="contract:ai.GeneratePracticeItemInput",
        output_schema_ref="contract:ai.PracticeItem",
        track=1,
        least_privilege=CapabilityScope(
            purpose="practice_item_generation",
            data_scopes=("ontology.skill", "curriculum.map"),
            emits_events=True,
        ),
        requires_verification=True,
        task_class="content.generate-practice-item",
        consequence=Consequence.PREPARE,  # a draft item; not served until verified
    ))

    reg.register(Capability(
        name="evaluate.response",
        description="Evaluate a learner response and produce evidence (independent vs supported).",
        input_schema_ref="contract:ai.EvaluateResponseInput",
        output_schema_ref="contract:ai.EvaluationResult",
        track=1,
        least_privilege=CapabilityScope(
            purpose="response_evaluation",
            data_scopes=("submission.response", "rubric.item"),
            emits_events=True,
        ),
        requires_verification=True,
        task_class="evaluation.response",
        # GRADING is consequential — human-final on consequential marks.
        consequence=Consequence.EXECUTE_WITH_PERMISSION,
    ))

    reg.register(Capability(
        name="explain.step",
        description="Explain one solution step (assistance ladder; pose-struggle-reveal aware).",
        input_schema_ref="contract:ai.ExplainStepInput",
        output_schema_ref="contract:ai.ExplainStepResult",
        track=1,
        least_privilege=CapabilityScope(
            purpose="step_explanation",
            data_scopes=("ontology.skill", "item.solution"),
            emits_events=False,
        ),
        requires_verification=True,
        task_class="content.explain-step",
        consequence=Consequence.RECOMMEND,
    ))

    reg.register(Capability(
        name="conversation.companion-turn",
        description="A bounded companion conversational turn (edge tier; high-frequency).",
        input_schema_ref="contract:ai.CompanionTurnInput",
        output_schema_ref="contract:ai.CompanionTurnResult",
        track=1,
        least_privilege=CapabilityScope(
            purpose="companion_dialogue",
            data_scopes=("conversation.context",),
            emits_events=True,
        ),
        requires_verification=True,
        task_class="conversation.companion-turn",
        consequence=Consequence.RECOMMEND,
    ))

    reg.register(Capability(
        name="conversation.voice-speech-to-speech",
        description=(
            "Vidya speech-to-speech turn (Gemini Live native audio): learner "
            "audio in, spoken reply out, behind the confidence gate."
        ),
        input_schema_ref="contract:ai.VoiceTurnInput",
        output_schema_ref="contract:ai.VoiceTurnResult",
        track=1,  # Track 1 — external LLM routing (INVARIANT 11)
        least_privilege=CapabilityScope(
            purpose="voice_companion_dialogue",
            # Minimal: the opaque conversation handle only — no PII.
            data_scopes=("conversation.context",),
            emits_events=True,
        ),
        requires_verification=True,  # audio passes the confidence gate (INVARIANT 7)
        task_class="conversation.voice-speech-to-speech",
        consequence=Consequence.RECOMMEND,
    ))

    return reg
