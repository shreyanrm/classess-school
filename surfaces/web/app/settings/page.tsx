'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Cell, Icon, Matrix, Tag } from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { useStore } from '@/lib/useStore';
import { restartOnboarding } from '@/lib/store';
import { signOut } from '@/lib/auth';
import { useT, LOCALES, type Locale } from '@/lib/i18n';

interface Toggle {
  key: string;
  title: string;
  detail: string;
  on: boolean;
}

/**
 * Settings — calm, plain controls over how Vidya and the surface behave for you.
 * Consent-gated reads and the permission ladder are visible here: nothing
 * consequential fires on its own, and behavioural data carries no personal
 * details. v4 throughout — no shadows, sharp corners, one accent.
 */
export default function SettingsPage() {
  const router = useRouter();
  const { account, consent, profile } = useStore();
  const { t, locale, setLocale } = useT();

  function reonboard() {
    restartOnboarding();
    router.push('/welcome/personalise');
  }

  function endSession() {
    void signOut().then(() => router.replace('/sign-in'));
  }

  const [toggles, setToggles] = useState<Toggle[]>([
    {
      key: 'voice',
      title: 'Voice replies',
      detail: 'Let Vidya speak answers aloud. You can always keep typing instead.',
      on: true,
    },
    {
      key: 'proactive',
      title: 'Proactive suggestions',
      detail:
        'Vidya may surface what to look at next. Nothing acts on its own — each suggestion waits for you.',
      on: true,
    },
    {
      key: 'share',
      title: 'Share my reads with my mentor',
      detail:
        'Off by default. Reads are shown in plain language only — never raw scores, never personal details.',
      on: false,
    },
  ]);

  function flip(key: string) {
    setToggles((prev) => prev.map((t) => (t.key === key ? { ...t, on: !t.on } : t)));
  }

  return (
    <SurfaceShell
      eyebrow={t('settings.eyebrow')}
      title={t('settings.title')}
      dockIntro="These settings shape how Vidya helps you. Ask me to explain any of them."
      dockChips={['What does proactive mean', 'Who can see my reads', 'Turn off voice']}
    >
      <section className="stack">
        <p className="overline">{t('settings.language')}</p>
        <p className="caption muted">{t('settings.languageHelp')}</p>
        <div className="row" style={{ gap: 'var(--space-2)', flexWrap: 'wrap' }} role="radiogroup" aria-label={t('settings.language')}>
          {LOCALES.map((l) => (
            <Button
              key={l.code}
              variant={locale === l.code ? 'primary' : 'ghost'}
              size="sm"
              role="radio"
              aria-checked={locale === l.code}
              data-testid="language-option"
              onClick={() => setLocale(l.code as Locale)}
            >
              {l.label}
            </Button>
          ))}
        </div>
      </section>

      <section className="stack">
        <p className="overline">{t('settings.howVidya')}</p>
        <Matrix columns={1}>
          {toggles.map((t) => (
            <Cell key={t.key}>
              <div className="row-between" style={{ gap: 'var(--space-4)' }}>
                <div>
                  <h3 className="body-lg" style={{ margin: 0 }}>
                    {t.title}
                  </h3>
                  <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
                    {t.detail}
                  </p>
                </div>
                <Button
                  variant={t.on ? 'primary' : 'ghost'}
                  size="sm"
                  aria-pressed={t.on}
                  onClick={() => flip(t.key)}
                >
                  {t.on ? 'On' : 'Off'}
                </Button>
              </div>
            </Cell>
          ))}
        </Matrix>
        <p className="caption quiet">
          {t('settings.behaviouralNote')}
        </p>
      </section>

      {consent ? (
        <section className="stack">
          <p className="overline">{t('settings.learned')}</p>
          <p className="caption muted">
            Built from your choices, never from a form. Transparent and revocable — this is the
            consent tier you set, and you can change or clear it any time.
          </p>
          <div className="admin-list">
            <div className="admin-list-row">
              <div className="body-sm">Consent tier</div>
              <Tag tone="info">{consent.tierLabel}</Tag>
            </div>
            <div className="admin-list-row">
              <div className="body-sm">Personalization</div>
              <Tag tone={consent.personalization ? 'success' : 'neutral'}>
                {consent.personalization ? 'On' : 'Off'}
              </Tag>
            </div>
            {profile?.preferredSubjects[0] ? (
              <div className="admin-list-row">
                <div className="body-sm">Shaped around</div>
                <Tag tone="neutral">{profile.preferredSubjects[0]}</Tag>
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      <section className="stack">
        <p className="overline">{t('settings.account')}</p>
        <div className="admin-list">
          <div className="admin-list-row">
            <div>
              <div className="body-sm">Demo identity</div>
              <div className="caption muted">
                {account ? `Opaque id, ${account.method} · holds no personal details` : 'Not signed in'}
              </div>
            </div>
            <Tag tone={account ? 'neutral' : 'warning'}>{account ? 'Signed in' : 'Signed out'}</Tag>
          </div>
        </div>
        <div className="rec-actions">
          <Button variant="secondary" size="sm" onClick={reonboard}>
            <Icon name="spark" size="sm" />
            {t('settings.reonboard')}
          </Button>
          <Button variant="ghost" size="sm" onClick={endSession}>
            {t('settings.signOut')}
          </Button>
        </div>
        <p className="caption quiet">
          Signing out clears your local demo identity and everything tied to it. Re-running
          onboarding lets me re-learn how you like to work.
        </p>
      </section>
    </SurfaceShell>
  );
}
