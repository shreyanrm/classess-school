# 15 · Master Checklist

The running ledger. Grouped by workstream so groups run in parallel (`14`). Keep it green
between checkpoints. `[ ]` open · `[~]` in progress · `[x]` done + both gates passed.

## Universal definition of done (applies to every item)

- [ ] On v4.1 tokens only — no coral/cream/Fraunces, no shadows, no generic defaults.
- [ ] Ships empty, loading, error, offline, permission states (designed, not defaulted).
- [ ] Every call gateway'd; auth via identity; no direct DB/Auth from a surface.
- [ ] Emits its events (every consequential action); reads governed views, not raw
      canonical.
- [ ] Mastery shown as independence-aware plain language to learners/parents — no raw
      score/formula.
- [ ] AI output carries a ConfidenceBand + opens an EvidenceDrawer; nothing unverified
      renders.
- [ ] Consequential actions wrapped in ApprovalControl + emit an audit event.
- [ ] One engine — no mastery/gap/evidence logic re-implemented in TypeScript.
- [ ] Multilingual + code-switching where text is shown; subject terms preserved.
- [ ] Confidentiality scrub clean (no codenames/personal-names/board-lockin/real-orgs;
      `₹X,XXX`; no plaintext secrets).
- [ ] `npm run ci` green (typecheck → vitest → pytest → `next build`).

---

## Group 0 — Wave 0: contracts + base + the four fixes (serial)

- [ ] `/contracts` locked: events, evidence, openapi, db, mastery, gaps, evaluation,
      ontology, tokens, capabilities.
- [ ] Data substrate: PII vault physically separate; `events` append-only + immutable;
      `consents`; `app_memberships`; `audit_log`; rebuildable projections (profiles,
      learner_graph, feature_store).
- [ ] PII rule proven: nothing outside the vault holds PII; `canonical_uuid` opaque;
      delete severs link, aggregate remains.
- [ ] Identity service live; no app-local signup; tokens issued + verified.
- [ ] Gateway live; RBAC + ABAC + consent enforced at the wall; schema-validated; audited.
- [ ] Event round-trips end to end (emit → store → governed view read).
- [ ] Secrets in Infisical only; key naming `clss.<app>.<env>.<purpose>`; rotation runbook.
- [ ] CI pipeline + the two gates wired.
- [ ] design-system package built on v4.1 tokens; the component vocabulary (`10`) stubbed.
- [ ] **Fix 1:** home is conversation-first (the dashboard/module-grid + floating-orb-home
      removed).
- [ ] **Fix 2:** the duplicated TS engine (`lib/engine.ts`) deleted; call sites read the
      spine via the typed client + cache.
- [ ] **Fix 3:** every surface routed through gateway + identity (no direct Supabase Auth/
      DB).
- [ ] **Fix 4:** every module slated to a real surface; the 136-map is the target.
- [ ] **Wave 0 done-line met → stop + report.**

## Group 1 — secure core (highest rigor; spans waves, lands early)

- [ ] AI fabric: LiteLLM router with Track 1/Track 2 config separated.
- [ ] Capability registry: typed I/O, ladder level, consent, events, track per capability.
- [ ] Generate-and-verify substrate: deterministic checks + second-model cross-check + the
      confidence gate (refuses + flags "needs human review").
- [ ] Agent layer: least-privilege, observable (Langfuse), reversible; AI control centre +
      emergency disable.
- [ ] Learner-record engine (b8): mastery (P×R×I×D×Re×C, never an average), ten gap types
      (confirmed on ≥2 signals), evidence weighting — the single source of truth.
- [ ] Governance: immutable audit; break-glass; data lineage; retention; erasure recompute.
- [ ] Per-user memory: PII-free, consent-gated, revocable.

## Group 2 — capability modules (parallel worktrees; bind to contracts)

Each module: Owns/Emits/Consumes/Data/API/Surfaces/DoD from `13` met; events emitted;
governed views exposed; adapters contract-complete against named env vars.

- [ ] b1 Institution & Policy
- [ ] b2 Scheduling & Continuity
- [ ] b3 Content & Resources
- [ ] b4 Teaching
- [ ] b5 Attendance
- [ ] b6 Coursework & Assessment
- [ ] b7 Learning
- [ ] b8 Learner Record (with Group 1)
- [ ] b9 Relationships & Communication
- [ ] b10 Teacher Growth
- [ ] b11 Intelligence Views

## Group 3 — Student surfaces (33) — `06`

- [ ] Home & companion (3): Today · Vidya companion · Notifications
- [ ] Learn (6): Learn home · Subject hub · Chapter view · Lesson player · Concept detail ·
      Misconception fix
- [ ] Practice (4): Practice home · Practice session · Practice review · Spaced retrieval
- [ ] Assess (5): Quizzes & tests · Quiz attempt · Quiz result · Mock tests · Mock result
      & forecast
- [ ] Work (4): Assignments · Assignment & submit · Project workspace · Submission history
- [ ] Progress (5): Knowledge view · Mastery detail · My gaps · Portfolio · Achievements &
      credentials
- [ ] Plan & ops (6): Revision planner · Readiness forecast · Attendance · Request leave ·
      Calendar · Settings

## Group 4 — Teacher surfaces (49) — `07`

- [ ] Home & companion (4): Today · Vidya copilot · Proactive feed · Notifications
- [ ] Plan (4): Planning home · Lesson plan · Differentiation · Teacher diary
- [ ] Classroom (5): Live classroom · Board detail · Live poll/quiz · Device-free check ·
      Session summary
- [ ] Attendance (3): Attendance · Risk & reconciliation · My attendance
- [ ] Content (3): Content library · Generate material · Resource detail
- [ ] Assign (5): Assignments · Create assignment · Review submissions · Project management
      · Originality review
- [ ] Assessment (6): Papers · Blueprint · Generate paper · Question bank · Schedule &
      proctoring · Moderation
- [ ] Evaluate (5): Evaluation queues · Evaluate (Mode 1) · Scanned (Mode 2) · Rubric
      library · Confidence review
- [ ] Students & insights (7): Students · Student detail · Gradebook · Reports · Report
      detail · Remedial · Class analysis
- [ ] Relationships (4): Parent meetings · PTM prep · PTM follow-up · Communicate
- [ ] Growth & settings (3): Growth & coaching · Continuity/handover · Settings

## Group 5 — Admin surfaces (34) — `08`

- [ ] Home & assistant (4): This morning · Exceptions · Institution assistant · Ask-anything
- [ ] Setup & governance config (6): Blueprint wizard · Hierarchy · Policies · Roles ·
      Consent · Hyperlocalization
- [ ] Academic config (3): Curriculum & ontology · Grading config · Assessment config
- [ ] Calendar & timetable (4): Academic calendar · Timetable · Substitution · Pacing
- [ ] Intelligence (6): Intelligence · Study quadrant · Target analytics · Coverage ·
      Trajectory · Teacher analytics
- [ ] People & ops (5): Students registry · Teachers & staff · Houses · Admissions (link) ·
      Content management
- [ ] Governance & integrations (6): AI control centre · Audit · Break-glass · Data
      governance · Integrations (FLUID) · Settings

## Group 6 — Parent surfaces (20) — `09`

- [ ] Home & companion (4): This week · Switch child · Parent companion · Notifications
- [ ] Reports (6): Reports & reviews · Progress report · Attendance review · Exam review ·
      Test analysis · Syllabus coverage
- [ ] Engagement (8): What to do at home · Learn alongside · Parent meetings · PTM prep ·
      PTM follow-up · Messages · The shareable win · Events & calendar
- [ ] Ops (2): Fees (Feesable link) · Account & settings

## Group 7 — component library (`10`)

- [ ] BriefingCard · RecommendationItem · EvidenceDrawer · ConfidenceBand · MasteryView ·
      IgniteDot · AssistanceLadderControl · KnowledgeView · StudyQuadrant · GradingMatrix ·
      EvaluationReviewTable · ApprovalControl · ChildSwitcher · ProofArtifact · VidyaDock ·
      TightMatrix · SubjectCard · Trajectory · ReportArtifact · InteractiveTeachingBlock ·
      Transcript
- [ ] Cross-component invariants enforced (band+drawer on AI output; approval+audit on
      consequential; MasteryView never a number; all five states; no shadows; one accent).

## Group 8 — Vidya & AI fabric (`11`)

- [ ] Vidya is the conversation-first home (all roles, role-shaped); docked on deep pages.
- [ ] Orchestrator: intent → context → plan → governed tools → verify → act → events.
- [ ] Model router two-track; capability-level routing config.
- [ ] Generate-and-verify on every content path; confidence gate enforced.
- [ ] Permission ladder enforced at the gateway on every agent action.
- [ ] Multimodal (text/voice/image/document/screen); multilingual + code-switching.
- [ ] Child-safety on every free-text + media surface; crisis → human escalation.
- [ ] Observability (Langfuse) tied to the event store; Track 2 slot present.

## Group 9 — data & contracts (`12`)

- [ ] Three store classes built; PII rule holds; projections rebuildable from events.
- [ ] Event catalog emitted; envelope complete (consent_ref, trace_id, scope).
- [ ] Governed read views power the UI (no engine internals, no TS re-implementation).
- [ ] Seed/mock data fictional + scrubbed; exercises every state + every confidence band.

## Group 10 — Wave 3: ecosystem scale + parked providers (`13` ledger)

- [ ] FLUID connectors (LTI/OneRoster/xAPI/QTI/SCORM/Clever/Ed-Fi/CASE/MCP) contract-
      complete + health-monitored.
- [ ] Comms lifecycle activates on WhatsApp/SMS/email keys.
- [ ] Multi-tenancy across group/franchise/programme/network; isolation proven.
- [ ] Track 2 capability swaps in by router config (no rebuild).
- [ ] Expo native tree: offline-first parity for the core flows.
- [ ] Parked adapters activate on key placement: live_media, recording, ocr, transcription,
      media_store, face, proctoring, payments, gpu.

## Final quality gates (before any release)

- [ ] Full click-through of every role: no orphan pages, no dead links, every rail entry
      reaches a real page.
- [ ] Every page renders all five states with seed data.
- [ ] The whole circuit demonstrably works for each role: identity → surface → capability →
      event → engine → recommend → approve → execute → outcome → learn.
- [ ] No coral/cream/Fraunces remnant; no shadow anywhere; one accent per surface; ultramarine
      only for brand + ignite.
- [ ] No raw learner-facing scores; mastery is independence-aware everywhere.
- [ ] Confidentiality scrub clean across the whole codebase, docs, seed data, commits.
- [ ] Secrets env-only; no plaintext anywhere including logs.
- [ ] `npm run ci` green; both gates pass; `ops/` records every provisioning step.
- [ ] Each wave's done-line was reported before the next began.
