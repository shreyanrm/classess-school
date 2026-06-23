'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Icon, type IconName } from '@classess/design-system';
import { useRole } from '@/lib/RoleContext';
import type { Role } from '@/lib/mock';
import { ROLE_LABELS } from '@/lib/mock';

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
    { href: '/messages', icon: 'send', label: 'Messages' },
    { href: '/insights', icon: 'grid', label: 'Class read' },
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
  const items = ROLE_ITEMS[role];

  function nextRole() {
    if (onRoleChange) {
      const order: Role[] = ['teacher', 'student', 'admin', 'parent'];
      const next = order[(order.indexOf(role) + 1) % order.length] ?? 'teacher';
      onRoleChange(next);
      setRole(next);
    } else {
      cycleRole();
    }
  }

  return (
    <>
      <nav className="rail" aria-label="Primary">
        <Link href={ROLE_HOME[role]} className="rail-mark" aria-label="Classess home" title="Classess">
          C
        </Link>

        <Link
          href="/"
          className={`rail-btn${pathname === '/' ? ' active' : ''}`}
          aria-label="New conversation"
          title="New conversation"
          onClick={onNewConversation}
        >
          <Icon name="plus" size="md" />
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
            >
              <Icon name={item.icon} size="md" />
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
        </button>

        <Link
          className={`rail-btn${pathname === '/settings' ? ' active' : ''}`}
          href="/settings"
          aria-label="Settings"
          title="Settings"
        >
          <Icon name="settings" size="md" />
        </Link>
        <Link
          className={`rail-btn${pathname === '/profile' ? ' active' : ''}`}
          href="/profile"
          aria-label="Profile"
          title="Profile"
        >
          <Icon name="user" size="md" />
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
          <div className="empty">
            <Icon name="search" size="lg" className="glyph" />
            <h4 className="body">No past conversations yet</h4>
            <p>
              Your threads will appear here. You do not need to return to old ones unless you want
              to.
            </p>
          </div>
        </aside>
      ) : null}
    </>
  );
}
