# Classess School — Roadmap & Task Record

Source of truth for scope: **`classess-school.html`** (d1–d22 + spine + §01–§13).
Full line-by-line status matrix: **`docs/COVERAGE.md`**. This file is the
**sequenced plan**: what's done, what's next, what's after. Keep it current.

_Last updated: this session._

---

## ✅ Done (recent)
- **Foundation/spine** complete (identity, gateway, event-store, intelligence, ai-fabric, governance, workflow) + 12 invariants.
- **Operational DB schema live** on Supabase — 40 tables across `pii_vault` / `platform` / `audit` / `operational`, RLS + immutability.
- **Live data circuit** — onboarding/school-setup persists to real DB (verified); server API routes via pooler.
- **Vidya (current)** — voice-first orb, tutor/explain/create/assess/answer/act, floating **SVG** canvas, speak-and-show, independent OpenAI verifier. (Full completion = NEXT.)
- **Auth** — stepped flow, Supabase Auth + local degrade, **delete-account** (right-to-erasure), branded **Resend email** (auth + transactional) with the **black logo**, social buttons (Google/Apple/Microsoft) wired (provider creds pending).
- **9 engine domains deepened** to the doc (coursework/learning/ontology/learner-record/classroom/attendance/scheduling/communication/identity).
- **Real provider engines** — Gemini ingestion/hyperloc/child-safety; observability; **model router** live.
- **Web depth** — child-safety wired into live web, i18n (en+hi) on core surfaces, logo everywhere.
- **Quality** — vitest 265, pytest across modules, tsc 0, prod build 46 pages, **Playwright E2E green (72 pass / all viewports)**; live on `3.classess.com`.
- **Bug fixed this pass:** the signed-in **home infinite-loop crash** (`useSyncExternalStore` snapshot) — real production bug, now fixed.

---

## ✅ Vidya, complete — DONE (live on 3.classess.com, commit 705a3ed)
4 role-shaped personas (student companion / teacher copilot / parent guide / admin assistant) · generative-UI (composes + operates real surfaces inline, typed+verified specs, permission ladder holds) · persistent per-user memory (PII-free, consent-gated, conditions the orchestrator) · multimodal intent (image/document/screen → Gemini) + voice · editable SVG canvas + sources · orb idle pulse frozen while open (calmer + actionable). E2E green (30 pass). Residual: the orb's NL-navigate E2E is `test.fixme` — feature works for real users (CDP-input deadlocks only the headless harness); revisit if we want it harness-driven.

## ▶ NEXT — the priority feature list to full capability (then E2E each)
Hyperlocalization · Metacognition (re-grade/reflection) · Blueprint wizard (conversational) · Policy versioning · Ontology steward depth · Timetable generation · Period swapping/pacing · Academic calendar · Generated material (summaries/worksheets) · Adaptive lesson/course planning · Flexible assignments (kinds/media/drafts) · Balanced group projects (6-dim rubric) · Originality (style-shift/web/model-answer) · Blueprint paper generation (sections/test-types) · Rubric library (13 types) · Voice mark entry · Adaptive practice (formats/topic-quiz/aptitude) · Fast flexible capture (Gemini vision/ASR) · Revision planner · Mock tests & readiness · Unified child view (real signals) · Intelligence dashboards · Prediction & trajectory · Ask-anything dashboard · Private teacher growth · SLM / a-mind-for-every-learner · Many-minds/model router (live wiring) · observability. **These mostly live in the Python spine — surfacing them in the live web needs THE CIRCUIT (below).**

## ⏭ AFTER — finish the priority list to full capability (then E2E each, checklist-driven)
Hyperlocalization · Metacognition (re-grade/reflection) · Blueprint wizard (conversational) · Policy versioning · Ontology steward depth · Timetable generation · Period swapping/pacing · Academic calendar · Generated material (summaries/worksheets) · Adaptive lesson/course planning · Flexible assignments (kinds/media/drafts) · Balanced group projects (6-dim rubric) · Originality (style-shift/web/model-answer) · Blueprint paper generation (sections/test-types) · Rubric library (13 types) · Voice mark entry · Adaptive practice (formats/topic-quiz/aptitude) · Fast flexible capture (Gemini vision/ASR) · Revision planner · Mock tests & readiness (time-left) · Unified child view (real signals) · Intelligence dashboards · Prediction & trajectory · Ask-anything dashboard · Private teacher growth · **SLM / a-mind-for-every-learner** (foundry → train) · Many-minds/model router (live wiring) · Generate/verify/agents + observability.

## 🔌 THE CIRCUIT (architectural enabler for "after")
Most engine depth lives in the Python spine; wire it into the live app:
- Deploy backend (gateway + spine + modules) to **Railway** (token in hand; needs explicit go-ahead).
- Point web → gateway with a Supabase-direct fallback; **activate KGtoPG** (web currently bypasses it).
- Comprehensive **cross-app E2E sweep** + console-error gate on every page; wire E2E into CI.

## ⏸ Parked — need external resources (your call)
Proprietary-model **training** (GPU) · **live-class** video/recording (media provider) · **FLUID** live connectors (integration creds) · **SMS/WhatsApp** (provider key) · board **3D/simulation/recording** media · payments · mobile (Expo).

## 🔒 Pre-launch hardening
Rotate every secret shared in chat · column-level PII encryption · DPDP consent verification · security review · Redis (sessions/OTP/rate-limit) if running services.

---
**Working order:** NEXT (Vidya) → AFTER (priority list, with the circuit enabling live wiring) → parked items as resources arrive → hardening before public launch.
