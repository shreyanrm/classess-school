'use client';

import Link from 'next/link';
import { Avatar, Icon, Tag } from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { StatMatrix, Panel, FlagRow, HandnotePanel, SecHead } from '../_components/StudentComposed';
import { useRole } from '@/lib/RoleContext';
import { useStore } from '@/lib/useStore';
import { useT } from '@/lib/i18n/LocaleContext';
import { LOCALES } from '@/lib/i18n/dictionary';
import { tierAllowsBehavioural, defaultAppearance } from '@/lib/store';
import { ROLE_LABELS } from '@/lib/mock';

/** A plain-language label for the chosen palette + accent. */
const ACCENT_LABEL: Record<string, string> = {
  cobalt: 'Cobalt',
  tiffany: 'Tiffany',
  emerald: 'Emerald',
  violet: 'Violet',
  indigo: 'Indigo',
  cyan: 'Cyan',
};

/**
 * Profile — recomposed to the bar. A calm identity hero opens it, a count-up
 * stat matrix carries the at-a-glance facts, a structured "what is kept" frame
 * sits on the left, and a right aside holds a privacy ignite-card + the
 * consent/transparency flags + a handnote.
 *
 * The role, workspace, language, and consent tier are read LIVE from the session
 * store (the real source captured at onboarding) and the active locale provider.
 * Generic labels only: no real personal names, no PII. Identity is opaque; the
 * surface shows a role and a plain summary, never raw behavioural data. v4
 * throughout — no shadows, sharp corners, one accent.
 */
export default function ProfilePage() {
  const { role } = useRole();
  const { account, consent, school, appearance, teaching, leaveApplications } = useStore();
  const { locale } = useT();
  const label = ROLE_LABELS[role];

  const look = { ...defaultAppearance(), ...appearance };
  const paletteLabel = look.theme === 'dark' ? 'Dark' : 'Light';
  const accentLabel = look.accent ? ACCENT_LABEL[look.accent] ?? look.accent : 'Role default';
  const a11yOn = look.largeText || look.highContrast || look.reduceMotion;
  const isTeacher = role === 'teacher';
  const canRequestLeave = role === 'teacher' || role === 'student';
  const pendingLeave = (leaveApplications ?? []).length;
  const teachingPersonaSet = Boolean(teaching?.persona) || Boolean(teaching?.styles && Object.keys(teaching.styles).length);

  const workspace = school?.institution.name ?? `${label} workspace`;
  const language = LOCALES.find((l) => l.code === locale)?.label ?? 'English';
  const tierLabel = consent?.tierLabel ?? 'Consent not yet set';
  const personalizationOn = Boolean(consent?.personalization);
  const behaviouralAllowed = consent ? tierAllowsBehavioural(consent.ageTier) : false;

  const aside = (
    <>
      <div className="ignite-card reveal reveal-3">
        <div className="row-between" style={{ marginBottom: 14 }}>
          <span className="overline">Your privacy</span>
          <Icon name="check" size="sm" style={{ color: 'var(--accent)' }} />
        </div>
        <div className="who">Plain-language reads, never raw scores</div>
        <p className="body-sm" style={{ opacity: 0.82, marginTop: 8 }}>
          Classess keeps what you can do in plain language. You never see a raw composite or formula,
          and neither does anyone else. Your identity stays opaque.
        </p>
      </div>

      <Panel title="What is shared" meta={<span className="overline">consent</span>}>
        <FlagRow flag={{ icon: 'check', title: tierLabel, caption: 'The consent tier you set — transparent and revocable any time.' }} />
        <FlagRow
          flag={{
            icon: personalizationOn ? 'spark' : 'info',
            title: personalizationOn ? 'Personalization on' : 'Personalization off',
            caption: personalizationOn
              ? 'Vidya may shape help around how you work, within your tier.'
              : 'Vidya keeps help general — nothing is inferred about you.',
          }}
        />
        <FlagRow flag={{ icon: 'info', title: 'No personal data in reads', caption: 'Reads carry what you can do, never who you are.' }} />
      </Panel>

      <HandnotePanel>your reads stay yours — opaque, plain-language, revocable</HandnotePanel>
    </>
  );

  return (
    <SurfaceShell
      eyebrow="Your account"
      title="Profile"
      meta={[
        { value: label, label: 'role' },
        { label: workspace.toLowerCase() },
        { label: language.toLowerCase() },
      ]}
      tabs={[
        { label: 'Profile', active: true },
        { label: 'Settings', href: '/settings' },
      ]}
      aside={aside}
      dockIntro="This is your profile in Classess. Ask me to change a preference or explain what is kept."
      dockChips={['What does Classess keep', 'What is kept private', 'Explain my consent tier']}
    >
      <section className="reveal reveal-2">
        <div
          className="panel"
          style={{ display: 'flex', gap: 'var(--space-5)', alignItems: 'center', flexWrap: 'wrap' }}
        >
          <Avatar initials={label.slice(0, 1)} size="lg" />
          <div style={{ minWidth: 0, flex: 1 }}>
            <h2 className="display-sm" style={{ fontSize: 26, margin: 0 }}>
              {label}
            </h2>
            <p className="caption muted" style={{ marginTop: 'var(--space-2)', maxWidth: 56 + 'ch' }}>
              You are signed in to the {label.toLowerCase()} workspace. Your identity is opaque —
              tied to an account, never to behavioural data.
              {account?.demo ? ' This is a demo identity — not a verified account.' : ''}
            </p>
          </div>
          <Tag tone={account ? 'success' : 'warning'} dot>
            {account ? 'Signed in' : 'Signed out'}
          </Tag>
        </div>
      </section>

      <div style={{ marginTop: 'var(--space-6)' }}>
        <StatMatrix
          columns={3}
          stats={[
            { label: 'Role', value: label, delta: 'your seat in Classess', deltaDir: 'flat' },
            { label: 'Workspace', value: workspace, delta: 'where you work', deltaDir: 'flat' },
            { label: 'Language', value: language, delta: 'your reading language', deltaDir: 'flat' },
          ]}
        />
      </div>

      <section className="stack reveal reveal-4" style={{ marginTop: 'var(--space-6)' }}>
        <SecHead title="What is kept" meta={<span className="overline">transparency</span>} />
        <div className="set-frame">
          <div className="set-row">
            <div className="set-row-lead">
              <div className="t">Plain-language reads, not raw scores</div>
              <div className="d">
                Classess keeps what you can do in plain language. You never see a raw composite or
                formula, and neither does anyone else.
              </div>
            </div>
            <Tag tone="success" dot>Always</Tag>
          </div>
          <div className="set-row">
            <div className="set-row-lead">
              <div className="t">Consent tier</div>
              <div className="d">
                {consent
                  ? behaviouralAllowed
                    ? 'Your tier permits inferred personalization; it stays within what you consented to and is revocable any time.'
                    : 'Your tier keeps personalization minimal and non-behavioural — the narrowest, by design.'
                  : 'Set your consent in onboarding to choose what Classess may personalise. Nothing is profiled until you do.'}
              </div>
            </div>
            <Tag tone="info" dot>{tierLabel}</Tag>
          </div>
          <div className="set-row">
            <div className="set-row-lead">
              <div className="t">Personalization</div>
              <div className="d">
                Off by default. When on, Vidya shapes help around how you work — within your tier,
                never beyond it.
              </div>
            </div>
            <Tag tone={personalizationOn ? 'success' : 'neutral'} dot>
              {personalizationOn ? 'On' : 'Off'}
            </Tag>
          </div>
        </div>
      </section>

      <section className="stack reveal reveal-5" data-testid="profile-preferences" style={{ marginTop: 'var(--space-6)' }}>
        <SecHead title="Your preferences" meta={<span className="overline">at a glance</span>} />
        <p className="caption muted">A quick read of how your surface is set. Change any of these in settings.</p>
        <div className="set-frame">
          <div className="set-row">
            <div className="set-row-lead">
              <div className="t">Appearance</div>
              <div className="d">Your palette and accent. The cool subject palette only — never warm.</div>
            </div>
            <Tag tone="info" dot>{paletteLabel} · {accentLabel}</Tag>
          </div>
          <div className="set-row">
            <div className="set-row-lead">
              <div className="t">Visual accessibility</div>
              <div className="d">Larger text, higher contrast, or reduced motion when you turn them on.</div>
            </div>
            <Tag tone={a11yOn ? 'success' : 'neutral'} dot>{a11yOn ? 'On' : 'Off'}</Tag>
          </div>
          {isTeacher ? (
            <div className="set-row">
              <div className="set-row-lead">
                <div className="t">Teaching style</div>
                <div className="d">Your instructional-style defaults and the persona Vidya prepares drafts in.</div>
              </div>
              <Tag tone={teachingPersonaSet ? 'success' : 'neutral'} dot>{teachingPersonaSet ? 'Set' : 'Default'}</Tag>
            </div>
          ) : null}
          {canRequestLeave ? (
            <div className="set-row">
              <div className="set-row-lead">
                <div className="t">Leave applications</div>
                <div className="d">Requests you have sent to the approval queue, awaiting a decision.</div>
              </div>
              <Tag tone={pendingLeave > 0 ? 'info' : 'neutral'} dot>
                {pendingLeave > 0 ? `${pendingLeave} sent` : 'None'}
              </Tag>
            </div>
          ) : null}
        </div>
      </section>

      <section className="stack reveal reveal-6" style={{ marginTop: 'var(--space-6)' }}>
        <SecHead title="Account and settings" meta={<span className="overline">manage</span>} />
        <p className="caption muted">
          Change how Vidya helps you, your language, your appearance, your teaching style, or apply
          for leave from settings. Switching role re-shapes the whole workspace from the rail.
        </p>
        <div className="rec-actions">
          <Link href="/settings" className="btn btn-secondary btn-sm row" style={{ gap: 'var(--space-2)' }}>
            <Icon name="settings" size="sm" />
            Open settings
          </Link>
        </div>
      </section>
    </SurfaceShell>
  );
}
