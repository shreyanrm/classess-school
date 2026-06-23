/* ============================================================================
   lib/vidyaServer.ts — the ONE Vidya server core, shared by the text route
   (app/api/vidya/chat) and the voice route (app/api/voice/converse).

   SERVER-ONLY. This module reads CLSS_AIFABRIC_DEV_GEMINI_API_KEY from
   process.env and NEVER returns it, logs it, or exposes it as a NEXT_PUBLIC
   var. It is imported only by server route handlers (runtime = 'nodejs').

   It holds the single source of truth for:
     - SYSTEM        : Vidya's persona (calm, plain language, explainable).
     - TOOLS         : the function declarations the model may request.
     - runTool       : tool execution against the REAL engine (lib/engine.ts)
                       over the seed events (lib/loopData.ts) + mock layer.
     - runVidyaTurn  : the tool-use loop — model reasons, requests a tool, the
                       server executes it, feeds the structured result back, the
                       model answers. Returns { text, actions }.

   Because text AND voice both call runVidyaTurn, a spoken request ("show my
   mastery", "start a quick check", "take attendance") runs the SAME tools,
   returns the SAME navigate/render actions, and obeys the SAME permission
   ladder as a typed one — voice can only ever PREPARE a consequential action,
   never auto-send.

   PERMISSION LADDER (invariant 8): anything consequential — publishing a quick
   check, sending a message — is prepared and returns requires_approval. It is
   never executed here. The human decides, by voice OR by text.

   PRODUCTION NOTE: the gateway is the wall. In production these routes call the
   AI fabric THROUGH the gateway (which holds the credential and runs verify).
   This dev broker calls the provider directly server-side so the surface runs
   now; the key never crosses to the client.
   ============================================================================ */

import {
  computeMastery,
  detectGaps,
  gapLabel,
  type MasteryResult,
  type GapResult,
} from './engine';
import {
  SEED_EVENTS,
  EDGES,
  SCENARIO_NOW,
  CURRENT_STUDENT,
  topicInfo,
  TOPIC_INDEX,
} from './loopData';
import { RECOMMENDATIONS } from './mock';
import type {
  VidyaAction,
  RenderConfidence,
  MasteryCardSpec,
  GapsCardSpec,
  DraftCardSpec,
  RecommendationCardSpec,
  StepsCardSpec,
  DerivationStep,
} from './vidya';
import {
  NAV_TARGETS,
  isNavTarget,
  HIGHLIGHT_REGIONS,
  isHighlightRegion,
  verifyStep,
} from './vidya';

export const KEY_ENV = 'CLSS_AIFABRIC_DEV_GEMINI_API_KEY';
const BASE = 'https://generativelanguage.googleapis.com/v1beta/models';
const MODELS = ['gemini-2.5-flash', 'gemini-flash-latest', 'gemini-2.0-flash'];
const TRANSIENT = new Set([404, 408, 425, 429, 500, 502, 503, 504]);
const MAX_TOOL_TURNS = 5; // hard ceiling on the tool-use loop

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// ---------------------------------------------------------------------------
// Vidya's persona — calm, plain language, explainable intelligence. ONE voice
// across text and speech. The transport may append a small role/modality note.
// ---------------------------------------------------------------------------
export const SYSTEM = [
  'You are Vidya, the calm academic companion in Classess School.',
  'You are autonomous: reason about what the person needs, then call the tools',
  'provided to read the real intelligence engine before you answer. Prefer a',
  'tool over guessing. Reply in plain, warm, concise language a learner can act',
  'on. Never use emoji or exclamation marks. Do not lecture; guide.',
  'When you show mastery or gaps, describe them in plain language and never',
  'mention a number, score, percentage, or formula to a learner.',
  'Anything consequential (publishing a check, sending a message, grading,',
  'submitting) is only ever prepared for a human to approve, never done',
  'automatically.',
  '',
  'CHOOSE THE RIGHT CAPABILITY FROM PLAIN LANGUAGE, then perform it for real with',
  'a tool and speak the result. Map intent to capability:',
  '- TUTOR: "I don\'t get adding fractions", "help me with X", "I\'m stuck on X",',
  '  "teach me X", "I want to learn X". You MUST call tutor_step — this OUTRANKS',
  '  explaining or navigating. NEVER explain first. Your spoken reply must POSE',
  '  the next small step AS A QUESTION; do NOT state the method, the rule, or the',
  '  answer in your text. Wait for the learner to try; scaffold on a wrong answer',
  '  (name the misconception); reveal only after they have attempted or are',
  '  clearly stuck. Protect the struggle. (Routing to the learn PAGE is only for',
  '  "open the learn page" / "go to learn", never for "teach me / I don\'t get X".)',
  '- EXPLAIN: "explain X", "show me how X works", "derive X", "walk me through X".',
  '  Use explain_steps to build a step-by-step derivation. Each arithmetic step',
  '  carries a deterministic check and is verified before it is shown.',
  '- CREATE: "draft a quick check", "make an assignment", "build a blueprint',
  '  paper", "a revision plan". Use draft_quick_check / draft_plan / create_study_plan.',
  '  Everything created is returned for a human to approve, never auto-published.',
  '- READ & EXPLAIN: "where am I", "how am I doing", "my mastery", "my gaps".',
  '  Use show_mastery / detect_gaps and explain in plain language (independent vs',
  '  with guidance) with the evidence and why they are seeing it.',
  '- ASSESS: "why this mark", "what does this confidence band mean". Explain the',
  '  marking and band in plain language; the human is always final.',
  '- ANSWER: ask-anything over the data; plain language, never a raw formula to a',
  '  learner.',
  '- ACT: advance the loop or prepare an intervention, permission-laddered.',
  '- NAVIGATE: only when routing is the right response.',
  '',
  'SPEAK AND SHOW. Teach visually in sync with your words. Alongside your reply',
  'you may return visual actions the surface renders: highlight_target rings a',
  'named on-screen region (so "look at your trigonometry mastery" visibly',
  'highlights it); annotate_target pins one short calm margin note near a region',
  '(use sparingly); explain_steps self-assembles a verified derivation that',
  'reveals one step at a time as you speak. Use highlight when you are pointing at',
  'something already on screen; use explain_steps when you are deriving or',
  'teaching a method. Keep it tasteful.',
  '',
  'NAVIGATION IS A FIRST-CLASS ACTION. When the intent is actionable — when the',
  'person wants to go somewhere, do something, or see a specific view — call the',
  'right tool or navigate IMMEDIATELY rather than chatting about it. Bias toward',
  'acting. Only stay conversational when the person is genuinely asking a',
  'question, is unsure, or no destination fits. Map everyday, colloquial human',
  'language to intent — do not require exact page names. Examples of intent ->',
  'destination/tool:',
  '"show me where I am struggling" / "what am I weak at" / "my weak spots" ->',
  'navigate /student/progress (a learner) or show_mastery / detect_gaps.',
  '"how am I doing" / "my progress" -> /student/progress.',
  '"I want to set up my school" / "configure the school" / "add classes and',
  'sections" -> navigate /admin/setup.',
  '"let me take attendance" / "mark the roll" / "who is here today" ->',
  'take_attendance.',
  '"draft a quick check on fractions" / "make me a quiz on X" / "test them on X"',
  '-> draft_quick_check.',
  '"how is my class doing" / "where does the class stand" / "class overview" ->',
  'navigate /teacher/students or show_mastery.',
  '"open the live class" / "start class" / "go to the classroom" / "run the',
  'board" -> start_live_class.',
  '"plan tomorrow\'s lesson" / "lesson plan for X" / "what should I teach" ->',
  'draft_plan.',
  '"let me practise" / "give me practice" -> navigate /student/practice.',
  '"teach me X" / "I want to learn X" / "I don\'t understand X" -> tutor_step',
  '(teach inline, pose first). Only "open the learn page" / "go to learn" ->',
  'navigate /student/learn.',
  '"my mocks" / "exam prep" / "revision plan" -> open_mock.',
  '"my assignments" / "homework" / "what is due" -> open_work.',
  '"my portfolio" / "my credentials" / "my certificates" -> open_portfolio.',
  '"message a parent" / "email the class" / "send a note" -> message_compose.',
  '"the library" / "resources" / "find materials on X" -> open_library.',
  '"the loop" / "show me the cycle" -> navigate /loop.',
  '"what needs my approval" / "the approval queue" / "pending actions" ->',
  'navigate /proactive.',
  '"my messages" / "inbox" -> navigate /messages.',
  '"school-wide data" / "across sections" / "pacing and mastery" -> navigate',
  '/admin/intelligence.',
  '"settings" -> /settings; "my profile" / "my account" -> /profile;',
  '"home" / "take me back" / "the start" -> navigate /.',
  '',
  'Tool reminders: take_attendance opens fast capture (you propose, the teacher',
  'confirms), draft_plan prepares a lesson plan, open_mock opens the student',
  'mocks and revision plan, start_live_class opens the classroom, and',
  'message_compose opens a draft in the communication hub — never sending it.',
  'open_library opens the content / resource library (only verified content is',
  'servable), open_work opens the student assignment inbox and group projects,',
  'and open_portfolio opens the learner portfolio and credentials — issuing or',
  'sharing a credential is the learner’s decision.',
  'Shape the destination to the person\'s role when a route is role-specific.',
  'Keep the reply itself under 80 words; let the rendered cards carry the detail.',
].join(' ');

// ---------------------------------------------------------------------------
// Tool / function declarations — what the model may request. The SAME set is
// offered for text and for voice, so a spoken request runs the same tools.
// ---------------------------------------------------------------------------
export const TOOLS = [
  {
    functionDeclarations: [
      {
        name: 'navigate',
        description:
          'Take the person to one of the real pages. Use this WHENEVER they express intent to go somewhere or see a specific view, even in casual, indirect, or colloquial language ("show me where I am struggling" -> /student/progress, "set up my school" -> /admin/setup, "how is my class doing" -> /teacher/students, "what needs my approval" -> /proactive, "take me home" -> /). Prefer navigating over only describing the page. Match the destination to the person\'s role when a route is role-specific. It does not navigate by itself — it returns a directive the client follows, so it is always safe.',
        parameters: {
          type: 'object',
          properties: {
            target: {
              type: 'string',
              enum: [...NAV_TARGETS],
              description: 'The destination route.',
            },
            reason: { type: 'string', description: 'A calm one-line reason, shown before routing.' },
          },
          required: ['target'],
        },
      },
      {
        name: 'show_mastery',
        description:
          'Compute the current plain-language mastery read for a topic from the real engine. Returns the band, whether it is independent, whether revision is due, and the six dimensions. Never returns a raw number to surface to a learner.',
        parameters: {
          type: 'object',
          properties: {
            topic: { type: 'string', description: 'The topic name, e.g. "Trigonometric Ratios".' },
            subject: { type: 'string', description: 'Optional subject name to disambiguate.' },
          },
          required: ['topic'],
        },
      },
      {
        name: 'detect_gaps',
        description:
          'Detect the learning gaps on a topic from the real engine. A gap is never confirmed from a single bad score. Returns each gap with a plain-language rationale, a confidence, and whether it is confirmed.',
        parameters: {
          type: 'object',
          properties: {
            topic: { type: 'string', description: 'The topic name.' },
          },
          required: ['topic'],
        },
      },
      {
        name: 'draft_quick_check',
        description:
          'Prepare a draft quick check for a topic. CONSEQUENTIAL: it is prepared for a human to review and set live, never published automatically. Returns a draft shape that requires approval.',
        parameters: {
          type: 'object',
          properties: {
            topic: { type: 'string', description: 'The topic the check targets.' },
            count: { type: 'integer', description: 'How many items (defaults to 5).' },
          },
          required: ['topic'],
        },
      },
      {
        name: 'list_recommendations',
        description:
          'List the current proactive recommendations, each with its evidence, confidence, owner, due date, the consequence of ignoring it, and why it appeared.',
        parameters: { type: 'object', properties: {} },
      },
      {
        name: 'explain_step',
        description:
          'Give a short, plain-language explanation of a concept as a hint that protects the struggle. Use this when a learner is stuck and asks how something works.',
        parameters: {
          type: 'object',
          properties: {
            concept: { type: 'string', description: 'The concept to explain plainly.' },
          },
          required: ['concept'],
        },
      },
      {
        name: 'tutor_step',
        description:
          'TUTOR on the assistance ladder: pose -> struggle -> reveal. Use this when a learner does not understand something or is stuck ("I don\'t get adding fractions", "help me with X"). NEVER explain first. With no attempt yet, pose ONE small step and wait. After a wrong attempt, scaffold and name the misconception. Reveal only once the learner has attempted it or is clearly stuck. Returns the phase so your reply matches it.',
        parameters: {
          type: 'object',
          properties: {
            concept: { type: 'string', description: 'What the learner is working on, e.g. "adding fractions".' },
            attempts: { type: 'integer', description: 'How many attempts the learner has made on this step (0 if they have not tried yet).' },
            lastCorrect: { type: 'boolean', description: 'Whether their latest attempt was correct.' },
            gaveUp: { type: 'boolean', description: 'True only if the learner explicitly asked to be shown or gave up.' },
          },
          required: ['concept'],
        },
      },
      {
        name: 'explain_steps',
        description:
          'EXPLAIN by self-assembling a step-by-step derivation that reveals one step at a time as you speak. Use for "explain X", "derive X", "walk me through X". Each arithmetic step may carry a deterministic check { lhs, rhs } that is VERIFIED before it is shown — only verified steps appear (generate-and-verify). Plain language; never a bare formula to a learner.',
        parameters: {
          type: 'object',
          properties: {
            topic: { type: 'string', description: 'The concept or problem being derived.' },
            title: { type: 'string', description: 'A short title for the derivation.' },
            steps: {
              type: 'array',
              description: 'Ordered steps. Each has plain-language text and, where the step makes a concrete arithmetic claim, a deterministic check.',
              items: {
                type: 'object',
                properties: {
                  text: { type: 'string', description: 'The plain-language line for this step.' },
                  check: {
                    type: 'object',
                    description: 'Optional deterministic arithmetic check; lhs must equal rhs exactly (e.g. lhs "1/2 + 1/4", rhs "3/4").',
                    properties: {
                      lhs: { type: 'string', description: 'Left-hand arithmetic expression.' },
                      rhs: { type: 'string', description: 'Right-hand arithmetic expression it should equal.' },
                    },
                  },
                },
                required: ['text'],
              },
            },
          },
          required: ['topic', 'steps'],
        },
      },
      {
        name: 'highlight_target',
        description:
          'SPEAK AND SHOW: ring/spotlight a named on-screen region while you talk about it, so the learner sees what you mean ("look at your trigonometry mastery"). Visual only — it never changes anything, so it is always safe.',
        parameters: {
          type: 'object',
          properties: {
            region: {
              type: 'string',
              enum: Object.keys(HIGHLIGHT_REGIONS),
              description: 'The on-screen region to ring.',
            },
            label: { type: 'string', description: 'A calm one-line caption shown by the ring.' },
          },
          required: ['region'],
        },
      },
      {
        name: 'annotate_target',
        description:
          'SPEAK AND SHOW: pin ONE short, calm margin note near a named region (the human-note feel). Use sparingly, for a single load-bearing aside. Visual only — always safe.',
        parameters: {
          type: 'object',
          properties: {
            region: {
              type: 'string',
              enum: Object.keys(HIGHLIGHT_REGIONS),
              description: 'The region the note pins to.',
            },
            note: { type: 'string', description: 'One calm line; no emoji, no exclamation.' },
          },
          required: ['region', 'note'],
        },
      },
      {
        name: 'create_study_plan',
        description:
          'CREATE a draft study / spaced-revision plan from the ontology topics a learner is working on. CONSEQUENTIAL: prepared for a human to review and adopt, never auto-applied. Returns a draft that requires approval.',
        parameters: {
          type: 'object',
          properties: {
            topic: { type: 'string', description: 'The focus topic for the plan.' },
            days: { type: 'integer', description: 'How many days the plan spans (defaults to 5).' },
          },
          required: ['topic'],
        },
      },
      {
        name: 'take_attendance',
        description:
          'Open the fast attendance capture for the class. Capture only ever PROPOSES a roll; the teacher confirms it — attendance is never finalised automatically. Returns a directive to the attendance page.',
        parameters: { type: 'object', properties: {} },
      },
      {
        name: 'draft_plan',
        description:
          'Prepare a draft adaptive lesson plan for a topic, mapped to the ontology outcomes and differentiated by mastery band. CONSEQUENTIAL once delivered: it is prepared for the teacher to review on the planning page, never published automatically.',
        parameters: {
          type: 'object',
          properties: {
            topic: { type: 'string', description: 'The topic the plan centres on.' },
          },
          required: ['topic'],
        },
      },
      {
        name: 'open_mock',
        description:
          'Open the mock tests and spaced-revision study planner for the student. Returns a directive to the mocks page; it does not start a test by itself.',
        parameters: { type: 'object', properties: {} },
      },
      {
        name: 'start_live_class',
        description:
          'Open the live classroom delivery surface (board, polls, device-free check, attention signals). Teacher-launched: it opens the workspace; it does not broadcast anything to students by itself.',
        parameters: { type: 'object', properties: {} },
      },
      {
        name: 'message_compose',
        description:
          'Open the communication hub with a draft message prepared for review. CONSEQUENTIAL: a message is never sent automatically — it is composed for the human to send, behind the approval control, with child-safety and quiet-hours respected.',
        parameters: {
          type: 'object',
          properties: {
            topic: { type: 'string', description: 'What the message is about.' },
          },
          required: [],
        },
      },
      {
        name: 'open_library',
        description:
          'Open the content / resource library (teacher and admin). Browse and search resources mapped to ontology topics, each with its generate-and-verify state; only verified content is servable. Opens the page; it does not publish or generate anything by itself.',
        parameters: { type: 'object', properties: {} },
      },
      {
        name: 'open_work',
        description:
          'Open the student work surface — the assignment inbox and group projects. Shows assigned checks, homework, and projects with due dates and status. Opens the page; submitting work is the learner’s decision and never auto-fires.',
        parameters: { type: 'object', properties: {} },
      },
      {
        name: 'open_portfolio',
        description:
          'Open the learner portfolio and credentials — the timeline of mastered topics with evidence, and verifiable credentials. Opens the page; issuing or sharing a credential is consequential and is the learner’s decision, never automatic.',
        parameters: { type: 'object', properties: {} },
      },
    ],
  },
];

// ---------------------------------------------------------------------------
// Tool execution — against the REAL engine + data. Each returns a structured
// result fed back to the model AND, when it should render, a client action.
// ---------------------------------------------------------------------------

interface ToolOutcome {
  /** The structured result fed back to the model as a functionResponse. */
  result: Record<string, unknown>;
  /** Optional client action this tool produced (navigate or render). */
  action?: VidyaAction;
}

function confidenceFor(value: number): RenderConfidence {
  if (value >= 0.66) return 'high';
  if (value >= 0.33) return 'middle';
  return 'low';
}

/** Resolve a free-text topic name to a seed topic id (case-insensitive match). */
function resolveTopicId(name: string): string | null {
  const q = name.trim().toLowerCase();
  for (const id of Object.keys(TOPIC_INDEX)) {
    if (TOPIC_INDEX[id]!.name.toLowerCase() === q) return id;
  }
  // Loose contains-match as a fallback.
  for (const id of Object.keys(TOPIC_INDEX)) {
    const n = TOPIC_INDEX[id]!.name.toLowerCase();
    if (n.includes(q) || q.includes(n)) return id;
  }
  return null;
}

/** Map a dimension value to a calm, plain level — never the raw number. */
function dimLevel(v: number): 'strong' | 'growing' | 'early' {
  if (v >= 0.6) return 'strong';
  if (v >= 0.3) return 'growing';
  return 'early';
}

function masteryToSpec(topicName: string, subject: string | undefined, m: MasteryResult): MasteryCardSpec {
  const d = m.reading.dimensions;
  return {
    kind: 'mastery',
    topic: topicName,
    subject,
    plainLanguage: m.plainLanguage,
    independent: m.reading.independent,
    revisionDue: m.revisionDue,
    observationCount: m.observationCount,
    dimensions: [
      { label: 'Performance', level: dimLevel(d.performance) },
      { label: 'Reliability', level: dimLevel(d.reliability) },
      { label: 'Independence', level: dimLevel(d.independence) },
      { label: 'Challenge', level: dimLevel(d.difficulty) },
      { label: 'Freshness', level: dimLevel(d.recency) },
      { label: 'Consistency', level: dimLevel(d.consistency) },
    ],
  };
}

function toolShowMastery(args: Record<string, unknown>): ToolOutcome {
  const name = String(args.topic ?? '');
  const subject = typeof args.subject === 'string' ? args.subject : undefined;
  const topicId = resolveTopicId(name);
  if (!topicId) {
    return { result: { found: false, note: 'No evidence on a topic by that name yet.' } };
  }
  const info = topicInfo(topicId);
  const m = computeMastery(SEED_EVENTS, CURRENT_STUDENT.ref, topicId, SCENARIO_NOW);
  const spec = masteryToSpec(info.name, subject ?? info.subjectName, m);
  return {
    result: {
      found: true,
      topic: info.name,
      plainLanguage: m.plainLanguage,
      independent: m.reading.independent,
      revisionDue: m.revisionDue,
      observationCount: m.observationCount,
    },
    action: { type: 'render', spec },
  };
}

function toolDetectGaps(args: Record<string, unknown>): ToolOutcome {
  const name = String(args.topic ?? '');
  const topicId = resolveTopicId(name);
  if (!topicId) {
    return { result: { found: false, note: 'No evidence on a topic by that name yet.' } };
  }
  const info = topicInfo(topicId);
  const gaps: GapResult[] = detectGaps(SEED_EVENTS, CURRENT_STUDENT.ref, topicId, EDGES, SCENARIO_NOW);
  const spec: GapsCardSpec = {
    kind: 'gaps',
    topic: info.name,
    gaps: gaps.slice(0, 4).map((g) => ({
      label: gapLabel(g.evidence.gapType),
      rationale: g.evidence.rationale,
      confidence: confidenceFor(g.evidence.confidence),
      confirmed: g.evidence.confirmed,
    })),
  };
  return {
    result: {
      found: true,
      topic: info.name,
      gaps: spec.gaps.map((g) => ({ label: g.label, confirmed: g.confirmed, confidence: g.confidence })),
    },
    action: gaps.length > 0 ? { type: 'render', spec } : undefined,
  };
}

function toolDraftQuickCheck(args: Record<string, unknown>): ToolOutcome {
  const name = String(args.topic ?? 'this topic');
  const count = Math.max(3, Math.min(10, Number(args.count) || 5));
  const topicId = resolveTopicId(name);
  const info = topicId ? topicInfo(topicId) : null;
  const topicName = info?.name ?? name;
  const items = [
    'Two recall items to settle the idea',
    'Two application items in a fresh context',
    'One short-answer item that asks them to explain their step',
  ].slice(0, Math.min(3, count));
  const spec: DraftCardSpec = {
    kind: 'draft',
    title: `Quick check — ${topicName}`,
    topic: topicName,
    body: `${count} items, mixed difficulty, mapped to the outcomes the class slipped on. Prepared for your review.`,
    items,
    confidence: 'middle',
    requiresApproval: true,
    openHref: '/teacher/assign',
    openLabel: 'Review and set live',
  };
  return {
    result: {
      prepared: true,
      requires_approval: true,
      note: 'A quick check is consequential. It is prepared for a human to review and set live; it is not published.',
      title: spec.title,
      itemCount: count,
    },
    action: { type: 'render', spec },
  };
}

function toolListRecommendations(): ToolOutcome {
  const specs: RecommendationCardSpec[] = RECOMMENDATIONS.map((r) => ({
    kind: 'recommendation',
    title: r.title,
    why: r.whySeeing,
    evidence: r.evidence,
    confidence: (r.confidence === 'high' ? 'high' : r.confidence === 'low' ? 'low' : 'middle') as RenderConfidence,
    owner: r.owner,
    due: r.due,
    consequence: r.consequence,
  }));
  return {
    result: {
      count: specs.length,
      recommendations: RECOMMENDATIONS.map((r) => ({
        title: r.title,
        confidence: r.confidence,
        owner: r.owner,
        due: r.due,
        consequence: r.consequence,
        why: r.whySeeing,
      })),
    },
    // Render only the first inline; the proactive page holds the full feed.
    action: specs[0] ? { type: 'render', spec: specs[0] } : undefined,
  };
}

function toolNavigate(args: Record<string, unknown>): ToolOutcome {
  if (!isNavTarget(args.target)) {
    return { result: { navigated: false, note: 'Unknown destination; not routing.' } };
  }
  const reason = typeof args.reason === 'string' ? args.reason : undefined;
  return {
    result: { navigated: true, target: args.target },
    action: { type: 'navigate', target: args.target, reason },
  };
}

/** explain_step is answered by the model itself — the tool just acknowledges so
 *  the model writes the plain-language hint into its final text. */
function toolExplainStep(args: Record<string, unknown>): ToolOutcome {
  const concept = String(args.concept ?? 'this');
  return {
    result: {
      ok: true,
      guidance:
        'Write a short plain-language hint that protects the struggle. One nudge toward the next step, not the full answer. No numbers, no formula.',
      concept,
    },
  };
}

/** Open the attendance capture. Capture proposes; the teacher confirms. */
function toolTakeAttendance(): ToolOutcome {
  return {
    result: {
      navigated: true,
      target: '/teacher/attendance',
      note: 'Attendance capture assists and proposes a roll. The teacher confirms; it is never finalised automatically.',
    },
    action: {
      type: 'navigate',
      target: '/teacher/attendance',
      reason: 'Fast capture is here. I will propose the roll; you confirm it.',
    },
  };
}

/** Prepare a draft adaptive plan for a topic, mapped to outcomes, by band. */
function toolDraftPlan(args: Record<string, unknown>): ToolOutcome {
  const name = String(args.topic ?? 'this topic');
  const topicId = resolveTopicId(name);
  const info = topicId ? topicInfo(topicId) : null;
  const topicName = info?.name ?? name;
  const spec: DraftCardSpec = {
    kind: 'draft',
    title: `Lesson plan — ${topicName}`,
    topic: topicName,
    body: 'A draft daily plan mapped to the outcome, with a differentiated path for each mastery band. Prepared for your review on the planning page.',
    items: [
      'Open: anchor the prior outcome the class secured',
      'Core: teach the new outcome with a worked, then a fresh context',
      'Differentiate: stretch for the strong, scaffold for the support band',
      'Close: a one-line check that becomes tomorrow’s read',
    ],
    confidence: 'middle',
    requiresApproval: true,
    openHref: '/teacher/plan',
    openLabel: 'Open the plan',
  };
  return {
    result: {
      prepared: true,
      note: 'A plan is prepared for the teacher to review and adapt on the planning page; it is not delivered automatically.',
      title: spec.title,
    },
    action: { type: 'render', spec },
  };
}

/** Open the mock tests + spaced-revision study planner for the student. */
function toolOpenMock(): ToolOutcome {
  return {
    result: { navigated: true, target: '/student/mocks' },
    action: {
      type: 'navigate',
      target: '/student/mocks',
      reason: 'Your mocks and the revision plan are here. Nothing starts until you choose to begin.',
    },
  };
}

/** Open the live classroom delivery surface. Teacher-launched. */
function toolStartLiveClass(): ToolOutcome {
  return {
    result: {
      navigated: true,
      target: '/classroom',
      note: 'The classroom opens for the teacher to launch. Nothing is broadcast to students automatically.',
    },
    action: {
      type: 'navigate',
      target: '/classroom',
      reason: 'The board, polls and device-free check are ready. You launch them.',
    },
  };
}

/** Open the communication hub with a draft prepared. Never sends. */
function toolMessageCompose(args: Record<string, unknown>): ToolOutcome {
  const topic = typeof args.topic === 'string' && args.topic.trim() ? args.topic.trim() : undefined;
  return {
    result: {
      prepared: true,
      requires_approval: true,
      target: '/messages',
      note: 'A message is consequential. It is composed for the human to review and send behind the approval control, with child-safety and quiet hours respected. It is never sent automatically.',
      topic,
    },
    action: {
      type: 'navigate',
      target: '/messages',
      reason: topic
        ? `I have opened a draft about ${topic}. Review and send it yourself.`
        : 'I have opened the messages hub. Compose there; nothing sends until you do.',
    },
  };
}

/** Open the content / resource library. Teacher + admin. Opens the page only. */
function toolOpenLibrary(): ToolOutcome {
  return {
    result: {
      navigated: true,
      target: '/content',
      note: 'The library opens to browse and search. Only verified content is servable; generating or publishing is a human decision.',
    },
    action: {
      type: 'navigate',
      target: '/content',
      reason: 'The resource library is here. Only verified material is servable — nothing publishes on its own.',
    },
  };
}

/** Open the student work inbox + group projects. Opens the page only. */
function toolOpenWork(): ToolOutcome {
  return {
    result: {
      navigated: true,
      target: '/student/work',
      note: 'Your assignments and projects open here. Submitting is your decision; nothing submits automatically.',
    },
    action: {
      type: 'navigate',
      target: '/student/work',
      reason: 'Your assignments and projects are here. You decide when to submit.',
    },
  };
}

/** Open the learner portfolio + credentials. Opens the page only. */
function toolOpenPortfolio(): ToolOutcome {
  return {
    result: {
      navigated: true,
      target: '/student/portfolio',
      note: 'Your record opens here, in plain language with the evidence behind it. Issuing or sharing a credential is your decision.',
    },
    action: {
      type: 'navigate',
      target: '/student/portfolio',
      reason: 'Your portfolio and credentials are here. Sharing is always your decision.',
    },
  };
}

/** TUTOR: decide the assistance-ladder phase and tell the model how to reply.
 *  Never reveals before a posed attempt (mirrors the pure tutorReveal helper). */
function toolTutorStep(args: Record<string, unknown>): ToolOutcome {
  const concept = String(args.concept ?? 'this');
  const attempts = Math.max(0, Number(args.attempts) || 0);
  const lastCorrect = args.lastCorrect === true;
  const gaveUp = args.gaveUp === true;

  let phase: 'pose' | 'scaffold' | 'reveal';
  if (attempts === 0 && !gaveUp) phase = 'pose';
  else if (lastCorrect || gaveUp || attempts > 2) phase = 'reveal';
  else phase = 'scaffold';

  const guidance: Record<typeof phase, string> = {
    pose:
      'Pose ONE small step toward the answer and ask the learner to try it. Do NOT explain the method or give the answer yet. One short prompt, plain language.',
    scaffold:
      'Their attempt was off. Name the likely misconception gently, give ONE targeted nudge toward the next step, and invite them to try again. Still do not give the full answer.',
    reveal:
      'They have earned the reveal. Walk the step through plainly and confirm the idea, then offer one more to check it stuck. No numbers-as-scores, no formula dump.',
  };

  return {
    result: { ok: true, concept, phase, attempts, guidance: guidance[phase] },
  };
}

/** EXPLAIN: build a verified, self-assembling derivation. Any step whose
 *  deterministic check fails is dropped — only verified steps are taught. */
function toolExplainSteps(args: Record<string, unknown>): ToolOutcome {
  const topic = typeof args.topic === 'string' && args.topic.trim() ? args.topic.trim() : 'this';
  const title = typeof args.title === 'string' && args.title.trim() ? args.title.trim() : `Step by step — ${topic}`;
  const rawSteps = Array.isArray(args.steps) ? args.steps : [];
  const verified: DerivationStep[] = [];
  let dropped = 0;
  for (const s of rawSteps) {
    if (!s || typeof s !== 'object') continue;
    const step = s as Record<string, unknown>;
    if (typeof step.text !== 'string' || step.text.trim().length === 0) continue;
    const check =
      step.check && typeof step.check === 'object'
        ? (step.check as { lhs?: unknown; rhs?: unknown })
        : undefined;
    if (check && typeof check.lhs === 'string' && typeof check.rhs === 'string') {
      if (!verifyStep(check.lhs, check.rhs)) {
        dropped++;
        continue; // generate-and-verify: never teach an unverified step
      }
      verified.push({ text: step.text.trim(), check: { lhs: check.lhs, rhs: check.rhs } });
    } else {
      verified.push({ text: step.text.trim() });
    }
  }
  if (verified.length === 0) {
    return {
      result: {
        verified: false,
        dropped,
        note: 'No step passed the deterministic check, so nothing is shown. Re-derive with correct arithmetic.',
      },
    };
  }
  const spec: StepsCardSpec = { kind: 'steps', title, topic, steps: verified };
  return {
    result: { verified: true, stepCount: verified.length, dropped, title },
    action: { type: 'render', spec },
  };
}

/** SPEAK AND SHOW: ring an on-screen region. Visual only; always safe. */
function toolHighlightTarget(args: Record<string, unknown>): ToolOutcome {
  if (!isHighlightRegion(args.region)) {
    return { result: { highlighted: false, note: 'Unknown region; not highlighting.' } };
  }
  const label = typeof args.label === 'string' ? args.label : undefined;
  return {
    result: { highlighted: true, region: args.region },
    action: { type: 'highlight', region: args.region, label },
  };
}

/** SPEAK AND SHOW: pin one calm margin note near a region. Visual only. */
function toolAnnotateTarget(args: Record<string, unknown>): ToolOutcome {
  if (!isHighlightRegion(args.region)) {
    return { result: { annotated: false, note: 'Unknown region; not annotating.' } };
  }
  const note = typeof args.note === 'string' ? args.note.trim() : '';
  if (!note) return { result: { annotated: false, note: 'No note text.' } };
  return {
    result: { annotated: true, region: args.region },
    action: { type: 'annotate', region: args.region, note },
  };
}

/** CREATE: a draft spaced-revision study plan, prepared for human approval. */
function toolCreateStudyPlan(args: Record<string, unknown>): ToolOutcome {
  const name = String(args.topic ?? 'this topic');
  const days = Math.max(3, Math.min(14, Number(args.days) || 5));
  const topicId = resolveTopicId(name);
  const info = topicId ? topicInfo(topicId) : null;
  const topicName = info?.name ?? name;
  const spec: DraftCardSpec = {
    kind: 'draft',
    title: `Study plan — ${topicName}`,
    topic: topicName,
    body: `A ${days}-day spaced-revision plan, sequenced from the prerequisites and paced for retrieval. Prepared for you to review and adopt.`,
    items: [
      'Day one: re-anchor the prior outcome with a short worked example',
      'Mid: retrieval practice on the topic in a fresh context',
      'Spaced: a low-stakes self-check after a rest day',
      'Close: a final confidence check before you move on',
    ],
    confidence: 'middle',
    requiresApproval: true,
    openHref: '/student/mocks',
    openLabel: 'Open the revision planner',
  };
  return {
    result: {
      prepared: true,
      requires_approval: true,
      note: 'A study plan is prepared for the learner to review and adopt; it is not applied automatically.',
      title: spec.title,
      days,
    },
    action: { type: 'render', spec },
  };
}

export function runTool(name: string, args: Record<string, unknown>): ToolOutcome {
  switch (name) {
    case 'navigate':
      return toolNavigate(args);
    case 'tutor_step':
      return toolTutorStep(args);
    case 'explain_steps':
      return toolExplainSteps(args);
    case 'highlight_target':
      return toolHighlightTarget(args);
    case 'annotate_target':
      return toolAnnotateTarget(args);
    case 'create_study_plan':
      return toolCreateStudyPlan(args);
    case 'show_mastery':
      return toolShowMastery(args);
    case 'detect_gaps':
      return toolDetectGaps(args);
    case 'draft_quick_check':
      return toolDraftQuickCheck(args);
    case 'list_recommendations':
      return toolListRecommendations();
    case 'explain_step':
      return toolExplainStep(args);
    case 'take_attendance':
      return toolTakeAttendance();
    case 'draft_plan':
      return toolDraftPlan(args);
    case 'open_mock':
      return toolOpenMock();
    case 'start_live_class':
      return toolStartLiveClass();
    case 'message_compose':
      return toolMessageCompose(args);
    case 'open_library':
      return toolOpenLibrary();
    case 'open_work':
      return toolOpenWork();
    case 'open_portfolio':
      return toolOpenPortfolio();
    default:
      return { result: { error: `unknown tool: ${name}` } };
  }
}

// ---------------------------------------------------------------------------
// Provider transport — retry within a model, fall back across models.
// ---------------------------------------------------------------------------
export async function generateContent(
  model: string,
  body: unknown,
  key: string,
  attemptsPerModel = 2,
): Promise<{ ok: boolean; status: number; json?: any }> {
  let status = 0;
  for (let attempt = 0; attempt < attemptsPerModel; attempt++) {
    const res = await fetch(`${BASE}/${model}:generateContent`, {
      method: 'POST',
      headers: { 'x-goog-api-key': key, 'content-type': 'application/json' },
      body: JSON.stringify(body),
    });
    status = res.status;
    if (res.ok) return { ok: true, status, json: await res.json() };
    if (!TRANSIENT.has(res.status)) return { ok: false, status };
    await sleep(250 * (attempt + 1));
  }
  return { ok: false, status };
}

export type GeminiContent = { role: 'user' | 'model'; parts: any[] };

/** The result of one orchestrated turn. `ok:false` means every model path
 *  failed transiently — the caller should degrade. */
export type VidyaTurnResult =
  | { ok: true; text: string; actions: VidyaAction[] }
  | { ok: false; status: number };

/**
 * The ONE Vidya tool-use loop, shared by text and voice. Seeds the conversation
 * with the shared SYSTEM persona, runs the model, executes any requested tools
 * against the real engine, feeds the results back, and returns the final text
 * plus the navigate/render actions. The SAME permission ladder applies on both
 * paths — a consequential tool only ever prepares.
 *
 * @param contents     the conversation as Gemini contents (first must be user).
 * @param key          the server-side provider key (never logged or returned).
 * @param systemExtra  an optional, short addendum to SYSTEM (role/modality).
 * @param maxOutputTokens cap on the final reply length (voice keeps this small).
 */
export async function runVidyaTurn(
  contents: GeminiContent[],
  key: string,
  systemExtra = '',
  maxOutputTokens = 700,
): Promise<VidyaTurnResult> {
  const system = systemExtra ? `${SYSTEM} ${systemExtra}` : SYSTEM;
  const actions: VidyaAction[] = [];
  let lastStatus = 502;

  for (const model of MODELS) {
    let modelFailed = false;
    for (let turn = 0; turn < MAX_TOOL_TURNS; turn++) {
      const body = {
        systemInstruction: { parts: [{ text: system }] },
        contents,
        tools: TOOLS,
        generationConfig: { temperature: 0.5, maxOutputTokens },
      };
      const out = await generateContent(model, body, key);
      if (!out.ok) {
        lastStatus = out.status || 502;
        modelFailed = true;
        break; // try the next fallback model
      }
      const candidate = out.json?.candidates?.[0];
      const parts: any[] = candidate?.content?.parts ?? [];
      const calls = parts.filter((p) => p.functionCall).map((p) => p.functionCall);

      if (calls.length === 0) {
        const text = parts.map((p) => p.text).filter(Boolean).join(' ').trim();
        return { ok: true, text, actions };
      }

      // Execute every requested tool, append the model turn + our responses.
      contents.push({ role: 'model', parts });
      const responseParts: any[] = [];
      for (const call of calls) {
        const name = String(call.name);
        const args = (call.args ?? {}) as Record<string, unknown>;
        const outcome = runTool(name, args);
        if (outcome.action) actions.push(outcome.action);
        responseParts.push({ functionResponse: { name, response: outcome.result } });
      }
      contents.push({ role: 'user', parts: responseParts });
    }
    if (!modelFailed) {
      // Ran out of tool turns without a final text — return what we have.
      return { ok: true, text: '', actions };
    }
    // else: this model failed transiently — try the next one with a fresh loop.
  }

  return { ok: false, status: lastStatus };
}
