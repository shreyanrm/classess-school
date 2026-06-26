# V2 → V3 Experience Upgrade Map

Cross-references the four **v2 experience maps** (Teacher / Student / Admin / Parent —
the tabs-and-cards "classess-school" app) against the **current v3 routes** under
`surfaces/web/app` (the role pages + the `Rail.tsx` destinations).

For each role: every v2 screen → the v3 route that carries it (existing or **NEW**) →
the data points, visualizations, tabs, drawers, internal pages v3 must carry (upgraded
to the **v3 ultramarine premium brand — `--accent: var(--ultramarine)` `#1F35E0`, NO
coral**; the v3 design system already enforces this — coral does not exist in the
codebase) → the **GAP** (what v3 is missing vs the v2 experience).

## How v3 already differs from v2 (read this first)

v2 is a **tabbed, page-per-feature CRUD app** with raw % everywhere. v3 is a **calm,
evidence-first OS**: one shell (`SurfaceShell`), a slim icon `Rail`, a conversational
Vidya dock on every surface, "manage by exception", the permission ladder (prepare →
human-approve, nothing auto-fires), `EvidenceDrawer` lineage on every conclusion,
`SourceNote` gateway-first honesty, and five designed states. So the upgrade is **not**
"port every v2 screen". It is: **carry the v2 information scent and data, drop the raw
scores, and re-express it in the v3 grammar** (StatCell matrix, SpotlightCard,
Trajectory, ConfidenceBand, ApprovalControl, ConsentGated, subject-accent cards).

Three v2 patterns are **deliberately NOT ported** (and that is correct, not a gap):
- raw % marks shown to students/parents → v3 shows plain-language bands + evidence;
- single-score judgements → v3 requires corroboration (confirmed gaps);
- auto-send / auto-grade → v3 routes everything through the approval ladder.

Everything below flags as a GAP only what v3 should genuinely carry forward.

---

## Rail destinations (current v3, per role)

| Role | v3 Rail items (href → label) |
|---|---|
| **Teacher** | `/teacher` Your day · `/teacher/plan` Class diary and plan · `/classroom` Classroom delivery · `/teacher/attendance` Attendance · `/teacher/assign` Assign a quick check · `/content` Resource library · `/teacher/evaluate` Evaluation review · `/teacher/students` Student insights · `/teacher/insights` Class insights · `/teacher/together` Parent meetings · `/messages` Messages · `/teacher/growth` Your growth · `/loop` The live loop · `/proactive` Approval queue |
| **Student** | `/student` Today · `/student/learn` Learn · `/student/practice` Practice · `/student/work` Your work · `/student/mocks` Mocks and study plan · `/student/timetable` Timetable and attendance · `/student/progress` Your progress · `/student/portfolio` Portfolio and credentials · `/messages` Messages · `/loop` The live loop |
| **Admin** | `/admin` Morning briefing · `/admin/setup` Setup and hierarchy · `/admin/curriculum` Curriculum and ontology · `/content` Resource library · `/admin/calendar` Calendar and timetable · `/admin/operations` Daily operations · `/admin/exams` Exam operations · `/admin/intelligence` School-wide intelligence · `/admin/network` Network leadership · `/admin/integrations` Integrations · `/messages` Messages · `/admin/control-centre` AI control centre · `/admin/governance` Governance and audit · `/proactive` Approval queue · `/loop` The live loop |
| **Parent** | `/parent` This week · `/parent/child` The child view · `/parent/reports` Reports and feedback · `/parent/together` Learn alongside and PTM · `/messages` Messages · `/loop` The live loop |

Shared across roles: `/` (Vidya home / new conversation), `/welcome` + `/welcome/personalise` (onboarding), `/settings`, `/profile`, `/messages`, `/loop`.

---

# TEACHER

| v2 screen | v3 route (existing / NEW) | Data points + viz + tabs + drawers + internal pages v3 must carry (ultramarine, no coral) | GAP vs v2 |
|---|---|---|---|
| Welcome / Splash | `/welcome` + `/` (Vidya home) | School name, "powered by Classess", time-based greeting, voice prompt, quick shortcuts. v3 already upgrades this to onboarding + Vidya orb. | Splash/loading branding moment is thinner than v2's hero. Low priority — v3's onboarding is richer. |
| My Workspace Hub | `Rail.tsx` (slim icon rail) | v3 replaces the 12-card hub grid with the always-present rail. All 12 destinations exist as rail items. | None structurally. v2's labelled card-grid "hub" landing is gone by design; some users may want a hub overview — minor. |
| Dashboard — Analytics | `/teacher` Your day + `/teacher/insights` Class insights | Class-mastery %, working-independently %, confirmed gaps, revision-due (StatCell matrix); subject-accent mastery cards; today's timetable; Vidya-flagged panel; per-student table → EvidenceDrawer. | v2's **STUDY Quadrant 2×2 matrix** (Star Performers / Emerging / Potential / At Risk), **Comparison-by-Section bar chart**, and **Target Analytics gauge** are NOT in v3. Quadrant + section-comparison are real teacher value → **GAP**. |
| Student Performance Modal | `/teacher/students/[ref]` (full page, not modal) | Per-student standing, 4-up matrix, per-topic six-dimension `DimensionBars`, gap chips, independence `Trajectory`, EvidenceDrawer lineage. | v2's **bubble chart (performance % vs prep-time, four quadrants)** is not in v3. v3's six-dimension read is deeper, but the prep-time-vs-performance bubble view is a distinct lens → minor GAP. |
| Class Diary | `/teacher/plan` (Class diary and plan) | Date, class schedule list w/ times, topic, status, room, chapter, lesson-notes link. v3 carries plan across annual/unit/weekly/daily horizons + planned-vs-delivered. | v3 plan is curriculum/horizon-led; the **day-by-day diary timeline with per-class COMPLETED badges + room + lesson-notes entry point** is thinner. Diary "today's classes with status" view → GAP. |
| Lesson Notes Editor Modal | within `/teacher/plan` (NEW sub-surface) | Notes textarea, voice input, "Format with AI", placeholders (topics/key points/concepts/questions/homework), char counter. | **No lesson-notes capture+AI-format surface exists in v3.** Voice→formatted notes is a signature v2 teacher feature → **GAP (build)**. |
| Course Flow (terms › periodics › chapters) | `/teacher/plan` + `/admin/curriculum` | Hierarchical term→periodic→chapter list, periods-per-chapter, per-chapter Lesson Plan button. v3 has the ontology graph (curriculum) + outcomes in plan. | The **teacher-facing hierarchical course-flow browser** (term/periodic/chapter with period counts and per-chapter lesson-plan launch) is not assembled on the teacher side → GAP. |
| Course Flow — Expanded Chapter | `/teacher/plan` (NEW lesson breakdown) | Per-period lessons, resource badges (Mind Maps, Presentations, Session Plans, Quizzes, Worksheets, My Resources, Class Reflection), COMPLETED/Assigned status, timeline connectors. | v3 generates lesson/session plans + worksheets but has **no per-chapter lesson-resource timeline** tying all artifact types together → GAP. |
| Lesson Plan Modal | `/teacher/plan` (lesson-plan generator, exists) | Chapter summary, key-concept tags, sessions dropdown, topics+count, progress bar (3/3 sessions), Custom Instructions + Your Skills tabs. v3: `useGenerator('lesson-plan')` → ConfidenceBand → ApprovalControl. | v3 has the generator + approval; missing v2's **session-progress bar, Custom Instructions tab, Your Skills tab**. Partial GAP. |
| Session / Lesson Detail Modal | `/teacher/plan` (session-plan generator, exists) | Topics covered, focus, learning objectives, materials, opening activity w/ time estimates. v3: session-plan artifact has timed segments + EvidenceDrawer. | Mostly covered. Missing explicit **learning-objectives + opening-activity** structured fields. Minor. |
| Quiz / Assessment Modal | `/teacher/assign` + `/content` | Question list, MCQ/TF type, A–D options, correct-answer highlight, view/hide answer key, per-period tabs. v3: worksheet generator items each with ConfidenceBand. | v3 prepares items but has **no answer-key toggle / per-question correct-answer review** in the assign flow → GAP. |
| Worksheet / Learning Material Modal | `/content` + `/teacher/assign` | Title, grade/class, instructions, MCQ section, T/F section, numbering. v3: verified worksheet artifact. | Covered structurally; missing the **formatted worksheet document preview** (instructions + sectioned questions as a printable). Minor GAP. |
| My Resources | `/content` Resource library | Resource gallery cards, type badge (PDF/Link/Video), Add Resource, thumbnails, count, verify state. v3: by-subject coverage, browse, generate-and-verify, ApprovalControl. | v3 is stronger (verification). Missing v2's **personal "My Resources" scoped library + thumbnails** as a distinct view. Minor. |
| Add New Resource Drawer | `/content` (add flow) | Type (Link/File), name, URL, Save, Clear. | v3 has generate + approve; an **explicit "add my own link/file" drawer** is thinner → minor GAP. |
| Assignments (by chapter) | `/teacher/assign` + `/teacher/evaluate` | Grade/section/subject filter, Assignments/Projects tabs, chapter grouping, homework/quiz tabs, published/title/submissions/due columns, status badges, Assign Homework. | v3 assign is topic-pick → prepare → approve. **No chapter-grouped assignment list with submissions %, due dates, published history** → GAP. **No Projects tab** → GAP. |
| Assignment Creation Form | `/teacher/assign` (exists) | Title, topics dropdown (curriculum), mode (offline/online), publish-now/later, due-date picker. v3: subject→topics→count→prepare→ApprovalControl. | v3 covers topics+approval. Missing **mode toggle, publish-later scheduling, explicit due-date picker** → GAP. |
| Assignment Detail — Homework | `/teacher/evaluate` | Topic tags, published/due dates, submissions count+%, student submission avatars colour-coded by status, submitted IDs. | v3 evaluate is per-response-of-one-submission. **No assignment-level submission tracker (who submitted, avatar grid, % submitted)** → GAP. |
| Assignment Detail — Question View | `/teacher/evaluate` (per-response rows, exists) | Question text, A–D options, student response, correct/incorrect badge, selected-vs-correct, feedback. v3: per-response state (correct/incomplete/misunderstood) + ConfidenceBand + EvidenceDrawer + human-final approval. | v3 is **stronger** (confidence + lineage + human-final). Covered. |
| Assignments — Projects tab | `/teacher/evaluate` (NEW) | Published date, project title, status %, submission date, EVALUATION link, submitted/not-submitted avatars, **rubric criteria matrix w/ rating levels**. | **No project / rubric-evaluation surface in v3** → **GAP (build)**. The six-dimension project rubric is explicitly noted missing in COVERAGE d9. |
| Project Detail — Rubric & Description | `/teacher/evaluate` (NEW) | Student/teacher-assigned radios, description, rubric criteria rows × Level 1–4 columns, Results status. | Same as above → **GAP (build)**. |
| Assessments hub | `/admin/exams` + `/teacher/evaluate` | Test Papers / Paper Analysis / Remedial Classes cards; overall stacked bar (Below/On/Above target); period breakdowns; above/on/below-target student counts. | v3 `/admin/exams` is admin-side ops. **No teacher-facing assessments hub with paper-analysis + remedial grouping + target-band distribution** → GAP. |
| Test Papers Detail | `/admin/exams` (papers stage, partial) | Question paper title, period, syllabus link, total marks, section-wise distribution (MCQ / Assertion-Reasoning / Long Answer) w/ counts+marks, Generate Paper, Preview, Answer Key, Test/Exam tabs. | v3 exams has stages + seating; **section-wise mark distribution, per-section question-type config, generate/preview/answer-key** noted missing (COVERAGE d10) → GAP. |
| Question Paper Preview | `/admin/exams` (NEW) | Section headings, questions w/ diagrams, point values, A–D, short answer, Answer Key tab, model answers. | No paper preview/answer-key render in v3 → GAP. |
| Assessments — Paper Analysis | `/teacher/insights` partial / NEW | Overall diff bar, Below/On/Above %, period grouping, per-assessment metrics, ABOVE/ON/BELOW TARGET badges, per-student attendance+avg-progress+status, Remedial Classes button + Remedial Groups modal. | **Remedial grouping + target-band analysis is a signature v2 feature, absent in v3** → **GAP (build)**. |
| Timetable & Calendar | `/teacher/plan` partial / NEW | Month/week calendar, week selector, Timetable/Academic-Calendar/Calendar tabs, class blocks per day/time, **My Stats** (classes this week/month/year, substitutions, leave). | v3 has a 3-line "Today" timetable only. **No full week/month calendar grid + teaching-stats counters** → GAP. |
| Attendance Marking (heatmap) | `/teacher/attendance` (exists, different model) | v3: multi-method capture (photo-scan / voice / roster / absent-only) → propose → human-confirm; calm consecutive/chronic risk flags; offline-capable. | v3 capture is **stronger**. Missing v2's **monthly attendance heatmap (student × date grid, P/A/Holiday/Leave colours, per-student %)** and **Leave Management** → GAP. |
| Students (roster) | `/teacher/students` (exists) | Grade/section/subject filter, roster table, per-student link, standing tags, mastery/independent %, EvidenceDrawer, "needs you now" aside. | v3 is **stronger**. Covered. |
| Grades & Reports — Markbook | `/teacher/insights` partial / NEW | Setup/View toggle, **markbook spreadsheet** (ROLL/STUDENTS rows × period/term columns, colour-coded grade cells, remarks), Reports-by-Subject + Report-by-Exam cards. | **No markbook spreadsheet grade-entry grid in v3** → GAP (v3 derives mastery from evidence, but teachers still expect a markbook). |
| Grades & Reports — Reports by Subject | `/teacher/insights` (partial) | Overall diff bar, Below/On/Above %, period sections, above/on/below-target student avatars+counts. | v3 has subject mastery cards + per-topic table; missing **target-band student grouping with avatars** → GAP. |
| Student Holistic Progress Card | `/teacher/students/[ref]` partial / NEW report | Executive summary, competency pie (Emerging/Proficient), performance trend, **Foundational Literacy & Numeracy bars (Reading/Writing/Numeracy/Reasoning)**, teacher observations, intervention strategies, attendance analytics (overall %, present/absent/late, monthly chart), **Print/PDF export**. | **No holistic progress-card report / PDF export in v3** → **GAP (build)** — explicitly a v2 signature, and COVERAGE d14 notes it missing. |
| Chat | `/messages` (exists) | Communication hub, threads, child-safety, conversation→task, approval gate, translation. v3 is **stronger**. | Covered. |
| PTM Dashboard | NEW (teacher side) | Date, time slots w/ availability, query-details & preparation, meeting summary, query list. v3 has parent-side PTM in `/parent/together` only. | **No teacher-side PTM management surface** (slot availability, parent queries, meeting summaries) → **GAP (build)**. |
| Help | `/settings` / NEW Help | Assistance + FAQs. v3 relies on Vidya dock. | No dedicated Help/FAQ surface → minor GAP (Vidya partly covers). |
| Notifications Panel | `/proactive` + global bell | Notifications list, View All, empty state. v3 has approval queue + proactive. | A dedicated **notifications drawer** (vs approval queue) is thinner → minor GAP. |
| Settings — Personal / Institute / Security / Preferences / Leave / Theme | `/settings` + `/profile` (exists) | Profile, institute info, security, **Teaching Preferences (homework/structured/oral/worksheet/test-paper/lesson-plan/substitution styles, project persona)**, Leave Management, Theme (light/dark + 15 palettes). v3: language, Vidya behaviour, consent, account, delete. | **Teaching-preference / instructional-style customization** missing (COVERAGE d6) → GAP. **Leave Management** missing → GAP. Theme-palette picker thinner. |

---

# STUDENT

| v2 screen | v3 route (existing / NEW) | Data points + viz + tabs + drawers + internal pages v3 must carry | GAP vs v2 |
|---|---|---|---|
| Welcome / Onboarding | `/welcome` + `/welcome/personalise` + `/` | Institution, time-based greeting, motivational prompt, quick actions. v3 onboarding is personalised + implicitly profiling + consent/age-gated. | Covered (v3 stronger). |
| Dashboard | `/student` Today | Next-step hero, on-your-own / in-motion / evidence / focuses matrix, subject cards, today's plan, focus panel. v3 shows **plain language, no marks ever**. | v2's **overall-performance donut (70%), per-subject % bars, last-exam scores, achievement badges (Quick Learner, Streak Master…)** are NOT in v3. Removing raw % is intentional; **achievement badges/gamification is a real motivation feature → GAP** (also COVERAGE d14 "badges"). |
| Course Overview | `/student/topic/[id]` + `/student/learn` | Learning objectives, learn-time, exercises-done, topic progress, Overview/Plans/Feedback tabs. v3: topic detail w/ six-dimension read + prerequisites + focuses. | v3 stronger on evidence; missing **learning-objectives + learn-time-estimate + Plans/Feedback tabs**. Minor. |
| Class Course Structure | `/student/learn` + `/student/progress` | Subject dropdown, term/periodic sections, chapter numbers+names, topic counts, sub-lesson types (Teacher-Shared-Material / Learn / Practice), expandable hierarchy. | **No hierarchical course-content browser for students** (chapters → topics → material/learn/practice) → GAP. |
| Planner / Timetable | NEW (student) | Week selector, day×time grid, colour-coded subjects, free slots, current-week indicator. | **No student timetable/planner grid** in v3 → GAP. |
| Class Planner Detail | NEW (student) | Date range, per-day topics, chapter/topic labels, revision indicators, DIFFICULT tags, tip callouts, Learn buttons. | Same → GAP (covered partly by `/student/mocks` revision plan, but no day-by-day planner). |
| Learn — Flashcard Session | `/student/learn` (different model) | Flashcard flip, card counter (1/5), audio pronunciation, track-progress. v3: predict→struggle→reveal "taught by trying first" + help-rung ladder. | v3's pose/struggle/reveal is pedagogically **stronger** but **flashcards as a format are missing** (COVERAGE d12 "varied formats") → GAP. |
| Learn — Practice Exercises | `/student/practice` (exists) | Fill-blank / matching, drag-drop word pills, timer, attempts, question counter, reset/check/submit. v3: adaptive items, unaided-count, a miss repeats the idea. | v3 covers adaptive practice. Missing **varied interaction formats (drag-drop fill-blank, matching, timer)** (COVERAGE d12) → GAP. |
| Assessment Selection — Space Quest | NEW (student games) | Assessment-type cards (Self Test, Flashcard, Smart Blank, Concept Matching, Cognitive Match, Mind Blocks, Space Quest, Add/Remove), descriptions, customize. | **No gamified assessment-type hub** in v3 → GAP. The four named interactions (predict-then-check etc., COVERAGE d12) partly overlap. |
| Quiz Preparation Modal | `/student/practice` / `/student/mocks` | 4-step generation progress (Checking/Generating/Options/Verifying). v3: generate-and-verify exists under the hood. | A visible **prep-progress modal** is missing → minor GAP. |
| Quiz — Multiple Choice | `/student/practice` (exists) | Question counter, mark value, A–D, prev/next, reset/check/submit, attempt counter. | Covered (v3 adaptive practice). Minor: explicit MCQ-with-marks format. |
| Test Session Results Modal | `/student/practice` / `/student/mocks` (partial) | Score % + status, **Bloom's breakdown (Remembering/Understanding/Applying/Analyzing)**, per-question correct/incorrect circles, chapters included. | v3 avoids raw % to students by design, but **Bloom's-level breakdown + per-question review** is valuable → GAP. |
| Cosmic Challenge Game | NEW | Space background, planets, concept bubbles, score, difficulty. | No game surface → GAP (gamification). |
| Assignments | `/student/work` Your work (exists) | Subject filter, PENDING/SUBMITTED/DRAFT badges, quiz/homework/project types, due dates, time-remaining, Upcoming/Past tabs, completion %. v3: inbox, "submitting is your choice", project milestones + team contributions. | v3 covers inbox + projects. Missing **Upcoming/Past tabs + subject filter + draft state**. Minor GAP. |
| Mock Test Generator | `/student/mocks` (exists) | Assessment selection (periods/terms), chapters-included counter, instructions, Generate, previously-generated list. | Covered (blueprint-aligned mocks). |
| Mock Test Taking | `/student/mocks` (partial) | Full test layout, total marks, duration, Section A MCQ / Section B short-answer, timer, marks-per-question. | v3 lists mocks but **no full mock-taking session UI (sectioned paper + timer)** → GAP. |
| Insights — Comprehensive | `/student/progress` (exists, different) | Subject tabs, progressive tracking, subject stats, performance trends line, **assignment activity heatmap**, **AI success-probability (90%)**, **Bloom's pie**. v3: mastery by subject, every-topic table, evidence drawers. | v3 strong on evidence; missing **performance-trend lines, activity heatmap, success-probability, Bloom's** → GAP. |
| Insights — Bloom's Taxonomy | `/student/progress` (NEW) | Donut: Comprehension/Interpretation/Analysis/Creative/Evaluate %. | **No Bloom's taxonomy view** → GAP. |
| Insights — Performance Trajectories | `/student/progress` (partial) | Line chart current-vs-predicted across exams, predicted final. v3 has `Trajectory` (teacher side) but not student-facing. | **Student-facing trajectory** not wired (component exists) → GAP (low effort). |
| Insights — Report Cards | `/parent/reports` analogue / NEW student | Report-card doc: student info, **Academic Performance table (subject / marks / total / grade / score points)**, school header. | v3 avoids raw report cards for students by design. A **formal report card** may still be expected → GAP (consider plain-language version). |
| Kaho Chat — Messaging | `/messages` (exists) | All/Direct/Groups/Broadcasts tabs, conversation list, online status, unread badges, two-pane. v3: role-aware channels + safety + presence. | v3 stronger. Covered. Missing **peer-to-peer student chat** specifically (v3 student channels are teacher/class only) → minor GAP. |
| Notification Center | global / `/proactive` | Notifications (live-lesson / assignment / project), clear-all, time-ago. | Thin dedicated notifications surface → minor GAP. |
| Attendance Tracker | NEW (student) | Overall % (92.12%), full-year month×day heatmap, P/A/H/L/Holiday colours, monthly stats. | **No student attendance view** → GAP. |
| Settings — Personal / Parent Info / Leave / Theme | `/settings` + `/profile` (exists) | Profile, parent info, leave application, theme + accessibility (larger fonts). v3: language, consent, account, delete. | Missing **leave application + visual-accessibility mode**. Minor GAP. |
| — (new in v3) | `/student/portfolio` | Mastered-topics timeline w/ evidence, portable record download, verifiable credentials. | v3-only upgrade (no v2 equivalent). |

---

# ADMIN

| v2 screen | v3 route (existing / NEW) | Data points + viz + tabs + drawers + internal pages v3 must carry | GAP vs v2 |
|---|---|---|---|
| Splash / Welcome | `/welcome` + `/` | School name, branding, greeting, mascot. | Mascot/animation thinner; fine. |
| Principal Dashboard | `/admin` Morning briefing + `/admin/intelligence` | Total students, attendance %, academic performance %, at-risk %, academic year, date; **School Performance Snapshot / Learning-&-Outcome-Analytics tabs**; academic-trend line; grade-wise attendance bar. v3: manage-by-exception briefing + concerns + recs + Trajectory. | v3 reframes to exception-driven. Missing **KPI snapshot tab + academic-trend line + grade-wise attendance bar** as a clean executive dashboard → GAP. |
| My Workspace — Daily Ops / School Mgmt / Settings & Oversight | `Rail.tsx` | v3 rail carries all destinations. The three grouped card-grids are gone by design. | Minor: no grouped workspace landing. |
| Staff Attendance | NEW (admin) | % present / absent / on-leave / late / cover-duty, department names, staff table w/ reason+cover, Staff/Student tabs. | **No staff attendance surface** in v3 (COVERAGE d8 lists staff attendance gaps) → GAP. |
| Student Attendance Register | `/teacher/attendance` analogue / NEW admin | Classroom selector, student×date matrix, P/A/Leave/Late colours, monthly grid. | **No admin/school-wide attendance register matrix** → GAP. |
| Leave Management | NEW (admin) | Pending/approved/rejected/flagged counts, request list, **detail drawer (leave details + student info + approve/reject)**, requested-by. | **No leave-approval workflow** in v3 → **GAP (build)**. |
| Discipline Log | NEW (admin) | Flagged / needs-attention / repeated / resolved counts, grade/section filter, empty state. | **No discipline log** → GAP. (Note: v3 treats behaviour calmly — design with care, non-punitive.) |
| Assignments (admin tracking) | `/admin/intelligence` partial / NEW | Grade tabs, Homework/Project/Quiz, completion rate, submissions, avg score, per-student progress bars. | **No admin assignment-tracking view** → GAP. |
| Calendar Dashboard | `/admin/calendar` (exists, different) | Academic year, exam-cycle status, critical alerts, monthly grid w/ colour-coded events (PTM/Homework), internal: Holidays / Timetable / Exam Schedule / PTM / Academic Planner. v3: cover-an-open-slot substitution scoring + approval. | v3 calendar is substitution-cover only. Missing **full academic calendar + event types + monthly grid** → GAP. |
| Events & Holidays Config | `/admin/setup` / `/admin/calendar` (NEW) | Holiday setup status, config instructions. | No holiday/event config → GAP (COVERAGE d1 "holidays/working-days"). |
| PTM Event Creation Wizard (5 steps) | `/parent/together` (parent side) / NEW admin | Meeting-type (group/individual slots), date/time picker, duration, multi-step progress 1–5. | **No admin PTM-creation wizard** → GAP. |
| Academic Planner | `/admin/curriculum` + `/admin/calendar` (NEW) | Grade/subject sidebar, year×month Gantt, colour-coded subject blocks, subject legend. | **No Gantt-style multi-subject academic planner** → GAP (COVERAGE d4 pacing/timetable). |
| Student Performance Indicators | `/admin/intelligence` + `/admin/section/[ref]` (exists) | Grade/section, total students, exam-score/attendance/assignment %, Below-Pass, subject heatmap, per-student table. v3: section detail + intelligence rollups + Trajectory. | Mostly covered. Missing **subject-performance heatmap grid + below-pass flags** styling. Minor GAP. |
| School Settings — Institute Config | `/admin/setup` (exists) | Board (CBSE), institute name, registration #, batch, weekend day, logo, **Institute/Structure/Teachers/Students tabs**. v3: blueprint wizard persists to store. | v3 stronger (persists). Missing **registration #, weekend-day, logo upload** fields → minor GAP. |
| School Settings — Students Config | `/admin/setup` (exists) | Excel upload guidance, class divisions, Add Student, Invite Parent, bulk import. | Missing **bulk Excel upload + invite-parent** → GAP. |
| User Management — Roles | `/admin/governance` (exists) | Super Admin / Principal / Academics Coordinator / HOD / Subject roles, descriptions, feature permissions. v3: policy/permissions table + allowed-roles. | v3 covers permissions. Missing the **full role catalogue (coordinator/HOD/examination/support/IT)** (COVERAGE access) → GAP. |
| Student Management | `/admin/network` + `/admin/section/[ref]` | Classroom selector, student list w/ avatars+roll+parent-email, **Organization Network pairing-code modal**. | Missing **pairing-code / org-network join modal** → GAP. |
| Teacher Substitution | `/admin/calendar` (exists) | Weekly calendar, grade/section/subject, no-substitute status, **live broadcast assignment**, auto/manual pick. v3: scored alternatives + approval. | v3 covers scored cover + approval. Missing **live-broadcast substitution + L4–L6 ladder** (COVERAGE d4) → GAP. |
| Attendance Access Control (geofencing) | `/admin/governance` / NEW | Time windows, geofencing lat/long + radius, Manual/Auto/Staff tabs. | **No geofencing/time-window config** (COVERAGE d8) → GAP. |
| Notifications Panel | `/proactive` + global | Leave-request notifications, actor, timestamp, activity feed. | Thin dedicated notifications drawer → minor GAP. |
| User Profile — Personal / Security | `/profile` + `/settings` (exists) | Name, role, institution, contact, change-password. | Covered. |
| Academic AI Blueprint — Overview | `/admin/control-centre` (exists) | Blueprint status, % enabled, Institutional-Identity / People / Operations / AI-Control tabs, feature list. v3: AI control centre w/ agents + autonomy + ApprovalControl. | v3 stronger (live-ish control). Missing **the structured blueprint feature-config tabs**. Partial. |
| AI Blueprint — Academic Calendar & Execution | `/admin/control-centre` / `/admin/setup` | Predictive holiday mgmt, exam-cadence config, academic-year config, how-it-works. | Config depth missing → GAP. |
| AI Blueprint — AI Behavior Control | `/admin/control-centre` (exists) | Suggested-only / never-auto-send-to-parents / log-every-action / max-privacy / conservative-default toggles. | v3 has autonomy + audit. Mostly covered; surface the **explicit behaviour toggles** → minor GAP. |
| Documents & Knowledge Base | `/content` / `/admin/setup` (NEW) | Upload docs (PDF/DOC/TXT) for AI reference, uploaded list. | **No institutional knowledge-base upload** → GAP. |
| — (new in v3) | `/admin/network` Network leadership · `/admin/integrations` Integrations · `/admin/exams` Exam ops · `/admin/governance` audit | Cross-campus rollups (opaque ids), FLUID connectors, exam seating/stages, immutable policy versions. | v3-only upgrades (no v2 equivalent). |

---

# PARENT

| v2 screen | v3 route (existing / NEW) | Data points + viz + tabs + drawers + internal pages v3 must carry | GAP vs v2 |
|---|---|---|---|
| Welcome / Switch Child | `/parent` + child switcher | Child name, class/section, avatar, switch-child. v3: ConsentGated, multi-child store. | Covered. Confirm **multi-child switcher** is surfaced in the rail/header. |
| Parent Dashboard (hub) | `Rail.tsx` + `/parent` | 12 module icon-grid → v3 rail (This week / Child / Reports / Together / Messages / Loop). | Card-grid hub gone by design. |
| Progress Board | `/parent` This week + `/parent/child` | Overall improvement gauge, attendance gauge, today's classes (time/subject/teacher), syllabus-completion bars, last-exam table. v3: plain-language weekly counts + briefing, consent-gated. | v3 avoids raw % (correct). Missing **today's-classes schedule + syllabus-completion bars + last-exam summary** in plain language → GAP. |
| Attendance | `/parent/child` partial / NEW | Overall % (93.38%), present/absent/half-day/leave/holiday badges, **month×day heatmap grid**, monthly breakdown, Overall/Present/Absent/Half-day/Leave/Holiday tabs. | **No parent attendance heatmap** → GAP. |
| Assignments | `/parent/child` / `/parent/reports` partial | Subject filter, upcoming + past table (topic/pub-date/sub-date/status/score/questions), Homework/Project/Quiz tabs, status colours. | **No parent assignment tracker** (what's due, submitted, scored) → GAP. |
| Assignment Detail — Periodic Test | `/parent/reports` (ReportCard, partial) | Test name, result % (Below Target), **Bloom's analysis (Remembering/Understanding/Applying/Analysis)**, MCQ answers, feedback sections (Analysis/Insights/Areas-for-Improvement/Recommendations), modal. | v3 reports show plain feedback; missing **Bloom's breakdown + per-question + structured feedback sections** → GAP. |
| Assessments | `/parent/reports` partial / NEW | Upcoming test + chapters, completed-tasks table (date / mode DIGITAL-WRITTEN / marks / analysis). | **No parent assessments overview** → GAP. |
| Report Cards | `/parent/reports` (exists, plain-language) | Term/period sidebar, **formal report-card doc (school header, student info, Academic-Performance table: subject/marks/total/max/grade/grade-points)**, Exam-Reports / Subject-wise / Holistic tabs. v3: shared reports w/ plain feedback + celebrations + next-steps, email export. | v3 is plain-language by design. Missing **formal report-card document + subject-grade table + tab structure** → GAP (decide: keep plain or offer formal export). |
| Subject Progress — Subject-wise | `/parent/child` partial / NEW | Subject selector, per-period assessment rows (test/grade/marks/%/GPA/report), expandable. | **No parent subject-wise progress breakdown** → GAP. |
| Holistic Progress Card | `/parent/reports` (NEW) / `/parent/child` | Executive summary + photo, **competency donut (Exemplary/Proficient/Beginning)**, performance-trend, GPA/attendance/competencies/growth, key insights (strengths + focus), **Bloom's competency pie**, performance trajectory. | **No holistic progress card for parents** → **GAP (build)** — signature v2 parent feature (COVERAGE d14, d16). |
| Insights | `/parent/child` (exists, plainer) | Subject tabs, progressive tracking, subject stats, performance trends, **AI predictive analysis (predicted grade + success probability)**, **Bloom's**, chapter-wise, grade progression. v3: plain-language strengths/focus + consent-gated. | Missing **predictive analysis, Bloom's, chapter-wise, performance-trend charts** for parents → GAP. |
| Timetable | NEW (parent) | Week range, day×period grid, subject + teacher per period, Timetable/Calendar toggle. | **No parent timetable view** → GAP. |
| Calendar — Event View | NEW (parent) | Month grid, event badges (homework/exams/projects/holidays), filters, upcoming-exams sidebar. | **No parent calendar** → GAP. |
| Chat | `/messages` (exists) | All/Direct/Groups/Broadcasts, recipient list, thread, timestamps, read/unread. v3: role-aware + safety + consent-gated counsellor DM + translation. | v3 stronger. Covered. |
| Meetings / PTM | `/parent/together` (exists) | Upcoming/past meetings tables, mode/type/date/slot/teacher/summary, **Book Slot**. v3: PTM card w/ booking request + ICS add, never auto-booked. | v3 covers booking + ICS. Missing **upcoming/past meetings tables + meeting-summary history** → GAP. |
| PTM Booking — Teacher Selection | `/parent/together` (exists) | Event title, date, duration, available teachers + availability, query details. v3: booking request. | Missing **explicit teacher-selection step + availability slots** → partial GAP. |
| PTM Booking — Time Selection | `/parent/together` (partial) | Time-slot selector, meeting mode/type, date confirm. | Time-slot picker thinner → minor GAP. |
| PTM Booking — Confirmation | `/parent/together` (exists) | Success message, booking details, reference token. | Covered. |
| Notifications | global / NEW | Notification list (assessment scheduled etc.), timestamps, unread badge. | Thin dedicated notifications surface → minor GAP. |
| Settings — Personal / My Children / Security / Theme | `/settings` + `/profile` (exists) | Parent name/email/phone/ID, **My Children (per-child details)**, security (password + PIN + logout), theme. v3: language, consent, account, delete. | Missing **My Children management + security PIN + theme** → minor GAP. |
| — (new in v3) | `/parent/together` learn-alongside activities | At-home activities, minutes-together, why-it-helps, delivered in parent's language. | v3-only upgrade. |

---

# Prioritized backlog — highest-impact gaps to close

Ranked by how much each makes v3 a genuine upgrade of v2 (value × number of roles served).
Brand note: every item ships in the **ultramarine premium brand** (`--accent: var(--ultramarine)`,
subject-accent cards from the `SubjectAccent` palette, no coral) using the existing v3
grammar (SurfaceShell, StatCell matrix, SpotlightCard, ConfidenceBand, EvidenceDrawer,
ApprovalControl, Trajectory, ConsentGated).

### P0 — signature features missing across multiple roles
1. **Holistic Progress Card report + PDF/print export** (Teacher build → shared to Parent; Student-facing plain version). v2 signature for both Teacher and Parent; COVERAGE d14/d16. Carry: competency distribution, foundational literacy/numeracy bars, performance trend, attendance analytics, teacher observations + intervention strategies, key strengths/focus. Re-express bands as plain language for student/parent; keep six-dimension reasoning teacher-only.
2. **Attendance heatmap (month × day grid)** — shared component for Teacher (class), Student (own), Parent (child), Admin (register). Highest cross-role reuse. P/A/Half-day/Leave/Holiday colour key + per-row %. v3 capture is strong but the historical heatmap read is entirely missing.
3. **Project + rubric evaluation** (Teacher `/teacher/evaluate` Projects tab). The six-dimension project rubric (criteria × Level 1–4), submission tracking (who submitted, avatars, %), Results/Evaluation flow. COVERAGE d9. Add the matching **Assignments list with submissions %, due dates, Homework/Quiz/Project tabs**.

### P1 — analytics depth users expect
4. **Assessment / Paper Analysis + Remedial grouping** (Teacher). Target-band distribution (Below/On/Above), per-period breakdowns, above/on/below-target student groups, Remedial Groups modal. Pairs with Test Papers (section-wise mark distribution, generate/preview/answer-key) and a teacher **Assessments hub**. COVERAGE d10.
5. **Bloom's taxonomy + performance-trend analytics** — Student `/student/progress`, Parent `/parent/child`, and quiz/test results. Donut + trend line + (parent) AI success-probability. Wire the existing student-facing `Trajectory`. Re-express honestly (direction not a grade for students).
6. **Full calendar + timetable** — Admin academic calendar (monthly grid + event types + Gantt academic planner), Teacher timetable+stats, Student + Parent timetable/calendar. One calendar engine, four role views. COVERAGE d4.

### P2 — operational workflows + teacher tooling
7. **Lesson-notes capture with voice → AI-format** (Teacher, in `/teacher/plan`). Textarea + voice input + "Format with AI" + structured placeholders. A beloved v2 daily-driver, and a clean Vidya-generative-UI showcase.
8. **Admin operational workflows**: Leave-approval (counts + detail drawer + approve/reject), Staff attendance, geofencing/time-window config, Discipline log (non-punitive), bulk-import + invite-parent. COVERAGE d8/d1.
9. **Markbook grade-entry grid + Reports-by-Subject target-band grouping** (Teacher). Spreadsheet markbook (students × periods, colour-coded cells, remarks) with Setup/View toggle — teachers still expect a markbook even though v3 derives mastery from evidence.

### P3 — engagement, completeness, polish
10. **Student engagement formats + (optional) gamification**: varied interaction formats (flashcards, drag-drop fill-blank, matching, the four named interactions — predict-then-check / assemble-the-proof / fill-the-missing-step / teach-it-back), a course-content browser, achievement badges, and a full mock-taking session UI (sectioned paper + timer). COVERAGE d12.
11. **Teacher-side PTM management** (slots, parent queries, meeting summaries) + Parent upcoming/past meeting tables + teacher-selection/availability booking step.
12. **Teaching preferences / instructional-style settings** (Teacher) + Leave management (Teacher/Student) + theme-palette + visual-accessibility mode; dedicated Notifications drawer and a Help/FAQ surface across roles.

> Brand status: **No coral exists anywhere in the v3 codebase** — the design system already
> defines `--accent: var(--ultramarine)` (`#1F35E0`) as the signature, reserved for brand
> mark + mastery ignite, with subjects drawn from the non-ultramarine accent palette. Every
> gap above should be built directly in that brand; no recolouring/decoral pass is needed.
