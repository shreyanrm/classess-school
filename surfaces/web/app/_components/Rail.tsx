'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Icon, type IconName } from '@classess/design-system';
import { useRole } from '@/lib/RoleContext';
import type { Role } from '@/lib/mock';
import { ROLE_LABELS } from '@/lib/mock';
import { Logo } from './Logo';
import { newVidyaConversation } from './VidyaOrb';

interface RailItem {
  href: string;
  icon: IconName;
  label: string;
}

/**
 * The role's feature destinations, reachable from the slim rail. Teacher and
 * Student carry the full Slice-1 page sets; Admin and Parent keep the existing
 * spine until their slices land. The live loop is reachable from every role —
 * it is the shared, visible payoff of the Student <-> Teacher cycle.
 */
const ROLE_ITEMS: Record<Role, RailItem[]> = {
  teacher: [
    { href: '/teacher', icon: 'home', label: 'Your day' },
    { href: '/teacher/plan', icon: 'calendar', label: 'Class diary and plan' },
    { href: '/classroom', icon: 'grid', label: 'Classroom delivery' },
    { href: '/teacher/attendance', icon: 'check', label: 'Attendance' },
    { href: '/teacher/assign', icon: 'book', label: 'Assign a quick check' },
    { href: '/content', icon: 'grid', label: 'Resource library' },
    { href: '/teacher/evaluate', icon: 'check', label: 'Evaluation review' },
    { href: '/teacher/students', icon: 'chart', label: 'Student insights' },
    { href: '/teacher/insights', icon: 'grid', label: 'Class insights' },
    { href: '/messages', icon: 'send', label: 'Messages' },
    { href: '/teacher/growth', icon: 'spark', label: 'Your growth' },
    { href: '/loop', icon: 'spark', label: 'The live loop' },
    { href: '/proactive', icon: 'flame', label: 'Approval queue' },
  ],
  student: [
    { href: '/student', icon: 'home', label: 'Today' },
    { href: '/student/learn', icon: 'book', label: 'Learn' },
    { href: '/student/practice', icon: 'target', label: 'Practice' },
    { href: '/student/work', icon: 'check', label: 'Your work' },
    { href: '/student/mocks', icon: 'calendar', label: 'Mocks and study plan' },
    { href: '/student/timetable', icon: 'clock', label: 'Timetable and attendance' },
    { href: '/student/progress', icon: 'chart', label: 'Your progress' },
    { href: '/student/portfolio', icon: 'spark', label: 'Portfolio and credentials' },
    { href: '/messages', icon: 'send', label: 'Messages' },
    { href: '/loop', icon: 'spark', label: 'The live loop' },
  ],
  admin: [
    { href: '/admin', icon: 'home', label: 'Morning briefing' },
    { href: '/admin/setup', icon: 'grid', label: 'Setup and hierarchy' },
    { href: '/admin/curriculum', icon: 'book', label: 'Curriculum and ontology' },
    { href: '/content', icon: 'grid', label: 'Resource library' },
    { href: '/admin/calendar', icon: 'calendar', label: 'Calendar and timetable' },
    { href: '/admin/operations', icon: 'clock', label: 'Daily operations' },
    { href: '/admin/exams', icon: 'check', label: 'Exam operations' },
    { href: '/admin/intelligence', icon: 'chart', label: 'School-wide intelligence' },
    { href: '/admin/network', icon: 'target', label: 'Network leadership' },
    { href: '/admin/integrations', icon: 'send', label: 'Integrations' },
    { href: '/messages', icon: 'send', label: 'Messages' },
    { href: '/admin/control-centre', icon: 'spark', label: 'AI control centre' },
    { href: '/admin/governance', icon: 'settings', label: 'Governance and audit' },
    { href: '/proactive', icon: 'flame', label: 'Approval queue' },
    { href: '/loop', icon: 'spark', label: 'The live loop' },
  ],
  parent: [
    { href: '/parent', icon: 'home', label: 'This week' },
    { href: '/parent/child', icon: 'chart', label: 'The child view' },
    { href: '/parent/reports', icon: 'book', label: 'Reports and feedback' },
    { href: '/parent/together', icon: 'spark', label: 'Learn alongside and PTM' },
    { href: '/messages', icon: 'send', label: 'Messages' },
    { href: '/loop', icon: 'spark', label: 'The live loop' },
  ],
};

/** The home destination for a role — where the brand mark and "new conversation" land. */
const ROLE_HOME: Record<Role, string> = {
  teacher: '/',
  student: '/',
  admin: '/',
  parent: '/',
};

export interface RailProps {
  /** Optional role override; defaults to the shared role context. */
  role?: Role;
  onRoleChange?: (role: Role) => void;
  /** Called when the user starts a new conversation (home only). */
  onNewConversation?: () => void;
}

/**
 * The slim, icon-only left rail. New conversation, search/history behind a
 * button, the role's feature destinations, and settings + profile at the
 * bottom. One shell, role-shaped — the role switcher cycles Teacher -> Student
 * -> Admin -> Parent and re-shapes the rail in place.
 */
export function Rail({ role: roleProp, onRoleChange, onNewConversation }: RailProps) {
  const pathname = usePathname();
  const { role: ctxRole, setRole, cycleRole } = useRole();
  const role = roleProp ?? ctxRole;
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [switchedTo, setSwitchedTo] = useState<Role | null>(null);
  const items = ROLE_ITEMS[role];

  // Clear the "you switched to X" confirmation after a calm beat.
  useEffect(() => {
    if (!switchedTo) return;
    const id = setTimeout(() => setSwitchedTo(null), 2400);
    return () => clearTimeout(id);
  }, [switchedTo]);

  function nextRole() {
    const order: Role[] = ['teacher', 'student', 'admin', 'parent'];
    const next = order[(order.indexOf(role) + 1) % order.length] ?? 'teacher';
    if (onRoleChange) {
      onRoleChange(next);
      setRole(next);
    } else {
      cycleRole();
    }
    // Surface a visible, announced confirmation — the switch re-shapes the whole
    // workspace, so it must never feel like a silent accidental tap.
    setSwitchedTo(next);
  }

  return (
    <>
      <nav className="rail" aria-label="Primary" data-testid="rail">
        <Link href={ROLE_HOME[role]} className="rail-mark rail-mark-logo" aria-label="Classess home" title="Classess">
          <Logo width={40} />
        </Link>

        <Link
          href="/"
          className={`rail-btn${pathname === '/' ? ' active' : ''}`}
          aria-label="New conversation"
          title="New conversation"
          onClick={() => {
            // Start a fresh Vidya thread (the orb owns it) AND navigate home, so
            // the button actually begins a new conversation, not just routes.
            newVidyaConversation();
            onNewConversation?.();
          }}
        >
          <Icon name="plus" size="md" />
          <span className="rail-label">New conversation</span>
        </Link>

        <button
          type="button"
          className={`rail-btn${drawerOpen ? ' active' : ''}`}
          aria-label="Search and history"
          aria-expanded={drawerOpen}
          title="Search and history"
          onClick={() => setDrawerOpen((v) => !v)}
        >
          <Icon name="search" size="md" />
          <span className="rail-label">Search and history</span>
        </button>

        {items.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`rail-btn${active ? ' active' : ''}`}
              aria-label={item.label}
              title={item.label}
              data-testid="rail-item"
              data-rail-href={item.href}
            >
              <Icon name={item.icon} size="md" />
              <span className="rail-label">{item.label}</span>
            </Link>
          );
        })}

        <span className="rail-spacer" />

        <button
          type="button"
          className="rail-btn"
          aria-label={`Switch role (currently ${ROLE_LABELS[role]})`}
          title={`Role: ${ROLE_LABELS[role]} — tap to switch`}
          onClick={nextRole}
        >
          <Icon name="grid" size="md" />
          <span className="rail-label">Role · {ROLE_LABELS[role]}</span>
        </button>

        <Link
          className={`rail-btn${pathname === '/settings' ? ' active' : ''}`}
          href="/settings"
          aria-label="Settings"
          title="Settings"
        >
          <Icon name="settings" size="md" />
          <span className="rail-label">Settings</span>
        </Link>
        <Link
          className={`rail-btn${pathname === '/profile' ? ' active' : ''}`}
          href="/profile"
          aria-label="Profile"
          title="Profile"
        >
          <Icon name="user" size="md" />
          <span className="rail-label">Profile</span>
        </Link>
      </nav>

      {drawerOpen ? (
        <aside className="rail-drawer" aria-label="Search and history">
          <div className="row-between">
            <span className="overline">Search and history</span>
            <button
              type="button"
              className="rail-btn"
              aria-label="Close"
              onClick={() => setDrawerOpen(false)}
            >
              <Icon name="close" size="sm" />
            </button>
          </div>
          <div className="search" style={{ marginTop: 'var(--space-3)' }}>
            <Icon name="search" size="sm" className="icon" />
            <input
              type="search"
              className="input"
              placeholder="Search your conversations"
              aria-label="Search your conversations"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="empty">
            <Icon name="search" size="lg" className="glyph" />
            <h4 className="body">
              {search ? `No matches for “${search}”` : 'No past conversations yet'}
            </h4>
            <p>
              Your threads will appear here. You do not need to return to old ones unless you want
              to.
            </p>
          </div>
        </aside>
      ) : null}

      {/* Role switch confirmation — announced + visible; auto-dismisses. */}
      <div className="rail-role-toast-region" role="status" aria-live="polite">
        {switchedTo ? (
          <div className="rail-role-toast">Switched to the {ROLE_LABELS[switchedTo]} workspace</div>
        ) : null}
      </div>
    </>
  );
}
