'use client';

import { type ReactNode } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Icon, SuggestionChip } from '@classess/design-system';
import { Rail } from './Rail';
import { openVidya } from './VidyaOrb';
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
  /**
   * Page-aware Vidya entry points. The old full-height dock is gone — Vidya now
   * floats as a single global orb — but these chips restore per-page context:
   * each opens the orb and seeds the conversation with that prompt (the same
   * openVidya path the role landing uses), so a destination page can route the
   * user straight into a relevant ask without bringing the dock back.
   */
  dockChips?: string[];
  /** A short, calm intro shown above the chips when present. */
  dockIntro?: string;
  children: ReactNode;
}

/**
 * The destination-page shell: the same slim rail, a top bar with the one
 * intention, and the page body. Vidya is no longer docked here — it floats as a
 * global orb on every page (app/_components/VidyaOrb, mounted in the layout) —
 * but the page's dockChips surface as a quiet row of Vidya entry points at the
 * top of the body, seeding the orb with page context.
 */
export function SurfaceShell({ title, eyebrow, dockChips, dockIntro, children }: SurfaceShellProps) {
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
          <div className="surface-topbar-inner">
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
        </div>

        <div className="surface-body">
          <div className="surface-body-inner">
            {dockChips && dockChips.length > 0 ? (
              <div className="surface-vidya-chips reveal reveal-1">
                <p className="overline" style={{ margin: 0 }}>
                  Ask Vidya
                </p>
                {dockIntro ? (
                  <p className="body-sm muted" style={{ margin: 0, maxWidth: 640 }}>
                    {dockIntro}
                  </p>
                ) : null}
                <div className="row" style={{ flexWrap: 'wrap', gap: 'var(--space-2)' }}>
                  {dockChips.map((chip) => (
                    <SuggestionChip key={chip} spark onClick={() => openVidya(chip)}>
                      {chip}
                    </SuggestionChip>
                  ))}
                </div>
              </div>
            ) : null}
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
