# 05 · Information Architecture

## The home — conversation-first and AI-native (all roles)

The home is the conversation, and it is calm. By default near-empty: a short greeting
and one composer, the way a clean AI assistant opens — **not a dashboard, not a module
grid.** The user states an intention; Vidya processes it dynamically and renders an
inline component only when the task warrants one. Most asks are answered or done
directly; it does not manufacture UI on every turn.

- **The left rail is slim and icon-based:** new conversation · search & history (tucked
  behind a button — the user does not return to old threads unless they need one) ·
  the role's features and pages · settings + profile at the bottom. The rail is where
  the deeper functions live. Expandable to labels on hover/pin; ~64px collapsed.
- **The proactive layer stays, quietly.** A few suggestion chips beneath the composer
  ("fix fractions, 15 min"), not a wall of cards. The full proactive feed is one of the
  rail's features, opened when wanted.
- **Small task → inline.** A self-contained ephemeral result renders as a generative
  component in the thread, carrying an "open in its page" control.
- **Big task → route.** A task that needs a real workspace or produces persistent state
  opens its dedicated page. Vidya stays docked there, collapsible, so the conversation
  keeps driving the page. The page is never a dead end.
- **Role-shaped, one shell.** Every role lands in the same conversation-first home with
  the same slim rail, shaped to them — the student's protects struggle; the teacher's
  executes and prepares; the admin's commands the institution; the parent's reports and
  reassures.
- **Full Vidya, not a text box.** The home preserves every Vidya capability (`11`):
  on-screen explanations, self-assembling derivations, misconception detonation, the
  editable canvas with sources and evidence, interactive teaching content, multimodal
  input, the assistance ladder, teach-back — with the permission ladder and
  child-safety on every free-text surface.

The fixed pages are the stable spine; the conversation is the front door over them. The
legacy v2 "home shapes" (My Workspace tile grid, role dashboards) are **deleted**;
their destinations live in the rail and are surfaced inside the conversation when
relevant.

## The rail (per role — icon → page group)

Each role's rail lists its feature groups (the surface map below). Order: New
conversation · Today/feed (the proactive home of that role) · the role's primary
groups in journey order · Search & history · Settings + profile (bottom). Every rail
entry reaches a real page; **no orphan pages, no dead links** is a quality gate (`15`).

## The 136-surface map

136 distinct surfaces: **Student 33 · Teacher 49 · Admin 34 · Parent 20.** Full
per-surface specs in `06`–`09`. The groups (and which `06`–`09` detail them):

### Student — 33 (`06`)
- **Home & companion (3):** Today · Vidya companion · Notifications.
- **Learn (6):** Learn home · Subject hub · Chapter view · Lesson player · Concept
  detail · Misconception fix.
- **Practice (4):** Practice home · Practice session · Practice review · Spaced
  retrieval.
- **Assess (5):** Quizzes & tests · Quiz attempt · Quiz result · Mock tests · Mock
  result & forecast.
- **Work (4):** Assignments · Assignment & submit · Project workspace · Submission
  history.
- **Progress (5):** Knowledge view · Mastery detail · My gaps · Portfolio ·
  Achievements & credentials.
- **Plan & ops (6):** Revision planner · Readiness forecast · Attendance · Request
  leave · Calendar · Settings.

### Teacher — 49 (`07`)
- **Home & companion (4):** Today · Vidya copilot · Proactive feed · Notifications.
- **Plan (4):** Planning home · Lesson plan · Differentiation · Teacher diary.
- **Classroom (5):** Live classroom · Board detail · Live poll/quiz · Device-free check
  · Session summary.
- **Attendance (3):** Attendance · Risk & reconciliation · My attendance.
- **Content (3):** Content library · Generate material · Resource detail.
- **Assign (5):** Assignments · Create assignment · Review submissions · Project
  management · Originality review.
- **Assessment (6):** Papers · Blueprint · Generate paper · Question bank · Schedule &
  proctoring · Moderation.
- **Evaluate (5):** Evaluation queues · Evaluate submission (Mode 1) · Scanned
  handwriting (Mode 2) · Rubric library · Confidence review.
- **Students & insights (7):** Students · Student detail · Gradebook · Reports · Report
  detail · Remedial · Class analysis.
- **Relationships (4):** Parent meetings · PTM prep · PTM follow-up · Communicate.
- **Growth & settings (3):** Growth & coaching · Continuity/handover · Settings.

### Admin — 34 (`08`)
- **Home & assistant (4):** This morning · Exceptions · Institution assistant ·
  Ask-anything dashboard.
- **Setup & governance config (6):** Blueprint wizard · Hierarchy & relationships ·
  Policies · Roles & access · Consent & permissions · Hyperlocalization.
- **Academic config (3):** Curriculum & ontology · Grading config · Assessment config.
- **Calendar & timetable (4):** Academic calendar · Timetable · Substitution · Pacing
  protection.
- **Intelligence (6):** Intelligence · Study quadrant · Target analytics · Syllabus
  coverage · Prediction & trajectory · Teacher analytics.
- **People & ops (5):** Students registry · Teachers & staff · Houses & groups ·
  Admissions (Edmissions citizen link) · Content management.
- **Governance & integrations (6):** AI control centre · Audit · Break-glass · Data
  governance · Integrations (FLUID) · Settings.

### Parent — 20 (`09`)
- **Home & companion (4):** This week · Switch child · Parent companion · Notifications.
- **Reports (6):** Reports & reviews · Progress report · Attendance review · Exam review
  · Test analysis · Syllabus coverage.
- **Engagement (8):** What to do at home · Learn alongside · Parent meetings · PTM prep
  · PTM follow-up · Messages · The shareable win · Events & calendar.
- **Ops (2):** Fees (Feesable citizen link) · Account & settings.

## Cross-cutting on every surface

- Emits attributed events on consequential actions (`12`).
- The permission ladder: approve before send/submit/publish/delete/charge/grade.
- No unverified generated content renders (the confidence gate).
- Mastery shown as independence-aware plain language, never a raw score.
- Vidya reachable everywhere, role-shaped, acting only through registered capabilities.
- Multilingual + code-switching; subject terminology preserved.

## The universal state model (every page ships all of these)

Every surface implements, designed not defaulted:

1. **Empty / first-time** — a calm explanation of what will appear here and the one
   action that starts it. Never a blank panel.
2. **Loading** — skeletons on the surface shell (no spinners as the primary state where
   a skeleton fits); progressive reveal as data arrives.
3. **Error** — a recoverable message with a retry and a Vidya "help me with this" path;
   never a stack trace, never a dead screen.
4. **Offline** — a **designed** state for the core flows (attendance, lessons,
   assignments, basic evaluation): the surface works against the local cache and shows a
   quiet "will sync" affordance. Non-core surfaces show a clear offline notice with what
   is and isn't available.
5. **Permission-denied** — explains what scope is required and who grants it; never a
   silent blank.

## Navigation rules

- Journey-based, not module-based. Each surface answers: what needs attention, what to
  do next, how long, why, what progress it creates.
- Progressive disclosure: the simple thing first; advanced config and deep analytics
  appear only when asked for.
- A page reached from the rail or from Vidya is never a dead end — Vidya stays docked,
  and the next best action is always present.
