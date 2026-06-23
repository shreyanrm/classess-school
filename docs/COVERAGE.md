# Classess School — Coverage Matrix (source of truth: `classess-school.html`)

Living checklist mapping **every** feature/sub-feature in `classess-school.html` to
built / partial / missing. Driven by the exhaustive line-by-line audit (run wf
`wycgg3bj1`, d1–d14 + spine) + the d15–d22/UX completion pass. Do not declare
"complete" until every box here is checked or explicitly deferred with the user.

## Two systemic gaps (highest leverage)

- [ ] **Connect the circuit (§12).** d1–d6 modules are pure-Python libraries (no
  FastAPI `main.py`, no operational tables wired); web surfaces are mock-store
  backed and call Supabase Auth directly instead of delegating to the KGtoPG
  identity service. → Operational tables now exist (0008–0011 applied). Wire web
  ⇄ live data via the server API tier; route auth through identity; flow events.
- [ ] **AI fabric is not live.** Router/orchestrator read provider keys by name
  but the spine path does not call LiteLLM; no retrieval, no response cache;
  Vidya (spine) is a thin intent-router, not a generative-UI conversational OS;
  no persistent per-learner memory/representation. (Web Vidya IS live on Gemini.)

## Missing (build new)

- [ ] **d7** board content: 3D explorable models, simulations, animated explanations; per-session generate-and-verify of board content.
- [ ] **d7** board: multiple themes; full drawing/shape tools; document sharing; freeze-frame annotate mode.
- [ ] **d7** class recording with searchable transcript + summary (consent-gated).
- [ ] **d9** risk-based assignment reminders; classroom-tool sync.
- [ ] **d10** blueprint coverage view (completed / untaught / previously-examined, colour-coded).
- [ ] **d10** test types: periodic, formative, summative, slip.
- [ ] **d11** voice mark entry (bound to the evaluation engine, not just a UI label).
- [ ] **d12** the four named interactions: predict-then-check, assemble-the-proof, fill-the-missing-step, teach-it-back; multiple explanation styles; multilingual delivery.
- [ ] **d14** IEP model + intervention history timeline.

## Partial (deepen to the document)

**Spine**
- [ ] Identity: add Google/Apple/Microsoft/SAML + institutional SSO; device/risk mgmt; full access history; **route web auth through the identity service** (no app-local signup).
- [ ] Access: delegated/temporary/substitute access as first-class; donor-aggregate + support-referred-only scopes; coordinator/HOD/examination/support/IT roles.
- [ ] AI router: live LiteLLM calls; retrieval; response cache; real Track-2 edge/offline.
- [ ] Vidya OS: generative-UI/on-the-fly surface composition; persistent per-learner memory; image/screen/document intake.
- [ ] FLUID: per-standard conformance depth; platform SDK artifact; live two-way exchange.

**d1–d6**
- [ ] d1 blueprint: conversational guided interview; academic-year/working-days/holidays/approval/comm rules; digital twin. Persist to DB (not mock).
- [ ] d1 hierarchy: ownership + funding/sponsor/govt-district relationship overlays.
- [ ] d1 policy: versioning + effective dates; board-terminology + local-exam-format hyperlocalisation as policy.
- [ ] d3 ontology depth: add skill→question→resource nodes; competitive-exam mappings; school local overlays; curriculum versioning + outcome-coverage tracking.
- [ ] d3 steward: duplicate flagging; missing-prerequisite detection; curriculum versioning.
- [ ] d4 timetable: from-scratch generation with the three named alternative axes (academic / workload / resource) + rooms/resource scoring; persist.
- [ ] d4 substitution: align levels to the doc (L4 cross-campus online, L5 external time-bound access then removed, L6 recorded-lesson/guided continuity); pick-up-at-the-right-point linkage.
- [ ] d4 pacing: recommend recovery actions; period swapping; low-risk automation within policy.
- [ ] d4 calendar: continuous optimisation; persist; wire absence→ladder live.
- [ ] d5 content: video chapter extraction; institution/personal/publisher libraries; outcome-coverage view; add **summaries + worksheets** artifacts; interactive presentations + embedded media; persist (DB).
- [ ] d6 planning: engagement signal input; teacher-preference/instructional-model selection; LLM-generated plans; approval routing; available-time/resource constraints; persist.

**d7–d14**
- [ ] d7 period launch wired (content+attendance+assessment from timetable); device-free room-photo **quiz** + leaderboard; raised-hand/no-person attention signals; engagement-vs-later-performance.
- [ ] d8 staff: early-departure + kiosk capture; subject-specific + exam-shortage risk; transport/gate reconciliation; geofencing; face/liveness engine; locked-correction-with-audit; parent-comm + catch-up-plan workflow.
- [ ] d9 assignments: worksheets/journals/portfolios kinds; delivery modes; submission media types; draft/revision/final; group milestones + the six-dimension project rubric; originality style-shift/web/model-answer + explain-or-rewrite.
- [ ] d10 papers: section-wise mark distribution; per-question edit/regenerate/refine; more question types; question bank + moderation/approval + results→gradebook/analytics; real OCR + proctoring providers.
- [ ] d11 evaluation: scanned-script per-student recognition + answer→question mapping; preventive graduated-hint wiring; **full 13-type rubric library** (5 ship); curriculum-aligned rubrics; "I think I'm right" re-grade + confidence check-ins + reflection prompts.
- [ ] d12 practice: varied formats; topic quizzes; per-student readiness/aptitude score.
- [ ] d13 revision PLANNER: exam-date plan from available-time + coverage + weakness; workload/stress distribution; auto re-plan on missed sessions; school/board/competitive scopes; readiness time-left achievable recalculation.
- [ ] d14 profile: continuous timeline (projects/achievements/observations/reflections, evidence-linked); year-end portfolio + student showcase; distinct certificate/badge artifacts; production asymmetric credential signing.

## d15–d22 + cross-cutting UX

**Missing (build new)**
- [ ] **d15** wellbeing check-ins + reflective support (voluntary, opt-in, human-controlled).
- [ ] **d15** persistent per-user companion memory (store + thread, not stateless per request).
- [ ] **d17** in-meeting silent assistant: consented transcription, notes, key-point extraction, action items.
- [ ] **d18** multi-channel delivery adapters: chat/push/email/SMS/WhatsApp-class over realtime.
- [ ] **d21** the three operating modes (overlay / lead / exchange) + approved third-party **tool catalogue**.
- [ ] **multilingual (web)**: i18n framework, locale capture in onboarding, language switcher, translated rendering, code-switching, parent reads in their language. (Backend hyperlocalisation exists; UI doesn't.)

**Partial (deepen / wire)**
- [ ] **d15** companion: one identity role-shaped into true student/teacher/parent/admin companions; "what do I need today" synthesised from timetable+tasks+permissions+progress; image/screen/document multimodal; wire web Vidya ⇄ the bounded Python companion; real translation rendering (currently degrade-only passthrough).
- [ ] **child-safety**: enforced in the Python module but **NOT applied to the live web** messages/Vidya free-text surfaces (screening is illustrative; `flagged` hard-coded false). Wire the safeguard into the running app.
- [ ] **d16** parent: unified per-child timeline, actionable briefings, parent-specific generated feedback — all currently hard-coded mock; wire to real signals + governed views; deliver in preferred language.
- [ ] **d17/d18/d19/d20/d22** + UX laws: remaining items from `wnatznt1t` (proactive nudges from real signals, teacher growth from real evidence, governance control-centre live actions, design/UX-law conformance, offline) — deepen as each domain wave runs.

## Cross-cutting

- [ ] Empty-state Create/Start/Try CTAs everywhere; loading consistency (in progress).
- [ ] SVG for all Vidya overlays/annotations/drawings (in progress).
- [ ] Realtime (messaging/presence/notifications).
- [ ] Offline PWA (service worker + sync queue); interface i18n.
- [ ] Full E2E (Playwright) across flows + Vidya NL + responsive viewports.

## Deferred with the user (need external resources)

- [ ] Proprietary model training (compute) · Live-class video/recording (media provider) · FLUID live connectors (integration credentials).
- [ ] Pre-launch hardening: rotate all secrets; column-level PII encryption; DPDP verification; security review.
