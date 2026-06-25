# 07 · Surface Spec — Teacher (49 surfaces)

Template as in `06`. **Teacher cross-cutting:** every action three steps or fewer; the
platform prepares, the teacher decides; AI output is confidence-banded and human-final
on anything consequential; the proactive feed carries evidence · confidence · owner ·
due · consequence; coaching signals are private to the teacher first. Subject accent
per the class being taught.

---

## Home & companion

### Today · `/teacher/`
Your day — ready in three steps or fewer.
- *v2→v3:* v2 opened on an analytics dashboard / workspace grid. v3 replaces it with the
  conversation-first home; this Today is the calm day surface.
- *Contains:* primary **briefing card** (next class · grade · topic); actions Start class
  / Pending evaluations; a short list of attention items (8 share an application gap →
  group + set; 2 papers awaiting moderation; Riya absent 2 days → catch-up + note); one
  private coaching insight; tomorrow's prep.
- *Behaviour:* assembled from timetable + the proactive loop; each attention item is a
  **recommendation item** with Approve / Adjust / Decline; nothing auto-fires.
- *Reads:* timetable, proactive recommendations, evaluation queue, coaching signals.
  *Emits:* `surface.viewed`, `recommendation.actioned`. *States:* empty (no class today →
  prep/planning surface); offline (cached day).
- *DoD:* day in one view; ≤3 steps to any action; recommendations carry full provenance;
  private coaching insight present.

### Vidya copilot · `/teacher/copilot`
Prepare and execute by asking.
- *v2→v3:* v2 had a Vidya modal that generated content. v3 is the full copilot workspace.
- *Contains:* conversation + canvas; "make a quiz on photosynthesis" → builder in-thread;
  actions New thread / Voice / Attach.
- *Behaviour:* role-shaped to execute and prepare (build a quick check, draft a paper,
  ask for analytics, in the chat); generative-UI composes real surfaces inline within the
  permission ladder (consequential actions need approval); generate-and-verify on all
  content.
- *Capabilities:* generate-and-verify, build-surface, draft-paper, query-analytics
  (Prepare / Execute-with-permission). *DoD:* in-thread builders; verified output;
  permission ladder holds.

### Proactive feed · `/teacher/feed`
Everything Classess found, with evidence and an owner.
- *v2→v3:* new — surfaces the proactive loop that v2 lacked.
- *Contains:* **recommendation items** (Grade 6-B application gap — 8 students; Grade 7
  pacing slip — 1 week behind; 3 parent concerns open). Each carries evidence ·
  confidence · owner · due · consequence and an Approve that acts.
- *Behaviour:* manage-by-exception; Approve runs the prepared action through the
  permission ladder; outcomes tracked back.
- *Reads:* proactive loop. *Emits:* `recommendation.actioned`, `intervention.created`.
- *DoD:* every item has full provenance; Approve executes the prepared action; outcomes
  return.

### Notifications · `/teacher/notifications`
What needs you. *Contains:* list (plan approved, 28 new submissions, PTM tomorrow).
*DoD:* deep-links; calm.

---

## Plan

### Planning home · `/teacher/plan`
Annual, unit, weekly, daily.
- *v2→v3:* v2 course-flow re-skinned; tabs by horizon.
- *Contains:* tabs Annual / Unit / Weekly / Daily; cards Today's lesson / This unit /
  Coverage; actions Open today.
- *Behaviour:* plans generated against curriculum + the chosen instructional model.
- *Reads:* ontology, coverage. *DoD:* four horizons; coverage accurate.

### Lesson plan · `/teacher/lesson-plan`
Generated, adapts to yesterday.
- *v2→v3:* v2 lesson-plan/material/quiz/worksheet generator re-skinned; adds
  adapt-to-yesterday.
- *Contains:* plan sections (warm-up recall, core application, exit 2-question check);
  actions Generate / Adapt to yesterday / Differentiate / Send for approval.
- *Behaviour:* next day adapts to completion + observed performance + engagement; routes
  for coordinator/head approval where policy requires.
- *Reads:* ontology, yesterday's delivery + performance. *Writes:* plan. *Emits:*
  `plan.generated`, `plan.submitted`. *Capabilities:* generate-and-verify, adapt.
- *DoD:* generates against curriculum; adapts to yesterday; approval routing works.

### Differentiation · `/teacher/differentiation`
Three tiers from mastery.
- *Contains:* the **study quadrant**; tiered paths. *Behaviour:* tiers drawn from the
  mastery model + gaps. *DoD:* tiers from real mastery; quadrant on v4.

### Teacher diary · `/teacher/diary`
Taught vs planned, automatically.
- *Contains:* table (date · planned · delivered). *Behaviour:* auto-recorded from
  delivery. *DoD:* auto-populated; planned-vs-delivered accurate.

---

## Classroom

### Live classroom · `/teacher/live`
Run the period — one launch.
- *v2→v3:* v2 had session/lesson launch. v3 makes one launch load content + attendance +
  checks together, with the interactive board.
- *Contains:* the interactive board canvas (ink over hardware-accelerated content);
  actions Launch period / Insert visual / Run poll / Device-free check / Breakout /
  Record.
- *Behaviour:* Launch loads the day's content, attendance, and checks together; generated
  visuals are **verified before reaching the board**; on-device attention signals assist,
  never grade from a face; recording is consent-gated.
- *Reads:* timetable, content, attendance. *Emits:* `class.launched`, `engagement.signal`.
  *Capabilities:* generate-and-verify board content, run-poll, device-free-check.
- *States:* offline (cached lesson + local attendance; live media degrades with notice).
- *DoD:* one launch loads everything; verified board content; attention assists not
  grades; consent-gated recording.

### Board detail · `/teacher/board`
Infinite canvas, subject-aware.
- *Contains:* ink + shapes + sim + frozen-frame annotate; multiple themes; document
  sharing. *Behaviour:* native ink floats over the content host sharing one camera;
  switch between live interaction and annotating a frozen frame. *DoD:* full ink/shape
  tools; freeze-frame; subject-aware content; verified generated visuals.

### Live poll / quiz · `/teacher/poll`
Instant grasp, mid-lesson.
- *Contains:* metrics Got it / Unsure / Lost; actions Regroup the 9 / Close.
- *Behaviour:* links to the day's lesson; results feed grasp signals; Regroup composes a
  group + set. *DoD:* live grasp; regroup acts.

### Device-free check · `/teacher/device-free`
Photograph the room — cards read instantly.
- *v2→v3:* v2 had Plicker-style cards. v3 keeps it: each student holds a response card;
  the teacher photographs the room for instant on-the-spot evaluation + a live
  leaderboard.
- *Contains:* canvas (26/28 cards read · 3 chose the misconception); actions Reteach now /
  Later. *Behaviour:* on-device card read; misconception count routes to detonation/
  regroup. *DoD:* room-photo read; misconception surfacing; reteach acts.

### Session summary · `/teacher/session-summary`
Recording, transcript, summary.
- *Contains:* searchable transcript / key moments / auto-summary. *Behaviour:* consent-
  gated; generated summary verified. *DoD:* transcript searchable; summary present;
  consent enforced.

---

## Attendance

### Attendance · `/teacher/attendance`
Mark in seconds — propose, you confirm.
- *v2→v3:* v2 attendance grids re-skinned; multiple fast methods; assist-not-finalise.
- *Contains:* actions Photo-scan / Voice roll-call / Absent-only / Confirm; Present /
  Absent counts.
- *Behaviour:* methods **assist** (propose), the teacher confirms — never auto-final;
  works offline and syncs; manual is always first-class.
- *Writes:* attendance. *Emits:* `attendance.marked`, `attendance.risk` (downstream).
  *Capabilities:* photo-scan/voice (Prepare; teacher confirms).
- *States:* offline (capture + sync). *DoD:* multiple methods; never auto-final;
  offline-safe.

### Risk & reconciliation · `/teacher/attendance-risk`
Early-warning, not misconduct.
- *Contains:* list (Riya — 2 consecutive; Sam — chronic pattern; gate-vs-classroom
  mismatch — review); actions Trigger catch-up / Notify parent.
- *Behaviour:* detects consecutive/chronic/pattern risk + reconciles signals (transport/
  gate vs classroom), flags conflicts for human review, never treats as misconduct;
  triggers the catch-up + parent-comm workflow.
- *DoD:* risk types detected; reconciliation flags for review; catch-up workflow fires.

### My attendance · `/teacher/staff-attendance`
Own presence and leave. *Contains:* this-month + Apply leave. *DoD:* staff capture +
leave.

---

## Content

### Content library · `/teacher/content`
Approved, personal, publisher — one view.
- *v2→v3:* v2 "My Resources" re-skinned to a tight matrix; tagged to outcomes.
- *Contains:* matrix (resource · topic · status); actions Upload / Generate material.
- *Behaviour:* uploads pass OCR/transcription/document-understanding; tagged to the
  ontology + outcomes; versioned, approval-status, licence; duplicates detected.
- *DoD:* unified library; outcome tags; dedup; versioning.

### Generate material · `/teacher/content-create`
Summaries, worksheets, mind maps, decks.
- *v2→v3:* v2 generated content (fill-in-the-blank, mind maps) re-skinned; verified.
- *Contains:* actions Summary / Worksheet / Mind map / Interactive deck; note "verified
  before use."
- *Behaviour:* generated against curriculum and **verified** before use; flows into
  lessons. *Capabilities:* generate-and-verify. *DoD:* four artifact types; verified;
  flows to lessons.

### Resource detail · `/teacher/resource-detail`
Tagged, versioned, licensed. *Contains:* outcome / version; Use in lesson. *DoD:* metadata
+ use-in-lesson.

---

## Assign

### Assignments · `/teacher/assign`
Create, assign, review. *Contains:* list (set — assigned, project — in progress, essay —
to grade). *DoD:* statuses; links.

### Create assignment · `/teacher/assign-create`
AI-generated, verified, differentiated.
- *v2→v3:* v2 create-assignment re-skinned; adds verify + differentiation + PDF→questions.
- *Contains:* form (topic, type, rubric, groups); actions Generate (verified) / Upload
  PDF → questions / Assign.
- *Behaviour:* generated-and-verified; differentiated from mastery; kinds homework/
  worksheet/journal/portfolio/project; media types; drafts/revisions/final.
- *Emits:* `assignment.created`. *Capabilities:* generate-and-verify, pdf-to-questions.
- *DoD:* verified generation; differentiation; PDF ingestion; assign is permission-gated.

### Review submissions · `/teacher/assign-grade`
Evaluate and feed mastery.
- *v2→v3:* v2 student×question grading **heatmap** re-skinned; now feeds the gap engine +
  confidence bands.
- *Contains:* the grading matrix (student · state · confidence); actions Auto-evaluate /
  Review flagged.
- *Behaviour:* per-response state (correct / incomplete / misunderstood); confidence-
  banded (high auto-provisional, middle review, low must-review); human-final on
  consequential marks; feeds mastery + gaps.
- *Reads:* submissions, rubric. *Writes:* scores. *Emits:* `score`, `evidence` (independent
  vs supported). *DoD:* heatmap on v4; states separated; confidence banding; human-final;
  feeds the engine.

### Project management · `/teacher/project-manage`
Balanced groups, milestones, rubrics.
- *v2→v3:* v2 project + rubric re-skinned; six-dimension rubric.
- *Contains:* the study quadrant; actions Compose groups / Open rubric.
- *Behaviour:* composes balanced groups from mastery; milestones; project rubric
  (contribution, collaboration, communication, leadership, quality, problem-solving).
- *DoD:* balanced grouping; milestones; six-dimension rubric.

### Originality review · `/teacher/originality`
A concern surfaced — never a verdict.
- *Contains:* list (sudden style shift — 1; web similarity — 1); actions Ask student to
  explain / Compare.
- *Behaviour:* compares vs web / classmates / model answers; flags style shifts; asks the
  student to explain or rewrite; assessed separately from correctness; **the teacher
  judges**.
- *DoD:* concern surfaced not declared; explain/rewrite path; separate from correctness.

---

## Assessment

### Papers · `/teacher/papers`
Your assessments. *Contains:* list (unit test — draft, slip test — scheduled, term paper —
moderation). *DoD:* statuses.

### Blueprint · `/teacher/blueprint`
Section marks, cognitive targets, topic map.
- *v2→v3:* v2 blueprint/paper-setter re-skinned; adds the colour-coded coverage view.
- *Contains:* form (section + global marks, cognitive targets, chapter selection) with a
  coverage view (completed / untaught / previously-examined, colour-coded); actions Save
  blueprint / Generate paper.
- *Behaviour:* the blueprint drives generation; coverage view prevents over-testing
  untaught topics. *DoD:* section marks + cognitive targets + coverage view; saves.

### Generate paper · `/teacher/paper-generate`
Multi-set, multi-version, verified.
- *v2→v3:* v2 paper generator re-skinned; verified; multi-set.
- *Contains:* sets A/B — verified; actions Regenerate item / Preview / Print-Download /
  Schedule.
- *Behaviour:* generates multi-set/multi-version/multi-difficulty from the blueprint;
  each item editable/regenerable; **verified** before use; supports periodic/formative/
  summative/slip. *Capabilities:* generate-and-verify. *DoD:* multi-set; per-item edit;
  verified; test types.

### Question bank · `/teacher/question-bank`
Item authoring and reuse. *Contains:* table (item · outcome · level); actions Add item /
  Import (QTI). *DoD:* authoring + QTI import.

### Schedule & proctoring · `/teacher/exam-schedule`
Secure delivery. *Contains:* form (date/time, seating, proctoring); actions Schedule /
  Accommodations. *Behaviour:* proctoring is a pluggable adapter; accommodations
  first-class. *DoD:* schedule + seating + proctoring adapter + accommodations.

### Moderation · `/teacher/moderation`
Approve before publish. *Contains:* list (term paper — review; marks — moderate); actions
  Approve / Send back. *Behaviour:* the publish gate; permission-laddered. *DoD:* approve/
  send-back; nothing publishes unmoderated.

---

## Evaluate

### Evaluation queues · `/teacher/evaluate`
Three modes; you are final.
- *Contains:* tabs Post-submission / Scanned / Preventive; table (band · items · action);
  actions Auto-evaluate / Review flagged / Publish.
- *Behaviour:* the three evaluation modes; confidence-banded; publish is permission-gated.
- *DoD:* three modes; banding; human-final publish.

### Evaluate submission (Mode 1) · `/teacher/evaluate-submission`
Score, separate wrong from incomplete from misunderstood.
- *Contains:* scored / flagged; actions Open rubric / Override / Enter by voice.
- *Behaviour:* scores against the rubric; separates wrong/incomplete/misunderstood; **voice
  mark entry** bound to the engine; feeds mastery + gaps; low-confidence flagged.
- *Emits:* `score`, `evidence`. *DoD:* rubric scoring; state separation; voice entry;
  feeds engine.

### Scanned handwriting (Mode 2) · `/teacher/evaluate-scanned`
Read scripts at scale; quality never lowers a mark.
- *Contains:* recognised N of M; uncertain pages → review; actions Review uncertain / Map
  to students.
- *Behaviour:* reads handwritten scripts, recognises each student, maps answers to
  questions, scores by rubric; **uncertain pages route to human review**; poor handwriting/
  scan quality never lowers a mark — flagged "needs human review."
- *Capabilities:* handwriting-understanding (pluggable OCR adapter). *DoD:* per-student
  recognition; answer→question mapping; never penalises quality; uncertain → review.

### Rubric library · `/teacher/rubric-library`
Reusable, editable, curriculum-aligned.
- *Contains:* the 13 rubric types (correctness, process/working, conceptual, competency,
  descriptive, essay/language, diagram, project, practical, oral, coding, originality,
  self-correction); actions Edit rubric / New rubric.
- *Behaviour:* partial credit for sound method; mistakes map to concepts and feed the gap
  engine; teachers own the rubrics. *DoD:* full 13 types; editable; partial credit; feeds
  the engine.

### Confidence review · `/teacher/confidence-review`
High auto, middle review, low must-review.
- *Contains:* High / Middle / Low; actions Review middle / Publish. *Behaviour:* the
  confidence-band workflow gates publication. *DoD:* banded queues; gated publish.

---

## Students & insights

### Students · `/teacher/students`
Class list and the study quadrant.
- *v2→v3:* v2 roster + analytics re-skinned; the quadrant becomes a grouping/intervention
  launcher.
- *Contains:* the study quadrant; actions Open student / Group by gap. *Behaviour:* tap a
  band to group + intervene. *DoD:* quadrant on v4; group-by-gap acts.

### Student detail · `/teacher/student-detail`
Evidence-linked, independence-aware.
- *Contains:* per-topic mastery (plain language); recommended next (application set →
  then Ratios); actions Create remedial / Open report.
- *Behaviour:* every conclusion has an evidence drawer; independence-aware. *DoD:* evidence-
  linked; independence-aware; recommended next action.

### Gradebook · `/teacher/gradebook`
Marks across the term.
- *v2→v3:* v2 gradebook re-skinned to the tight matrix; numbers here are professional-
  facing, with evidence. *Contains:* table (student · unit 1 · unit 2 · trend). *DoD:*
  matrix; trend; evidence on tap.

### Reports · `/teacher/reports`
Consolidated, term, subject. *Contains:* cards Consolidated / Term / Subject / Heatmap;
  actions Open. *DoD:* report types.

### Report detail · `/teacher/report-detail`
The picture and the next action.
- *v2→v3:* v2 holistic report card re-skinned; trajectory actual-solid / predicted-dotted.
- *Contains:* trajectory chart; actions Export / Create remedial. *DoD:* trajectory; export;
  remedial link.

### Remedial · `/teacher/remedial`
A targeted set from a detected gap.
- *Contains:* note (15-min set · 5 problems · verified · 3 tiers); actions Preview &
  assign. *Behaviour:* generated from a detected gap; verified; tiered. *DoD:* gap-driven;
  verified; assign permission-gated.

### Class analysis · `/teacher/analysis`
Common mistakes, distribution, outcomes. *Contains:* common mistake / distribution; actions
  Drill topic / Focus group. *DoD:* common-mistake surfacing; drill + focus-group act.

---

## Relationships

### Parent meetings · `/teacher/ptm`
Prepared, captured, followed up.
- *v2→v3:* v2 MEETMOX/PTM dashboard re-skinned. *Contains:* list (parent — Fri; parent —
  next week). *DoD:* schedule; statuses.

### PTM prep · `/teacher/ptm-prep`
A brief before every meeting.
- *Contains:* academic/attendance/wellbeing brief; suggested discussion points; the
  parent's pre-submitted questions; actions Start meeting (capture).
- *Behaviour:* the brief is generated from real signals; capture (transcription, notes,
  key-point + action extraction) is consent-gated. *DoD:* brief from real signals; consent-
  gated capture.

### PTM follow-up · `/teacher/ptm-followup`
Every meeting → an action plan. *Contains:* table (action · owner · due). *Behaviour:* each
  action gets owner/timeline/follow-up across teacher/parent/student. *DoD:* action plan;
  ownership; follow-up.

### Communicate · `/teacher/messages`
Routed, translated, turned into tasks.
- *v2→v3:* v2 chat re-skinned; adds translate + make-task + safety.
- *Contains:* list (parent · class channel · broadcast); actions New message / Translate /
  Make task. *Behaviour:* messages can become routed, owned, tracked tasks; translation
  per parent's language; safety classifiers + escalation on every channel. *DoD:*
  translate; make-task; safety layer.

---

## Growth & settings

### Growth & coaching · `/teacher/growth`
Private, constructive.
- *v2→v3:* new framing of v2 analytics — now private, support-first.
- *Contains:* table (signal · this week · trend); actions Hand over class. *Behaviour:*
  talk ratio, questioning, wait time, equity — surfaced **to the teacher first**; no
  automated punitive ranking; employment decisions need human review. *DoD:* private
  signals; no ranking; support framing.

### Continuity / handover · `/teacher/continuity`
A substitute picks up at the exact point.
- *Contains:* lesson position / today's plan / group composition / the live gap note;
  actions Hand over. *Behaviour:* transfers lesson position + context to a substitute so
  students lose no continuity. *DoD:* full handover packet; pick-up-at-the-right-point.

### Settings · `/teacher/settings`
Profile, preferences, access.
- *v2→v3:* v2 Personal/Institute Info, Security, Teaching Preferences, Leaves consolidated
  on v4. *Contains:* Profile · Notifications · Teaching preferences (instructional model,
  project mentoring, consultation availability) · Access · Leaves. *DoD:* all sections;
  preferences drive planning.
