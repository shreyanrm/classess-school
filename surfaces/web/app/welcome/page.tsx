import { OnboardingFlow } from './OnboardingFlow';

export const metadata = { title: 'Welcome — Classess School' };

/**
 * The legacy implicit-profiling onboarding (kept reachable for the admin
 * school-setup narrative). The primary first-run is now the familiar auth flow
 * (/sign-in, /sign-up) gated by app/_components/AuthGate, with the short
 * personalise step at /welcome/personalise. The whole flow stays calm, implicit,
 * and Vidya-narrated — no questionnaire, no marketing wall.
 */
export default function WelcomePage() {
  return <OnboardingFlow />;
}
