'use client';

import Link from 'next/link';
import { Avatar, Cell, Icon, Matrix, Stat, Tag } from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { useRole } from '@/lib/RoleContext';
import { useStore } from '@/lib/useStore';
import { useT } from '@/lib/i18n/LocaleContext';
import { LOCALES } from '@/lib/i18n/dictionary';
import { tierAllowsBehavioural } from '@/lib/store';
import { ROLE_LABELS } from '@/lib/mock';

/**
 * Profile — a calm, plain view of who you are in Classess and what Vidya knows.
 * The role, workspace, language, and consent tier are read LIVE from the session
 * store (the real source captured at onboarding) and the active locale provider —
 * not a static placeholder. ROLE_LABELS stays a label dictionary (static display
 * copy, never live data). Generic labels only: no real personal names, no PII.
 * Identity is opaque; the surface shows a role and a plain summary, never raw
 * behavioural data. v4 throughout — no shadows, sharp corners, one accent.
 */
export default function ProfilePage() {
  const { role } = useRole();
  const { account, consent, school } = useStore();
  const { locale } = useT();
  const label = ROLE_LABELS[role];

  // Live workspace: the institution the human set up (when present), else the
  // role workspace. Never a baked-in class name.
  const workspace = school?.institution.name ?? `${label} workspace`;
  // Live language: the active locale's own-script label.
  const language = LOCALES.find((l) => l.code === locale)?.label ?? 'English';
  // Live consent: the tier captured at onboarding and whether profiling is on.
  const tierLabel = consent?.tierLabel ?? 'Consent not yet set';
  const personalizationOn = Boolean(consent?.personalization);
  const behaviouralAllowed = consent ? tierAllowsBehavioural(consent.ageTier) : false;

  return (
    <SurfaceShell
      eyebrow="Your account"
      title="Profile"
      dockIntro="This is your profile in Classess. Ask me to change a preference or explain what is kept."
      dockChips={['What does Classess keep', 'What is kept private', 'Explain my consent tier']}
    >
      <section className="stack">
        <div className="row" style={{ gap: 'var(--space-4)', alignItems: 'center' }}>
          <Avatar initials={label.slice(0, 1)} size="lg" />
          <div>
            <h2 className="body-lg" style={{ margin: 0 }}>
              {label}
            </h2>
            <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
              You are signed in to the {label.toLowerCase()} workspace. Your identity is opaque —
              tied to an account, never to behavioural data.
            </p>
          </div>
        </div>
      </section>

      <section className="stack">
        <p className="overline">At a glance</p>
        <Matrix columns={3}>
          <Cell>
            <Stat label="Role" value={label} />
          </Cell>
          <Cell>
            <Stat label="Workspace" value={workspace} />
          </Cell>
          <Cell>
            <Stat label="Language" value={language} />
          </Cell>
        </Matrix>
      </section>

      <section className="stack">
        <p className="overline">What is kept</p>
        <Matrix columns={1}>
          <Cell>
            <h3 className="body-lg" style={{ margin: 0 }}>
              Plain-language reads, not raw scores
            </h3>
            <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
              Classess keeps what you can do in plain language. You never see a raw composite or
              formula, and neither does anyone else.
            </p>
          </Cell>
        </Matrix>
        <div className="row" style={{ gap: 'var(--space-2)', flexWrap: 'wrap' }}>
          <Tag tone="success">{tierLabel}</Tag>
          <Tag tone={personalizationOn ? 'success' : 'neutral'}>
            {personalizationOn ? 'Personalization on' : 'Personalization off'}
          </Tag>
          <Tag tone="neutral">No personal data in reads</Tag>
        </div>
        <p className="caption quiet">
          {consent
            ? behaviouralAllowed
              ? 'Your tier permits inferred personalization; it stays within what you consented to and is revocable any time.'
              : 'Your tier keeps personalization minimal and non-behavioural — the narrowest, by design.'
            : 'Set your consent in onboarding to choose what Classess may personalise. Nothing is profiled until you do.'}
        </p>
      </section>

      <section className="stack">
        <p className="overline">Account and settings</p>
        <p className="caption muted">
          Change how Vidya helps you, your language, or your role from settings. Switching role
          re-shapes the whole workspace from the rail.
          {account?.demo ? ' This is a demo identity — not a verified account.' : ''}
        </p>
        <div className="rec-actions">
          <Link href="/settings" className="btn btn-secondary btn-sm">
            <Icon name="arrow-right" size="sm" />
            Open settings
          </Link>
        </div>
      </section>
    </SurfaceShell>
  );
}
