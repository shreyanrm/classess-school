'use client';

/* ============================================================================
   app/welcome/personalise/PersonaliseFlow.tsx — the short, optional personalise.

   Runs once, right after sign-up. It is NOT a questionnaire: one intent tap and
   (for learners/parents) one subject tap, each a single natural choice. From
   those, store.inferProfile builds the personalization profile WITHOUT asking the
   user to declare anything. Consent defaults to the adult tier with personalization
   on; it stays transparent and revocable in Settings. Skippable at any point.

   v4: per-surface accent via data-surface, sharp corners, no shadows, plain
   language, no emoji.
   ============================================================================ */

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Icon, SpotlightCard, SuggestionChip } from '@classess/design-system';
import { useRole } from '@/lib/RoleContext';
import { INTENT_CHIPS, SUBJECT_CHOICES, GOAL_CHIPS, tierLabel } from '@/lib/onboarding';
import {
  recordChoice,
  setConsent,
  setProfile,
  inferProfile,
  completeOnboarding,
  readStore,
  type ConsentState,
} from '@/lib/store';

export function PersonaliseFlow() {
  const router = useRouter();
  const { role } = useRole();

  const [intent, setIntent] = useState<string | undefined>();
  const [subject, setSubject] = useState<string | undefined>();
  const [goal, setGoal] = useState<string | undefined>();

  // Guard: an already-onboarded user must never be made to re-do onboarding
  // (e.g. an OAuth sign-in that still routed here). Land them straight home.
  useEffect(() => {
    if (readStore().onboarding?.completed) router.replace('/');
  }, [router]);

  const showSubject = role === 'student' || role === 'parent';
  const ready = Boolean(intent && (!showSubject || subject));

  /** Persist the natural choices, infer the profile, finish, and land home. */
  function finish(skip = false) {
    if (!skip) {
      recordChoice({ intent, subject, goal });
      const consent: ConsentState = {
        ageTier: 'adult',
        personalization: true,
        guardianConsent: false,
        tierLabel: tierLabel('adult'),
        decidedAt: new Date().toISOString(),
      };
      setConsent(consent);
      const profile = inferProfile(readStore().onboarding.choices, consent);
      setProfile(profile, consent);
    }
    completeOnboarding();
    router.replace('/');
  }

  return (
    <main className="auth-shell" data-surface={role}>
      <div className="auth-card auth-card-wide">
        <div className="auth-head">
          <span className="auth-mark" aria-hidden="true">
            C
          </span>
          <h1 className="display-sm auth-title">A moment to shape your space</h1>
          <p className="body-sm muted auth-sub">
            A couple of natural taps, never a form. You can change any of this later in Settings.
          </p>
        </div>

        <SpotlightCard>
          <p className="overline">What brings you in today</p>
          <div className="auth-chip-row">
            {INTENT_CHIPS[role].map((c) => (
              <SuggestionChip key={c} spark aria-pressed={intent === c} onClick={() => setIntent(c)}>
                {c}
              </SuggestionChip>
            ))}
          </div>
        </SpotlightCard>

        {showSubject ? (
          <SpotlightCard>
            <p className="overline">Pick a subject that looks interesting</p>
            <div className="auth-chip-row">
              {SUBJECT_CHOICES.map((c) => (
                <SuggestionChip key={c} aria-pressed={subject === c} onClick={() => setSubject(c)}>
                  {c}
                </SuggestionChip>
              ))}
            </div>
          </SpotlightCard>
        ) : null}

        <SpotlightCard>
          <p className="overline">What would you like to get from this</p>
          <div className="auth-chip-row">
            {GOAL_CHIPS[role].map((c) => (
              <SuggestionChip key={c} aria-pressed={goal === c} onClick={() => setGoal(c)}>
                {c}
              </SuggestionChip>
            ))}
          </div>
        </SpotlightCard>

        <div className="auth-personalise-actions">
          <Button variant="accent" disabled={!ready} onClick={() => finish(false)}>
            Continue
            <Icon name="arrow-right" size="sm" />
          </Button>
          <Button variant="ghost" onClick={() => finish(true)}>
            Skip for now
          </Button>
        </div>
        <p className="caption quiet">
          Each tap is a hint, not a form. I shape your space from these — you never have to describe
          yourself.
        </p>
      </div>
    </main>
  );
}
