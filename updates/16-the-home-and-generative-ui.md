# 16 · The Home and the Generative-UI Engine

This supersedes the home description in `05`/`11` with the exact, build-ready spec. The
home on **every** role is the conversation-first surface (the Gemini shape, on v4.1).
The reference implementation is `prototype/vidya-experience.html` — build the React app
to match its shape, motion, and behaviour.

## 16.1 The home — anatomy (every role)

A calm, near-empty screen. Top to bottom, left to right:

- **The thin rail (left).** Collapsed to `--rail-collapsed` (64px). Full spec in `18`.
- **The topbar (right of rail).** Left: a mono role/context line ("Student · Class 10-B
  · <institution>"). Right: the command button (opens Cmd-K, `17`) and the theme toggle.
  No page title — the home has none.
- **The greeting.** One light-weight (300) large line, role-shaped, sentence case, **no
  exclamation mark**: "Where would you like to begin, <name>". A quiet sub-line: "Ask
  anything, or pick up where you left off."
- **The ambient bloom.** Behind the composer, an extremely subtle living
  molten→ultramarine→violet field (canvas, very low alpha). It is *atmosphere*, never a
  focal point — it makes the screen feel alive without shouting. Reduced-motion renders
  it static.
- **The composer.** A single rounded input row: a `+` attach control (left), the text
  field ("Ask Vidya, or describe what you want to do"), a model selector ("Auto ▾"), and
  a mic control (right). Focus moves the border to the signature. This is the one primary
  affordance on the screen.
- **Suggestion chips.** 3–5 chips beneath, each a real next action drawn from the
  proactive loop (`13` b11), with a subject dot. Hover uses the rise-fill motion. These
  replace v2's dashboard — the proactive layer is present but quiet.
- **The hint bar (bottom).** Quiet affordances: `Cmd K` command · click the orb or hold
  Space to talk · hover the rail to expand.
- **The floating orb (fixed, bottom-right).** The living Vidya presence (`17`).

Role-shaping changes only the greeting, the chips, the role line, and which capabilities
Vidya exposes — the shell is identical. Student/Teacher/Admin/Parent greetings and chips
per `06`–`09`.

## 16.2 The generative-UI engine — what happens when you ask

A request enters via the composer, a chip, voice (`17`), or Cmd-K. Vidya classifies it
and takes exactly one of five paths. This taxonomy is the contract Claude Code builds to.

### Path 1 — Answer inline (prose)
A question with a direct answer. Vidya replies in the thread as prose, with sources and
a ConfidenceBand; any claim can open an EvidenceDrawer. No component is manufactured for
its own sake.

### Path 2 — Compose a live component (generative surface)
The request implies a *view*. Vidya composes a real, interactive component **in the
thread** — not a screenshot, not static. The component **takes shape** with the
border-draw motion (the frame draws itself) + a staggered reveal of its contents + bars
growing from zero. It is fully functional: it reads live governed data, renders the
v4.1 components from `10`, and carries its own actions. Examples and what each renders:

| Ask | Composed component (from `10`) |
|---|---|
| "where am I weakest" | MasteryView + a small generated bar viz + "Start the fix" / "Open in Progress" / "Why this" |
| "compare 10-A vs 10-B in Science" | a Chart (only because the shape is read) + RecommendationItem |
| "quiz me on photosynthesis" | a live quiz component (verified items) inline |
| "make a paper, 30 marks, trigonometry" | a Blueprint mini-surface (prepared, not committed) + "Open in Papers" |
| "who needs intervention in 6-B" | StudyQuadrant + grouped RecommendationItems |
| "show this child's week" (parent) | the reassurance card + one at-home action |

Every composed component carries, where relevant: a **ConfidenceBand**, an **EvidenceDrawer**
trigger ("Why this"), a **primary action** (rise-fill), and an **"Open in <page>"**
promote (fill-wipe). The component is generated-and-verified before it renders (`11`);
nothing unverified appears.

### Path 3 — Take the action (within the permission ladder)
The request is a *task* Vidya can perform. Vidya **prepares** it and surfaces an
**ApprovalControl** for anything consequential (send/submit/publish/delete/charge/grade),
or performs it directly if it is safe-automatic and policy-permitted. The result returns
to the thread with what changed and an undo where reversible. The ladder (`11`) is never
bypassed in the chat — "do it" in conversation still raises the approval step for
consequential actions.

### Path 4 — Route to the page (when the page is the right place)
The task needs a full workspace or produces persistent state. Vidya **opens the
dedicated page** and **docks itself** there (the VidyaDock, `17`), pre-filled with the
context from the conversation. The thread shows a short "opened <page> for you" with a
link back. The page is never a dead end; Vidya keeps driving it.

### Path 5 — Route + guide with on-screen SVG (when the user must act)
For a task Vidya cannot or should not finish for the user (a decision, a credential, a
manual step, a consequential confirmation), Vidya routes to the page and **draws the
steps on screen**: an SVG guide overlay — a soft spotlight on the target control, a
hairline arrow drawn to it (border-draw style), and a one-line caption. Steps advance as
the user acts. This is the "guide them with SVGs" pattern: teach-by-doing, not a popup
wall. The overlay is dismissible and never blocks the underlying control.

**The decision rule (build it as a classifier contract):** answerable → Path 1; a view
helps → Path 2; an action Vidya may take → Path 3; needs a workspace → Path 4; the user
must act → Path 5. When ambiguous, Vidya asks one clarifying question rather than
guessing.

## 16.3 Drawers, popovers, modals, toasts — when each appears and what it does

A precise inventory so behaviour is consistent everywhere:

- **EvidenceDrawer (right slide-in, ~420px, frosted edge, no shadow).** Trigger: "Why
  this" / tapping any conclusion, mastery cell, recommendation, or generated artifact.
  Contains: the claim, the evidence list (attempts/quizzes/observations, dated, with the
  independent-vs-supported flag), the model/source + ConfidenceBand, and "why am I seeing
  this." Read-only; deep-links to each source. Dismiss: Esc / click-out / close.
- **VidyaDock (docked panel/orb on deep pages).** Collapsible; drives the current page;
  see `17`.
- **Command palette (centered, frosted, Cmd-K).** `17`/`18`. Search, jump, ask, voice.
- **ApprovalControl (inline card or bottom sheet).** Appears before any consequential
  action. Contains: the prepared action summary, its consequence, Approve / Adjust /
  Decline, and records who approved + when (audit). Never auto-dismisses; the action does
  not fire until Approve.
- **Popover (small, anchored, frosted).** For the model selector, the `+` attach menu,
  filters, the child switcher (parent), row overflow menus. Light, dismiss on click-out.
- **Modal (centered, scrim, frosted, ≤640px, radius-md).** Reserved for a focused
  sub-task that must capture full attention (confirm a destructive action, a short wizard
  step). Used sparingly — most v2 modals become inline disclosures or pages (`01`).
- **Toast (bottom-center, transient).** Confirmation of a completed action, with undo
  where reversible. Never carries critical information that needs acknowledgement.
- **Guide overlay (full-surface SVG, non-blocking).** Path 5. Spotlight + drawn arrow +
  caption; advances with the user; dismissible.

## 16.4 Buttons and controls — function inventory

Every interactive control names its function and motion (motions per `20`):

- **Primary action** (rise-fill, signature): the one consequential or forward action on a
  surface — Start, Generate, Assign, Approve, Submit. One per context.
- **Secondary action** (fill-wipe): Open in <page>, Compare, Adjust, Regenerate.
- **Ghost / icon button**: utility (attach, voice, overflow, close) — no fill, hairline
  or bare.
- **"Why this" / evidence**: opens the EvidenceDrawer.
- **"Open in <page>"**: Path-4 promote — routes + docks Vidya.
- **Suggestion chip** (rise-fill): a proactive next action; queues or opens it.
- **Approve / Adjust / Decline**: the ApprovalControl triad; only Approve commits.
- **Model selector**: switches the routed model (Auto by best-fit, or an explicit
  choice) — config, never changes price or capability scope.
- **Mic / orb**: opens voice mode (`17`).
- **Pin (rail)**: pins the sidebar expanded.

## 16.5 What automates vs what waits for a human

- **Automates (safe-automatic, reversible, policy-permitted):** composing a view,
  generating-and-verifying content for preview, drafting a plan/paper/group (prepared,
  not committed), rescheduling a missed revision block within policy, surfacing
  recommendations, classifying intent, routing, translating, summarising a session
  (consent-gated).
- **Waits for a human (Execute-with-permission):** sending any message, submitting work,
  publishing content, assigning to students, charging, deleting, and **grading a
  consequential mark** — each through the ApprovalControl. AI prepares; the person
  decides. Mastery is never shown to a learner/parent as a raw number; consequential
  marks are human-final and confidence-banded.

## 16.6 Elevation & experience (the premium feel, made concrete)

- **Calm first, power on demand.** The home is near-empty; complexity appears only when
  summoned. Restraint is the positioning made visual.
- **European-spacey.** Generous, compositional whitespace (24/32/48 rhythm); light-weight
  large headings; one accent per surface; the two lightest whites carry the shell.
- **Depth without shadow.** Hairlines (0.5px), tonal surface steps, frost on overlays
  only. A shadow anywhere is a defect.
- **Motion that means something.** Components draw themselves into being (border-draw),
  fills rise (rise-fill), stats count up, mastery crystallizes (`20`). Never decorative
  bounce. Everything honours reduced-motion.
- **Alive, not loud.** The ambient bloom and the living orb make the product feel awake;
  they never compete with content.
- **Buttery.** All motion is GPU-friendly (transform/opacity), eased
  (`cubic-bezier(0.2,0,0,1)`), and frame-budgeted; the rail and palette never lag.
