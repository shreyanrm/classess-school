'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Icon, Tag } from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { Panel, FlagRow, HandnotePanel, SecHead } from '../_components/StudentComposed';
import { useStore } from '@/lib/useStore';
import { restartOnboarding, setPreference, defaultPreferences, type Preferences } from '@/lib/store';
import { signOut, deleteAccount, confirmsDeletion } from '@/lib/auth';
import { useT, LOCALES, type Locale } from '@/lib/i18n';

interface Toggle {
  key: keyof Preferences;
  title: string;
  detail: string;
  on: boolean;
}

/**
 * Settings — recomposed to the bar as a STRUCTURED settings area. Each group is
 * a hairline-framed .set-frame of .set-row controls (a plain label + helper on
 * the left, the control on the right), with a right aside carrying a consent
 * ignite-card + the safety/transparency flags + a handnote.
 *
 * Calm, plain controls over how Vidya and the surface behave for you.
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
    void deleteAccount().finally(() => {
      router.replace('/sign-in?farewell=1');
    });
  }

  const toggles: Toggle[] = [
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
    setPreference(key, !on);
  }

  const aside = (
    <>
      <div className="ignite-card reveal reveal-3">
        <div className="row-between" style={{ marginBottom: 14 }}>
          <span className="overline">Your control</span>
          <Icon name="check" size="sm" style={{ color: 'var(--accent)' }} />
        </div>
        <div className="who">Nothing fires on its own</div>
        <p className="body-sm" style={{ opacity: 0.82, marginTop: 8 }}>
          Every consequential step waits for you. These settings shape how Vidya helps — they are
          transparent, and revocable any time.
        </p>
      </div>

      <Panel title="What this protects" meta={<span className="overline">safety</span>}>
        <FlagRow flag={{ icon: 'check', title: 'Plain-language reads', caption: 'No raw scores or formulas — to you or anyone.' }} />
        <FlagRow flag={{ icon: 'info', title: 'Behavioural data is anonymised', caption: 'It carries no personal details and is revocable.' }} />
        <FlagRow flag={{ icon: 'target', title: 'The permission ladder', caption: 'Consequential actions always ask before acting.' }} />
      </Panel>

      <HandnotePanel>turn proactive on if you want me to surface what is next</HandnotePanel>
    </>
  );

  return (
    <SurfaceShell
      eyebrow={t('settings.eyebrow')}
      title={t('settings.title')}
      meta={[
        { label: account ? 'signed in' : 'signed out' },
        { label: (consent?.tierLabel ?? 'consent not set').toLowerCase() },
        { label: locale === 'en' ? 'english' : locale },
      ]}
      tabs={[
        { label: 'Settings', active: true },
        { label: 'Profile', href: '/profile' },
      ]}
      aside={aside}
      dockIntro="These settings shape how Vidya helps you. Ask me to explain any of them."
      dockChips={['What does proactive mean', 'Who can see my reads', 'Turn off voice']}
    >
      <section className="stack reveal reveal-2">
        <SecHead title={t('settings.language')} meta={<span className="overline">reading language</span>} />
        <p className="caption muted">{t('settings.languageHelp')}</p>
        <div
          className="row"
          style={{ gap: 'var(--space-2)', flexWrap: 'wrap' }}
          role="radiogroup"
          aria-label={t('settings.language')}
        >
          {LOCALES.map((l) => (
            <Button
              key={l.code}
              variant={locale === l.code ? 'primary' : 'secondary'}
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

      <section className="stack reveal reveal-3" style={{ marginTop: 'var(--space-6)' }}>
        <SecHead title={t('settings.howVidya')} meta={<span className="overline">vidya</span>} />
        <div className="set-frame">
          {toggles.map((tg) => (
            <div className="set-row" key={tg.key}>
              <div className="set-row-lead">
                <div className="t">{tg.title}</div>
                <div className="d">{tg.detail}</div>
              </div>
              <Button
                variant={tg.on ? 'primary' : 'secondary'}
                size="sm"
                aria-pressed={tg.on}
                onClick={() => flip(tg.key, tg.on)}
              >
                {tg.on ? 'On' : 'Off'}
              </Button>
            </div>
          ))}
        </div>
        <p className="caption quiet">{t('settings.behaviouralNote')}</p>
      </section>

      {consent ? (
        <section className="stack reveal reveal-4" style={{ marginTop: 'var(--space-6)' }}>
          <SecHead title={t('settings.learned')} meta={<span className="overline">consent</span>} />
          <p className="caption muted">
            Built from your choices, never from a form. Transparent and revocable — this is the
            consent tier you set, and you can change or clear it any time.
          </p>
          <div className="set-frame">
            <div className="set-row">
              <div className="set-row-lead">
                <div className="t">Consent tier</div>
                <div className="d">The tier you set at onboarding. It scopes everything Vidya may infer.</div>
              </div>
              <Tag tone="info" dot>{consent.tierLabel}</Tag>
            </div>
            <div className="set-row">
              <div className="set-row-lead">
                <div className="t">Personalization</div>
                <div className="d">Whether Vidya may shape help around how you work, within your tier.</div>
              </div>
              <Tag tone={consent.personalization ? 'success' : 'neutral'} dot>
                {consent.personalization ? 'On' : 'Off'}
              </Tag>
            </div>
            {profile?.preferredSubjects[0] ? (
              <div className="set-row">
                <div className="set-row-lead">
                  <div className="t">Shaped around</div>
                  <div className="d">A preference you shared — used only to make help more relevant.</div>
                </div>
                <Tag tone="neutral" dot>{profile.preferredSubjects[0]}</Tag>
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      <section className="stack reveal reveal-5" style={{ marginTop: 'var(--space-6)' }}>
        <SecHead title={t('settings.account')} meta={<span className="overline">session</span>} />
        <div className="set-frame">
          <div className="set-row">
            <div className="set-row-lead">
              <div className="t">Demo identity</div>
              <div className="d">
                {account ? `Opaque id, ${account.method} · holds no personal details` : 'Not signed in'}
              </div>
            </div>
            <Tag tone={account ? 'neutral' : 'warning'} dot>{account ? 'Signed in' : 'Signed out'}</Tag>
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

      <section className="stack reveal reveal-6" data-testid="delete-account" style={{ marginTop: 'var(--space-6)' }}>
        <SecHead title="Delete account" meta={<span className="overline">permanent</span>} />
        <p className="caption muted">
          A quiet, permanent step. When you delete your account, your identity and personal details
          are erased. Your anonymised learning history — which holds no personal data — is kept so
          the school records stay consistent. This cannot be undone.
        </p>

        {!confirming ? (
          <div className="rec-actions">
            <Button variant="danger" size="sm" data-testid="delete-account-open" onClick={requestDelete}>
              Delete my account
            </Button>
          </div>
        ) : (
          <div className="set-frame" data-testid="delete-account-confirm" style={{ padding: 'var(--space-5)' }}>
            <p className="caption">
              To confirm, type <strong>DELETE</strong> below. We will erase your identity and personal
              details and sign you out. Your anonymised learning history is retained and becomes
              un-attributable.
            </p>
            <label className="field-label" htmlFor="delete-confirm-input" style={{ marginTop: 'var(--space-3)' }}>
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
            <div className="rec-actions" style={{ marginTop: 'var(--space-3)' }}>
              <Button variant="ghost" size="sm" onClick={cancelDelete} disabled={deleting}>
                Keep my account
              </Button>
              <Button
                variant="danger"
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
