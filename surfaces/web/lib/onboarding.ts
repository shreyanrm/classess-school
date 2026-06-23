/* ============================================================================
   lib/onboarding.ts — the calm, implicit first-run script.

   This is NOT a questionnaire. Every option below is a single natural tap on a
   chip or card. From those choices plus the role, lib/store.inferProfile builds
   the personalization profile WITHOUT ever asking the learner to declare
   interests, likes, or dislikes. Vidya narrates throughout (the GREETING tone:
   calm, plain language, no exclamation, no emoji).
   ============================================================================ */

import type { Role } from './mock';
import type { AgeTier } from './store';

/** Role chosen at the door, each with a calm one-line invitation. */
export interface RoleChoice {
  role: Role;
  label: string;
  invite: string;
}

export const ROLE_CHOICES: RoleChoice[] = [
  { role: 'student', label: 'I am a learner', invite: 'Find your next step and learn at your pace.' },
  { role: 'teacher', label: 'I teach a class', invite: 'See where your class stands and prepare in minutes.' },
  { role: 'admin', label: 'I run a school', invite: 'Set up your school and manage by exception.' },
  { role: 'parent', label: 'I am a parent', invite: 'Follow your child calmly, in plain language.' },
];

/**
 * "What brings you in today" — a few intent chips per role. One tap, never a
 * free-text interrogation. These map to interest tags in store.inferProfile.
 */
export const INTENT_CHIPS: Record<Role, string[]> = {
  student: ['Catch up on something', 'Get ahead', 'Just exploring', 'Prepare for a test'],
  teacher: ['Help my class', 'Get ahead', 'Just exploring'],
  admin: ['Set up my school', 'Just exploring'],
  parent: ['See how my child is doing', 'Just exploring'],
};

/** Subjects a learner can find interesting — a tap, not a declared preference. */
export const SUBJECT_CHOICES = ['Mathematics', 'Science', 'English', 'Social Studies'];

/** Goal chips — what the experience shapes around. */
export const GOAL_CHIPS: Record<Role, string[]> = {
  student: ['Build strong foundations', 'Reach independence', 'Enjoy the subject', 'Master the basics fast'],
  teacher: ['Build strong foundations', 'Reach independence'],
  admin: ['Build strong foundations'],
  parent: ['Build strong foundations', 'Enjoy the subject'],
};

/** Vidya's opening greeting for the welcome step — calm, not a marketing wall. */
export const WELCOME_LINE =
  'Hello. I am Vidya. Let us set up a calm space that fits you. This takes a moment, and I will learn as we go rather than asking you to fill anything in.';

/** The age tiers offered at the consent step, with their lawful labels. */
export interface AgeTierChoice {
  tier: AgeTier;
  label: string;
  note: string;
}

export const AGE_TIER_CHOICES: AgeTierChoice[] = [
  { tier: 'adult', label: '18 or older', note: 'You consent for yourself.' },
  { tier: 'teen', label: '13 to 17', note: 'A reduced profiling tier, as the law allows.' },
  { tier: 'child', label: 'Under 13', note: 'Needs a guardian. The narrowest tier — minimal personalization.' },
];

/**
 * The plain-language consent explanation Vidya shows at the consent step. The
 * profiling is transparent and revocable; it never exceeds the chosen tier.
 */
export function consentExplanation(tier: AgeTier): string {
  switch (tier) {
    case 'adult':
      return 'I will shape your experience from the choices you make as you use Classess — never from a form, and never from personal details. You can review or turn this off any time in Settings.';
    case 'teen':
      return 'I will personalise gently, within the reduced tier the law sets for your age. No personal details are used, and you can turn it off any time.';
    case 'child':
      return 'A guardian needs to agree first. Even then I keep personalization minimal and never build a behavioural profile, as the law requires for your age.';
  }
}

/** A plain tier label for the stored ConsentState. */
export function tierLabel(tier: AgeTier): string {
  switch (tier) {
    case 'adult':
      return 'Adult';
    case 'teen':
      return 'Teen (reduced tier)';
    case 'child':
      return 'Child (guardian consent)';
  }
}
