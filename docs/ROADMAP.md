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

## ▶ NEXT — Vidya, complete (highest priority, "nothing left behind")
Per §04 + d15 + §09. Build, then E2E each:
1. **Generative-UI conversational OS** — Vidya summons/composes/operates real surfaces inline (e.g. "make a quiz" → working builder in the conversation), not just fixed cards.
2. **Four role-shaped personas** — student companion / teacher copilot / parent guide / admin assistant, one identity.
3. **Full multimodal** — text + voice (done) **+ image, document, screen** intake.
4. **Persistent per-user memory** — wire the learned per-learner representation (built in `spine/intelligence`) into the live orchestrator so Vidya remembers + conditions every turn.
5. **Editable canvas + sources/evidence** alongside (the workspace).
6. **Make the orb fully E2E-driveable** (un-skip the navigate spec; ensure the panel settles for the harness).
   _Also: ensure voice-first never holds the UI when there's no mic._

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
