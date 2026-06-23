import { OnboardingFlow } from './OnboardingFlow';

export const metadata = { title: 'Welcome — Classess School' };

/**
 * The first-run entry. When the store holds no account and no institution, the
 * app routes here (see app/_components/FirstRunGate). The whole flow is calm,
 * implicit, and Vidya-narrated — no questionnaire, no marketing wall.
 */
export default function WelcomePage() {
  return <OnboardingFlow />;
}
