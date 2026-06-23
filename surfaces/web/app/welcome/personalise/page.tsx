import { PersonaliseFlow } from './PersonaliseFlow';

export const metadata = { title: 'A moment to personalise — Classess School' };

/**
 * The SHORT, optional personalisation that runs right after sign-up. One or two
 * natural choices (no forms), reusing the existing implicit-profiling intent, and
 * then the role home. Skippable at any point — nothing is interrogated.
 */
export default function PersonalisePage() {
  return <PersonaliseFlow />;
}
