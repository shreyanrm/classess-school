# Classess School — Slice 2: the Admin surface and Vidya voice

This is the build document for Ring 1, Slice 2. Where `docs/SLICE1.md` cut the
Student-Teacher learning loop down through the spine, Slice 2 builds the
institutional layer above it — the surfaces and modules an administrator works
in — and gives Vidya a voice. It adds two capability modules (Institution B1,
Scheduling B2), one new spine capability (the AI fabric voice adapter), the Admin
web surface, and the voice UI that docks beside the home composer.

Slice 2 binds to the same frozen `@classess/contracts` boundary and the same
twelve invariants. Nothing here authors a consequential act on its own: the
admin works by exception, every timetable or substitution change is prepared and
then human-approved, and Vidya's voice degrades to silence rather than fabricate.

The slice is built board-agnostic and on generic labels throughout (Campus
North, Section 10-B); no PII, no real pricing, no board lock-in.

---

## 1. The Admin model — manage by exception

The Admin surface is a morning briefing, not a dashboard. It does not present
every metric; it surfaces only what needs a human decision and explains why.
Each item carries the explainable-intelligence contract: evidence, a confidence
band, the owner, a due date, the consequence of ignoring it, and a
why-am-I-seeing-this line. The administrator reviews exceptions and approves,
adjusts, or declines; routine state stays quiet.

Two authority laws hold across the whole slice and are enforced in code:

- **No structural or operational change auto-commits.** Provisioning an
  institution, committing a timetable change, and assigning a substitute are all
  Prepare-class: the engine validates and returns the change for a human to
  approve. The act of approval is a separate, explicit call that fails closed
  without an approver.
- **Autonomy is bounded and revocable.** The governance surface locks every
  consequential capability off so it can never auto-fire, and break-glass
  requires a typed confirmation that is recorded to an append-only audit trail.
  Human authority is never surrendered.

---

## 2. Institution and policy — `modules/institution` (B1)

The institutional spine: the board-agnostic structure ladder, the provisioning
wizard, policy inheritance, and logical multi-tenancy. A pure, import-safe Python
package (standard library only) under `modules/institution`, matching the
sibling-module layout (`app/` subpackage, `conftest.py`, `pytest.ini`,
env-name-only config). 44 tests pass.

- **`hierarchy.py`** — the configurable node ladder
  group -> region -> campus -> school -> department -> grade -> section, with a
  rank-checked containment tree (a child can only sit under a higher-rank
  parent), plus a many-to-many scoped relationship graph whose edges are
  time-bound (`valid_from` / `valid_to`) and filterable with `active_on`. All
  reads are tenant-guarded. The board is a labelled node, never an enum — the
  structure widens without changing shape.
- **`blueprint.py`** — the provisioning wizard. It composes identity (mint an
  opaque tenant id), structure, roster (opaque members in scoped, time-bound
  roles — `canonical_uuid` only, never a name), and policy into one validation
  gate that collects every problem at once, so a half-built institution is never
  provisioned. It is a PREPARE-class step: it returns a tenant-scoped
  `InstitutionConfig` and BUILDS the append-only provisioning events; it never
  sends them. The caller emits through the gateway after approval.
- **`policy.py`** — inheritance down the tree with nearest-setter-wins and child
  override; locked-floor policies where the highest lock wins; full provenance
  (the why and the setting node) on every `ResolvedPolicy`. Hyperlocalization via
  three well-known keys (language, region, calendar).
- **`tenancy.py`** — logical isolation. Every record carries an opaque tenant
  scope; cross-tenant reads are denied by default; grants are explicit and
  immutable; there is no wildcard; an unscoped record is never served.
- **`events.py`** — structure, roster, and policy events on the contract envelope
  shape (`app.canonical_uuid.type.purpose.consent_ref`), append-only; degrades to
  returning the event object when no gateway is wired.

**Owns:** institutional structure, provisioning, policy resolution, tenant
isolation. **Exposes:** the hierarchy, blueprint, policy, tenancy, and events
surfaces (Python `app/`). **Consumes:** the event envelope contract; opaque
tenant / node / canonical ids only.

**Contract note (flagged upstream).** `contracts/src/events` has no
structure / roster / policy payloads — the v1 `EventType` union is a closed set
(attempt / assignment / submission / score / mastery / intervention / consent).
B1 emits its three operational events under the institution namespace
(`institution.structure.changed` / `.roster.changed` / `.policy.changed`) on the
EXACT spine envelope and the operations purpose; when the spine adds them to its
versioned union the type strings adopt canonical names with no envelope change.

---

## 3. Scheduling and continuity — `modules/scheduling` (B2)

The calendar, the dynamic timetable solver, the substitution ladder, and pacing.
A production-grade, dependency-free Python package under `modules/scheduling`,
following the coursework layout. 37 tests pass; import-safe on bare `python3`.

- **`calendar.py`** — the academic calendar: `Term`, `CalendarException`
  (holiday / non_working / working_override), and `AcademicCalendar` with
  board-agnostic working-day math (in-term, an instructional weekday, not a
  holiday; a working_override beats a same-day holiday), `working_day_count`, a
  bounded `next_working_day`, and six-day-week support.
- **`timetable.py`** — the dynamic timetable and constraint solver. Rules are
  HARD / SOFT / CONTEXTUAL; a hard breach disqualifies a candidate
  (`feasible=False`, score 0), soft breaches cost score, contextual rules abstain
  when inapplicable. `TimetableSolver.solve` returns ranked `ScoredAlternative`s
  (feasible first) each carrying evidence, a confidence band, the owner, the
  consequence of applying, and a why — the A5 Recommendation contract.
  `SolverResult.committed` is always `False`; **`apply_change` is a separate call
  that raises `PermissionError` without `approved_by` and refuses an infeasible
  alternative.**
- **`substitution.py`** — the substitution ladder, Level 1-6 (`SubLevel`
  IntEnum). `build_ladder` ranks supervised options best-first (lower level +
  higher continuity); a free duty teacher guarantees a Level 6 supervised combine
  fallback, so a free (unsupervised) period is structurally impossible
  (`is_free_period` is `Literal[False]`). **`assign_substitute` raises
  `PermissionError` without `approved_by`.** Substitute subject-fit is a
  CONTEXTUAL rule that surfaces "expertise unverified — confirm before approving"
  rather than silently assuming fit (wire A2 ontology / a competency feed into
  `default_rules().substitute_subject_fit` when available).
- **`pacing.py`** — `PacingPlan` / `assess_pacing` with drift bands
  (ahead / on_track / slipping / behind / at_risk) computed against the
  working-day denominator, so holidays never read as behind; expected is capped at
  the plan total. `HandoverNote` / `build_handover_note` for teacher knowledge
  transfer (opaque refs and curriculum position only; rejects non-string watch
  points to defend the no-PII rule).
- **`events.py`** — emits `timetable.changed`, `attendance.trigger`,
  `pacing.drift_flagged` on the attributed append-only envelope (operations
  purpose, schema_version v1, opaque ids only); degrades to a clearly-labelled
  in-memory append-only sink. `build_timetable_changed_payload` refuses without
  `approved_by`.

**Owns:** the calendar, the timetable solver, the substitution ladder, pacing
and handover. **Exposes:** the calendar, timetable, substitution, pacing, and
events surfaces. **Consumes:** the event envelope; opaque ids only. The same
closed-union contract note as B1 applies — scheduling rides the spine envelope
with three operational type strings and an operations purpose.

---

## 4. The AI fabric voice capability — `spine/ai-fabric/app/voice.py` (A4)

A Vidya speech-to-speech capability (Gemini Live native audio) added to the AI
fabric without touching the existing router / verify / registry. It is Track 1
(external LLM routing) and provider-correct: the task targets Gemini (Google), a
non-Anthropic provider, so no Claude-specific guidance applies.

`VoiceAdapter` exposes two entrypoints:

- **`mint_browser_session()`** — mints a short-lived ephemeral session token so a
  browser can open a Live session and the raw key NEVER leaves the server. The
  raw key is read by NAME only, used solely to ask the provider to mint the
  token, never returned in any result object, never logged. A provider token that
  comes back equal to the raw key is rejected.
- **`respond_speech_to_speech()`** — runs a server-side audio-in to audio-out
  turn behind the existing `ConfidenceGate` (INVARIANT 7) and the permission
  ladder (INVARIANT 8). Audio is SERVED only when the deterministic checks pass
  (non-empty audio + a transcript to cross-check), an independent second model
  agrees, and confidence clears the gate; otherwise the turn is refused with a
  reason. The voice turn sits on the RECOMMEND rung (it drafts a reply, served
  only via the gate); any consequential follow-on still honours an
  `approval_token` path.

**Degrade contract.** When the provider SDK is absent OR the key is unset, every
entrypoint returns `provider_available=False` with no token and no audio — never
fabricating. `_load_sdk_minter` / `_load_sdk_model` guard-import `google.genai`
and return `None` until verified wiring exists, so the capability reports
unavailable rather than guessing. The real provider seams plug into the
`LiveTokenMinter` / `LiveAudioModel` Protocols (constructor-injectable, exercised
by in-process fakes in the tests — no network).

**`config.py`** adds a `gemini_api_key` field (default `None`) resolving
`CLSS_AIFABRIC_DEV_GEMINI_API_KEY` via the pydantic-settings env prefix
`CLSS_AIFABRIC_DEV_`, with a standard-library fallback loader (same prefix and
field) so the package stays import-safe if pydantic-settings is absent.

**Registration.** The capability is registered in `default_registry()` with
`track=1`, `requires_verification=true`, and a least-privilege scope (purpose
`voice_companion_dialogue`, single data scope `conversation.context`, no PII);
its task class was added to the router tier map (edge). The full suite passes:
60 tests, including 19 new voice tests.

**Owns:** the Vidya voice adapter, the ephemeral-token mint seam, the gated
speech-to-speech turn. **Exposes:** `VoiceAdapter`, the voice capability
descriptor, the provider Protocols. **Consumes:** the existing `ConfidenceGate` /
second-model / registry; the named Gemini key by env name only.

---

## 5. The Admin surface — `surfaces/web/app/admin`

The administrator's surface on the v4 design system, reachable via the rail's
role switcher, with Vidya docked on every page through `SurfaceShell`.
`tsc --noEmit` is clean.

- **`admin/page.tsx`** — the morning briefing: `AdminBriefingCard`s for what
  needs attention, classes behind, teachers needing support, and improvements; an
  interventions section with confidence bands; open concerns; and blocking
  approvals rendered as `RecommendationItem`s.
- **`admin/setup/page.tsx`** — a calm four-step blueprint wizard (Structure,
  Roles, Policies, Review) on the loop-step stepper. It creates nothing until an
  explicit final confirm — the surface mirror of the B1 PREPARE-class wizard.
- **`admin/calendar/page.tsx`** — substitution cover showing SCORED ALTERNATIVES
  (plain-language fit and tradeoff) with an Approval control that never
  auto-commits: select -> review -> approve / decline.
- **`admin/intelligence/page.tsx`** — a tight Matrix of Stat cards, plain-language
  mastery trends, and ask-anything via the docked Vidya.
- **`admin/governance/page.tsx`** — the permissions matrix; the AI control centre
  with consequential toggles locked off so they can never auto-fire; an
  append-only audit trail; and break-glass requiring a typed `BREAK GLASS`
  confirmation that is recorded and keeps human authority.
- **`admin/loading.tsx`** / **`admin/error.tsx`** — first-class loading and error
  states; offline / empty states are handled by `SurfaceShell` and inline empties.

The rail lands Admin on the five admin destinations; admin mock data lives in
`lib/mock.ts` (generic labels, no PII, no real pricing, board-agnostic). The
surface never touches the event store or PII vault directly.

---

## 6. The Vidya voice UI — `surfaces/web/app/api/voice` + `lib/voice.ts`

The voice experience beside the home composer. Quiet, not dominant.

- **`app/api/voice/token/route.ts`** — server-only (`runtime = 'nodejs'`,
  `dynamic = 'force-dynamic'`). Reads `CLSS_AIFABRIC_DEV_GEMINI_API_KEY`
  server-side ONLY and never returns it raw. It mints an opaque, HMAC-signed,
  60-second ephemeral token (the key is used only as the HMAC secret, never
  embedded). An unset or short key returns a clean 503 "voice unavailable" JSON;
  a mint failure returns 503. It never crashes and never logs the key. In
  production this route brokers the ephemeral mint with the AI fabric THROUGH the
  gateway and returns that token — the client interface does not change.
- **`app/_components/VoiceCapsule.tsx`** — a quiet voice affordance (inline mic
  glyph + CSS waveform) wired beside the home composer. Tap to speak;
  listening / thinking / speaking states; a transcript line; a calm "voice
  unavailable" on 503 with a retry on transient error.
- **`lib/voice.ts`** — the typed client: a `VoiceState` machine, a
  `VoiceProvider` interface (so a missing key degrades cleanly), `httpVoiceProvider`
  mapping 503 -> `unavailable` and never throwing, and a `VoiceSession` holding
  ONLY the opaque ephemeral token (with an expiry check).

**The ephemeral-token model.** The raw provider key lives in the server
environment and is read server-side only — never returned, never logged, never a
`NEXT_PUBLIC` var, and grep confirms no client / lib code reads its value (only
the env-var NAME is referenced). The browser receives only a short-lived opaque
token and opens the Live session with that; if the token expires or is leaked it
is low-risk and quickly dead. This satisfies INVARIANT 4 (secrets are env-only,
server-only) end to end across the surface and the spine adapter.

**Design-system note.** The kit ships no mic / wave primitives, so the glyph and
waveform are built inside the web surface from an inline SVG at the house 1.5px
stroke and token-only CSS — the signature ultramarine is reserved for the active
mic / wave state (the brand / ignite allowance), `prefers-reduced-motion` is
honoured, no new colours, no shadows, sharp corners.

---

## 7. Human-authority gates (INVARIANT 8)

```
Recommend → Prepare → Execute-with-permission → Safe-automatic
```

Every consequential act in Slice 2 stops at a human:

- **Provisioning** (B1 `blueprint.py`) is PREPARE-class — it returns the config
  and the events, never emits them. The Admin setup wizard creates nothing until
  the explicit final confirm.
- **Timetable changes** (B2 `timetable.py`) — `solve` only ranks alternatives;
  `apply_change` raises `PermissionError` without `approved_by` and refuses an
  infeasible alternative. The Admin calendar select -> review -> approve flow
  never auto-commits.
- **Substitutions** (B2 `substitution.py`) — `build_ladder` only ranks supervised
  options; `assign_substitute` raises `PermissionError` without `approved_by`. A
  free unsupervised period is structurally impossible.
- **Voice** (A4) sits on the RECOMMEND rung; audio is emitted only when the
  confidence gate serves it, and any consequential follow-on requires an approval
  token.
- **Break-glass** (Admin governance) requires a typed `BREAK GLASS` confirmation
  and is recorded to the append-only audit trail; the AI control centre locks
  consequential autonomy off so it can never auto-fire.

---

## 8. Environment variables (names only — never a value)

All secrets are environment-only and follow `clss.<app>.<env>.<purpose>`. None is
hardcoded; absence degrades gracefully behind a clear interface.

| Module | Env var names |
|---|---|
| ai-fabric (voice) | `clss.aifabric.dev.gemini_api_key` (OS env `CLSS_AIFABRIC_DEV_GEMINI_API_KEY`) |
| institution (B1) | `clss.institution.dev.gateway_url`, `clss.institution.dev.event_sink_url`, `clss.institution.dev.database_url`, `clss.institution.dev.identity_url`, `clss.institution.dev.ontology_url` |
| scheduling (B2) | `clss.scheduling.dev.gateway_url`, `clss.scheduling.dev.event_sink_url`, `clss.scheduling.dev.database_url`, `clss.scheduling.dev.workflow_url` |
| web surface (voice) | `CLSS_AIFABRIC_DEV_GEMINI_API_KEY` (server-only; read by the token route, never `NEXT_PUBLIC`), plus the existing `NEXT_PUBLIC_CLSS_WEB_PROD_GATEWAY_URL` and `CLSS_WEB_PROD_GATEWAY_TOKEN` |

The web token route and the ai-fabric voice adapter read the SAME named Gemini
secret server-side; the browser never receives it — only the minted ephemeral
token.

---

## 9. Running it

> Do not run installers or builds inside a single lane during the parallel build;
> the orchestrator installs and builds centrally. The steps below are what the
> central setup enables.

### 9.1 The Admin surface and voice UI

```bash
# from surfaces/web, after the central npm install
npm run dev          # next dev — serves /admin and its destinations
```

Open `/admin` for the morning briefing, then `/admin/setup`,
`/admin/calendar`, `/admin/intelligence`, and `/admin/governance`. With no
`CLSS_AIFABRIC_DEV_GEMINI_API_KEY` set, the voice capsule shows a calm "voice
unavailable" and typing to Vidya keeps working; set the key to exercise the
ephemeral-token mint path. Verification used `tsc --noEmit` (clean) and
`vitest run --project web` (16 passing: 9 new voice + 7 existing).

### 9.2 The Python packages (tests)

Each package degrades to offline, deterministic behaviour with no provider.

```bash
# the voice capability (in the ai-fabric suite)
pip install -r spine/ai-fabric/requirements.txt && python -m pytest spine/ai-fabric   # 60 tests (19 voice)

# the new capability modules
python -m pytest modules/institution   # 44 tests, standard-library-only
python -m pytest modules/scheduling     # 37 tests, dependency-free
```

The repo venv at `.venv` (pytest 9.1.1, pydantic-settings) runs the full ai-fabric
suite. `modules/institution` and `modules/scheduling` import on bare `python3`
with no third-party deps; run them with whichever interpreter has pytest present.

---

## 10. What this slice proves, and what it defers

It proves the institutional layer end to end without compromising the invariants:
an institution is provisioned only after a single all-problems validation gate
and an explicit human confirm; a timetable change and a substitution are ranked
with full provenance and never auto-commit; pacing reads against working days so
holidays never look like drift; Vidya can speak, gated by the same
generate-and-verify substrate as every other capability, with the raw key never
leaving the server.

It defers — behind named env vars, with no re-architecture — the live Gemini Live
SDK wiring (the `LiveTokenMinter` / `LiveAudioModel` seams), the gateway-brokered
ephemeral mint in production, the live event-store egress for the B1 / B2
operational events, and the A2 competency feed for substitute subject-fit. The
closed v1 `EventType` union does not yet carry the structure / roster / policy /
timetable / attendance / pacing payloads; they ride the exact spine envelope with
namespaced type strings and an operations purpose until the contracts owner adds
them upstream.
