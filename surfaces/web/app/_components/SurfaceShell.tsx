'use client';

import { type ReactNode } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Icon } from '@classess/design-system';
import { Rail } from './Rail';
import { VidyaDock } from './VidyaDock';
import { useOnline } from '@/lib/useOnline';
import { useRole } from '@/lib/RoleContext';
import type { Role } from '@/lib/mock';

/**
 * The surface a page belongs to drives its accent hue. Derive it from the route
 * so /student/* always reads as the student surface (tiffany) even before the
 * role context hydrates; shared routes (home, loop, messages, content, …) fall
 * back to the active role.
 */
function surfaceFromPath(pathname: string, role: Role): Role {
  if (pathname.startsWith('/teacher')) return 'teacher';
  if (pathname.startsWith('/student')) return 'student';
  if (pathname.startsWith('/admin')) return 'admin';
  if (pathname.startsWith('/parent')) return 'parent';
  return role;
}

export interface SurfaceShellProps {
  title: string;
  eyebrow?: string;
  /** Quiet chips for the docked Vidya, shaped to this page. */
  dockChips?: string[];
  dockIntro?: string;
  children: ReactNode;
}

/**
 * The destination-page shell: the same slim rail, a top bar with the one
 * intention, the page body, and a docked, collapsible Vidya so the conversation
 * keeps driving the page. Big task -> route, Vidya stays docked.
 */
export function SurfaceShell({
  title,
  eyebrow,
  dockChips,
  dockIntro,
  children,
}: SurfaceShellProps) {
  const online = useOnline();
  const { role } = useRole();
  const pathname = usePathname();
  const surface = surfaceFromPath(pathname ?? '', role);

  return (
    // data-surface binds --accent to THIS surface's hue (the shared accent
    // contract): student -> tiffany, teacher -> cobalt, admin -> violet,
    // parent -> amber. Derived from the route so each surface keeps its own hue
    // regardless of the active role default. --signature stays reserved for the
    // brand mark + ignite.
    <div className="app-frame" data-surface={surface}>
      <Rail />

      <div className="surface">
        {!online ? (
          <div className="offline-banner" role="status">
            You are offline. This view is showing the last synced read; changes will sync when you
            reconnect.
          </div>
        ) : null}

        <div className="surface-topbar">
          <div>
            {eyebrow ? (
              <p className="overline" style={{ margin: 0 }}>
                {eyebrow}
              </p>
            ) : null}
            <h1 className="display-sm" style={{ margin: '4px 0 0' }}>
              {title}
            </h1>
          </div>
          <Link href="/" className="btn btn-ghost btn-sm row" style={{ gap: 'var(--space-2)' }}>
            <Icon name="home" size="sm" />
            Back to the conversation
          </Link>
        </div>

        <div className="surface-split">
          <div className="surface-body">
            <div className="surface-body-inner">{children}</div>
          </div>
          <VidyaDock chips={dockChips} intro={dockIntro} />
        </div>
      </div>
    </div>
  );
}
