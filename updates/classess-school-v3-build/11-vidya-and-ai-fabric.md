# 11 · Vidya and the AI Fabric

Vidya is the front door; the AI fabric is the secure-core machinery behind it. The
team's work is **integration only** — calling governed capabilities through the API.
Surfaces never build the orchestrator, the agents, or touch the platform stores.

## Vidya as the home (not a chat button)

Vidya **is** the conversation-first home (`05`). Calm and near-empty by default: a
greeting and one composer. The user states intent; Vidya decides whether to answer, do,
or compose a surface. Role-shaped on one shell: student companion (protects struggle),
teacher copilot (prepares + executes), admin assistant (commands + governs), parent
companion (reassures + guides). On deep pages Vidya is **docked** (the VidyaDock), still
driving. Full capability set on every surface:

- On-screen explanations and self-assembling derivations.
- Misconception detonation (the one counterexample that breaks a wrong model).
- The editable canvas with sources + the EvidenceDrawer alongside.
- Interactive, generated, **verified** teaching content (JSXGraph/Mafs/Three.js).
- Multimodal input — text, voice, image, document, screen.
- The assistance ladder + teach-back (productive struggle, never answer-handover).
- Generative UI — composes real surfaces inline within the permission ladder.
- Multilingual with code-switching; subject terminology preserved.
- Child-safety on every free-text turn.

## The orchestrator

The single brain routing every request: classify intent → assemble context (consented
memory, mastery/gaps, ontology, surface state) → select capabilities → plan → execute
through governed tools → verify → respond/act → emit events. It holds no credentials of
its own beyond the least-privilege capabilities it is granted, and every consequential
step passes the permission ladder. **Never named in team-facing output** — referred to
as "the orchestrator" / "Vidya."

## The model router (LiteLLM) — two tracks, never conflated

- **Track 1 — external market LLMs** (Claude, Gemini, OpenAI, others) routed per feature
  by best-fit or an explicit choice. Routing config is data, not code: per-capability
  model, fallback, cost/latency ceilings, context budget.
- **Track 2 — proprietary fine-tuned + edge SLMs** — the margin and moat. The slot exists
  in router config from line one; filled later with **no re-architecture**. Edge SLMs
  power the narrow offline paths (simple help, offline evaluation fallback).
- The two are separate in gateway/router config with different ownership (invariant 11).
  A capability declares which track/model it uses; switching is a config change.

## Generate-and-verify (nothing unverified reaches a user)

Every generated artifact — lesson visual, question, paper, explanation, report prose,
proof artifact — passes verification before it renders or is served:

1. **Deterministic checks where possible:** symbolic verification (math/physics), re-run
   simulations, numeric-bounds and unit checks, schema validation.
2. **Second-model cross-check** for content without a deterministic oracle.
3. **The confidence gate** refuses anything that fails; low confidence is flagged "needs
   human review," never silently shipped.

The ConfidenceBand (`10`) renders the result; the EvidenceDrawer shows the source +
checks. This is invariant 7 and is non-negotiable on every content path.

## The capability registry

Agents act only through registered, governed, least-privilege capabilities — never raw
model calls or direct DB access. Each capability declares: inputs/outputs (typed against
`/contracts`), the permission-ladder level it requires, the events it emits, the consent/
purpose it needs, and its track/model. Examples: `generate_and_verify_content`,
`evaluate_submission`, `compose_dashboard`, `generate_timetable`, `propose_substitution`,
`draft_paper`, `suggest_intervention`, `explain_progress`. Surfaces call capabilities;
they never inline the logic.

## The permission ladder (every agent action)

`Recommend → Prepare → Execute-with-permission → Safe-automatic`.

- **Recommend:** surface a suggestion (RecommendationItem).
- **Prepare:** build the artifact/action but do not commit (a draft paper, a proposed
  group, a generated plan).
- **Execute-with-permission:** commit only after the ApprovalControl — anything that
  sends, submits, publishes, deletes, charges, or grades a consequential mark.
- **Safe-automatic:** only the narrow, reversible, policy-permitted, low-risk class
  (e.g. rescheduling a missed revision block within policy). Everything else needs a human.

Agents hold no credentials; they invoke governed capabilities. The ladder level is part
of each capability's contract and is enforced at the gateway.

## The agent layer

Specialised agents coordinated by the orchestrator, each scoped to a bounded job
(planning, evaluation, intervention, communication, analytics composition, ontology
stewardship). Agents are least-privilege, observable (Langfuse), and reversible; their
proposed actions enter the proactive loop and the permission ladder. No agent acts on
anything consequential without human approval; institution admins govern which agents
run, their tools, and routing via the AI control centre (`08`), including an emergency
disable.

## Per-user memory (PII-free, consent-gated)

Vidya remembers within a person's consented scope: preferences, the learner's current
edge, recent threads, language. Memory carries the opaque `canonical_uuid` and behavioral
context only — never PII (invariant 1). It is consent-gated, transparent, and revocable;
deletion severs it with the PII link. Memory sharpens personalization without becoming a
profile dossier the user can't see or control.

## Multimodal

Text, voice (STT/TTS, the voice mark-entry and roll-call paths), image (diagram/graph/
camera understanding for the preventive check + scanned scripts), document (OCR /
document-understanding for content ingestion), and screen context. Each input is consent-
gated where it involves a person (camera/mic) and verified where it produces content.

## Child-safety subsystem (every free-text and media surface)

- Input + output moderation on every turn (age-appropriate, abuse/grooming/self-harm
  classifiers).
- Crisis detection → escalation to a responsible adult, never handled silently by the
  bot.
- No content that sexualises, grooms, isolates, or endangers a minor — ever, under any
  framing.
- Camera/mic/recording strictly consent-gated and purpose-bound; attention signals
  assist, never grade from a face.
- Tighter behavioral-profiling tiers gated by the age/consent the law permits (DPDP —
  treat as an open gating item, `02`).

## Observability (Langfuse + the event seam)

Every model call, capability invocation, verification result, and agent action is traced:
prompt/version, model/track, latency, cost, confidence, verification outcome, the emitted
events. This gives cost/quality control, regression detection, and the audit trail the
governance surfaces read. Tie traces to the immutable event store so every learner-facing
conclusion is reconstructable.

## Track 2 — the model foundry (later, no re-architecture)

The proprietary track: fine-tuned domain models + edge SLMs trained on the platform's own
(consented, de-identified, aggregate) event data — the moat. Built behind the same router
slot and capability contracts, so turning it on is a routing-config change per capability,
not a rebuild. GPU provisioning is a parked step (`13`); the contracts and the slot exist
from line one.
