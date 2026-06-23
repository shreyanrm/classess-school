'use client';

import { useMemo, useState } from 'react';
import { Button, Composer, Icon, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { EvidenceDrawer } from '../_components/EvidenceDrawer';
import { useRole } from '@/lib/RoleContext';
import type { Role } from '@/lib/mock';

/**
 * d18 — The communication hub. Until now there was no messaging UI. This is the
 * channels/DM list + thread, a compose box, conversation-to-task routing, and
 * the standing safety rails: child-safety on every free-text surface, quiet-hours
 * indicators, and consent gating. Role-aware: each role sees its own channels.
 *
 * Sending is consequential — it sits behind the approval control and never fires
 * on its own. A concern can be routed to a task with an owner and a due date.
 */

interface Channel {
  id: string;
  name: string;
  kind: 'channel' | 'dm' | 'broadcast';
  /** Generic label only — never a real personal name. */
  preview: string;
  /** Whether this conversation is consent-gated for the viewer. */
  gated?: boolean;
}

interface Msg {
  id: string;
  from: string;
  text: string;
  mine?: boolean;
  /** A flagged free-text surface — child-safety caught something to review. */
  flagged?: boolean;
}

const CHANNELS: Record<Role, Channel[]> = {
  teacher: [
    { id: 'c1', name: 'Class 10-B parents', kind: 'channel', preview: 'Homework query from a guardian' },
    { id: 'c2', name: 'Mathematics department', kind: 'channel', preview: 'Moderation for next week’s paper' },
    { id: 'c3', name: 'Guardian — Student C', kind: 'dm', preview: 'Following up on attendance' },
  ],
  student: [
    { id: 'c1', name: 'Your class teacher', kind: 'dm', preview: 'A note about your last check' },
    { id: 'c2', name: 'Class 10-B', kind: 'channel', preview: 'Reminder: mock on Friday' },
  ],
  admin: [
    { id: 'c1', name: 'School-wide broadcast', kind: 'broadcast', preview: 'Exam week logistics' },
    { id: 'c2', name: 'Coordinators', kind: 'channel', preview: 'Substitution cover for Tuesday' },
    { id: 'c3', name: 'Open parent concerns', kind: 'channel', preview: 'Two concerns awaiting an owner' },
  ],
  parent: [
    { id: 'c1', name: 'Class teacher', kind: 'dm', preview: 'Celebration: a topic just clicked' },
    { id: 'c2', name: 'School office', kind: 'channel', preview: 'PTM scheduling' },
    { id: 'c3', name: 'Counsellor', kind: 'dm', preview: 'Shared only with consent', gated: true },
  ],
};

const THREADS: Record<string, Msg[]> = {
  c1: [
    { id: 'm1', from: 'Guardian', text: 'Could you share what to revise this weekend?' },
    { id: 'm2', from: 'You', text: 'Of course — I will send the spaced-revision list shortly.', mine: true },
  ],
  c2: [{ id: 'm1', from: 'Coordinator', text: 'Paper moderation is due by Thursday.' }],
  c3: [
    { id: 'm1', from: 'Guardian', text: 'I am worried about the missed days.', flagged: false },
  ],
};

export default function MessagesPage() {
  const { role } = useRole();
  const channels = CHANNELS[role];
  const [activeId, setActiveId] = useState<string>(channels[0]?.id ?? 'c1');
  const [draft, setDraft] = useState('');
  const [prepared, setPrepared] = useState(false);
  const [routed, setRouted] = useState(false);

  const active = channels.find((c) => c.id === activeId) ?? channels[0];
  const thread = useMemo(() => THREADS[activeId] ?? [], [activeId]);

  // A calm, illustrative quiet-hours read (after 9pm, before 7am locally).
  const hour = new Date().getHours();
  const quietHours = hour >= 21 || hour < 7;

  function prepare() {
    if (draft.trim().length === 0) return;
    setPrepared(true);
  }

  return (
    <SurfaceShell
      eyebrow="Communication hub"
      title="Messages"
      dockIntro="I can draft a reply, translate for a family, or turn a concern into a tracked task with an owner. I never send for you — a message waits at the approval gate, with child-safety and quiet hours respected."
      dockChips={['Draft a calm reply', 'Turn this into a task', 'Translate for the family']}
    >
      <div className="cols-2" style={{ alignItems: 'start' }}>
        <section className="stack">
          <p className="overline">Channels and direct messages</p>
          <div className="stack" style={{ gap: 'var(--space-2)' }}>
            {channels.map((c) => {
              const on = c.id === activeId;
              return (
                <button
                  key={c.id}
                  type="button"
                  className="cell"
                  onClick={() => {
                    setActiveId(c.id);
                    setPrepared(false);
                    setRouted(false);
                  }}
                  aria-pressed={on}
                  style={{ textAlign: 'left', cursor: 'pointer', borderColor: on ? 'var(--accent)' : undefined }}
                >
                  <div className="row-between">
                    <span className="row" style={{ gap: 'var(--space-2)' }}>
                      <Icon name={c.kind === 'dm' ? 'user' : c.kind === 'broadcast' ? 'send' : 'grid'} size="sm" />
                      <span className="body-sm">{c.name}</span>
                    </span>
                    {c.gated ? <Tag tone="warning">Consent</Tag> : null}
                  </div>
                  <p className="caption muted" style={{ marginTop: 4 }}>
                    {c.preview}
                  </p>
                </button>
              );
            })}
          </div>
        </section>

        <section className="stack">
          {active?.gated ? (
            <SpotlightCard>
              <div className="empty">
                <Icon name="info" size="lg" className="glyph" />
                <h4 className="body">This conversation is consent-gated</h4>
                <p>
                  It opens only when the relevant consent stands. Reads here are gated; nothing is
                  shown until sharing is turned on.
                </p>
              </div>
            </SpotlightCard>
          ) : (
            <>
              <div className="row-between">
                <p className="overline" style={{ margin: 0 }}>
                  {active?.name}
                </p>
                {quietHours ? (
                  <Tag tone="warning" dot>
                    Quiet hours
                  </Tag>
                ) : (
                  <Tag tone="success" dot>
                    Within hours
                  </Tag>
                )}
              </div>

              <div className="thread" aria-live="polite" style={{ minHeight: 120 }}>
                {thread.length === 0 ? (
                  <p className="muted body-sm">No messages yet. Start the conversation below.</p>
                ) : (
                  thread.map((m) => (
                    <div key={m.id} className={`msg ${m.mine ? 'msg-user' : 'msg-vidya'}`}>
                      <div className="bubble body-sm">
                        {m.text}
                        {m.flagged ? (
                          <div style={{ marginTop: 6 }}>
                            <Tag tone="danger">Flagged for a responsible adult</Tag>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  ))
                )}
              </div>

              <div className="stack" style={{ gap: 'var(--space-2)' }}>
                <Composer
                  value={draft}
                  onValueChange={setDraft}
                  onSend={() => prepare()}
                  placeholder={quietHours ? 'Draft now; it will hold until quiet hours pass' : 'Write a message'}
                  sendLabel="Prepare message"
                />
                <p className="caption quiet">
                  <Icon name="info" size="sm" /> Child-safety runs on this free-text surface. Anything
                  concerning is routed to a responsible adult; there are no unmonitored channels.
                </p>
              </div>

              {prepared ? (
                <SpotlightCard padLg>
                  <div className="row-between" style={{ alignItems: 'flex-start' }}>
                    <div>
                      <p className="overline" style={{ margin: 0 }}>
                        The approval control
                      </p>
                      <h3 className="body-lg" style={{ margin: '4px 0 0' }}>
                        Message prepared
                      </h3>
                    </div>
                    <Tag tone="info">Awaiting your send</Tag>
                  </div>
                  <p className="body-sm muted" style={{ marginTop: 'var(--space-3)' }}>
                    {draft || 'Your message'}
                  </p>
                  <EvidenceDrawer
                    evidence={[
                      'Translation to the recipient’s language is applied on send, where set.',
                      quietHours
                        ? 'Quiet hours are active — on approve, delivery holds until the window passes.'
                        : 'Within communication hours — delivery is immediate on approve.',
                      'Child-safety screened this text before it reached the gate.',
                    ]}
                    whySeeing="Sending is consequential, so it waits for your explicit approval. You decide when and whether it goes."
                  />
                  <div className="divider" />
                  <div className="rec-actions">
                    <Button variant="accent" size="sm" onClick={() => { setPrepared(false); setDraft(''); }}>
                      {quietHours ? 'Approve — send when hours open' : 'Approve and send'}
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setPrepared(false)}>
                      Keep editing
                    </Button>
                  </div>
                </SpotlightCard>
              ) : null}

              <SpotlightCard>
                <div className="row-between" style={{ alignItems: 'flex-start' }}>
                  <div>
                    <p className="overline" style={{ margin: 0 }}>
                      Conversation to task
                    </p>
                    <p className="body-sm" style={{ marginTop: 4, maxWidth: 460 }}>
                      A concern should not stay a stray message. Route it to an owner with a due date
                      and a resolution track.
                    </p>
                  </div>
                  {routed ? <Tag tone="success">Routed</Tag> : null}
                </div>
                <div className="divider" />
                {routed ? (
                  <p className="caption muted">
                    Routed to the class teacher · due in two days · status open. It is now tracked, not
                    lost in chat.
                  </p>
                ) : (
                  <div className="rec-actions">
                    <Button variant="secondary" size="sm" onClick={() => setRouted(true)}>
                      <Icon name="arrow-right" size="sm" /> Route to a task
                    </Button>
                    <span className="caption muted">Owned, tracked, and closed — not left as a stray chat.</span>
                  </div>
                )}
              </SpotlightCard>
            </>
          )}
        </section>
      </div>
    </SurfaceShell>
  );
}
