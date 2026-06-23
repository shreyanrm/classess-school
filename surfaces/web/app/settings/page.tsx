'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Cell, Icon, Matrix, Tag } from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { useStore } from '@/lib/useStore';
import { restartOnboarding, setPreference, defaultPreferences, type Preferences } from '@/lib/store';
import { signOut, deleteAccount, confirmsDeletion } from '@/lib/auth';
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
  const { account, consent, profile, preferences } = useStore();
  const prefs: Preferences = { ...defaultPreferences(), ...preferences };
  const { t, locale, setLocale } = useT();

  function reonboard() {
    restartOnboarding();
    router.push('/welcome/personalise');
  }

  function endSession() {
    void signOut().then(() => router.replace('/sign-in'));
  }

  // The Delete-account confirm gate. Step 1 is a quiet control; step 2 explains
  // in plain language what happens and requires the explicit word DELETE before
  // the erasure can run. Nothing consequential fires on its own.
  const [confirming, setConfirming] = useState(false);
  const [confirmText, setConfirmText] = useState('');
  const [deleting, setDeleting] = useState(false);
  const canDelete = confirmsDeletion(confirmText);

  function requestDelete() {
    setConfirming(true);
  }

  function cancelDelete() {
    setConfirming(false);
    setConfirmText('');
  }

  function runDelete() {
    if (!canDelete || deleting) return;
    setDeleting(true);
    // The route severs identity + PII server-side; deleteAccount always clears
    // local state, so the farewell + redirect work even on the degraded path.
    void deleteAccount().finally(() => {
      router.replace('/sign-in?farewell=1');
    });
  }

  const toggles: Array<Toggle & { key: keyof Preferences }> = [
    {
      key: 'voice',
      title: 'Voice replies',
      detail: 'Let Vidya speak answers aloud. You can always keep typing instead.',
      on: prefs.voice,
    },
    {
      key: 'proactive',
      title: 'Proactive suggestions',
      detail:
        'Vidya may surface what to look at next. Nothing acts on its own — each suggestion waits for you.',
      on: prefs.proactive,
    },
    {
      key: 'shareReads',
      title: 'Share my reads with my mentor',
      detail:
        'Off by default. Reads are shown in plain language only — never raw scores, never personal details.',
      on: prefs.shareReads,
    },
  ];

  function flip(key: keyof Preferences, on: boolean) {
    // Persist to the store so the choice survives reload and other surfaces read it.
    setPreference(key, !on);
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
                  onClick={() => flip(t.key, t.on)}
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

      <section className="stack" data-testid="delete-account">
        <p className="overline">Delete account</p>
        <p className="caption muted">
          A quiet, permanent step. When you delete your account, your identity and personal
          details are erased. Your anonymised learning history — which holds no personal data —
          is kept so the school records stay consistent. This cannot be undone.
        </p>

        {!confirming ? (
          <div className="rec-actions">
            <Button
              variant="ghost"
              size="sm"
              data-testid="delete-account-open"
              onClick={requestDelete}
            >
              Delete my account
            </Button>
          </div>
        ) : (
          <div className="admin-list" data-testid="delete-account-confirm">
            <p className="caption">
              To confirm, type <strong>DELETE</strong> below. We will erase your identity and
              personal details and sign you out. Your anonymised learning history is retained and
              becomes un-attributable.
            </p>
            <label className="caption muted" htmlFor="delete-confirm-input">
              Type DELETE to confirm
            </label>
            <input
              id="delete-confirm-input"
              data-testid="delete-account-input"
              className="input"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder="DELETE"
              autoComplete="off"
              aria-label="Type DELETE to confirm account deletion"
            />
            <div className="rec-actions">
              <Button variant="ghost" size="sm" onClick={cancelDelete} disabled={deleting}>
                Keep my account
              </Button>
              <Button
                variant="primary"
                size="sm"
                data-testid="delete-account-confirm-button"
                disabled={!canDelete || deleting}
                onClick={runDelete}
              >
                {deleting ? 'Erasing…' : 'Erase my account'}
              </Button>
            </div>
          </div>
        )}
      </section>
    </SurfaceShell>
  );
}
