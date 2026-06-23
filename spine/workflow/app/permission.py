"""The permission-ladder enforcement (INVARIANT 8).

This module classifies an action onto a rung and returns a *decision object*. It
never performs the side effect itself — it only states whether, and under what
conditions, the action may proceed.

The ladder:

    recommend -> prepare -> execute_with_permission -> safe_automatic

The keystone rule: any action whose effect SENDS, SUBMITS, PUBLISHES, DELETES,
CHARGES, or GRADES is CONSEQUENTIAL. A consequential action:
  * can never be classified safe_automatic;
  * is pinned at execute_with_permission;
  * CANNOT auto-fire — ``may_autofire`` is always False for it, regardless of
    confidence or policy. It needs an explicit human approval decision.

Low-risk, in-policy, non-consequential actions MAY be safe_automatic and may
auto-fire — but only inside an explicit policy allow-list. Anything not on the
allow-list defaults to ``recommend`` (surface it; the human decides). We fail
closed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import LadderStage

#: Effect verbs that make an action consequential. INVARIANT 8 names
#: send/submit/publish/delete/charge; grading is added because grading a learner
#: is a high-stakes judgment that must never auto-fire (CORE correctness).
CONSEQUENTIAL_VERBS: frozenset[str] = frozenset(
    {"send", "submit", "publish", "delete", "charge", "grade"}
)

#: Default policy: which non-consequential action kinds may be safe_automatic.
#: An institution policy can supply its own allow-list; absent one, we fail
#: closed to ``recommend`` for anything not listed here.
DEFAULT_SAFE_AUTOMATIC_KINDS: frozenset[str] = frozenset(
    {
        "recompute_mastery",  # internal recomputation, no outward effect
        "refresh_dashboard",  # read-side cache refresh
        "log_observation",  # append an internal, non-PII observation
        "schedule_reminder_internal",  # queue a reminder for later human review
    }
)


@dataclass(frozen=True)
class ActionDescriptor:
    """A description of what a recommendation would *do* if acted on.

    ``effect_verb`` is the primitive effect (e.g. 'send', 'recompute'). ``kind``
    is the named action used to look up policy. ``targets_external`` is True when
    the effect leaves the platform boundary (a message to a parent, a published
    paper) — such effects are treated conservatively.
    """

    kind: str
    effect_verb: str
    targets_external: bool = False
    description: str = ""


@dataclass(frozen=True)
class LadderDecision:
    """The classification result — a decision, never a side effect."""

    stage: LadderStage
    is_consequential: bool
    may_autofire: bool
    reason: str
    requires_human_approval: bool
    #: The action this decision is about, echoed for the audit trail.
    action_kind: str = ""
    #: Policy allow-list consulted, for provenance.
    policy_basis: str = ""


@dataclass
class LadderPolicy:
    """Institution-scoped policy for what may run unattended.

    Absent an explicit allow-list the runtime fails closed: only the conservative
    DEFAULT_SAFE_AUTOMATIC_KINDS are eligible, and only when non-consequential.
    """

    safe_automatic_kinds: frozenset[str] = field(default=DEFAULT_SAFE_AUTOMATIC_KINDS)
    #: When True, even allow-listed external-facing effects stay manual.
    external_effects_always_manual: bool = True


def is_consequential(action: ActionDescriptor) -> bool:
    """True when the action sends/submits/publishes/deletes/charges/grades."""
    return action.effect_verb.strip().lower() in CONSEQUENTIAL_VERBS


def classify_action(
    action: ActionDescriptor,
    policy: LadderPolicy | None = None,
) -> LadderDecision:
    """Classify an action onto the ladder and return a decision object.

    This NEVER performs the action. It states the rung, whether the action is
    consequential, whether it may auto-fire, and the reason — for the audit
    trail and for ``execute`` to honour.
    """
    policy = policy or LadderPolicy()
    consequential = is_consequential(action)

    if consequential:
        # Pinned: execute_with_permission, never auto-fire, needs a human.
        return LadderDecision(
            stage=LadderStage.EXECUTE_WITH_PERMISSION,
            is_consequential=True,
            may_autofire=False,
            requires_human_approval=True,
            reason=(
                f"Action '{action.kind}' has a consequential effect "
                f"('{action.effect_verb}'); INVARIANT 8 pins it to "
                "execute_with_permission and forbids auto-fire."
            ),
            action_kind=action.kind,
            policy_basis="consequential-verb",
        )

    # Non-consequential. Eligible for safe_automatic only if policy allows AND
    # it does not leave the platform boundary under a conservative policy.
    external_blocked = action.targets_external and policy.external_effects_always_manual
    allow_listed = action.kind in policy.safe_automatic_kinds

    if allow_listed and not external_blocked:
        return LadderDecision(
            stage=LadderStage.SAFE_AUTOMATIC,
            is_consequential=False,
            may_autofire=True,
            requires_human_approval=False,
            reason=(
                f"Action '{action.kind}' is non-consequential and in the "
                "safe-automatic policy allow-list; it may proceed unattended "
                "with a full audit trail."
            ),
            action_kind=action.kind,
            policy_basis="safe-automatic-allow-list",
        )

    # Fail closed: surface it, let the human decide.
    reason_tail = (
        "it leaves the platform boundary and policy keeps external effects manual"
        if external_blocked
        else "it is not in the safe-automatic policy allow-list"
    )
    return LadderDecision(
        stage=LadderStage.RECOMMEND,
        is_consequential=False,
        may_autofire=False,
        requires_human_approval=False,
        reason=(
            f"Action '{action.kind}' is non-consequential but {reason_tail}; "
            "defaulting to 'recommend' (fail closed) — surface it for a human."
        ),
        action_kind=action.kind,
        policy_basis="fail-closed-default",
    )


def may_autofire(action: ActionDescriptor, policy: LadderPolicy | None = None) -> bool:
    """Convenience: True only when the action may proceed without a human."""
    return classify_action(action, policy).may_autofire
