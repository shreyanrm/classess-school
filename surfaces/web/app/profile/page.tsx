'use client';

import Link from 'next/link';
import { Avatar, Cell, Icon, Matrix, Stat, Tag } from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { useRole } from '@/lib/RoleContext';
import { ROLE_LABELS } from '@/lib/mock';

/**
 * Profile — a calm, plain view of who you are in Classess and what Vidya knows.
 * Generic labels only: no real personal names, no PII. Identity is opaque; the
 * surface shows a role and a plain summary, never raw behavioural data. v4
 * throughout — no shadows, sharp corners, one accent.
 */
export default function ProfilePage() {
  const { role } = useRole();
  const label = ROLE_LABELS[role];

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
            <Stat label="Workspace" value="Class 10-B" />
          </Cell>
          <Cell>
            <Stat label="Language" value="English" />
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
        <div className="row" style={{ gap: 'var(--space-2)' }}>
          <Tag tone="success">Consent-gated</Tag>
          <Tag tone="neutral">No personal data in reads</Tag>
        </div>
      </section>

      <section className="stack">
        <p className="overline">Account and settings</p>
        <p className="caption muted">
          Change how Vidya helps you, your language, or your role from settings. Switching role
          re-shapes the whole workspace from the rail.
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
