'use client';

/* ============================================================================
   app/welcome/OnboardingFlow.tsx — the calm, implicit first-run experience.

   A docked Vidya narrates the whole way (left). The right is one calm step at a
   time. Crucially, the personalization step is conversational, not a form: the
   user makes natural choices (intent chip -> a subject that looks interesting ->
   a goal -> pace) and from those, store.inferProfile builds the profile WITHOUT
   asking a single explicit "what do you like" question. Consent is captured per
   the age tier (DPDP), transparent and revocable. At the finish, Vidya names
   what it learned, having interrogated nothing.
   ============================================================================ */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Composer, Icon, Input, SpotlightCard, SuggestionChip } from '@classess/design-system';
import { MessageThread, type ChatMessage } from '../_components/MessageThread';
import { messageId } from '../_components/respond';
import { useRole } from '@/lib/RoleContext';
import type { Role } from '@/lib/mock';
import {
  ROLE_CHOICES,
  INTENT_CHIPS,
  SUBJECT_CHOICES,
  GOAL_CHIPS,
  WELCOME_LINE,
  AGE_TIER_CHOICES,
  consentExplanation,
  tierLabel,
} from '@/lib/onboarding';
import {
  signIn,
  setAccountRole,
  setOnboardingStep,
  recordChoice,
  setConsent,
  setProfile,
  completeOnboarding,
  inferProfile,
  profileSummaryLine,
  readStore,
  maskContact,
  type AgeTier,
  type ConsentState,
  type OnboardingStep,
  type PreferredPace,
} from '@/lib/store';

const PACE_CHIPS: Array<{ pace: PreferredPace; label: string }> = [
  { pace: 'steady', label: 'Steady and supported' },
  { pace: 'brisk', label: 'Brisk, keep me moving' },
  { pace: 'deep', label: 'Slow and deep' },
];

export function OnboardingFlow() {
  const router = useRouter();
  const { setRole } = useRole();

  const [step, setStep] = useState<OnboardingStep>('welcome');
  const [role, setLocalRole] = useState<Role>('student');
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [tier, setTier] = useState<AgeTier>('adult');

  // Vidya's narration thread — she speaks at each step. No real backend; this is
  // the calm offline narration, always available.
  const [thread, setThread] = useState<ChatMessage[]>([
    { id: 'greet', role: 'vidya', text: WELCOME_LINE },
  ]);

  const said = useRef(new Set<string>(['greet']));
  function vidyaSay(key: string, text: string) {
    if (said.current.has(key)) return;
    said.current.add(key);
    setThread((prev) => [...prev, { id: messageId(), role: 'vidya', text }]);
  }

  // Mirror the step into the store so a reload resumes where the user was.
  useEffect(() => {
    setOnboardingStep(step);
  }, [step]);

  function go(next: OnboardingStep) {
    setStep(next);
  }

  // --- Step handlers -------------------------------------------------------

  function chooseRole(r: Role) {
    setLocalRole(r);
    setRole(r);
    setAccountRole(r);
    const inv = ROLE_CHOICES.find((c) => c.role === r)?.invite ?? '';
    vidyaSay(`role-${r}`, `Good. ${inv} A couple of quick taps and we are set.`);
    go('discover');
  }

  function sendOtp() {
    if (phone.replace(/\D/g, '').length < 4) return;
    setOtpSent(true);
    vidyaSay(
      'otp',
      `I have sent a code to ${maskContact(phone)}. This is a demo identity — I keep only a masked hint, never the number itself.`,
    );
  }

  function verifyOtp() {
    // Demo: accept any code. Mint a local opaque account; never store the number.
    signIn({ role, method: 'phone-otp', contactRaw: phone });
    vidyaSay('signed', 'You are in, with a demo identity that holds no personal details. Now, who are you here as.');
    go('role');
  }

  function oauth(method: 'google' | 'apple') {
    signIn({ role, method });
    vidyaSay('signed', 'You are in, with a demo identity that holds no personal details. Now, who are you here as.');
    go('role');
  }

  // Natural choices — each a single tap, recorded as implicit signal.
  function pickIntent(intent: string) {
    recordChoice({ intent });
    vidyaSay(`intent-${intent}`, intentResponse(intent));
  }
  function pickSubject(subject: string) {
    recordChoice({ subject });
    vidyaSay(`subj-${subject}`, `${subject} it is. I will keep an eye on what works for you there, and widen out as we go.`);
  }
  function pickGoal(goal: string) {
    recordChoice({ goal });
    vidyaSay(`goal-${goal}`, 'Noted. That shapes how I pace things for you.');
  }
  function pickPace(pace: PreferredPace) {
    recordChoice({ pace });
    go('consent');
    vidyaSay('to-consent', 'One last thing — a quick, honest note on how I personalise, and your say over it.');
  }

  function confirmConsent(personalization: boolean) {
    const consent: ConsentState = {
      ageTier: tier,
      // For a child, personalization stands only on a guardian's agreement.
      personalization,
      guardianConsent: tier === 'child' ? personalization : false,
      tierLabel: tierLabel(tier),
      decidedAt: new Date().toISOString(),
    };
    setConsent(consent);
    const choices = readStore().onboarding.choices;
    const profile = inferProfile(choices, consent);
    setProfile(profile, consent);
    vidyaSay('finish', profileSummaryLine(personalization ? profile : null));
    go('finish');
  }

  function finish() {
    completeOnboarding();
    router.push('/');
  }

  // Whether each discover sub-choice is made (drives the Continue affordance).
  const choices = step === 'discover' ? readStore().onboarding.choices : {};
  const discoverReady = Boolean(choices.intent && (role !== 'student' || choices.subject));

  const headline = useMemo(() => STEP_HEADLINE[step], [step]);

  return (
    <div className="app-frame">
      <aside className="vidya-dock" aria-label="Vidya" style={{ borderRight: 'var(--border-width) solid var(--border)', borderLeft: 'none' }}>
        <div className="vidya-dock-head">
          <span className="vidya-dock-title row" style={{ gap: 'var(--space-2)' }}>
            <Icon name="spark" size="sm" />
            <span className="overline" style={{ margin: 0 }}>
              Vidya
            </span>
          </span>
        </div>
        <div className="vidya-dock-body">
          <MessageThread messages={thread} />
        </div>
        <div className="vidya-dock-foot">
          <p className="caption quiet" style={{ margin: 0 }}>
            I learn from your choices as we go. I never ask you to fill in a profile.
          </p>
        </div>
      </aside>

      <main className="app-main">
        <div className="home-canvas has-thread">
          <div className="home-center" style={{ maxWidth: 640 }}>
            <div className="home-greeting" style={{ marginBottom: 'var(--space-4)' }}>
              <p className="overline">{headline.eyebrow}</p>
              <h1 className="display-sm" style={{ margin: '4px 0 0' }}>
                {headline.title}
              </h1>
            </div>

            {step === 'welcome' ? (
              <SpotlightCard padLg>
                <p className="body" style={{ color: 'var(--text-secondary)', marginTop: 0 }}>
                  Classess is a calm place to learn, teach, and run a school. There is nothing to fill
                  in here. I will shape things around the choices you make.
                </p>
                <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
                  <Button variant="accent" size="sm" onClick={() => go('sign-in')}>
                    Begin
                    <Icon name="arrow-right" size="sm" />
                  </Button>
                </div>
              </SpotlightCard>
            ) : null}

            {step === 'sign-in' ? (
              <SpotlightCard padLg>
                <p className="caption quiet" style={{ marginTop: 0 }}>
                  This is a demo identity. I mint a local, opaque id and keep only a masked hint of
                  your number — never the number, never personal details.
                </p>
                <div className="divider" />
                {!otpSent ? (
                  <>
                    <Input
                      label="Phone number"
                      hint="Any number works here — this is a demo."
                      inputMode="tel"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      placeholder="Your phone"
                    />
                    <div className="rec-actions" style={{ marginTop: 'var(--space-3)' }}>
                      <Button variant="primary" size="sm" onClick={sendOtp}>
                        Send code
                      </Button>
                    </div>
                  </>
                ) : (
                  <>
                    <Input
                      label="Enter the code"
                      hint="Any code works — this is a demo."
                      inputMode="numeric"
                      value={otp}
                      onChange={(e) => setOtp(e.target.value)}
                      placeholder="6-digit code"
                    />
                    <div className="rec-actions" style={{ marginTop: 'var(--space-3)' }}>
                      <Button variant="accent" size="sm" onClick={verifyOtp}>
                        Verify and continue
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => setOtpSent(false)}>
                        Change number
                      </Button>
                    </div>
                  </>
                )}
                <div className="divider" />
                <p className="overline">Or continue with</p>
                <div className="rec-actions">
                  <Button variant="secondary" size="sm" onClick={() => oauth('google')}>
                    Continue with Google
                  </Button>
                  <Button variant="secondary" size="sm" onClick={() => oauth('apple')}>
                    Continue with Apple
                  </Button>
                </div>
              </SpotlightCard>
            ) : null}

            {step === 'role' ? (
              <div className="stack">
                {ROLE_CHOICES.map((c) => (
                  <SpotlightCard key={c.role}>
                    <button
                      type="button"
                      className="row-between"
                      style={{ width: '100%', textAlign: 'left', background: 'none', border: 'none', cursor: 'pointer', gap: 'var(--space-4)' }}
                      onClick={() => chooseRole(c.role)}
                    >
                      <div>
                        <h3 className="body-lg" style={{ margin: 0 }}>
                          {c.label}
                        </h3>
                        <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
                          {c.invite}
                        </p>
                      </div>
                      <Icon name="arrow-right" size="sm" />
                    </button>
                  </SpotlightCard>
                ))}
              </div>
            ) : null}

            {step === 'discover' ? (
              <DiscoverStep
                role={role}
                onIntent={pickIntent}
                onSubject={pickSubject}
                onGoal={pickGoal}
                onPace={pickPace}
                ready={discoverReady}
                onContinue={() => {
                  // If pace not yet tapped, default it and move on (still implicit).
                  if (!readStore().onboarding.choices.pace) recordChoice({ pace: 'steady' });
                  go('consent');
                  vidyaSay('to-consent', 'One last thing — a quick, honest note on how I personalise, and your say over it.');
                }}
              />
            ) : null}

            {step === 'consent' ? (
              <SpotlightCard padLg>
                <p className="overline">Your age, so I stay within the law</p>
                <div className="chips" style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
                  {AGE_TIER_CHOICES.map((a) => (
                    <SuggestionChip
                      key={a.tier}
                      aria-pressed={tier === a.tier}
                      onClick={() => setTier(a.tier)}
                    >
                      {a.label}
                    </SuggestionChip>
                  ))}
                </div>
                <p className="caption quiet" style={{ marginTop: 'var(--space-2)' }}>
                  {AGE_TIER_CHOICES.find((a) => a.tier === tier)?.note}
                </p>
                <div className="divider" />
                <p className="body" style={{ color: 'var(--text-secondary)' }}>
                  {consentExplanation(tier)}
                </p>
                <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
                  <Button variant="accent" size="sm" onClick={() => confirmConsent(true)}>
                    {tier === 'child' ? 'A guardian agrees' : 'Personalise for me'}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => confirmConsent(false)}>
                    Not now
                  </Button>
                </div>
                <p className="caption quiet" style={{ marginTop: 'var(--space-3)' }}>
                  You can review or revoke this any time in Settings. Nothing here is final or hidden.
                </p>
              </SpotlightCard>
            ) : null}

            {step === 'finish' ? (
              <SpotlightCard padLg>
                <div className="row" style={{ gap: 'var(--space-3)' }}>
                  <Icon name="success" size="lg" />
                  <div>
                    <h3 className="body-lg" style={{ margin: 0 }}>
                      You are set up
                    </h3>
                    <p className="body-sm muted" style={{ marginTop: 'var(--space-2)' }}>
                      {profileSummaryLine(readStore().profile)}
                    </p>
                  </div>
                </div>
                <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
                  <Button variant="accent" size="sm" onClick={finish}>
                    Go to my home
                    <Icon name="arrow-right" size="sm" />
                  </Button>
                </div>
              </SpotlightCard>
            ) : null}
          </div>
        </div>
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// The discover step — the conversational, implicit personalization heart.
// ---------------------------------------------------------------------------

function DiscoverStep({
  role,
  onIntent,
  onSubject,
  onGoal,
  onPace,
  ready,
  onContinue,
}: {
  role: Role;
  onIntent: (v: string) => void;
  onSubject: (v: string) => void;
  onGoal: (v: string) => void;
  onPace: (v: PreferredPace) => void;
  ready: boolean;
  onContinue: () => void;
}) {
  // Local selected state for the calm pressed look; the store holds the truth.
  const [sel, setSel] = useState<{ intent?: string; subject?: string; goal?: string; pace?: PreferredPace }>({});

  return (
    <div className="stack">
      <SpotlightCard>
        <p className="overline">What brings you in today</p>
        <div className="chips" style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
          {INTENT_CHIPS[role].map((c) => (
            <SuggestionChip
              key={c}
              spark
              aria-pressed={sel.intent === c}
              onClick={() => {
                setSel((s) => ({ ...s, intent: c }));
                onIntent(c);
              }}
            >
              {c}
            </SuggestionChip>
          ))}
        </div>
      </SpotlightCard>

      {role === 'student' || role === 'parent' ? (
        <SpotlightCard>
          <p className="overline">Pick a subject that looks interesting</p>
          <div className="chips" style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
            {SUBJECT_CHOICES.map((c) => (
              <SuggestionChip
                key={c}
                aria-pressed={sel.subject === c}
                onClick={() => {
                  setSel((s) => ({ ...s, subject: c }));
                  onSubject(c);
                }}
              >
                {c}
              </SuggestionChip>
            ))}
          </div>
        </SpotlightCard>
      ) : null}

      <SpotlightCard>
        <p className="overline">What would you like to get from this</p>
        <div className="chips" style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
          {GOAL_CHIPS[role].map((c) => (
            <SuggestionChip
              key={c}
              aria-pressed={sel.goal === c}
              onClick={() => {
                setSel((s) => ({ ...s, goal: c }));
                onGoal(c);
              }}
            >
              {c}
            </SuggestionChip>
          ))}
        </div>
      </SpotlightCard>

      <SpotlightCard>
        <p className="overline">A pace that suits you</p>
        <div className="chips" style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
          {PACE_CHIPS.map((p) => (
            <SuggestionChip
              key={p.pace}
              aria-pressed={sel.pace === p.pace}
              onClick={() => {
                setSel((s) => ({ ...s, pace: p.pace }));
                onPace(p.pace);
              }}
            >
              {p.label}
            </SuggestionChip>
          ))}
        </div>
      </SpotlightCard>

      <div className="rec-actions">
        <Button variant="accent" size="sm" disabled={!ready} onClick={onContinue}>
          Continue
          <Icon name="arrow-right" size="sm" />
        </Button>
      </div>
      <p className="caption quiet">
        Each tap is a hint, not a form. I shape your space from these — you never have to describe
        yourself.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step copy + Vidya intent responses.
// ---------------------------------------------------------------------------

const STEP_HEADLINE: Record<OnboardingStep, { eyebrow: string; title: string }> = {
  welcome: { eyebrow: 'Welcome', title: 'Let us begin, calmly' },
  'sign-in': { eyebrow: 'A demo identity', title: 'Sign in to keep your space' },
  role: { eyebrow: 'Who you are here as', title: 'Choose how you will use Classess' },
  discover: { eyebrow: 'A few natural choices', title: 'Tap what fits — I will do the rest' },
  consent: { eyebrow: 'Your say, in plain words', title: 'How I personalise for you' },
  finish: { eyebrow: 'All set', title: 'Your space is ready' },
  done: { eyebrow: 'All set', title: 'Your space is ready' },
};

function intentResponse(intent: string): string {
  switch (intent) {
    case 'Get ahead':
      return 'I will keep things moving and stretch you a little. Tell me what looks interesting next.';
    case 'Catch up on something':
      return 'We will go steadily and rebuild any shaky ground first. What looks interesting to start.';
    case 'Prepare for a test':
      return 'I will keep practice tight and focused on recall. Pick a subject to centre on.';
    case 'Help my class':
      return 'I will surface where your class stands and prepare in minutes. Pick a goal that matters most.';
    case 'Set up my school':
      return 'I can draft your structure and a starter roster, all for you to approve. Pick a goal to anchor it.';
    case 'See how my child is doing':
      return 'I will keep it calm and in plain language. Pick a subject you would like to follow.';
    default:
      return 'Good. Let us see what looks interesting, with no pressure.';
  }
}
