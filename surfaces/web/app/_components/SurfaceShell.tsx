'use client';

import { type ReactNode } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Icon, SuggestionChip, useTheme } from '@classess/design-system';
import { Rail } from './Rail';
import { openVidya } from './VidyaOrb';
import { openCommandPalette } from './CommandPalette';
import { useOnline } from '@/lib/useOnline';
import { useRole } from '@/lib/RoleContext';
import type { Role } from '@/lib/mock';

/**
 * The surface a page belongs to drives its accent hue. Derive it from the route
 * so /student/* always reads as the student surface even before the role context
 * hydrates; shared routes (home, loop, messages, content, …) fall back to the
 * active role.
 */
function surfaceFromPath(pathname: string, role: Role): Role {
  if (pathname.startsWith('/teacher')) return 'teacher';
  if (pathname.startsWith('/student')) return 'student';
  if (pathname.startsWith('/admin')) return 'admin';
  if (pathname.startsWith('/parent')) return 'parent';
  return role;
}

/** One breadcrumb hop: a label, optionally a link. The last hop reads as current. */
export interface Crumb {
  label: string;
  href?: string;
}

/** One mono meta fact in the page-head meta line (e.g. "38 learners"). */
export interface MetaFact {
  /** The strong value (rendered in <b>) — a number or short token. */
  value?: ReactNode;
  /** The trailing label, in quiet mono. */
  label: ReactNode;
}

/** One tab in the page-head tab strip. */
export interface ShellTab {
  label: string;
  /** Active tab — exactly one should be active. */
  active?: boolean;
  href?: string;
  onClick?: () => void;
}

export interface SurfaceShellProps {
  /** The big weight-300 page title. */
  title: string;
  /** A mono overline kicker above the title (the class label, the section). */
  eyebrow?: string;
  /** The breadcrumb trail above the head. */
  breadcrumb?: Crumb[];
  /** The mono meta line beneath the title — the page's facts at a glance. */
  meta?: MetaFact[];
  /** The page's primary + secondary actions, right-aligned in the head. */
  actions?: ReactNode;
  /** A tab strip beneath the head (Overview / Students / …). */
  tabs?: ShellTab[];
  /**
   * A right rail (320px) — the composed aside the sample page rides on (ignite
   * moment, flagged panel, today's schedule, a handnote). When present the body
   * lays out as `.cols` (1fr + 320px); without it the body is a single column.
   */
  aside?: ReactNode;
  /**
   * Page-aware Vidya entry points. Each opens the orb and seeds the conversation
   * with that prompt, routing the user straight into a relevant ask.
   */
  dockChips?: string[];
  /** A short, calm intro shown above the chips when present. */
  dockIntro?: string;
  children: ReactNode;
}

/**
 * The shared destination-page chrome every surface rides on, composed to the
 * sample-page bar:
 *   · the fixed ExpandingRail (left)
 *   · a STICKY topbar — mono brand + a search + theme toggle + the command button
 *   · a breadcrumb
 *   · a .page-head — the big weight-300 title + a mono .meta line + the actions
 *   · an optional .tabs strip
 *   · a .cols content area (main + a 320px .aside) when an aside is supplied
 *
 * Depth is hairline + tonal step + frost only — never a shadow. One accent per
 * surface (the route's hue). The Vidya orb still floats globally; per-page
 * dockChips surface as a quiet Ask-Vidya row at the top of the body.
 */
export function SurfaceShell({
  title,
  eyebrow,
  breadcrumb,
  meta,
  actions,
  tabs,
  aside,
  dockChips,
  dockIntro,
  children,
}: SurfaceShellProps) {
  const online = useOnline();
  const { role } = useRole();
  const pathname = usePathname();
  const surface = surfaceFromPath(pathname ?? '', role);
  const { theme, toggleTheme } = useTheme();

  const hasAside = Boolean(aside);

  return (
    // data-surface binds --accent to THIS surface's hue (the shared accent
    // contract). --signature stays reserved for the brand mark + ignite.
    <div className="app-frame" data-surface={surface}>
      <Rail />

      <div className="surface">
        {/* The sticky top chrome — present on every page, the same as the bar. */}
        <header className="topbar" data-testid="surface-topbar">
          <Link href="/" className="brand" aria-label="Classess home">
            <span className="mark" aria-hidden="true" />
            Classess
          </Link>
          <span className="overline topbar-surface">{ROLE_WORD[surface]}</span>

          <button
            type="button"
            className="search topbar-search"
            onClick={openCommandPalette}
            aria-label="Search, jump to a page, or ask Vidya"
            data-testid="topbar-search"
          >
            <Icon name="search" size="sm" className="icon" />
            <span className="topbar-search-text">Search, jump, or ask Vidya</span>
            <kbd className="kbd topbar-kbd">⌘K</kbd>
          </button>

          <span className="topbar-spacer" />

          <button
            type="button"
            className="btn btn-secondary btn-sm row"
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
            data-testid="theme-toggle"
            style={{ gap: 'var(--space-2)' }}
          >
            <Icon name={theme === 'dark' ? 'home' : 'settings'} size="sm" />
            <span>{theme === 'dark' ? 'Light' : 'Dark'}</span>
          </button>

          <button
            type="button"
            className="btn btn-accent btn-sm row"
            onClick={openCommandPalette}
            aria-label="Open the command palette"
            data-testid="topbar-command"
            style={{ gap: 'var(--space-2)' }}
          >
            <Icon name="spark" size="sm" />
            <span className="topbar-command-text">Command</span>
          </button>
        </header>

        {!online ? (
          <div className="offline-banner" role="status">
            You are offline. This view is showing the last synced read; changes will sync when you
            reconnect.
          </div>
        ) : null}

        <div className="surface-body">
          <div className={`surface-page${hasAside ? ' has-aside' : ''}`}>
            {breadcrumb && breadcrumb.length > 0 ? (
              <nav className="breadcrumb reveal" aria-label="Breadcrumb">
                {breadcrumb.map((c, i) => {
                  const last = i === breadcrumb.length - 1;
                  return (
                    <span key={`${c.label}-${i}`} className="row" style={{ gap: 'var(--space-2)' }}>
                      {i > 0 ? (
                        <span className="sep" aria-hidden="true">
                          /
                        </span>
                      ) : null}
                      {c.href && !last ? (
                        <Link href={c.href}>{c.label}</Link>
                      ) : (
                        <span
                          aria-current={last ? 'page' : undefined}
                          style={last ? { color: 'var(--text-primary)' } : undefined}
                        >
                          {c.label}
                        </span>
                      )}
                    </span>
                  );
                })}
              </nav>
            ) : null}

            <div className="page-head reveal reveal-1">
              <div className="page-head-lead">
                {eyebrow ? (
                  <p className="overline" style={{ margin: '0 0 var(--space-2)' }}>
                    {eyebrow}
                  </p>
                ) : null}
                <h1 className="page-title">{title}</h1>
                {meta && meta.length > 0 ? (
                  <div className="page-meta">
                    {meta.map((m, i) => (
                      <span className="m" key={i}>
                        {m.value != null ? <b>{m.value}</b> : null}
                        {m.value != null ? ' ' : null}
                        {m.label}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
              {actions ? <div className="page-head-actions row">{actions}</div> : null}
            </div>

            {tabs && tabs.length > 0 ? (
              <div className="tabs reveal reveal-2" role="tablist">
                {tabs.map((t) =>
                  t.href ? (
                    <Link
                      key={t.label}
                      href={t.href}
                      className={`tab${t.active ? ' active' : ''}`}
                      role="tab"
                      aria-selected={t.active}
                    >
                      {t.label}
                    </Link>
                  ) : (
                    <button
                      key={t.label}
                      type="button"
                      className={`tab${t.active ? ' active' : ''}`}
                      role="tab"
                      aria-selected={t.active}
                      onClick={t.onClick}
                    >
                      {t.label}
                    </button>
                  ),
                )}
              </div>
            ) : null}

            {dockChips && dockChips.length > 0 ? (
              <div className="surface-vidya-chips reveal reveal-2">
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

            {hasAside ? (
              <div className="cols reveal reveal-3">
                <div className="cols-main">{children}</div>
                <aside className="cols-aside">{aside}</aside>
              </div>
            ) : (
              children
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/** The quiet mono word that sits beside the brand — the surface's plain name. */
const ROLE_WORD: Record<Role, string> = {
  teacher: 'Teaching',
  student: 'Learning',
  admin: 'School',
  parent: 'Family',
};
