# 09 · Surface Spec — Parent (20 surfaces)

Template as in `06`. **Parent cross-cutting:** partnership and pride, never surveillance
or fear; plain language, never raw scores or jargon; every concern pairs with a concrete
"what you can do"; the child switcher re-renders the whole surface; reads are consent-
scoped to that parent's relationship to that child; this is the **absolution engine** —
it tells a parent their child is okay and exactly how to help, reducing anxiety rather
than amplifying it. Subject accents appear only inside a child's subject detail.

---

## Home & companion

### This week · `/parent/`
Your child this week — calm and clear.
- *v2→v3:* v2 opened on a parent dashboard / module grid. v3 deletes it; the conversation-
  first home greets, and this is the calm weekly destination.
- *Contains:* the **child switcher** (top); one reassurance line (plain language: "Aanya
  is on track; one thing to support this week"); the single home action ("10 minutes on
  word problems — here's exactly how"); chips Reports / Attendance / Message teacher.
- *Behaviour:* the absolution engine composes a calm, honest weekly picture + one concrete
  support action; switching child re-renders everything; consent-scoped.
- *Reads:* child's mastery/attendance/coursework (governed, consent-scoped). *Emits:*
  `surface.viewed`. *States:* empty (no child linked → link-a-child flow); offline (cached
  week).
- *DoD:* reassurance + one action; child switcher re-renders; plain language; consent-
  scoped; no raw score.

### Switch child · `/parent/children`
All your children, one tap.
- *Contains:* child cards (name · grade · status). *Behaviour:* sets the active child for
  every surface. *DoD:* multi-child; active-child drives all reads.

### Parent companion · `/parent/companion`
Ask about your child, in your language.
- *v2→v3:* v2 chat re-skinned to the full Vidya companion, parent-shaped + translated.
- *Contains:* conversation + (read-only) canvas of the child's picture; actions New thread
  / Voice / Translate. *Behaviour:* answers about progress/attendance/upcoming, always
  pairing a concern with a "what you can do"; reads are consent-scoped; multilingual.
  *Capabilities:* explain-progress, suggest-support (read/Recommend). *DoD:* parent-shaped;
  consent-scoped; concern→action pairing; translated.

### Notifications · `/parent/notifications`
What changed, what needs you. *Contains:* list (report ready, PTM Friday, fee reminder —
links to Feesable). *Behaviour:* calm, grouped; quiet-hours aware. *DoD:* deep-links;
calm.

---

## Reports

### Reports & reviews · `/parent/reports`
Every report, in plain language. *Contains:* list (term report, periodic test, progress
review). *DoD:* report list; plain-language entry points.

### Progress report · `/parent/progress-report`
Strengths, growth, and how to help.
- *v2→v3:* v2 holistic report card re-skinned; the read recomposes it for a parent.
- *Contains:* strengths / growth areas / how-to-help; actions Download / Discuss with
  teacher. *Behaviour:* the same evidence, recomposed without jargon, each growth area
  paired with a concrete home action. *DoD:* strengths+growth+help; no jargon; concern→
  action.

### Attendance review · `/parent/attendance`
Presence and patterns, gently.
- *v2→v3:* v2 attendance grid re-skinned; framed as support not policing.
- *Contains:* present/absent (plain); actions Request leave / Message. *DoD:* accurate;
  supportive framing.

### Exam review · `/parent/exam-review`
How an exam went, what it means. *Contains:* plain-language result + the one focus area;
  actions Discuss. *DoD:* plain-language; one focus; no bare score.

### Test analysis · `/parent/test-analysis`
Per-test grasp, not a grade. *Contains:* grasp + named gap. *DoD:* grasp over grade.

### Syllabus coverage · `/parent/coverage`
What's been taught. *Contains:* table (subject · coverage). *DoD:* per-subject coverage,
  plain language.

---

## Engagement

### What to do at home · `/parent/at-home`
The single most useful thing this week.
- *v2→v3:* new — turns insight into an at-home action (the absolution engine's core).
- *Contains:* one activity (15 min, no expertise needed) with exactly how; actions Mark
  done / Different idea. *Behaviour:* derived from the child's top gap; achievable by a
  non-expert; pride-oriented. *Reads:* gaps. *DoD:* one concrete action; non-expert-
  friendly; tied to a real gap.

### Learn alongside · `/parent/learn-alongside`
Understand what your child is learning. *Contains:* a parent-level explainer of the
  current topic; actions Show me. *Behaviour:* generated-and-verified at a parent reading
  level; multilingual. *DoD:* verified; parent-level; translated.

### Parent meetings · `/parent/ptm`
Book, prepare, follow up.
- *v2→v3:* v2 PTM booking wizard (select teacher → slot → review → booked) re-skinned.
- *Contains:* upcoming/past; actions Book slot. *Behaviour:* booking is permission-gated;
  reminders. *DoD:* booking flow; reminders.

### PTM prep · `/parent/ptm-prep`
Walk in informed. *Contains:* your child's brief + space to submit questions ahead; actions
  Submit questions. *Behaviour:* questions reach the teacher's PTM prep. *DoD:* brief +
  pre-submit reaches teacher.

### PTM follow-up · `/parent/ptm-followup`
The agreed plan and your part. *Contains:* table (action · owner · due) with the parent's
  items highlighted. *DoD:* shared plan; parent items clear.

### Messages · `/parent/messages`
Talk to teachers, in your language.
- *v2→v3:* v2 chat re-skinned; translate + safety. *Contains:* threads; actions New
  message / Translate. *Behaviour:* two-way, translated per language, on the safety layer.
  *DoD:* translate; safety; routing.

### The shareable win · `/parent/win`
A moment worth being proud of.
- *v2→v3:* new — a WhatsApp-native proof artifact the child can trigger.
- *Contains:* a generated proof-of-progress card (a real achievement, evidence-linked);
  actions Share. *Behaviour:* celebrates genuine progress; child-triggerable; permission-
  scoped; shareable to WhatsApp natively. *Capabilities:* generate proof artifact (verified).
  *DoD:* evidence-linked; child-triggerable; WhatsApp-native share; permission-scoped.

### Events & calendar · `/parent/calendar`
Holidays, exams, meetings. *Contains:* month view. *DoD:* events correct; offline cached.

---

## Ops

### Fees · `/parent/fees`
Feesable citizen — linked, not built here. *Contains:* note "handled by the Feesable
citizen"; a clean handoff. *DoD:* clean link/handoff to Feesable, not a built module.

### Account & settings · `/parent/settings`
Profile, children, language, consent.
- *v2→v3:* v2 My Children / Security re-skinned + consolidated on v4. *Contains:* Profile ·
  My children · Language · Notifications · Consent (visible + revocable) · Account. *DoD:*
  all sections; consent revocable; language drives translation.
