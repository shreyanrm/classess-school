# 13 · Capability Modules

Eleven modules cover all 22 documented feature domains. Each: *Owns · Emits · Consumes ·
Data · API · Surfaces · DoD.* All are feature-modular inside one FastAPI deployable with
clean boundaries (splittable later); each owns its operational schema, emits events up,
and reads governed views down (never bulk-reads canonical). Spine concerns
(identity/ontology/event/evidence/AI-fabric/governance) live in the spine, never in a
module. Parked-provider adapters are **contract-complete; only the credential is
missing** — each names its env var (`clss.<app>.<env>.<purpose>`, placed in Infisical).

---

### b1 · Institution & Policy
- *Owns:* org structure, hierarchy + relationship graph, policies (inherit/override/lock),
  roles (RBAC) + attribute scoping (ABAC) + delegation, consent grants, hyperlocalization
  config, the blueprint wizard.
- *Emits:* `institution.configured`, `membership.granted`, `consent.granted/revoked`,
  `policy.changed`.
- *Consumes:* identity, ontology.
- *Data:* institutions, nodes, edges, policies (versioned, effective-dated), roles,
  scopes, consents, locale config.
- *API:* configure-institution, set-policy, assign-role, delegate-access, manage-consent,
  set-locale.
- *Surfaces:* Admin Setup, Hierarchy, Policies, Roles, Consent, Hyperlocalization.
- *DoD:* persists + survives reload; RBAC+ABAC+delegation; policy inheritance/versioning;
  consent gates reads; age-tier aware.

### b2 · Scheduling & Continuity
- *Owns:* academic calendar, timetable generation (constraint solver), the 6-level
  substitution ladder, pacing protection.
- *Emits:* `timetable.generated`, `substitution.proposed`, `pacing.behind`,
  `calendar.updated`.
- *Consumes:* institution/policy, attendance (for substitution triggers), coverage.
- *Data:* calendar, slots, constraints (hard/soft/contextual), substitutions, pacing
  records.
- *API:* generate-timetable, propose-substitution, track-pacing, recommend-recovery.
- *Surfaces:* Admin Calendar, Timetable, Substitution, Pacing; Teacher Continuity.
- *DoD:* generation with scored alternatives + human approval; ladder picks up at the
  right point + absence-triggered; pacing recovery within policy.

### b3 · Content & Resources
- *Owns:* the content library, generation (summaries/worksheets/mind maps/decks/interactive
  visuals), ingestion (OCR/transcription/document-understanding), outcome tagging, version/
  licence, dedup.
- *Emits:* `content.generated`, `content.verified`, `content.rejected`, `resource.ingested`.
- *Consumes:* ontology, the AI fabric (generate-and-verify).
- *Data:* resources (pgvector), versions, tags→outcomes, licences.
- *API:* generate-material (verified), ingest-resource, tag-to-outcome, search-content.
- *Surfaces:* Teacher Content library/Generate/Resource; Admin Content management.
- *Adapters:* document OCR / transcription provider — **env:** `clss.school.<env>.ocr`,
  `clss.school.<env>.transcription`. Interactive-media (board 3D/sim) render libs are
  in-app (JSXGraph/Mafs/Three.js); heavy media hosting — **env:**
  `clss.school.<env>.media_store`.
- *DoD:* unified library; verified generation; ingestion tags to ontology; dedup;
  versioning; nothing unverified served.

### b4 · Teaching
- *Owns:* planning (annual/unit/weekly/daily), lesson-plan generation + adapt-to-yesterday,
  differentiation, the teacher diary, the live classroom + interactive board + live polls +
  device-free checks + session summary.
- *Emits:* `plan.generated`, `plan.submitted`, `class.launched`, `engagement.signal`,
  `poll.run`, `session.summarised`.
- *Consumes:* ontology, learner record (mastery/gaps), content, the AI fabric.
- *Data:* plans, diary, class sessions, polls, summaries.
- *API:* generate-plan, adapt-plan, differentiate, launch-class, run-poll, device-free-
  check, summarise-session.
- *Surfaces:* Teacher Plan*, Live*, Board, Poll, Device-free, Session summary.
- *Adapters:* live-class video/recording media — **env:** `clss.school.<env>.live_media`,
  `clss.school.<env>.recording`.
- *DoD:* plans against curriculum + adapt-to-yesterday; one-launch period; verified board
  content; attention assists-not-grades; consent-gated recording.

### b5 · Attendance
- *Owns:* marking (photo-scan/voice/manual — assist-not-finalise), risk detection
  (consecutive/chronic/pattern), reconciliation (gate vs classroom), access control
  (manual/face/geofence — consent-gated, human-confirmed), staff attendance + leave.
- *Emits:* `attendance.marked`, `attendance.risk`, `attendance.reconcile_flag`,
  `leave.requested`.
- *Consumes:* institution/policy, identity, consent.
- *Data:* attendance records, risk flags, leave, access-control config.
- *API:* mark-attendance, detect-risk, reconcile, request-leave.
- *Surfaces:* Teacher Attendance/Risk/My-attendance; Admin attendance + access-control;
  Student/Parent attendance + leave.
- *Adapters:* face-recognition provider — **env:** `clss.school.<env>.face`; geofence —
  device/location only, consent-gated.
- *DoD:* multi-method, never auto-final; offline capture + sync; risk types + reconciliation
  flags for human review; consent-gated biometrics.

### b6 · Coursework & Assessment
- *Owns:* assignments (homework/worksheet/journal/portfolio/project), projects + rubrics +
  balanced grouping, papers + blueprints + multi-set generation, the question bank,
  scheduling/seating/proctoring/accommodations, moderation/publish gate.
- *Emits:* `assignment.created`, `submission.created`, `assessment.submitted`,
  `paper.generated`, `moderation.approved`.
- *Consumes:* ontology, learner record, content, the AI fabric.
- *Data:* assignments, submissions (draft→final), projects, papers, blueprints, items
  (QTI), schedules.
- *API:* create-assignment (verified), generate-paper (verified), schedule-exam, moderate.
- *Surfaces:* Teacher Assign*, Papers/Blueprint/Generate/Question-bank/Schedule/Moderation;
  Student Work*; the assessment-config admin surfaces.
- *Adapters:* proctoring provider — **env:** `clss.school.<env>.proctoring`; PDF→questions
  via the AI fabric.
- *DoD:* verified generation; multi-set; differentiation; QTI import; moderation gate;
  permission-gated assign/publish.

### b7 · Learning (learner experience)
- *Owns:* the lesson player (pose→predict→reveal, ladder), practice (adaptive, gap-mapped),
  spaced retrieval, the misconception-fix flow, the preventive (Mode-3) check, teach-back.
- *Emits:* `attempt`, `prediction.committed`, `misconception.detected/resolved`,
  `retrieval.completed`, `teachback.completed`.
- *Consumes:* ontology, learner record, content + the AI fabric (generate-and-verify,
  detonation, hints).
- *Data:* sessions, attempts, retrieval schedules.
- *API:* serve-lesson, serve-practice, schedule-retrieval, preventive-check, teach-back.
- *Surfaces:* Student Learn*, Practice*, Lesson, Concept, Misconception, Retrieval,
  Assignment-submit (preventive).
- *DoD:* reveal gated on prediction; ladder fades; nothing unverified; preventive never
  reveals the answer; attempts carry the independence flag; offline lesson/practice packs.

### b8 · Learner Record
- *Owns:* the mastery model + ten-gap engine + evidence weighting (the **single** engine
  behind the gateway — `03` Drift 2), evaluation (3 modes, 13 rubric types, confidence
  bands, voice entry, scanned-script understanding), gradebook, reports + report cards +
  holistic cards, portfolio, verifiable credentials.
- *Emits:* `evidence.recorded`, `mastery.updated`, `gap.detected/resolved`, `score`,
  `evaluation.completed`, `credential.issued`.
- *Consumes:* events (firehose), ontology, the AI fabric.
- *Data:* the feature store + learner graph projections (rebuildable from events), scores,
  reports, credentials.
- *API (gateway'd):* get-mastery, get-gaps, get-graph, evaluate-submission, get-report,
  issue-credential — the governed views `10` binds to.
- *Surfaces:* Student Progress*; Teacher Evaluate*/Students/Gradebook/Reports/Remedial;
  the mastery/knowledge components everywhere.
- *Adapters:* handwriting OCR for scanned scripts — **env:** `clss.school.<env>.ocr`.
- *DoD:* one engine, no TS re-implementation; mastery never an average; gaps confirmed on
  ≥2 signals; quality never lowers a mark; confidence-banded human-final; rebuildable
  projections.

### b9 · Relationships & Communication
- *Owns:* PTM scheduling/prep/follow-up, messaging (translate + make-task + safety),
  notifications, the parent absolution engine (reassurance + concern→action), the shareable
  proof artifact.
- *Emits:* `message.sent`, `ptm.scheduled/completed`, `action.assigned`,
  `notification.sent`, `proof.generated`.
- *Consumes:* learner record, calendar, the AI fabric, consent.
- *Data:* threads, meetings, actions, notifications.
- *API:* schedule-ptm, prep-ptm, send-message (translated), make-task, generate-proof.
- *Surfaces:* Teacher PTM*/Communicate; Parent companion/reports/at-home/PTM*/messages/win;
  notifications for all roles.
- *Adapters:* WhatsApp/SMS/email — **env:** `clss.school.<env>.whatsapp`,
  `clss.school.<env>.sms`, `clss.school.<env>.email`.
- *DoD:* translated two-way; make-task routes + owns; safety on every channel; absolution =
  reassurance + one action; proof verified + child-triggerable + native share.

### b10 · Teacher Growth
- *Owns:* private coaching signals (talk ratio, questioning, wait time, equity), the growth
  surface, continuity/handover packets.
- *Emits:* `coaching.signal` (private), `handover.created`.
- *Consumes:* class sessions, learner record.
- *Data:* coaching signals (private-first), handover packets.
- *API:* get-coaching (teacher-private), aggregate (post-private, support-first),
  create-handover.
- *Surfaces:* Teacher Growth, Continuity; Admin Teacher-analytics (aggregate, no punitive
  ranking).
- *DoD:* private-to-teacher-first; no automated punitive ranking; employment decisions need
  human review; handover lets a sub pick up at the right point.

### b11 · Intelligence Views
- *Owns:* the proactive feed/loop (observe→interpret→recommend→approve→execute→outcome→
  learn), the study quadrant, target analytics, syllabus coverage, prediction/trajectory,
  the ask-anything live dashboard composition over the governed semantic layer.
- *Emits:* `recommendation.created/actioned`, `intervention.created/outcome`.
- *Consumes:* learner record, attendance, coursework, the AI fabric; the governed semantic
  layer (one metric defined once).
- *Data:* recommendations, interventions, the semantic-metric definitions.
- *API:* get-feed, get-quadrant, get-trajectory, get-coverage, compose-dashboard.
- *Surfaces:* Teacher Feed/Class-analysis; Admin Intelligence/Quadrant/Targets/Coverage/
  Trajectory/Ask; Student/Parent readiness + reassurance reads.
- *DoD:* manage-by-exception; every item evidence·confidence·owner·due·why; metrics defined
  once; recommendations execute via the ladder; outcomes return + train the loop.

---

## The adapter/credential ledger (parked providers, contract-complete)

| Capability | Module | Env var (Infisical) | Built? |
|---|---|---|---|
| Live class video/recording | b4 | `clss.school.<env>.live_media` / `.recording` | code yes, key parked |
| Document OCR / transcription | b3, b8 | `clss.school.<env>.ocr` / `.transcription` | code yes, key parked |
| Heavy media hosting | b3 | `clss.school.<env>.media_store` | code yes, key parked |
| Face recognition (attendance) | b5 | `clss.school.<env>.face` | code yes, key parked |
| Proctoring | b6 | `clss.school.<env>.proctoring` | code yes, key parked |
| WhatsApp / SMS / email | b9 | `clss.school.<env>.whatsapp` / `.sms` / `.email` | code yes, key parked |
| Payments (→ Feesable citizen) | b1/link | `clss.school.<env>.payments` | linked citizen |
| FLUID live connectors | spine/FLUID | per-connector keys | code yes, key parked |
| Track 2 GPU/training | AI fabric | `clss.school.<env>.gpu` | slot yes, filled later |

Each adapter ships fully implemented against its named env var; placing the key in
Infisical activates the live provider — no code change. This is "no partial development":
complete code, pluggable provider.
