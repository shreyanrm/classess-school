# Pages and experience

Pages per role, then the shared component vocabulary every screen is composed from. The exact buttons, drawers, tables, and states for each page are authored during that slice's build, on the v4 kit (`07`) and against the contracts (`06`) — this file fixes the inventory and the patterns so nothing is invented twice.

## The home — conversation-first and AI-native

The home is the conversation, and it is calm. By default it is near-empty: a short greeting and one composer, the way a clean AI assistant opens — not a dashboard. The user states an intention; Vidya processes it dynamically and renders an inline component only when the task warrants one. Most asks are answered or done directly; it does not manufacture UI on every turn.

- **The left rail** is slim and icon-based: new conversation, search and history (tucked behind a button — the user does not return to old threads unless they need one), the role's features and pages, and settings + profile at the bottom. The rail is where the deeper functions live.
- **The proactive layer stays, quietly.** The platform still does not wait to be asked — but in this calm home it surfaces as a few suggestion chips beneath the composer ("fix fractions, 15 min"), not a wall of cards. The full proactive feed is one of the rail's features, opened when wanted.
- **Small task → inline.** A self-contained, ephemeral result renders as a generative component in the thread, carrying an "open in its page" control.
- **Big task → route.** A task that needs a real workspace or produces persistent state opens its dedicated page. Vidya stays docked there, collapsible, so the conversation keeps driving the page. The page is never a dead-end.
- **Role-shaped, one shell.** Every role lands in the same conversation-first home with the same slim rail, shaped to them — the student's protects struggle; the teacher's executes and prepares (ask for analytics, build a quick check, draft a paper, in the chat); the admin's commands the institution; the parent's reports and reassures.
- **Full Vidya, not a text box.** The home preserves every Vidya capability: on-screen explanations, self-assembling derivations, misconception detonation, the editable canvas with sources and evidence, interactive teaching content, multimodal input, the assistance ladder, and teach-back — with the permission ladder and child-safety on every free-text surface.

The fixed pages still exist as the stable spine; the conversation is the front door over them. The legacy "home shape" tabs (Today, My Work, People & Classes, Insights, Apps) are not separate landing tabs — they are reachable from the rail and surfaced inside the conversation when relevant.

## Pages per role

### Admin (role-scoped: owner, principal, coordinator, HOD, examination, support, IT)
Today (briefing — what needs attention, which classes are behind, which teachers need support, which students need intervention, open parent concerns, blocking approvals, what improved after the last intervention) · Setup & hierarchy (blueprint wizard, structure, roles, policies) · Calendar & timetable (generation, substitution, pacing) · School-wide intelligence (study quadrant, target analytics, curriculum coverage, ask-anything) · The proactive feed · Governance & audit (policy, permissions, AI control centre, break-glass). Behaves as: manage by exception — review, approve, track outcome.

### Teacher
Today (next class, ready lesson, pending evaluations, students needing attention, messages, tomorrow's prep, one private coaching insight) · Class diary & planning · Classroom delivery (board, polls, device-free check, attention signals, breakout rooms) · Attendance (voice, photo-scan, photo-roster, absent-only) · Assignments & papers (blueprint generation, worksheets, projects, multi-set) · Evaluation (three modes, rubric library, voice entry, confidence-banded review) · Student insights / grades & reports / PTM prep / remedial. Every action three steps or fewer.

### Student
Today (next step, why, how long, what it builds) · Learn (pose-struggle-reveal, multiple styles, multilingual) · Practice (adaptive, mistake-based, spaced retrieval) · Progress (the knowledge profile — independent vs support-dependent, plain language, queryable) · Assignments, assessments & feedback · Study planner & mock tests · The companion (Ask). Never overwhelmed with administration or analytics; adapts to age and stage.

### Parent
Today (three actions that need attention this week, in the parent's language) · The child view (one timeline per child, one-click switching, progress, strengths, support areas) · Assignments, exams & reports (parent-specific feedback, celebration points, next steps) · Learn-alongside & PTM. Partnership and pride, never surveillance or fear.

## Shared component vocabulary

Build these once, reuse everywhere. All on v4 tokens, no shadows, one semantic accent per surface.

- **Briefing card** — the Today unit. A single attention item: title, the one next action, time estimate, why it is recommended, the progress it creates. Action button + dismiss/defer.
- **Recommendation item (the proactive feed)** — evidence summary, confidence band, owner, due date, consequence of ignoring, and an Approve / Adjust / Decline control. This is the manage-by-exception primitive across Admin and Teacher.
- **Evidence drawer** — slides over any conclusion to show the linked evidence and lineage. Nothing is asserted without a path to its evidence.
- **Confidence band** — the standard treatment for any AI output: high (provisional auto), middle (flagged for review), low (must be reviewed). Used in evaluation, recommendations, and dashboards.
- **Mastery view** — the knowledge profile rendered as independent vs support-dependent, in plain language, never a number or formula. Queryable ("what am I weakest at," "what unlocks this").
- **Assistance ladder control** — Learn → Coach → Hint → Work-with-me → Check-my-work → Independent, visibly fading as competence grows. The student always knows whether the system is helping them learn or formally evaluating them.
- **Evaluation review table** — per-response rows: question, answer state (correct / incomplete / misunderstood), rubric score, confidence band, the human-final control. Voice mark entry supported.
- **Approval control** — the gate on anything consequential (send, submit, publish, delete, charge, grade). Never auto-fires; always shows what will happen.
- **Child switcher (parent)** — one-click switch that re-renders the entire surface for the selected child.
- **Proof artifact (parent)** — a beautiful, shareable, WhatsApp-native moment drawn from the child's own learning; child-triggerable ("show what I just cracked").
- **Vidya panel** — the conversational fast-path: conversation on one side, an editable canvas in the centre, sources and evidence alongside; multimodal input; the permission ladder enforced in-conversation; child-safety on every free-text surface.

## States are first-class

Every page ships its empty, loading, error, offline, and permission-denied states — not as afterthoughts. Offline is a designed state for the core flows (attendance, lessons, assignments, basic evaluation), not a failure screen.
