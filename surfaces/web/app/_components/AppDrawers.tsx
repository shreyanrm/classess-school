'use client';

/* ============================================================================
   AppDrawers — the two global, imperatively-opened side panels that the topbar
   bell and the Help affordance reach: a Notifications drawer and a Help / FAQ
   drawer.

   Both ride the SHARED right-slide drawer chrome already established by the
   EvidenceDrawer (.ev-drawer-* classes): a frosted scrim, a hairline-bordered
   panel sliding from the right, Escape to close, focus trapped, page scroll
   locked, focus restored on close. No new drawer mechanics — these extend the
   existing vocabulary rather than reinvent it.

   Mounting: <AppDrawersHost /> is rendered once in the root layout. Anywhere can
   open them imperatively:
     openNotifications()  — the topbar bell
     openHelp()           — the topbar help affordance / a "?" anywhere

   Laws honoured: hairline + tonal + frost depth (NEVER a shadow), ONE accent
   (the surface hue, via --accent), cool/brand only, motion is transform+opacity
   on the kit ease and reduced-motion safe. Every state is designed — the
   notifications empty state carries a real CTA, never a blank panel.
   ============================================================================ */

import { useEffect, useRef, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { Button, Icon, Tag, type IconName } from '@classess/design-system';
import { openVidya } from './VidyaOrb';

/* ── Imperative open contract — mirrors the orb's window-event pattern ─────── */

export const NOTIFICATIONS_OPEN_EVENT = 'clss:notifications:open';
export const HELP_OPEN_EVENT = 'clss:help:open';

/** Open the Notifications drawer. Safe on the server. */
export function openNotifications(): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(NOTIFICATIONS_OPEN_EVENT));
}

/** Open the Help / FAQ drawer, optionally jumping to a topic id. */
export function openHelp(topic?: string): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(HELP_OPEN_EVENT, { detail: { topic } }));
}

/* ── A shared right-slide drawer shell on the existing .ev-drawer chrome ───── */

function SideDrawer({
  open,
  onClose,
  eyebrow,
  children,
  foot,
}: {
  open: boolean;
  onClose: () => void;
  eyebrow: string;
  children: ReactNode;
  foot?: ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const restoreRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    restoreRef.current = (document.activeElement as HTMLElement) ?? null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const focusFirst = window.setTimeout(() => {
      const el = panelRef.current?.querySelector<HTMLElement>(
        'button, a[href], input, [tabindex]:not([tabindex="-1"])',
      );
      (el ?? panelRef.current)?.focus();
    }, 30);

    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== 'Tab') return;
      const focusables = panelRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], input:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (!focusables || focusables.length === 0) return;
      const first = focusables[0]!;
      const last = focusables[focusables.length - 1]!;
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
    document.addEventListener('keydown', onKey, true);
    return () => {
      window.clearTimeout(focusFirst);
      document.removeEventListener('keydown', onKey, true);
      document.body.style.overflow = prevOverflow;
      restoreRef.current?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="ev-drawer-root">
      <div className="ev-drawer-scrim" onClick={onClose} aria-hidden="true" />
      <div
        className="ev-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={eyebrow}
        ref={panelRef}
        tabIndex={-1}
      >
        <div className="ev-drawer-head">
          <span className="overline" style={{ margin: 0 }}>
            {eyebrow}
          </span>
          <button type="button" className="rail-btn ev-drawer-close" aria-label="Close" onClick={onClose}>
            <Icon name="close" size="sm" />
          </button>
        </div>
        <div className="ev-drawer-body">{children}</div>
        {foot ? <div className="ev-drawer-foot">{foot}</div> : null}
      </div>
    </div>
  );
}

/* ── Notifications ─────────────────────────────────────────────────────────── */

type NoteTone = 'info' | 'success' | 'warning';

interface NoteItem {
  id: string;
  icon: IconName;
  tone: NoteTone;
  title: string;
  body: string;
  when: string;
  href?: string;
  unread?: boolean;
}

/** Seed notifications — plain-language, no raw scores, no personal lock-in. */
const SEED_NOTES: NoteItem[] = [
  {
    id: 'n1',
    icon: 'flame',
    tone: 'success',
    title: 'A mastery moment landed',
    body: 'A learner crossed into independent on Trigonometry — verified on unaided evidence.',
    when: 'just now',
    href: '/teacher/insights',
    unread: true,
  },
  {
    id: 'n2',
    icon: 'spark',
    tone: 'info',
    title: 'Vidya flagged three gaps this week',
    body: 'Ranked by impact, with the evidence behind each. Nothing acts on its own.',
    when: '2h ago',
    href: '/teacher/insights',
    unread: true,
  },
  {
    id: 'n3',
    icon: 'check',
    tone: 'info',
    title: 'A recommendation is waiting for you',
    body: 'A scaffolded-autonomy task is prepared in the approval queue — approve, adjust, or decline.',
    when: 'today',
    href: '/proactive',
    unread: true,
  },
  {
    id: 'n4',
    icon: 'warning',
    tone: 'warning',
    title: 'Two parents still owe consent',
    body: 'A gentle nudge before Friday keeps their child’s reads flowing.',
    when: 'yesterday',
    href: '/messages',
  },
];

function NotificationsDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [notes, setNotes] = useState<NoteItem[]>(SEED_NOTES);
  const unread = notes.filter((n) => n.unread).length;

  function markRead(id: string) {
    setNotes((prev) => prev.map((x) => (x.id === id ? { ...x, unread: false } : x)));
  }

  return (
    <SideDrawer
      open={open}
      onClose={onClose}
      eyebrow="Notifications"
      foot={
        <>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setNotes((prev) => prev.map((n) => ({ ...n, unread: false })))}
            disabled={unread === 0}
          >
            Mark all read
          </Button>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </>
      }
    >
      <div className="row-between">
        <h3 className="h4" style={{ margin: 0 }}>
          What changed
        </h3>
        <Tag tone={unread ? 'info' : 'neutral'} dot>
          {unread ? `${unread} new` : 'all read'}
        </Tag>
      </div>

      {notes.length === 0 ? (
        <div className="empty">
          <Icon name="bell" size="lg" className="glyph" />
          <h4 className="body">You are all caught up</h4>
          <p>Nothing needs you right now. New mastery moments and flags will land here.</p>
          <Link href="/teacher/insights" className="btn btn-secondary btn-sm" onClick={onClose}>
            Open class insights
          </Link>
        </div>
      ) : (
        <div className="note-list">
          {notes.map((n) =>
            n.href ? (
              <Link
                key={n.id}
                href={n.href}
                className={`note-row${n.unread ? ' unread' : ''}`}
                onClick={() => {
                  markRead(n.id);
                  onClose();
                }}
              >
                <span className={`note-ic note-${n.tone}`}>
                  <Icon name={n.icon} size="sm" />
                </span>
                <span className="note-main">
                  <span className="note-top">
                    <span className="note-title">{n.title}</span>
                    <span className="data note-when">{n.when}</span>
                  </span>
                  <span className="note-body">{n.body}</span>
                </span>
                {n.unread ? <span className="note-dot" aria-hidden="true" /> : null}
              </Link>
            ) : (
              <button
                key={n.id}
                type="button"
                className={`note-row${n.unread ? ' unread' : ''}`}
                onClick={() => markRead(n.id)}
              >
                <span className={`note-ic note-${n.tone}`}>
                  <Icon name={n.icon} size="sm" />
                </span>
                <span className="note-main">
                  <span className="note-top">
                    <span className="note-title">{n.title}</span>
                    <span className="data note-when">{n.when}</span>
                  </span>
                  <span className="note-body">{n.body}</span>
                </span>
                {n.unread ? <span className="note-dot" aria-hidden="true" /> : null}
              </button>
            ),
          )}
        </div>
      )}

      <p className="caption quiet" style={{ margin: 0 }}>
        Notifications are plain-language reads — never raw scores, and nothing fires on its own.
      </p>
    </SideDrawer>
  );
}

/* ── Help / FAQ ────────────────────────────────────────────────────────────── */

interface FaqItem {
  q: string;
  a: string;
  ask?: string;
}

const FAQ: FaqItem[] = [
  {
    q: 'What is the live loop?',
    a: 'It runs the whole Student-to-Teacher cycle in your browser. Every reading is computed live by the same engine the platform uses — assign, attempt, classify, intervene, reassess, and the teacher view updates.',
    ask: 'Walk me through the live loop',
  },
  {
    q: 'Why does mastery only move on unaided work?',
    a: 'Working with help shows what is possible with a scaffold; working alone shows what has transferred. A reading only crosses into independent on fresh, unaided evidence — never a single lucky score.',
    ask: 'Why is independence the keystone',
  },
  {
    q: 'Does anything act on its own?',
    a: 'No. Every consequential step waits for you. Recommendations are prepared and held in the approval queue — you approve, adjust, or decline. This is the permission ladder.',
    ask: 'Explain the permission ladder',
  },
  {
    q: 'Who can see a learner’s reads?',
    a: 'Reads are shown in plain language only — never raw scores or personal details. Sharing with a mentor is off by default, and every inference stays inside the consent tier you set.',
    ask: 'Who can see my reads',
  },
  {
    q: 'How do I change the theme or text size?',
    a: 'Settings → Appearance carries a light or dark palette, a cool accent, and a visual-accessibility mode (larger text, higher contrast, reduced motion). Your choice survives a reload.',
    ask: 'Open appearance settings',
  },
];

interface HelpLink {
  icon: IconName;
  title: string;
  body: string;
  href: string;
}

const HELP_LINKS: HelpLink[] = [
  { icon: 'spark', title: 'See the live loop', body: 'Watch the cycle run end to end.', href: '/loop' },
  { icon: 'chart', title: 'Class insights', body: 'The cohort rollup and where the class stands.', href: '/teacher/insights' },
  { icon: 'settings', title: 'Settings', body: 'Theme, accent, accessibility, and consent.', href: '/settings' },
];

function HelpDrawer({ open, onClose, topic }: { open: boolean; onClose: () => void; topic?: string }) {
  const [openItem, setOpenItem] = useState<number | null>(0);

  useEffect(() => {
    if (open && topic != null) {
      const i = FAQ.findIndex((f) => f.q.toLowerCase().includes(topic.toLowerCase()));
      if (i >= 0) setOpenItem(i);
    }
  }, [open, topic]);

  return (
    <SideDrawer
      open={open}
      onClose={onClose}
      eyebrow="Help & FAQ"
      foot={
        <>
          <Button
            variant="accent"
            size="sm"
            onClick={() => {
              onClose();
              openVidya('I have a question about Classess');
            }}
          >
            <Icon name="spark" size="sm" />
            Ask Vidya
          </Button>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </>
      }
    >
      <div className="ignite-card" style={{ marginTop: 0 }}>
        <div className="row-between" style={{ marginBottom: 12 }}>
          <span className="overline">Help</span>
          <Icon name="info" size="sm" style={{ color: 'var(--accent)' }} />
        </div>
        <div className="who" style={{ fontSize: 22 }}>
          Ask anything, anytime
        </div>
        <p className="body-sm" style={{ opacity: 0.82, marginTop: 8 }}>
          Vidya is the front door. Read the common questions below, or ask in your own words and get a
          plain-language answer with its evidence.
        </p>
      </div>

      <div>
        <p className="overline ev-drawer-section" style={{ marginTop: 0 }}>
          Common questions
        </p>
        <div className="faq-list">
          {FAQ.map((f, i) => {
            const expanded = openItem === i;
            return (
              <div className={`faq-item${expanded ? ' open' : ''}`} key={i}>
                <button
                  type="button"
                  className="faq-q"
                  aria-expanded={expanded}
                  onClick={() => setOpenItem(expanded ? null : i)}
                >
                  <span>{f.q}</span>
                  <Icon name={expanded ? 'minus' : 'plus'} size="sm" />
                </button>
                {expanded ? (
                  <div className="faq-a">
                    <p className="body-sm" style={{ margin: 0 }}>
                      {f.a}
                    </p>
                    {f.ask ? (
                      <button
                        type="button"
                        className="faq-ask"
                        onClick={() => {
                          onClose();
                          openVidya(f.ask);
                        }}
                      >
                        <Icon name="spark" size="sm" />
                        {f.ask}
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      </div>

      <div>
        <p className="overline ev-drawer-section">Jump to</p>
        <div className="help-links">
          {HELP_LINKS.map((l) => (
            <Link key={l.href} href={l.href} className="flag flag-link" onClick={onClose}>
              <span className="flag-ic">
                <Icon name={l.icon} size="sm" />
              </span>
              <span>
                <span className="body-sm" style={{ fontWeight: 500, display: 'block' }}>
                  {l.title}
                </span>
                <span className="caption">{l.body}</span>
              </span>
            </Link>
          ))}
        </div>
      </div>
    </SideDrawer>
  );
}

/* ── The host — mount once in the root layout ──────────────────────────────── */

export function AppDrawersHost() {
  const [notesOpen, setNotesOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [helpTopic, setHelpTopic] = useState<string | undefined>(undefined);

  useEffect(() => {
    function onNotes() {
      setNotesOpen(true);
    }
    function onHelp(e: Event) {
      const t = (e as CustomEvent<{ topic?: string }>).detail?.topic;
      setHelpTopic(t);
      setHelpOpen(true);
    }
    window.addEventListener(NOTIFICATIONS_OPEN_EVENT, onNotes);
    window.addEventListener(HELP_OPEN_EVENT, onHelp);
    return () => {
      window.removeEventListener(NOTIFICATIONS_OPEN_EVENT, onNotes);
      window.removeEventListener(HELP_OPEN_EVENT, onHelp);
    };
  }, []);

  return (
    <>
      <NotificationsDrawer open={notesOpen} onClose={() => setNotesOpen(false)} />
      <HelpDrawer open={helpOpen} onClose={() => setHelpOpen(false)} topic={helpTopic} />
    </>
  );
}
