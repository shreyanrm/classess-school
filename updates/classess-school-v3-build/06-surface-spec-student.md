# 06 · Surface Spec — Student (33 surfaces)

**Per-surface template.** Each entry: **Route** · purpose · *v2→v3* (what v2 had and
the makeover move) · *Contains* · *Behaviour* (when/why/how) · *Reads / Writes / Emits*
(data, events, capabilities — see `12`/`13`) · *States* (the non-default ones) · *DoD*.

**Student cross-cutting:** never render a raw score or the mastery formula — only the
independence-aware plain-language mastery view; never overwhelm with administration or
analytics; the experience adapts to age and stage; the assistance ladder always
protects productive struggle; Vidya is the companion, guiding, never just handing over
answers. One subject accent per subject surface. Subject accents per `04`.

---

## Home & companion

### Today · `/student/`
Your one next step — what, why, how long, what it builds.
- *v2→v3:* v2 opened on a radial home then a dashboard with donut + performance bars +
  leaderboards. v3 deletes the dashboard-home; the conversation-first home (`11`)
  greets and offers one composer; this Today surface is the calm single-next-step
  destination, reached from the rail and surfaced inline by Vidya.
- *Contains:* one **briefing card** (primary next action, e.g. "Practise Fractions on
  your own"); the why (plain language), the time estimate, the progress it creates;
  actions Start / Why this / Ask Vidya; suggestion chips (retrieval due, homework due
  tomorrow, 2-min confidence check).
- *Behaviour:* the next step is computed from the learner's live mastery + gaps +
  calendar via a gateway read of the intelligence API. Start opens the recommended
  surface; Why opens the **evidence drawer**; chips queue work. Recomputed on each
  visit and on fresh evidence.
- *Reads:* intelligence (mastery/gaps for the learner), calendar, coursework due.
  *Emits:* `surface.viewed`, `recommendation.actioned`. *Capabilities:* none consequential.
- *States:* empty (new learner → "let's find where to start" diagnostic entry); offline
  (last cached next step + "will refresh"); loading (skeleton briefing card).
- *DoD:* one clear next step, plain-language why, evidence drawer, no raw score, chips
  queue real work, recomputes on new evidence.

### Vidya companion · `/student/vidya`
Ask or do anything — guidance, never just answers.
- *v2→v3:* v2 had a subject-listed chat with empty states. v3 is the full Vidya
  workspace (`11`): conversation + editable canvas + sources/evidence alongside.
- *Contains:* conversation pane; editable canvas (centre); sources & evidence;
  actions New thread / Voice / Attach image-doc-screen / History.
- *Behaviour:* role-shaped student companion; protects productive struggle (the
  assistance ladder, teach-back); summons any surface inline within the permission
  ladder; multimodal; multilingual with code-switching. Child-safety on every free-text
  turn (moderation, crisis detection → escalation to a responsible adult). Never just
  hands over answers.
- *Reads:* per-user memory (PII-free, consent-gated), mastery/gaps, ontology.
  *Emits:* `vidya.turn`, `assistance.level.changed`, `teachback.completed`.
  *Capabilities:* generate-and-verify content, explain, hint, summon-surface
  (Prepare/Execute-with-permission).
- *States:* offline (a constrained on-device/edge fallback for simple help, with a
  clear "full Vidya needs a connection"); error (retry + safe fallback).
- *DoD:* canvas editable; sources shown; ladder enforced; safety on every turn; no
  answer-handover; voice + multimodal work.

### Notifications · `/student/notifications`
What changed, what's due, what needs you.
- *v2→v3:* v2 list re-skinned to v4 tight list; calm, no badges screaming.
- *Contains:* list (homework graded, new quiz Friday, retrieval due, streak/identity
  note). Each item links to its surface.
- *Behaviour:* generated from real events; grouped by what-needs-you vs FYI; quiet-hours
  aware.
- *Reads:* notification stream (Realtime). *Emits:* `notification.opened`.
- *States:* empty ("nothing needs you right now"); offline (cached).
- *DoD:* every item deep-links; no raw scores; calm tone.

---

## Learn

### Learn home · `/student/learn`
Continue learning, by subject.
- *v2→v3:* v2 subject cards re-expressed as a **tight subject matrix**, one accent per
  subject, mastery shown as plain-language state not %.
- *Contains:* subject cards (Mathematics, Science, English…) with "where you are" in
  plain language; actions Continue / Browse topics.
- *Behaviour:* Continue resumes the last open topic at the right assistance rung; cards
  ordered by what most needs attention.
- *Reads:* ontology (subjects/chapters), mastery per subject. *Emits:* `learn.opened`.
- *States:* empty (diagnostic to seed the map); offline (cached subjects).
- *DoD:* subject matrix on v4; plain-language state; Continue resumes correctly.

### Subject hub · `/student/subject`
One subject — lesson, homework, project, quiz, notes.
- *Contains:* tabs Lesson / Homework / Project / Quiz / Notes; cards current lesson,
  homework, notes; actions Open lesson / Open homework.
- *Behaviour:* a single subject's working set in one place; the subject's accent colours
  the surface.
- *Reads:* ontology, coursework, content. *Emits:* `subject.opened`.
- *DoD:* tabs work; one accent; deep-links correct.

### Chapter view · `/student/chapter`
Topics in a chapter, with your mastery on each.
- *v2→v3:* v2 chapter/topic outline re-skinned; mastery per topic shown as
  independent / with-guidance / review-due, not %.
- *Contains:* topic list with plain-language mastery state; actions Open topic.
- *Behaviour:* tapping a topic opens the lesson player or practice at the right rung;
  review-due driven by spaced retrieval.
- *Reads:* ontology (chapter→topics), mastery, retrieval schedule.
- *DoD:* per-topic plain-language state; review-due accurate.

### Lesson player · `/student/lesson`
Build it — pose → predict → reveal, help that fades.
- *v2→v3:* v2 had a lesson with roadmap context + a predict-then-check modal. v3 makes
  pose-struggle-reveal the spine, with the assistance ladder and verified content.
- *Contains:* the canvas (pose → predict → reveal); the **assistance ladder control**
  (Learn → Coach → Hint → Work-with-me → Check-my-work → Independent); actions Commit
  prediction / Hint / Teach it back / Different explanation / Switch language.
- *Behaviour:* **reveal is locked until a prediction is committed** (generation effect).
  Wrong answers route to the gap engine; specific misconceptions fire **misconception
  detonation** (the one counterexample that breaks the model). Content is **verified
  before it renders** (confidence gate). Support visibly fades as mastery grows.
- *Reads:* ontology, mastery/gaps, content engine. *Writes:* attempt records.
  *Emits:* `attempt` (with independent-vs-supported flag, difficulty, assistance level),
  `misconception.detected`, `teachback.completed`. *Capabilities:* generate-and-verify,
  hint, detonation, teach-back.
- *States:* offline (pre-synced verified lesson pack for the scheduled topics; new
  generation deferred with a clear notice); loading (skeleton canvas); error (safe
  fallback to a cached explanation).
- *DoD:* reveal gated on prediction; misconception detonation fires on the right model;
  nothing unverified renders; ladder fades; attempt event carries the independence flag.

### Concept detail · `/student/concept`
A concept several ways, in your language.
- *v2→v3:* v2 multiple-explanation cards re-expressed as tabs; multilingual.
- *Contains:* tabs Visual / Worked / Analogy / Formal; actions Show another way /
  Practise this.
- *Behaviour:* each style generated-and-verified; language switch preserves subject
  terms.
- *DoD:* four styles; verified; language switch works.

### Misconception fix · `/student/misconception`
The exact counterexample that breaks the wrong idea.
- *Contains:* canvas — your mental model vs the engineered counterexample; actions I see
  it now / Try the corrected version.
- *Behaviour:* fires when the gap engine identifies the specific broken model behind a
  wrong answer — aimed remediation. The shatter is an animate-meaning moment (`04`).
- *Reads:* gap classification. *Emits:* `misconception.resolved`.
- *DoD:* counterexample is specific to the detected model; animate-meaning shatter;
  routes to a corrected attempt that re-evaluates unaided.

---

## Practice

### Practice home · `/student/practice`
Right difficulty, your real gaps.
- *v2→v3:* v2 had a practice-variety panel (concept mastery, smart/mind match, quick
  quiz, flashcards). v3 keeps the variety, drives difficulty from the live read.
- *Contains:* cards Continue practice / Weak spots / Retrieval; actions Start /
  Flashcards.
- *Behaviour:* selections target the learner's confirmed gaps; difficulty seeded from
  mastery.
- *Reads:* mastery/gaps. *DoD:* variety preserved; difficulty seeded from the live read.

### Practice session · `/student/practice-session`
Adaptive items at your level.
- *v2→v3:* v2 quiz/question UI re-skinned; now adaptive + gap-mapped.
- *Contains:* item canvas; actions Submit / Flag question / Hint; quiet progress.
- *Behaviour:* difficulty adapts live; mistakes map to concepts and feed mastery;
  solutions unlock only post-attempt. Items generated-and-verified.
- *Writes:* attempts. *Emits:* `attempt`, `practice.item.completed`.
- *States:* offline (pre-synced item pack); error (skip-and-retry).
- *DoD:* adaptive difficulty; gap mapping; verified items; solutions post-attempt only.

### Practice review · `/student/practice-review`
What you got, what it means, what next.
- *Contains:* a plain-language result (not a bare score); the named gap; actions Start
  the 15-min fix / Back.
- *Behaviour:* converts the session into the single best next action.
- *DoD:* plain-language result; named gap; one next action.

### Spaced retrieval · `/student/retrieval`
Review exactly when memory is fading — honest, not guilt.
- *v2→v3:* new vs v2's generic reminders; uses the real forgetting curve.
- *Contains:* retrieval cards scheduled on the curve; actions Start review / Why now.
- *Behaviour:* schedules review when memory is genuinely fading (spaced repetition);
  never guilt-based; "Why now" explains the science + this learner's curve.
- *Reads:* retrieval schedule, mastery. *Emits:* `retrieval.completed`.
- *DoD:* schedule reflects the real curve; honest tone; Why-now explains.

---

## Assess

### Quizzes & tests · `/student/assess`
Everything to attempt.
- *Contains:* list (chapter quiz — opens Friday, unit mock — available, slip test —
  done). *Behaviour:* status-driven; links to attempt. *DoD:* statuses accurate; links work.

### Quiz attempt · `/student/quiz-attempt`
Palette, timer, flags.
- *v2→v3:* v2 question palette + timer re-skinned to calm v4.
- *Contains:* canvas (N questions · timer); actions Start / Flag / Submit.
- *Behaviour:* Submit is permission-gated; autosave; offline-tolerant.
- *Writes:* responses. *Emits:* `assessment.submitted`.
- *States:* offline (local capture + sync); error (no data loss).
- *DoD:* timer + palette + flags; permission-gated submit; no data loss offline.

### Quiz result · `/student/quiz-result`
Grasp, not just a grade.
- *v2→v3:* v2 donut result modal → a plain-language grasp summary + the named gap, with
  a number only if the assessment is formally graded (and then with evidence).
- *Contains:* grasp summary; the gap; actions Start targeted fix / Review answers.
- *Behaviour:* confidence-banded; consequential marks are human-final; links straight to
  a fix.
- *Reads:* evaluation result. *DoD:* grasp over grade; confidence band; fix link.

### Mock tests · `/student/mock`
Real format and difficulty.
- *Contains:* cards Unit mock / Board pattern; actions Start mock / Readiness forecast.
- *Behaviour:* mocks mirror the real format/difficulty; generated-and-verified.
- *DoD:* format-faithful; verified.

### Mock result & forecast · `/student/mock-result`
Where you'd land, and what's still achievable.
- *Contains:* projected vs achievable (plain language + a chart only if the shape is
  read); actions Rebalance plan.
- *Behaviour:* predictive read recalculates what's achievable given time left and
  weightage; turns a forecast into a plan.
- *Reads:* prediction (intelligence). *DoD:* projection + achievable; rebalance writes
  to the planner.

---

## Work

### Assignments · `/student/work`
Homework and projects.
- *Contains:* list (set — due tomorrow, project — week 2, essay — submitted).
- *Behaviour:* risk-based reminders (not generic spam). *DoD:* statuses; risk reminders.

### Assignment & submit · `/student/assignment`
Do, check yourself, submit.
- *v2→v3:* v2 assignment + submission re-skinned; adds the preventive (Mode-3) check.
- *Contains:* form (type, attach photo/audio/doc/camera, your answer); actions
  Preventive check / Save draft / Submit.
- *Behaviour:* the **preventive check** gives graduated hints from the camera before
  submitting — never the final answer, never forced. Submit is permission-gated. Drafts/
  revisions/final tracked.
- *Writes:* submission (draft→final). *Emits:* `submission.created`, `attempt`.
  *Capabilities:* preventive evaluate (Prepare), submit (Execute-with-permission).
- *States:* offline (draft saved locally, submit queued); error (no loss).
- *DoD:* multi-media submit; preventive check never reveals the answer; permission-gated
  submit; offline-safe.

### Project workspace · `/student/project`
Group, milestones, contribution.
- *Contains:* group, milestone, contribution; actions Open milestone / My contribution /
  Message group.
- *Behaviour:* balanced groups composed from mastery; individual contribution tracked
  alongside teamwork.
- *DoD:* milestones; contribution view; group messaging routes through the safety layer.

### Submission history · `/student/submissions`
Drafts, revisions, finals.
- *Contains:* table (work · state · date). *DoD:* full history; states accurate.

---

## Progress

### Knowledge view · `/student/progress`
A mirror of your thinking — independent vs support-dependent.
- *v2→v3:* v2 had a galaxy/knowledge-map visual + analytics dashboards. v3 becomes the
  **knowledge view**: the signature, queryable map showing independent vs
  support-dependent mastery, igniting a region on genuine mastery.
- *Contains:* the knowledge-view visual; a table (topic · where you are · evidence);
  actions Ask the twin / Open evidence / Set a goal.
- *Behaviour:* queryable in natural language ("what am I weakest at", "what unlocks
  astrophysics"); tapping a region opens its **evidence drawer**; the **ignite** fires
  on genuine comprehension. Never a number or formula.
- *Reads:* learner graph, mastery, evidence (governed views). *Emits:* `knowledge.queried`,
  `goal.set`. *Capabilities:* query-the-graph (read).
- *States:* empty (diagnostic seeds the map); loading (progressive region reveal).
- *DoD:* independent vs support-dependent visible; queryable; evidence on tap; ignite on
  mastery; no raw score.

### Mastery detail · `/student/mastery-detail`
One topic, the full evidence trail.
- *Contains:* plain-language dimensions (independent, reliable, recent…); the evidence
  list (attempts, quizzes, dates, supported-vs-unaided).
- *Behaviour:* shows the six dimensions in plain language, never a raw score; every row
  links to the originating evidence.
- *DoD:* six dimensions in plain language; full evidence trail; no formula.

### My gaps · `/student/gaps`
Named, not just 'low'.
- *Contains:* gap list (Application — word problems; Retention — older topics); actions
  Fix the top gap.
- *Behaviour:* each gap is one of the ten types, confirmed on ≥2 signals; Fix routes to
  targeted, verified practice.
- *DoD:* named gap types; confirmation rule honoured; fix routes correctly.

### Portfolio · `/student/portfolio`
Your evidence-linked story.
- *Contains:* cards Projects / Achievements / Best work; actions Share.
- *Behaviour:* built from evidence; each item carries source + permission controls.
- *DoD:* evidence-linked; permission-scoped sharing.

### Achievements & credentials · `/student/achievements`
Verifiable, portable, yours.
- *Contains:* cards Badges / Certificates; actions Verify / Share the win.
- *Behaviour:* credentials issued + verifiable; portable under the learner's control.
- *DoD:* verifiable; portable; permission-scoped.

---

## Plan & ops

### Revision planner · `/student/revision`
Exam-aware, rebalances on reality.
- *v2→v3:* v2 smart/exam planner re-skinned; now rebalances on missed sessions.
- *Contains:* form (exam date, subjects, time/day); actions Generate plan / Start session.
- *Behaviour:* prioritises weak prerequisites; distributes workload to reduce stress;
  **a missed session auto-reschedules** (never nags).
- *Reads:* mastery/gaps, calendar. *Writes:* plan. *DoD:* prereq-prioritised; auto-rebalances.

### Readiness forecast · `/student/readiness`
What's achievable given time left.
- *Contains:* now vs by-exam (plain language); actions Apply to plan.
- *Behaviour:* predictive read; recalculates achievable given time + weightage.
- *DoD:* honest forecast; applies to the planner.

### Attendance · `/student/attendance`
Presence and leave.
- *v2→v3:* v2 attendance heatmap re-skinned to a calm matrix.
- *Contains:* term + absent (plain); actions Request leave / Download.
- *DoD:* accurate; calm; export works.

### Request leave · `/student/leave`
Ask, track approval.
- *Contains:* form (date, reason); actions Send request. *Behaviour:* permission-gated;
  status tracked. *DoD:* request + approval status.

### Calendar · `/student/calendar`
Classes, exams, due dates.
- *Contains:* month view. *DoD:* classes/exams/due dates correct; offline cached.

### Settings · `/student/settings`
Profile, notifications, language, account.
- *v2→v3:* v2 had Personal/Institute Info, Security, My Devices, Theme. Consolidated on
  v4: Profile · Notifications · Language/region · Account (incl. delete-account /
  right-to-erasure) · Devices · Theme (light/dark via `data-theme`).
- *Behaviour:* language/region drive hyperlocalization; consent visible + revocable.
- *DoD:* all sections; delete-account works; consent revocable; theme flips.
