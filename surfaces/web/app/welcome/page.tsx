import { OnboardingFlow } from './OnboardingFlow';

export const metadata = { title: 'Welcome — Classess School' };

/**
 * The WELCOME preamble — the very first screen, shown BEFORE sign-in. It
 * introduces Vidya and the shape of the flow (sign in → who you are → a couple
 * of natural taps), then hands to the one modern auth flow at (auth). Calm and
 * conversational; nothing is interrogated, no marketing wall. The implicit
 * personalisation finale lives at /welcome/personalise.
 */
export default function WelcomePage() {
  return <OnboardingFlow />;
}
