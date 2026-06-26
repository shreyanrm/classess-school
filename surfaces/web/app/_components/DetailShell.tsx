'use client';

import { type ReactNode } from 'react';
import Link from 'next/link';
import { Icon } from '@classess/design-system';
import { SurfaceShell, type Crumb, type MetaFact, type ShellTab } from './SurfaceShell';

/* ============================================================================
   DetailShell — the reusable internal / drill-down page pattern.

   When a stage drills into one thing (a student, a topic, an assignment, an
   exam), it rides this layout: the same sticky chrome, a breadcrumb, the big
   page-head, an optional cols + 320px aside, and — always — a calm "back"
   affordance so the drill-down never strands the user. It composes SurfaceShell
   so every detail page inherits the bar automatically.
   ============================================================================ */

export interface DetailShellProps {
  /** The thing's name — the big weight-300 title. */
  title: string;
  /** A mono overline kicker above the title (the kind of thing this is). */
  eyebrow?: string;
  /** The breadcrumb trail back up to where this was opened from. */
  breadcrumb?: Crumb[];
  /** The mono meta line — the detail's facts at a glance. */
  meta?: MetaFact[];
  /** Where "back" returns to. Defaults to the parent crumb, else home. */
  backHref?: string;
  /** The back link label. */
  backLabel?: string;
  /** Extra actions, placed before the back link in the head. */
  actions?: ReactNode;
  /** A tab strip beneath the head. */
  tabs?: ShellTab[];
  /** A right rail (320px) — evidence, related, a next step. */
  aside?: ReactNode;
  children: ReactNode;
}

export function DetailShell({
  title,
  eyebrow,
  breadcrumb,
  meta,
  backHref,
  backLabel = 'Back',
  actions,
  tabs,
  aside,
  children,
}: DetailShellProps) {
  // Back returns to the last linked breadcrumb hop before the current page, else
  // to an explicit backHref, else home — a drill-down always has a way up.
  const parentHref =
    backHref ??
    [...(breadcrumb ?? [])]
      .slice(0, -1)
      .reverse()
      .find((c) => c.href)?.href ??
    '/';

  return (
    <SurfaceShell
      title={title}
      eyebrow={eyebrow}
      breadcrumb={breadcrumb}
      meta={meta}
      tabs={tabs}
      aside={aside}
      actions={
        <>
          {actions}
          <Link
            href={parentHref}
            className="btn btn-secondary btn-sm row"
            style={{ gap: 'var(--space-2)' }}
            data-testid="detail-back"
          >
            <Icon name="arrow-right" size="sm" style={{ transform: 'rotate(180deg)' }} />
            {backLabel}
          </Link>
        </>
      }
    >
      {children}
    </SurfaceShell>
  );
}
