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
import { useT, LOCALES, type Locale } from '@/lib/i18n';
import { Logo } from '@/app/_components/Logo';
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
  const { t, locale, setLocale } = useT();

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
          <Logo width={110} className="auth-logo" />
          <h1 className="display-sm auth-title">{t('personalise.title')}</h1>
          <p className="body-sm muted auth-sub">
            {t('personalise.sub')}
          </p>
        </div>

        <SpotlightCard>
          <p className="overline">{t('personalise.language')}</p>
          <div className="auth-chip-row">
            {LOCALES.map((l) => (
              <SuggestionChip
                key={l.code}
                aria-pressed={locale === l.code}
                onClick={() => setLocale(l.code as Locale)}
              >
                {l.label}
              </SuggestionChip>
            ))}
          </div>
        </SpotlightCard>

        <SpotlightCard>
          <p className="overline">{t('personalise.intent')}</p>
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
            <p className="overline">{t('personalise.subject')}</p>
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
          <p className="overline">{t('personalise.goal')}</p>
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
            {t('common.continue')}
            <Icon name="arrow-right" size="sm" />
          </Button>
          <Button variant="ghost" onClick={() => finish(true)}>
            {t('common.skipForNow')}
          </Button>
        </div>
        <p className="caption quiet">
          {t('personalise.footnote')}
        </p>
      </div>
    </main>
  );
}
