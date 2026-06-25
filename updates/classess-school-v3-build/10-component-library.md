# 10 · Component Library

The shared vocabulary every surface composes from. Built once in
`packages/design-system` (or `surfaces/web/components`), v4.1-token-driven, framework-
agnostic CSS mapping 1:1 to React. Each spec: *Purpose · Anatomy · Behaviour · Tokens ·
States · v2→v4 · DoD.* No component ships a shadow; depth is hairline + tonal step +
frost.

## Primitives (from the kit, extended)

`Button` (primary/secondary/ghost/danger; sizes; loading), `Card` (hairline, no shadow),
`Matrix` (the tight grid wrapper), `Chip`/`SuggestionChip` (sharp 2–3px), `Stat` (mono
tabular), `Input`/`Select`/`Textarea`, `Tabs`, `Drawer`, `Sheet`, `Toast`, `Skeleton`,
`EmptyState`, `ErrorState`, `OfflineBadge`, `PermissionGate`. These cover the shell; the
list below is the platform-specific vocabulary the surface specs call by name.

---

## The intelligence components (the heart of the makeover)

### BriefingCard
- *Purpose:* the home/today primary — one next action with its reasoning. Replaces v2's
  dashboard-as-home.
- *Anatomy:* eyebrow (context) · headline (the action, light-weight large) · plain-
  language why · meta (time estimate · progress it creates) · actions (Start · Why this ·
  Ask Vidya).
- *Behaviour:* exactly one primary action; Why opens the EvidenceDrawer; never shows a raw
  score.
- *Tokens:* surface bg, ink headline, one subject/role accent, hairline divider.
- *States:* loading (skeleton), empty (first-time prompt), offline (cached + "will
  refresh").
- *v2→v4:* v2 donut+KPI dashboard → one calm card.
- *DoD:* single action; plain-language why; evidence one tap; no score.

### RecommendationItem
- *Purpose:* one unit of the proactive feed — what was found + the prepared action.
- *Anatomy:* what-was-found · evidence link · confidence band · owner · due · consequence-
  of-ignoring · actions (Approve · Adjust · Decline).
- *Behaviour:* Approve runs the prepared action through the permission ladder; outcome
  tracked back; manage-by-exception.
- *States:* approved/declined reflect immediately; loading; empty ("nothing needs you").
- *v2→v4:* v2 static analytics → an actionable, owned, evidenced recommendation.
- *DoD:* full provenance (evidence·confidence·owner·due·why); Approve executes; outcome
  returns.

### EvidenceDrawer
- *Purpose:* the provenance behind any conclusion or AI output. Invariant 7.
- *Anatomy:* the claim · the evidence list (attempts/quizzes/observations with dates + the
  independent-vs-supported flag) · the model/source + confidence · "why am I seeing this."
- *Behaviour:* opens from any conclusion, mastery cell, recommendation, or generated
  artifact; read-only; deep-links to each source.
- *v2→v4:* v2 had no provenance surface → first-class everywhere.
- *DoD:* every conclusion in the app can open it; lists real evidence; shows confidence +
  source.

### ConfidenceBand
- *Purpose:* the certainty of an AI output (high/medium/low) driving the workflow.
- *Anatomy:* a three-segment hairline band + label; optional "needs human review" tag.
- *Behaviour:* high → auto-provisional; medium → review; low → must-review. Renders on
  every generated/auto-evaluated artifact.
- *Tokens:* semantic success/warning/danger (never subject hues).
- *DoD:* present on all AI output; drives the gate; gated publish honours it.

### MasteryView (independence-aware)
- *Purpose:* the learner-facing mastery primitive — independent vs support-dependent in
  plain language. **Never a number, never the formula.**
- *Anatomy:* state label ("can do independently" / "can do with guidance" / "review due")
  · the six dimensions in plain language · the IgniteDot · open-evidence.
- *Behaviour:* fed only by a gateway read of the spine engine; ignites on genuine mastery.
- *v2→v4:* v2 mastery % / donut → plain-language independence state.
- *DoD:* no raw score/formula; six dimensions in words; evidence on tap; ignite fires
  correctly.

### IgniteDot
- *Purpose:* the signature mastery moment.
- *Behaviour:* an ultramarine ring expands and fades around the dot on genuine
  comprehension (the `ignite` motion, `04`); reduced-motion shows a static filled state.
- *Tokens:* ultramarine `#1F35E0` (the only place beyond the brand mark it appears).
- *DoD:* fires on real mastery only; respects reduced-motion.

### AssistanceLadderControl
- *Purpose:* the productive-struggle dial.
- *Anatomy:* rungs Learn → Coach → Hint → Work-with-me → Check-my-work → Independent;
  current rung highlighted.
- *Behaviour:* the learner can step up for help; the system steps down as mastery grows
  (support fades visibly); the level is recorded on each attempt (independent vs
  supported).
- *DoD:* six rungs; fades with mastery; level written to the attempt event.

### KnowledgeView
- *Purpose:* the queryable map of a learner's understanding (student) / a class (teacher).
- *Anatomy:* nodes coloured by independent vs support-dependent; edges = prerequisites; a
  natural-language query bar; tap → EvidenceDrawer; ignite on mastered regions.
- *Behaviour:* reads the learner graph (governed); answers "what am I weakest at / what
  unlocks X"; never a score.
- *v2→v4:* v2 galaxy/knowledge-map visual → the queryable, evidence-linked, igniting view.
- *DoD:* independent-vs-dependent visible; queryable; evidence on tap; ignite; no score.

### StudyQuadrant
- *Purpose:* star / emerging / potential / at-risk grouping + intervention launcher.
- *Anatomy:* 4-band plot (mastery × consistency or performance × growth), students as
  points; tap a band → group + suggested set.
- *Behaviour:* drawn from the mastery model; tapping launches grouping/remedial.
- *v2→v4:* v2 4-colour scatter → re-skinned + actionable.
- *DoD:* four bands from real mastery; tap-to-group acts; v4 palette.

### GradingMatrix (student × question)
- *Purpose:* the per-response evaluation grid.
- *Anatomy:* rows students · columns questions · cells correct/incomplete/misunderstood
  (semantic colour) · per-cell confidence · open-response.
- *Behaviour:* states separated (not just right/wrong); feeds mastery + gaps; human-final
  on consequential marks; the matrix-hover wipe (`04`).
- *v2→v4:* v2 red/green heatmap → states + confidence + engine feed.
- *DoD:* three states; confidence per cell; feeds engine; human-final.

### EvaluationReviewTable
- *Purpose:* the confidence-banded evaluation queue.
- *Anatomy:* band (high/medium/low) · items · the action (auto-provisional/review/must-
  review) · publish (permission-gated).
- *DoD:* banded; gated publish; voice-entry hook.

### ApprovalControl
- *Purpose:* the permission ladder made visible. Invariant 8.
- *Anatomy:* the prepared action summary · its consequence · Approve / Adjust / Decline ·
  who approved + when (to audit).
- *Behaviour:* wraps anything that sends/submits/publishes/deletes/charges/grades; nothing
  consequential fires without it; emits an audit event.
- *DoD:* present on every consequential action; writes an audit event; no bypass.

### ChildSwitcher (parent)
- *Purpose:* set the active child for every surface.
- *Behaviour:* switching re-renders the whole surface against the new child; reads consent-
  scoped to that relationship.
- *DoD:* re-renders all reads; consent-scoped.

### ProofArtifact (the shareable win)
- *Purpose:* a WhatsApp-native, evidence-linked proof of genuine progress.
- *Behaviour:* generated-and-verified; child-triggerable; permission-scoped; native share.
- *DoD:* verified; evidence-linked; child-triggerable; native share.

### VidyaDock
- *Purpose:* Vidya present on every deep page (the retained orb pattern — only docked,
  never the home).
- *Anatomy:* collapsible panel/orb · conversation · drives the page it sits on.
- *Behaviour:* operates the current surface within the permission ladder; collapsible;
  never a dead end.
- *v2→v4:* v2 floating-orb-as-home → docked companion over a real workspace; home stays
  conversation-first.
- *DoD:* on every deep page; collapsible; acts within the ladder.

---

## Content/visual components

`TightMatrix` (the hairline-shared grouping, `04`), `SubjectCard` (sets `--subject` +
`--subject-ink`; one accent), `Trajectory` (actual solid / predicted dotted; chart only
where the shape is read), `Chart` wrapper (used sparingly — a chart survives only when a
human reads its shape; otherwise convert to a RecommendationItem), `ReportArtifact`
(printable, re-skinned report cards / holistic cards), `InteractiveTeachingBlock` (the
verified, generated lesson visuals — JSXGraph/Mafs/Three.js per the content libraries),
`Transcript` (searchable session/recording transcript).

## Cross-component invariants

- Every AI output renders a ConfidenceBand and can open an EvidenceDrawer.
- Every consequential action renders an ApprovalControl and emits an audit event.
- Learner-facing mastery uses MasteryView — never a raw number.
- Every list/grid ships empty, loading, error, offline, permission states.
- No shadows; depth via hairline + tonal step + frost only.
- One accent per surface; ultramarine reserved for brand + ignite.
