'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Icon, Tag, type SubjectAccent } from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { Panel, FlagRow, HandnotePanel, SecHead } from '../_components/StudentComposed';
import { LeaveApplyForm } from '../_components/LeaveApplyForm';
import { useStore } from '@/lib/useStore';
import { useRole } from '@/lib/RoleContext';
import {
  restartOnboarding,
  setPreference,
  defaultPreferences,
  defaultTeachingPreferences,
  defaultAppearance,
  setTeachingStyle,
  setTeachingPersona,
  setAppearance,
  type Preferences,
  type TeachingStyleKey,
  type TeachingPersona,
} from '@/lib/store';
import { signOut, deleteAccount, confirmsDeletion } from '@/lib/auth';
import { useT, LOCALES, type Locale } from '@/lib/i18n';

/* ── Teaching preferences — the instructional-style options, per surface ───── */

interface StyleGroup {
  key: TeachingStyleKey;
  title: string;
  detail: string;
  /** The style options for this surface — the default is the first one. */
  options: Array<{ id: string; label: string }>;
}

const TEACHING_STYLES: StyleGroup[] = [
  {
    key: 'homework',
    title: 'Homework',
    detail: 'How homework drafts are shaped before you send them.',
    options: [
      { id: 'scaffolded', label: 'Scaffolded' },
      { id: 'practice', label: 'Practice-heavy' },
      { id: 'exam-style', label: 'Exam-style' },
      { id: 'project-led', label: 'Project-led' },
    ],
  },
  {
    key: 'structured',
    title: 'Structured plans',
    detail: 'How a structured study plan is laid out.',
    options: [
      { id: 'step-by-step', label: 'Step by step' },
      { id: 'outcome-first', label: 'Outcome-first' },
      { id: 'spiral', label: 'Spiral revisit' },
    ],
  },
  {
    key: 'oral',
    title: 'Oral checks',
    detail: 'How a quick oral check is prepared.',
    options: [
      { id: 'conversational', label: 'Conversational' },
      { id: 'rapid-recall', label: 'Rapid recall' },
      { id: 'explain-back', label: 'Explain-it-back' },
    ],
  },
  {
    key: 'worksheet',
    title: 'Worksheets',
    detail: 'The default shape of a generated worksheet.',
    options: [
      { id: 'mixed', label: 'Mixed format' },
      { id: 'mcq', label: 'MCQ-led' },
      { id: 'short-answer', label: 'Short-answer' },
      { id: 'application', label: 'Application' },
    ],
  },
  {
    key: 'testPaper',
    title: 'Test papers',
    detail: 'How a prepared test paper is weighted across sections.',
    options: [
      { id: 'balanced', label: 'Balanced' },
      { id: 'concept-heavy', label: 'Concept-heavy' },
      { id: 'application-heavy', label: 'Application-heavy' },
    ],
  },
  {
    key: 'lessonPlan',
    title: 'Lesson plans',
    detail: 'The default rhythm of a prepared lesson plan.',
    options: [
      { id: 'inquiry', label: 'Inquiry-led' },
      { id: 'direct', label: 'Direct instruction' },
      { id: 'activity', label: 'Activity-led' },
    ],
  },
  {
    key: 'substitution',
    title: 'Substitution notes',
    detail: 'How a hand-off note for a covering teacher reads.',
    options: [
      { id: 'detailed', label: 'Detailed' },
      { id: 'essentials', label: 'Just essentials' },
      { id: 'self-run', label: 'Self-running' },
    ],
  },
];

const PERSONA_OPTIONS: Array<{ id: TeachingPersona; label: string; note: string }> = [
  { id: 'warm-mentor', label: 'Warm mentor', note: 'Encouraging, patient, plain.' },
  { id: 'plain-coach', label: 'Plain coach', note: 'Direct and to the point.' },
  { id: 'socratic-guide', label: 'Socratic guide', note: 'Asks before it tells.' },
  { id: 'brisk-examiner', label: 'Brisk examiner', note: 'Crisp, exam-focused.' },
];

/* ── Appearance — theme palette + cool subject-accent tints ────────────────── */

const ACCENT_OPTIONS: Array<{ id: SubjectAccent; label: string }> = [
  { id: 'cobalt', label: 'Cobalt' },
  { id: 'tiffany', label: 'Tiffany' },
  { id: 'emerald', label: 'Emerald' },
  { id: 'violet', label: 'Violet' },
  { id: 'indigo', label: 'Indigo' },
  { id: 'cyan', label: 'Cyan' },
];

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
  const { account, consent, profile, preferences, teaching, appearance } = useStore();
  const { role } = useRole();
  const prefs: Preferences = { ...defaultPreferences(), ...preferences };
  const teach = { ...defaultTeachingPreferences(), ...teaching };
  const look = { ...defaultAppearance(), ...appearance };
  const { t, locale, setLocale } = useT();

  // Who is leave for: teachers/admins apply as staff, students as students.
  const leaveWho: 'staff' | 'student' = role === 'student' ? 'student' : 'staff';
  const canRequestLeave = role === 'teacher' || role === 'student';
  const isTeacher = role === 'teacher';

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
      dockIntro="These settings shape how Vidya helps you, how the surface looks, and how to apply for leave. Ask me to explain any of them."
      dockChips={[
        isTeacher ? 'Set my homework style' : 'Apply for leave',
        'Switch to a dark palette',
        canRequestLeave ? 'Where does my leave go' : 'Who can see my reads',
      ]}
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

      {isTeacher ? (
        <section className="stack reveal reveal-3" data-testid="teaching-preferences" style={{ marginTop: 'var(--space-6)' }}>
          <SecHead title="Teaching preferences" meta={<span className="overline">instructional style</span>} />
          <p className="caption muted">
            How Vidya shapes the drafts it prepares for you — homework, plans, worksheets, papers, and
            hand-off notes. These set the shape of a draft; nothing is sent, graded, or applied on its
            own. The permission ladder still holds.
          </p>

          <div className="set-frame">
            {TEACHING_STYLES.map((g) => {
              const current = teach.styles[g.key] ?? g.options[0]?.id;
              return (
                <div className="set-row" key={g.key}>
                  <div className="set-row-lead">
                    <div className="t">{g.title}</div>
                    <div className="d">{g.detail}</div>
                  </div>
                  <div
                    className="row"
                    style={{ gap: 'var(--space-2)', flexWrap: 'wrap', justifyContent: 'flex-end' }}
                    role="radiogroup"
                    aria-label={`${g.title} style`}
                  >
                    {g.options.map((o) => (
                      <Button
                        key={o.id}
                        variant={current === o.id ? 'primary' : 'secondary'}
                        size="sm"
                        role="radio"
                        aria-checked={current === o.id}
                        data-testid="teaching-style-option"
                        onClick={() => setTeachingStyle(g.key, o.id)}
                      >
                        {o.label}
                      </Button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>

          <SecHead title="Project persona" meta={<span className="overline">voice</span>} />
          <p className="caption muted">The calm voice Vidya writes your prepared drafts in.</p>
          <div className="set-frame">
            {PERSONA_OPTIONS.map((p) => (
              <div className="set-row" key={p.id}>
                <div className="set-row-lead">
                  <div className="t">{p.label}</div>
                  <div className="d">{p.note}</div>
                </div>
                <Button
                  variant={teach.persona === p.id ? 'primary' : 'secondary'}
                  size="sm"
                  aria-pressed={teach.persona === p.id}
                  data-testid="teaching-persona-option"
                  onClick={() => setTeachingPersona(p.id)}
                >
                  {teach.persona === p.id ? 'Chosen' : 'Choose'}
                </Button>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="stack reveal reveal-4" data-testid="appearance" style={{ marginTop: 'var(--space-6)' }}>
        <SecHead title="Appearance" meta={<span className="overline">theme · accent · access</span>} />
        <p className="caption muted">
          A calm light or dark palette, an optional cool accent, and a visual-accessibility mode. The
          whole surface re-skins from here and your choice survives a reload.
        </p>

        <div className="set-frame">
          <div className="set-row">
            <div className="set-row-lead">
              <div className="t">Palette</div>
              <div className="d">Light or dark. Only the calm token layer flips — the structure never changes.</div>
            </div>
            <div className="row" style={{ gap: 'var(--space-2)' }} role="radiogroup" aria-label="Palette">
              {(['light', 'dark'] as const).map((th) => (
                <Button
                  key={th}
                  variant={look.theme === th ? 'primary' : 'secondary'}
                  size="sm"
                  role="radio"
                  aria-checked={look.theme === th}
                  data-testid="theme-option"
                  onClick={() => setAppearance('theme', th)}
                >
                  {th === 'light' ? 'Light' : 'Dark'}
                </Button>
              ))}
            </div>
          </div>

          <div className="set-row">
            <div className="set-row-lead">
              <div className="t">Accent</div>
              <div className="d">A cool signature hue for this surface, or keep your role’s own. Cool palette only — never warm.</div>
            </div>
            <div
              className="row"
              style={{ gap: 'var(--space-2)', flexWrap: 'wrap', justifyContent: 'flex-end' }}
              role="radiogroup"
              aria-label="Accent"
            >
              <Button
                variant={!look.accent ? 'primary' : 'secondary'}
                size="sm"
                role="radio"
                aria-checked={!look.accent}
                data-testid="accent-option"
                onClick={() => setAppearance('accent', undefined)}
              >
                Role default
              </Button>
              {ACCENT_OPTIONS.map((a) => (
                <Button
                  key={a.id}
                  variant={look.accent === a.id ? 'primary' : 'secondary'}
                  size="sm"
                  role="radio"
                  aria-checked={look.accent === a.id}
                  data-testid="accent-option"
                  onClick={() => setAppearance('accent', a.id)}
                >
                  <span
                    aria-hidden
                    style={{
                      display: 'inline-block',
                      width: 9,
                      height: 9,
                      borderRadius: '50%',
                      background: `var(--${a.id})`,
                      marginRight: 6,
                      verticalAlign: 'middle',
                    }}
                  />
                  {a.label}
                </Button>
              ))}
            </div>
          </div>
        </div>

        <SecHead title="Visual accessibility" meta={<span className="overline">comfort</span>} />
        <div className="set-frame">
          {([
            { key: 'largeText' as const, title: 'Larger text', detail: 'Increase the reading size without breaking the layout.' },
            { key: 'highContrast' as const, title: 'Higher contrast', detail: 'Firmer text and hairlines for easier reading.' },
            { key: 'reduceMotion' as const, title: 'Reduce motion', detail: 'Turn animation down. Your device setting still applies on its own.' },
          ]).map((tg) => {
            const on = look[tg.key];
            return (
              <div className="set-row" key={tg.key}>
                <div className="set-row-lead">
                  <div className="t">{tg.title}</div>
                  <div className="d">{tg.detail}</div>
                </div>
                <Button
                  variant={on ? 'primary' : 'secondary'}
                  size="sm"
                  aria-pressed={on}
                  data-testid="a11y-toggle"
                  onClick={() => setAppearance(tg.key, !on)}
                >
                  {on ? 'On' : 'Off'}
                </Button>
              </div>
            );
          })}
        </div>
      </section>

      {canRequestLeave ? (
        <section className="stack reveal reveal-5" data-testid="leave-application" style={{ marginTop: 'var(--space-6)' }}>
          <SecHead title="Leave application" meta={<span className="overline">routes to approval</span>} />
          <p className="caption muted">
            Apply for leave here. Your request routes to the approval queue via the permission ladder —
            a coordinator clears a short leave, the principal holds a longer one. Nothing is approved on
            its own, and you will see the outcome here.
          </p>
          <LeaveApplyForm who={leaveWho} />
        </section>
      ) : null}

      {consent ? (
        <section className="stack reveal reveal-6" style={{ marginTop: 'var(--space-6)' }}>
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

      <section className="stack reveal reveal-7" style={{ marginTop: 'var(--space-6)' }}>
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

      <section className="stack reveal reveal-8" data-testid="delete-account" style={{ marginTop: 'var(--space-6)' }}>
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
