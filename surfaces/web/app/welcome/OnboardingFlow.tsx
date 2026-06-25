'use client';

/* ============================================================================
   app/welcome/OnboardingFlow.tsx — the WELCOME preamble (the very first screen).

   This is the §1 entry point: a calm, conversational introduction that runs
   BEFORE sign-in. It introduces Vidya and the shape of what follows (sign in,
   say who you are, a couple of natural taps), then hands off to the one modern
   auth flow at (auth). It interrogates nothing and shows no marketing wall.

   The legacy duplicate auth (a second phone-OTP / role / discover / consent
   stack that used to live here) is RETIRED — there is now exactly one auth flow
   (app/(auth)/AuthForm) and one implicit-profiling step (/welcome/personalise).

   Vidya is present and guiding here too: a living orb that drifts + breathes
   (the same visual vocabulary as the global orb) introduces herself in plain
   language. An already-signed-in visitor is sent straight home.

   v4.1 tokens only · GPU-only motion (transform/opacity), eased cubic-bezier
   (0.2,0,0,1), staggered reveal · NO shadows (hairlines + tone + frost) · honours
   prefers-reduced-motion (renders the resolved end-state) · no emoji.
   ============================================================================ */

import { useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Button, Icon } from '@classess/design-system';
import { useAuth } from '@/lib/useAuth';
import { useT } from '@/lib/i18n';
import { Logo } from '@/app/_components/Logo';

/** The three calm beats of what follows — Vidya narrating the shape of it. */
const STEP_KEYS = ['signIn', 'role', 'shape'] as const;

export function OnboardingFlow() {
  const router = useRouter();
  const { session, loading } = useAuth();
  const { t } = useT();

  // A returning, already-signed-in visitor never sees the preamble — straight home.
  useEffect(() => {
    if (!loading && session) router.replace('/');
  }, [loading, session, router]);

  return (
    <main className="welcome-shell">
      {/* The living presence — Vidya as a drifting, breathing orb (not the global
          orb, which is hidden on this route; this is her introducing herself). */}
      <div className="welcome-hero">
        <span className="welcome-orb" aria-hidden="true">
          <span className="welcome-orb-ring" />
          <span className="welcome-orb-core" />
          <span className="welcome-orb-glass" />
        </span>

        <Logo width={132} className="welcome-logo" />

        <h1 className="display-sm welcome-title">{t('welcome.title')}</h1>
        <p className="body-lg welcome-lede">{t('welcome.lede')}</p>

        {/* The shape of what follows — a calm three-beat, staggered in. Each beat
            mirrors a real step (sign in → role → a couple of natural taps). */}
        <ol className="welcome-beats" aria-label={t('welcome.beatsLabel')}>
          {STEP_KEYS.map((key, i) => (
            <li
              key={key}
              className="welcome-beat"
              style={{ ['--i' as string]: i } as React.CSSProperties}
            >
              <span className="welcome-beat-index overline" aria-hidden="true">
                {String(i + 1).padStart(2, '0')}
              </span>
              <span className="welcome-beat-text body-sm">{t(`welcome.beat.${key}`)}</span>
            </li>
          ))}
        </ol>

        <div className="welcome-actions">
          <Button variant="accent" onClick={() => router.push('/sign-up')}>
            {t('welcome.begin')}
            <Icon name="arrow-right" size="sm" />
          </Button>
          <p className="caption muted welcome-switch">
            {t('welcome.haveAccount')}{' '}
            <Link href="/sign-in" className="auth-link">
              {t('common.signIn')}
            </Link>
          </p>
        </div>

        <p className="caption quiet welcome-foot">{t('welcome.foot')}</p>
      </div>
    </main>
  );
}
