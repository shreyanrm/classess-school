# Build breakdown — the entire build, in detail

Every component, with what it owns, the contracts it emits/exposes/consumes, its dependencies, who builds it, and key notes. Domain numbers (`d1`–`d22`) reference the platform document feature catalogue.

Legend — **Tier:** `CORE` = secure core (highest rigor, most reviewed passes) · `APP` = capability module · `MIX` = core engine + app/surface. In this build Claude Code is the sole builder and runs every tier as parallel agents — the tier sets the rigor, not who builds it. Where any file says "developer lane," read "a Claude Code build agent."

---

## A. Spine modules (ecosystem / KGtoPG — secure core)

### A1 · Identity & access  `CORE` · Ring 0
- **Owns:** canonical user, AppMembership (user × app × role × scope, time-bound), RBAC + ABAC, consent. PII vault (segregated). `‹d2›`
- **Exposes:** auth/token issuance, membership + scope resolution, consent checks.
- **Depends on:** data substrate.
- **Notes:** Supabase Auth as mechanism, phone-OTP-first plus Google/Apple/institutional SSO. Role removal immediate on enrolment/employment change. Delegated/temporary/substitute access first-class.

### A2 · Curriculum & ontology  `CORE` · Ring 0 (contract) → Ring 1 (ingestion)
- **Owns:** board mapping, curriculum ingestion, the prerequisite graph, ontology steward, cross-board equivalence. `‹d3›`
- **Exposes:** ontology lookups (board → … → topic → outcome → competency → question → resource), prerequisite edges.
- **Depends on:** data substrate (pgvector), document-understanding pipeline.
- **Notes:** prerequisite edges are an owned, expert-validated artifact — proposed by the steward, confirmed before trusted. Ingested from documents/standards/publisher content, never hard-coded.

### A3 · Event & evidence  `CORE` · Ring 0 (store + contract) → Ring 1 (engines)
- **Owns:** the immutable append-only event store; the event/evidence contract; the evidence engine, mastery model, gap engine; the learner graph; the feature store. `‹§05, §10, d14 graph, d19 engine›`
- **Exposes:** governed, scoped, consent- and purpose-gated read views.
- **Depends on:** identity (canonical_uuid), ontology.
- **Notes:** mastery = Performance × Reliability × Independence × Difficulty × Recency × Consistency. Ten gap types. Derived stores are projections built by replaying events; understanding of every past learner improves as models improve.

### A4 · AI fabric  `CORE` · Ring 1
- **Owns:** the model router (Track 1 / Track 2 config separated), the Vidya orchestrator, the capability registry, the agent layer + permission ladder, the generate-and-verify substrate, observability. `‹§04, §09, d15 engine›`
- **Exposes:** generation, evaluation, conversation, capability invocation — all behind structured-output validation and the confidence gate.
- **Depends on:** gateway, secrets, ontology, event/evidence.
- **Notes:** LiteLLM gateway, Langfuse tracing. Frontier for hard/rare reasoning, mid for volume, small at edge for the high-frequency ocean. Track 2 slot exists from start.

### A5 · Proactive / workflow engine  `CORE` · Ring 1
- **Owns:** the observe → interpret → recommend → approve → execute → outcome → learn loop every module's proactive behavior runs on. `‹§05›`
- **Exposes:** recommendation objects (evidence, confidence, owner, due date, consequence), approval workflows.
- **Depends on:** event/evidence, AI fabric, gateway.
- **Notes:** low-risk actions automatable within policy; consequential actions require human approval.

### A6 · Integration (FLUID)  `CORE` (contract) / `DEV` (adapters) · Ring 2
- **Owns:** the two-way standards bridge and the platform SDK. `‹d21›`
- **Exposes:** LTI 1.3 · OneRoster 1.2 · xAPI/Caliper · QTI · SCORM · Clever/ClassLink · Ed-Fi · CASE · MCP; connector-health monitoring.
- **Depends on:** identity, gateway, event/evidence.
- **Notes:** can run as the intelligence layer on top of an existing system, take over, or just exchange data. Adapters are a dev lane; the contract surface is core.

### A7 · Governance & safety  `CORE` · Ring 0 (skeleton) → ongoing
- **Owns:** immutable audit, break-glass, the AI control centre, encryption, tenant isolation, consent/retention/lineage services, the child-safety subsystem. `‹d22›`
- **Exposes:** policy enforcement, audit queries, emergency disable, lineage on every insight.
- **Depends on:** identity, gateway.
- **Notes:** the most powerful surfaces are the best-governed. Child-safety (moderation, crisis detection, escalation, no unmonitored channels) runs on every free-text surface.

---

## B. Capability modules (Classess School)

### B1 · Institution & policy  `DEV` (behind gateway) · Ring 0 (minimal provisioning) → Ring 1
- **Owns:** org hierarchy + relationship graph, the blueprint wizard, policy inheritance, hyperlocalization config, multi-tenancy. `‹d1›`
- **Emits:** structure/roster/policy events. **Consumes:** identity, ontology.
- **Notes:** nodes configurable (group → region → campus → school → department → grade → section), many-to-many relationships scoped and time-bound. Minimal provisioning (institution + structure + roster) is the Ring 0 prerequisite; schema canonical even if UI is thin.

### B2 · Scheduling & continuity  `DEV` · Ring 1
- **Owns:** academic calendar, the dynamic timetable, the substitution ladder, pacing protection, teacher knowledge transfer. `‹d4, d20-continuity›`
- **Emits:** timetable/attendance-trigger/pacing events. **Consumes:** attendance, leave, ontology, the workflow engine.
- **Notes:** constraint solver classifies rules hard/soft/contextual, produces scored alternatives for human approval. Substitution ladder Level 1–6, never a free period. Tracks planned vs delivered periods.

### B3 · Content & resources  `MIX` (engine CORE, library DEV) · Ring 1
- **Owns:** the content repository/library, generated supporting material, the verification surface. `‹d5›`
- **Emits:** content-usage events. **Consumes:** the content engine + verification substrate (A4), ontology.
- **Notes:** generated against curriculum, verified before use. OCR/transcription/document-understanding on uploads; pgvector semantic search; versioning, approval, licence metadata.

### B4 · Teaching  `DEV` (board CORE-reviewed) · Ring 1
- **Owns:** lesson/course planning, classroom delivery, the interactive board, live class, polls/quizzes, the device-free check, attention signals. `‹d6, d7›`
- **Emits:** delivery/engagement/grasp events. **Consumes:** content, ontology, mastery/gap data.
- **Notes:** native ink over hardware-accelerated content host; on-device vision assists, never grades from a face; plans adapt to yesterday's completion and performance.

### B5 · Attendance  `DEV` · Ring 1
- **Owns:** fast flexible capture (photo-scan, voice roll-call, photo roster, absent-only, online presence), risk/reconciliation, offline sync. `‹d8›`
- **Emits:** attendance + risk events. **Consumes:** scheduling (triggers the substitution ladder), workflow engine.
- **Notes:** capture methods assist; the teacher confirms — never auto-finalised. Detects consecutive/chronic/pattern risk; reconciles signals, flags conflicts for human review.

### B6 · Coursework & assessment  `DEV` (evaluation engine CORE) · Ring 1
- **Owns:** assignments/homework/projects, assessment + exam architecture, blueprint-driven paper generation, the evaluation engine (three modes), the rubric library, originality. `‹d9, d10, d11›`
- **Emits:** submission/score/evidence events (independent vs supported flagged). **Consumes:** content engine, ontology, mastery/gap engines.
- **Notes:** evaluation engine is CORE (correctness is existential): three modes (post-submission, scanned-handwriting, preventive-before-submission), confidence-banded, human-final on consequential marks; never reduces marks for poor handwriting/scan — flags "needs human review."

### B7 · Learning  `DEV` (adaptive engine CORE) · Ring 1
- **Owns:** learn/practice/mastery, the assistance ladder, revision planner, mock tests, exam-readiness forecasting. `‹d12, d13›`
- **Emits:** attempt/practice/mastery-evidence events. **Consumes:** content+verification, mastery model, the companion.
- **Notes:** pose → struggle → reveal, never explain-first. Spaced retrieval against the real forgetting curve. Assistance ladder fades as competence grows. Practice contributes evidence, not a completion tick.

### B8 · Learner record  `DEV` (reads CORE views) · Ring 1
- **Owns:** the evidence-linked profile, portfolio, credentials — the School-facing composition of the evidence graph. `‹d14›`
- **Emits:** portfolio/credential events. **Consumes:** governed reads of the learner graph + evidence store.
- **Notes:** shows independent vs support-dependent mastery, not a number. Every item carries source + permission controls. Credentials verifiable and portable under the learner's control.

### B9 · Relationships & communication  `DEV` (companion + safety CORE) · Ring 1→2
- **Owns:** the companion/care surface, parent engagement, parent–teacher partnership, the communication hub, safeguarding. `‹d15, d16, d17, d18›`
- **Emits:** message/meeting/sentiment events. **Consumes:** Vidya orchestrator, the child-safety subsystem, scoped reads, translation.
- **Notes:** companion role-shaped, bounded (no manipulation/exclusivity/dependence); serious matters escalate to qualified humans. Messages can become routed, owned, tracked tasks. Parent surface is partnership and pride, not surveillance.

### B10 · Teacher growth  `DEV` · Ring 2
- **Owns:** private evidence-based coaching, classroom-interaction insight, quality review. `‹d20›`
- **Emits:** coaching-signal events (private). **Consumes:** interaction analysis, the continuity engine.
- **Notes:** signals (talk ratio, questioning, equity, wait time) surface to the teacher first; no automated punitive ranking; employment decisions require human review.

### B11 · Intelligence views  `DEV` (over CORE loop) · Ring 1→2
- **Owns:** the dashboards, the study quadrant, target analytics, prediction/trajectory, the ask-anything dashboard, the institution-specific assistant. `‹d19›`
- **Emits:** view-usage events. **Consumes:** the proactive loop + feature store, the governed semantic layer.
- **Notes:** composes the §05 loop into "here is what I found and what to do." Every alert carries evidence, confidence, owner, due date, and "why am I seeing this." One metric, defined once, computed the same everywhere.

---

## C. Surfaces

### C1 · Admin  `DEV` · Ring 1 (provisioning) → Ring 1 (full)
- Role-scoped (owner, principal, coordinator, HOD, examination, support, IT). Home = a morning briefing, not a dashboard. Composes B1, B2, B11, A5, A7.

### C2 · Teacher  `DEV` · Ring 1 (with Student)
- Home = the day. Three steps or fewer per action. Composes B2–B7, B11.

### C3 · Student  `DEV` · Ring 1 (with Teacher)
- Home = next step, why, how long, what it builds. Adapts to age/stage. Composes B3, B6, B7, B8, B9, Vidya.

### C4 · Parent  `DEV` · Ring 1 (after the loop)
- Home = partnership, not surveillance — three actions, in the parent's language. Composes B8, B9, consent.

### C5 · Vidya — the home and front door  `CORE` engine + `MIX` surface · Ring 1
- The conversation-first home every role lands in, and the intention-primary OS across the platform. Full capabilities, not a text box: generative-UI and inline components, on-screen explanations and self-assembling derivations, misconception detonation, the editable canvas with sources and evidence alongside, interactive teaching content, multimodal input, per-user memory, the assistance ladder and teach-back, the permission ladder in-conversation, and the child-safety subsystem on every free-text surface. Processes dynamically — renders a component only when the task warrants it, never on every turn. Small tasks render inline with an "open in its page" control; big tasks route to their page with Vidya docked. The fixed pages are the stable spine; the conversation is the front door over them.
