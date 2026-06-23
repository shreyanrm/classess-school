/* ============================================================================
   lib/vidyaPersona.ts — ONE identity, FOUR behaviours.

   Vidya is a single conversational OS. Its base persona (calm, plain language,
   explainable, permission-laddered) lives in vidyaServer.SYSTEM. This module
   SHAPES that one identity into a role-specific behaviour:

     - student  -> COMPANION : protects productive struggle, never hands answers.
     - teacher  -> COPILOT   : executes and prepares the teacher's work.
     - parent   -> GUIDE     : reports and reassures in plain language.
     - admin    -> ASSISTANT : commands the institution.

   The role is passed in from the request (lib/mock Role). It selects:
     1) a system-prompt ADDENDUM appended to the shared SYSTEM, and
     2) a TOOL ALLOWLIST — the subset of declared tools that fit the role, so a
        parent is never offered take_attendance and a student is never offered
        message_compose. The base permission ladder still holds for every tool.

   PURE + SERVER/CLIENT-SAFE: no provider key, no I/O. Used by the orchestrator
   to condition the turn and by the routes to pick the allowlist.
   ============================================================================ */

import type { Role } from './mock';

/** Vidya's role-shaped behaviour label. One identity, four behaviours. */
export type VidyaPersona = 'companion' | 'copilot' | 'guide' | 'assistant';

/** The behaviour each role selects. */
export const PERSONA_FOR_ROLE: Record<Role, VidyaPersona> = {
  student: 'companion',
  teacher: 'copilot',
  parent: 'guide',
  admin: 'assistant',
};

/** Resolve a (possibly untrusted) role string to a persona, defaulting safely. */
export function personaForRole(role: unknown): VidyaPersona {
  if (role === 'student' || role === 'teacher' || role === 'parent' || role === 'admin') {
    return PERSONA_FOR_ROLE[role];
  }
  // An unknown caller gets the most conservative behaviour: the student
  // COMPANION protects the struggle and never hands answers.
  return 'companion';
}

/**
 * The full declared tool name set. The allowlist below is a SUBSET of this per
 * role; an out-of-set tool is dropped before the model ever sees it.
 */
export const ALL_TOOL_NAMES = [
  'navigate',
  'show_mastery',
  'detect_gaps',
  'draft_quick_check',
  'list_recommendations',
  'explain_step',
  'tutor_step',
  'explain_steps',
  'show_on_canvas',
  'highlight_target',
  'annotate_target',
  'create_study_plan',
  'compose_surface',
  'take_attendance',
  'draft_plan',
  'open_mock',
  'start_live_class',
  'message_compose',
  'open_library',
  'open_work',
  'open_portfolio',
] as const;

export type VidyaToolName = (typeof ALL_TOOL_NAMES)[number];

/**
 * The tools every role may use — the universally-safe read/teach/navigate set.
 * navigate is shared, but the SYSTEM still shapes the destination to the role.
 */
const SHARED_TOOLS: VidyaToolName[] = [
  'navigate',
  'show_mastery',
  'detect_gaps',
  'list_recommendations',
  'show_on_canvas',
  'highlight_target',
  'annotate_target',
  'compose_surface',
];

/**
 * The tool allowlist per persona. The base permission ladder is unchanged — a
 * consequential tool still only PREPARES — this narrows WHICH tools each role is
 * even offered, so the behaviour reads true to the role.
 */
export const TOOLS_FOR_PERSONA: Record<VidyaPersona, VidyaToolName[]> = {
  // COMPANION: learns alongside the student. Tutors (pose-first), explains,
  // plans their own revision. Never the teacher's class-operation tools.
  companion: [
    ...SHARED_TOOLS,
    'tutor_step',
    'explain_step',
    'explain_steps',
    'create_study_plan',
    'open_mock',
    'open_work',
    'open_portfolio',
  ],
  // COPILOT: executes and prepares the teacher's work — checks, plans, the
  // class operation. May draft consequential work (it still requires approval).
  copilot: [
    ...SHARED_TOOLS,
    'explain_steps',
    'draft_quick_check',
    'draft_plan',
    'take_attendance',
    'start_live_class',
    'message_compose',
    'open_library',
  ],
  // GUIDE: reports and reassures the parent in plain language. Reads + composes
  // a message to the school. Never the student's tutor tools or class operation.
  guide: [...SHARED_TOOLS, 'message_compose'],
  // ASSISTANT: commands the institution. Reads, plans, composes, opens the
  // library; the institution-wide navigation is shaped by SYSTEM.
  assistant: [
    ...SHARED_TOOLS,
    'draft_quick_check',
    'draft_plan',
    'message_compose',
    'open_library',
  ],
};

/** Whether a persona may use a given tool. */
export function personaAllowsTool(persona: VidyaPersona, tool: string): boolean {
  return (TOOLS_FOR_PERSONA[persona] as string[]).includes(tool);
}

/**
 * The role-shaped system-prompt ADDENDUM. One identity, four behaviours: the
 * shared SYSTEM carries the calm voice, the laws, and the capability map; this
 * appends HOW the role wants Vidya to behave. Kept short so it does not drown
 * the base prompt — it biases, it does not rewrite.
 */
export function personaInstruction(role: Role): string {
  const persona = PERSONA_FOR_ROLE[role];
  switch (persona) {
    case 'companion':
      return [
        'You are speaking with a STUDENT, as their COMPANION. Learn alongside them.',
        'Protect productive struggle above all: you NEVER hand over an answer. When',
        'they are stuck, tutor — pose one small step and wait, scaffold a wrong',
        'attempt by naming the misconception, and reveal only after they have tried',
        'or are clearly stuck. Prefer tutor_step over explaining. Keep it warm and',
        'encouraging; never a number, score, or formula. You cannot run a class:',
        'no attendance, no class plans, no sending messages — those are not yours.',
      ].join(' ');
    case 'copilot':
      return [
        'You are working with a TEACHER, as their COPILOT. Execute and prepare their',
        'work: draft checks and plans, open the classroom, take attendance, compose',
        'a message — always prepared for the teacher to approve, never auto-fired.',
        'Be efficient and direct; do the legwork so the teacher decides. You may',
        'summon a working surface inline (compose_surface) to build a check or read',
        'a class without leaving the conversation.',
      ].join(' ');
    case 'guide':
      return [
        'You are speaking with a PARENT, as their GUIDE. Report and reassure in plain,',
        'everyday language — no jargon, no scores, no formulas, no school acronyms.',
        'Explain how their child is doing and what helps, calmly and honestly. You',
        'may compose a message to the school for the parent to send, never sending it',
        'yourself. You do not tutor the child or operate the class; you inform and',
        'reassure the parent.',
      ].join(' ');
    case 'assistant':
      return [
        'You are working with an ADMIN, as their institution ASSISTANT. Command the',
        'institution: read school-wide intelligence, prepare plans and checks, open',
        'the library, compose communications — all prepared for the admin to approve,',
        'never auto-fired. Speak at the institutional altitude (sections, pacing,',
        'governance), in plain language, and route to the admin surfaces.',
      ].join(' ');
  }
}
