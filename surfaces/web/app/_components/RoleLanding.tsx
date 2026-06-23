'use client';

/* ============================================================================
   app/_components/RoleLanding.tsx — the home as a role landing ("today").

   The home is no longer a central chat space; the conversation lives in the
   floating Vidya orb. This is the role's calm landing: a greeting + briefing
   cards + suggestion chips (which open the orb straight into the conversation)
   + quick links to the role's destinations.

   v4 throughout: per-surface accent via data-surface, sharp corners, no shadows,
   plain language, no emoji. The brand mark + ignite stay ultramarine; everything
   else reads in the surface accent.
   ============================================================================ */

import Link from 'next/link';
import { Icon, SpotlightCard, SuggestionChip, type IconName } from '@classess/design-system';
import { Rail } from './Rail';
import { BriefingCard } from './BriefingCard';
import { AdminBriefingCard } from './AdminBriefingCard';
import { useOnline } from '@/lib/useOnline';
import { useRole } from '@/lib/RoleContext';
import {
  GREETING,
  HOME_CHIPS,
  ROLE_LABELS,
  BRIEFINGS,
  ADMIN_BRIEFINGS,
  type Role,
} from '@/lib/mock';
import { useStore } from '@/lib/useStore';
import { profileSummaryLine } from '@/lib/store';
import { openVidya } from './VidyaOrb';

interface QuickLink {
  href: string;
  icon: IconName;
  label: string;
  detail: string;
}

/** A small set of quick links per role — the calm "where to go" on the landing. */
const QUICK_LINKS: Record<Role, QuickLink[]> = {
  teacher: [
    { href: '/teacher/plan', icon: 'calendar', label: 'Class diary and plan', detail: 'Your ready lessons and the week ahead.' },
    { href: '/teacher/evaluate', icon: 'check', label: 'Evaluation review', detail: 'Answers waiting on your sign-off.' },
    { href: '/teacher/students', icon: 'chart', label: 'Student insights', detail: 'Where the class stands, in plain language.' },
    { href: '/loop', icon: 'spark', label: 'The live loop', detail: 'The Student to Teacher cycle, live.' },
  ],
  student: [
    { href: '/student/learn', icon: 'book', label: 'Learn', detail: 'Pick up where you left off.' },
    { href: '/student/practice', icon: 'target', label: 'Practice', detail: 'A short, focused set for today.' },
    { href: '/student/progress', icon: 'chart', label: 'Your progress', detail: 'What you can do on your own now.' },
    { href: '/student/portfolio', icon: 'spark', label: 'Portfolio', detail: 'Your work and credentials.' },
  ],
  admin: [
    { href: '/admin/intelligence', icon: 'chart', label: 'School-wide intelligence', detail: 'Pacing and mastery across sections.' },
    { href: '/admin/control-centre', icon: 'spark', label: 'AI control centre', detail: 'Autonomy bounded by the permission ladder.' },
    { href: '/admin/governance', icon: 'settings', label: 'Governance and audit', detail: 'Who may do what, and the trail.' },
    { href: '/proactive', icon: 'flame', label: 'Approval queue', detail: 'Consequential actions waiting on you.' },
  ],
  parent: [
    { href: '/parent/child', icon: 'chart', label: 'The child view', detail: 'A calm look at how this week is going.' },
    { href: '/parent/reports', icon: 'book', label: 'Reports and feedback', detail: 'Plain-language reads, never raw scores.' },
    { href: '/parent/together', icon: 'spark', label: 'Learn alongside and PTM', detail: 'Ways to support at home.' },
    { href: '/messages', icon: 'send', label: 'Messages', detail: "Your child's teachers, in one place." },
  ],
};

export function RoleLanding() {
  const online = useOnline();
  const { role, setRole } = useRole();
  const { profile } = useStore();

  const links = QUICK_LINKS[role];
  const showBriefings = role === 'teacher' || role === 'admin';

  return (
    <div className="app-frame" data-surface={role}>
      <Rail role={role} onRoleChange={setRole} />

      <main className="app-main">
        {!online ? (
          <div className="offline-banner" role="status">
            You are offline. The core flows still work; new conversations will sync when you
            reconnect.
          </div>
        ) : null}

        <div className="landing" data-testid="role-landing">
          <header className="landing-head reveal reveal-1">
            <p className="overline">{ROLE_LABELS[role]} home</p>
            <h1 className="display-sm" style={{ margin: '4px 0 0' }}>
              {GREETING[role]}
            </h1>
            {profile ? (
              <p className="body-sm muted" style={{ marginTop: 'var(--space-3)', maxWidth: 560 }}>
                {profileSummaryLine(profile)}
              </p>
            ) : null}
          </header>

          <section className="landing-section reveal reveal-2">
            <p className="overline">Try with Vidya</p>
            <div className="home-chips" style={{ justifyContent: 'flex-start' }}>
              {HOME_CHIPS[role].map((chip) => (
                <SuggestionChip key={chip} spark onClick={() => openVidya(chip)}>
                  {chip}
                </SuggestionChip>
              ))}
            </div>
          </section>

          {showBriefings ? (
            <section className="landing-section reveal reveal-3">
              <p className="overline">Your briefing</p>
              <div className="landing-briefings">
                {role === 'teacher'
                  ? BRIEFINGS.map((b) => <BriefingCard key={b.id} briefing={b} />)
                  : ADMIN_BRIEFINGS.map((b) => <AdminBriefingCard key={b.id} briefing={b} />)}
              </div>
            </section>
          ) : null}

          <section className="landing-section reveal reveal-4">
            <p className="overline">Quick links</p>
            <div className="landing-links">
              {links.map((l) => (
                <Link key={l.href} href={l.href} className="landing-link">
                  <SpotlightCard>
                    <div className="row" style={{ gap: 'var(--space-3)', alignItems: 'flex-start' }}>
                      <Icon name={l.icon} size="md" />
                      <div>
                        <h3 className="body-lg" style={{ margin: 0 }}>
                          {l.label}
                        </h3>
                        <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
                          {l.detail}
                        </p>
                      </div>
                    </div>
                  </SpotlightCard>
                </Link>
              ))}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
