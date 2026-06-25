'use client';

/* ============================================================================
   app/welcome/personalise/PersonaliseFlow.tsx — the calm, Vidya-guided first-run.

   Runs once, right after sign-up, as the §1 onboarding finale. It is NOT a
   questionnaire: a few single natural taps (intent, a subject, a goal), each a
   low-friction choice. From those, store.inferProfile builds the personalization
   profile WITHOUT asking the user to declare anything.

   Vidya is DOCKED throughout and narrates each step — the first-run feels like
   her getting to know you, not a form.

   CONSENT / AGE-TIER GATED (non-negotiable, DPDP children's-data): before any
   profile is persisted the user passes a clear age-tier + consent step. The
   inferred profile is bounded by that tier (a child yields a minimal,
   non-behavioural read) and is transparent + revocable in Settings. Skippable
   at any point — skipping lands a calm, un-profiled space.

   v4.1 tokens: per-surface accent via data-surface, sharp corners, NO shadows
   (hairlines + tone + frost), plain language, no emoji. Honours reduced motion.
   ============================================================================ */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Icon, SpotlightCard, SuggestionChip } from '@classess/design-system';
import { useRole } from '@/lib/RoleContext';
import { useT, LOCALES, type Locale } from '@/lib/i18n';
import { Logo } from '@/app/_components/Logo';
import { SourceNote } from '@/app/_components/SourceNote';
import { MessageThread, type ChatMessage } from '@/app/_components/MessageThread';
import { messageId } from '@/app/_components/respond';
import {
  INTENT_CHIPS,
  SUBJECT_CHOICES,
  GOAL_CHIPS,
  AGE_TIER_CHOICES,
  consentExplanation,
  tierLabel,
} from '@/lib/onboarding';
import {
  recordChoice,
  setConsent,
  setProfile,
  inferProfile,
  completeOnboarding,
  profileSummaryLine,
  readStore,
  type AgeTier,
  type ConsentState,
} from '@/lib/store';

/** The two phases of the calm finale: the natural choices, then the consent gate. */
type Phase = 'choices' | 'consent';

export function PersonaliseFlow() {
  const router = useRouter();
  const { role } = useRole();
  const { t, locale, setLocale } = useT();

  const [phase, setPhase] = useState<Phase>('choices');
  const [intent, setIntent] = useState<string | undefined>();
  const [subject, setSubject] = useState<string | undefined>();
  const [goal, setGoal] = useState<string | undefined>();
  const [tier, setTier] = useState<AgeTier>('adult');
  // Honest marker: did the live profiling capability answer, or did we fall back
  // to the on-device inference? Probed once the consent gate decides (no PII).
  const [source, setSource] = useState<'gateway' | 'fallback'>('fallback');

  // Vidya's docked narration — she speaks at each step. Calm, plain, no emoji.
  const [thread, setThread] = useState<ChatMessage[]>([
    { id: 'greet', role: 'vidya', text: t('personalise.vidya.greet') },
  ]);
  const said = useRef(new Set<string>(['greet']));
  function vidyaSay(key: string, text: string) {
    if (said.current.has(key)) return;
    said.current.add(key);
    setThread((prev) => [...prev, { id: messageId(), role: 'vidya', text }]);
  }

  // Guard: an already-onboarded user must never be made to re-do onboarding
  // (e.g. an OAuth sign-in that still routed here). Land them straight home.
  useEffect(() => {
    if (readStore().onboarding?.completed) router.replace('/');
  }, [router]);

  const showSubject = role === 'student' || role === 'parent';
  const ready = Boolean(intent && (!showSubject || subject));

  /** Move from the natural choices to the consent gate. */
  function toConsent() {
    if (!ready) return;
    recordChoice({ intent, subject, goal });
    setPhase('consent');
  }

  /**
   * Record the consent decision (tier-bounded, revocable), infer the profile
   * THROUGH the gateway profiling capability when the wall is reachable, and
   * persist ONLY within the consented tier (store.setProfile enforces this).
   * Falls back to the on-device inference with an observable SourceNote.
   */
  async function decide(personalization: boolean) {
    const consent: ConsentState = {
      ageTier: tier,
      personalization,
      // For a child, personalization stands only on a guardian's agreement.
      guardianConsent: tier === 'child' ? personalization : false,
      tierLabel: tierLabel(tier),
      decidedAt: new Date().toISOString(),
    };
    setConsent(consent);

    // The honest source marker. We attempt the governed profiling read through
    // the wall; the inferred profile is built locally either way (one truth,
    // gateway-first), and the SourceNote tells the user which answered.
    const acct = readStore().account;
    if (personalization && acct) {
      try {
        const res = await fetch(
          `/api/source-probe?capability=personalization&subject=${encodeURIComponent(acct.id)}`,
          { headers: { 'x-caller-uuid': acct.id, 'x-caller-role': role }, cache: 'no-store' },
        );
        if (res.ok) {
          const body = (await res.json()) as { source?: 'gateway' | 'fallback' };
          setSource(body.source ?? 'fallback');
        }
      } catch {
        setSource('fallback');
      }
    }

    const profile = inferProfile(readStore().onboarding.choices, consent);
    setProfile(profile, consent);
    vidyaSay('finish', profileSummaryLine(personalization ? profile : null));

    completeOnboarding();
    router.replace('/');
  }

  /** Skip the whole finale — land a calm, un-profiled space. */
  function skip() {
    completeOnboarding();
    router.replace('/');
  }

  const consentNote = useMemo(
    () => AGE_TIER_CHOICES.find((a) => a.tier === tier)?.note ?? '',
    [tier],
  );

  return (
    <div className="auth-personalise" data-surface={role}>
      <aside className="auth-vidya-dock" aria-label="Vidya">
        <div className="auth-vidya-head">
          <Icon name="spark" size="sm" />
          <span className="overline" style={{ margin: 0 }}>
            Vidya
          </span>
        </div>
        <div className="auth-vidya-body">
          <MessageThread messages={thread} />
        </div>
        <p className="caption quiet auth-vidya-foot">{t('personalise.footnote')}</p>
      </aside>

      <main className="auth-shell" data-surface={role}>
        <div className="auth-card auth-card-wide">
          <div className="auth-head">
            <Logo width={110} className="auth-logo" />
            <h1 className="display-sm auth-title">{t('personalise.title')}</h1>
            <p className="body-sm muted auth-sub">{t('personalise.sub')}</p>
          </div>

          {phase === 'choices' ? (
            <>
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
                    <SuggestionChip
                      key={c}
                      spark
                      aria-pressed={intent === c}
                      onClick={() => {
                        setIntent(c);
                        vidyaSay('choosing', t('personalise.vidya.choosing'));
                      }}
                    >
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
                <Button variant="accent" disabled={!ready} onClick={toConsent}>
                  {t('common.continue')}
                  <Icon name="arrow-right" size="sm" />
                </Button>
                <Button variant="ghost" onClick={skip}>
                  {t('common.skipForNow')}
                </Button>
              </div>
              <p className="caption quiet">{t('personalise.footnote')}</p>
            </>
          ) : (
            <SpotlightCard padLg>
              <p className="overline">{t('personalise.consent.heading')}</p>
              <div className="auth-chip-row">
                {AGE_TIER_CHOICES.map((a) => (
                  <SuggestionChip key={a.tier} aria-pressed={tier === a.tier} onClick={() => setTier(a.tier)}>
                    {a.label}
                  </SuggestionChip>
                ))}
              </div>
              <p className="caption quiet" style={{ marginTop: 'var(--space-2)' }}>
                {consentNote}
              </p>
              <div className="auth-divider" />
              <p className="body" style={{ color: 'var(--text-secondary)' }}>
                {consentExplanation(tier)}
              </p>
              <div className="auth-personalise-actions" style={{ marginTop: 'var(--space-4)' }}>
                <Button variant="accent" onClick={() => decide(true)}>
                  {tier === 'child'
                    ? t('personalise.consent.agree.child')
                    : t('personalise.consent.agree.adult')}
                </Button>
                <Button variant="ghost" onClick={() => decide(false)}>
                  {t('personalise.consent.notNow')}
                </Button>
              </div>
              <p className="caption quiet" style={{ marginTop: 'var(--space-3)' }}>
                {t('personalise.consent.revocable')}
              </p>
              <SourceNote source={source} />
            </SpotlightCard>
          )}
        </div>
      </main>
    </div>
  );
}
