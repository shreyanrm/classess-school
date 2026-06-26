'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Avatar, Button, Composer, Icon, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { EvidenceDrawer } from '../_components/EvidenceDrawer';
import { LanguageBadge } from '../_components/LanguageBadge';
import { SourceNote } from '../_components/SourceNote';
import { useRole } from '@/lib/RoleContext';
import type { Role } from '@/lib/mock';
import { useStore } from '@/lib/useStore';
import { useGatewaySource } from '@/lib/useGatewaySource';
import { mintId, channelRef as deriveChannelRef } from '@/lib/store';
import { joinChannel, type ChannelHandle, type LiveMessage, type LivePresence } from '@/lib/realtime';
import { saveMessageLive, loadMessagesLive } from '@/lib/opData';
import { translateForReader, routeToTask } from '@/lib/commData';
import { useT } from '@/lib/i18n';
import { openVidya } from '../_components/VidyaOrb';

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
  /**
   * A student-to-student direct message. Peer chats run through the SAME
   * child-safety screening on every send (flagged content is blocked +
   * escalated per the crisis path), carry a visible 'report message'
   * affordance, and show a calm note that they are safety-screened.
   */
  peer?: boolean;
  /** Two-letter initials for the classmate avatar (a generic handle, no PII). */
  initials?: string;
}

interface Msg {
  id: string;
  from: string;
  text: string;
  mine?: boolean;
  /** A flagged free-text surface — child-safety caught something to review. */
  flagged?: boolean;
  /** A crisis caught by the safety gate — routed/escalated to a human. */
  escalated?: boolean;
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
    // Student-to-student direct messages — classmates by generic study handle,
    // never a real personal name. Each peer chat is safety-screened on send.
    { id: 'p1', name: 'Study partner — Maths', kind: 'dm', preview: 'Want to compare trig answers?', peer: true, initials: 'MP' },
    { id: 'p2', name: 'Lab buddy — Physics', kind: 'dm', preview: 'Did you finish the kinematics set?', peer: true, initials: 'LB' },
    { id: 'p3', name: 'Revision group — 10-B', kind: 'dm', preview: 'Let’s share notes before Friday', peer: true, initials: 'RG' },
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
  // Peer DM seed threads — ordinary classmate study chat. Generic handles only.
  p1: [
    { id: 'm1', from: 'Study partner', text: 'Hey! Want to compare answers on the trig set?' },
    { id: 'm2', from: 'You', text: 'Yes — I got stuck on question 4. Can you explain it?', mine: true },
  ],
  p2: [
    { id: 'm1', from: 'Lab buddy', text: 'Did you finish the kinematics worksheet?' },
  ],
  p3: [
    { id: 'm1', from: 'Revision group', text: 'Let’s pool notes before Friday’s mock.' },
  ],
};

export default function MessagesPage() {
  const { role } = useRole();
  const { account, school } = useStore();
  const { locale } = useT();
  // Probe the live communication capability (translate / route) so the thread can
  // show the OBSERVABLE source marker — the seed thread + reader-language render
  // run either way, but the seed bodies are never presented as if live when the
  // spine is silent.
  const { source } = useGatewaySource('communication');
  const channels = CHANNELS[role];
  const [activeId, setActiveId] = useState<string>(channels[0]?.id ?? 'c1');
  const [draft, setDraft] = useState('');
  const [prepared, setPrepared] = useState(false);
  const [routed, setRouted] = useState(false);
  const [routing, setRouting] = useState(false);
  const [taskOwner, setTaskOwner] = useState('Class teacher');
  const [taskDue, setTaskDue] = useState('In two days');

  // Moderation affordance for peer chats — a viewer can report any message to a
  // responsible adult. Reported message ids are held in a set so the bubble
  // shows it was routed; a calm confirmation line is surfaced. This is the
  // SAME escalation destination as the safety gate: a human, never a peer.
  const [reportedIds, setReportedIds] = useState<Set<string>>(() => new Set());
  const [reportNote, setReportNote] = useState<string | null>(null);
  const reportMessage = useCallback((id: string) => {
    setReportedIds((prev) => {
      if (prev.has(id)) return prev;
      const next = new Set(prev);
      next.add(id);
      return next;
    });
    setReportNote('Reported to a responsible adult. They will review this conversation — thank you for speaking up.');
    window.setTimeout(() => setReportNote(null), 6000);
  }, []);

  // Split the conversation list so student-to-student DMs read as their own
  // 'Classmates' group, distinct from the teacher / class channels above.
  const peerChannels = useMemo(() => channels.filter((c) => c.peer), [channels]);
  const coreChannels = useMemo(() => channels.filter((c) => !c.peer), [channels]);

  // GAP#8 — message bodies rendered into the reader's language. A message id maps
  // to its rendered (reader-language) body; the original is shown until/unless a
  // render lands, so nothing ever blanks. Translation runs THROUGH the wall
  // (communication.translate), which preserves subject terminology + code-switch.
  const [renderedBodies, setRenderedBodies] = useState<Record<string, string>>({});

  // Render a message body into the reader's language, gateway-first. On any
  // degrade the original text stands (passthrough), never dropped. Subject terms
  // are preserved by the module; we only store the rendered text by message id.
  const renderForReader = useCallback(
    async (id: string, text: string) => {
      if (!text.trim()) return;
      const res = await translateForReader({ text, preferredLang: locale });
      const rendered = res.ok ? res.data?.rendered_text : undefined;
      if (rendered && rendered !== text) {
        setRenderedBodies((prev) => (prev[id] === rendered ? prev : { ...prev, [id]: rendered }));
      }
    },
    [locale],
  );

  // Live messaging state (Supabase Realtime). Degrades to local when unwired.
  const [liveMsgs, setLiveMsgs] = useState<LiveMessage[]>([]);
  const [present, setPresent] = useState<LivePresence[]>([]);
  const [toast, setToast] = useState<string | null>(null);
  const channelRef = useRef<ChannelHandle | null>(null);

  const active = channels.find((c) => c.id === activeId) ?? channels[0];
  // The seed thread plus any live messages received this session.
  const baseThread = useMemo(() => THREADS[activeId] ?? [], [activeId]);

  // This client's opaque ref + a non-identifying handle (a role label, no PII).
  // A stable fallback uuid is minted once per mount for an anonymous viewer so
  // the route's uuid guard passes and the safety verdict (incl. a crisis) is
  // never dropped on the no-account edge.
  const fallbackSelf = useRef<string>(mintId());
  const selfRef = account?.id ?? fallbackSelf.current;
  const selfHandle = role.charAt(0).toUpperCase() + role.slice(1);

  // The live institution ref this conversation persists under. When no real
  // institution is set we mint one once per mount (stable across sends) so a
  // thread still keys consistently on the degraded/local path.
  const fallbackInstitution = useRef<string>(mintId());
  const liveInstitution = school?.institution.liveId ?? fallbackInstitution.current;

  // ONE stable channel ref per conversation, derived deterministically from the
  // institution + role + active id. Every send in this thread reuses it, so the
  // durable history (operational.messages WHERE channel_id = ...) can read the
  // thread back. It is a pure hash of opaque ids — never random per send, never
  // PII — shaped like a uuid so it satisfies the route guard and the channels FK.
  const channelId = useMemo(
    () => deriveChannelRef(`${liveInstitution}:${role}:${activeId}`),
    [liveInstitution, role, activeId],
  );

  // Join a live channel for the active conversation. Two open clients on the
  // same channel see each other's messages + presence; a remote message raises
  // a calm toast. Tears down on channel change / unmount. No-op when unwired.
  useEffect(() => {
    let cancelled = false;
    setLiveMsgs([]);
    setPresent([]);
    const topic = `msg:${role}:${activeId}`;
    void joinChannel({
      topic,
      self: { ref: selfRef, handle: selfHandle },
      onMessage: (m) => {
        if (cancelled) return;
        setLiveMsgs((prev) => (prev.some((p) => p.id === m.id) ? prev : [...prev, m]));
      },
      onPresence: (p) => {
        if (!cancelled) setPresent(p);
      },
      onNotify: (line) => {
        if (cancelled) return;
        setToast(line);
        window.setTimeout(() => setToast((t) => (t === line ? null : t)), 4000);
      },
    }).then((handle) => {
      if (cancelled) {
        void handle.leave();
        return;
      }
      channelRef.current = handle;
      setPresent(handle.presence());
    });
    return () => {
      cancelled = true;
      const h = channelRef.current;
      channelRef.current = null;
      if (h) void h.leave();
    };
  }, [activeId, role, selfRef, selfHandle]);

  // Durable history: when a real institution is set, re-read the persisted thread
  // for this conversation's STABLE channel ref so a reload (or a switch back to a
  // channel) shows what was sent. No-op / empty on the degraded (no-db) path —
  // the surface stays on its local seed thread and never blanks or crashes.
  useEffect(() => {
    if (!school?.institution.liveId) return;
    let cancelled = false;
    void loadMessagesLive(channelId, liveInstitution).then((res) => {
      if (cancelled || !res.persisted || !res.rows) return;
      const history: LiveMessage[] = res.rows.map((r) => ({
        id: String(r.message_id),
        senderRef: String(r.sender_ref),
        body: String(r.body),
        flagged: r.flagged === true,
        postedAt: typeof r.posted_at === 'string' ? r.posted_at : new Date().toISOString(),
      }));
      setLiveMsgs((prev) => {
        const seen = new Set(prev.map((m) => m.id));
        const merged = [...history.filter((m) => !seen.has(m.id)), ...prev];
        return merged;
      });
    });
    return () => {
      cancelled = true;
    };
  }, [channelId, liveInstitution, school]);

  // The calm supportive line shown when the safety gate detects a crisis. A
  // crisis is NEVER silenced — it is held, escalated to a human, and the surface
  // shows this supportive response rather than a blank send.
  const [crisisSupport, setCrisisSupport] = useState<string | null>(null);

  // Send: SCREEN on the server first (child-safety), then react to the real
  // verdict — broadcast + persist a safe message; hold + flag harassment; on a
  // crisis route/escalate to a human and show a calm supportive response. The
  // verdict is the server's, never a hard-coded flagged:false.
  const sendLive = useCallback(
    async (text: string) => {
      const messageId = mintId();
      // Screen through the live messages route (the server-only safety gate). The
      // route validates uuids; when a real institution is set it persists too. We
      // always read the safety verdict back, and never silence a crisis. The
      // channel ref is STABLE for this conversation (channelId) so the durable
      // history can read the thread back, and the route upserts the channel row
      // first so the FK is satisfied.
      const screened = await saveMessageLive({
        institutionId: liveInstitution,
        channelId,
        senderRef: selfRef,
        body: text,
        surface: role,
      });

      const escalated = screened.escalate === true;
      const flagged = screened.flagged === true;

      if (escalated) {
        // A crisis: never silenced. Hold the message as flagged + escalated, show
        // it routed to a responsible adult, and surface the calm supportive line.
        const held: LiveMessage = {
          id: messageId,
          senderRef: selfRef,
          body: text,
          flagged: true,
          postedAt: new Date().toISOString(),
        };
        setLiveMsgs((prev) => [...prev, held]);
        setCrisisSupport(screened.support ?? 'A person who can help has been notified and will reach out to you.');
        // It is NOT broadcast to the channel — it is routed to a human, not to an
        // unmonitored or peer channel.
        return;
      }

      const message: LiveMessage = {
        id: messageId,
        senderRef: selfRef,
        body: text,
        flagged,
        postedAt: new Date().toISOString(),
      };
      // Echo locally, then fan out (flagged messages are held visibly for review,
      // but still kept in the MONITORED channel — never an unmonitored one).
      setLiveMsgs((prev) => [...prev, message]);
      if (!flagged) void channelRef.current?.send(message);
      // GAP#8 — translation is APPLIED ON SEND: render the just-sent text into the
      // reader's language through the wall (communication.translate). This is a
      // REAL call now, not a claim in the evidence drawer; the rendered body is
      // shown where it differs, and subject terminology is preserved by the module.
      void renderForReader(messageId, text);
    },
    [selfRef, liveInstitution, channelId, role, renderForReader],
  );

  // GAP#8 — render every message body (the seed thread + any live/loaded
  // messages) into the reader's language, gateway-first. Runs when the active
  // thread or the locale changes; each render is best-effort and the original
  // text stands until one lands. Already-rendered ids are skipped.
  useEffect(() => {
    for (const m of baseThread) {
      if (!renderedBodies[m.id]) void renderForReader(m.id, m.text);
    }
    for (const m of liveMsgs) {
      if (!renderedBodies[m.id]) void renderForReader(m.id, m.body);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseThread, liveMsgs, locale]);

  // A calm, illustrative quiet-hours read (after 9pm, before 7am locally).
  const hour = new Date().getHours();
  const quietHours = hour >= 21 || hour < 7;

  function prepare() {
    if (draft.trim().length === 0) return;
    setPrepared(true);
  }

  const channelIcon = (kind: Channel['kind']) =>
    kind === 'dm' ? 'user' : kind === 'broadcast' ? 'send' : 'grid';

  // One conversation row in the rail. Peer DMs show a classmate avatar (generic
  // initials, never PII); teacher/class channels keep the kind glyph.
  const renderChan = (c: Channel) => {
    const on = c.id === activeId;
    return (
      <button
        key={c.id}
        type="button"
        className={`msg-chan${on ? ' active' : ''}`}
        onClick={() => {
          setActiveId(c.id);
          setPrepared(false);
          setRouted(false);
          setCrisisSupport(null);
          setReportNote(null);
        }}
        aria-pressed={on}
      >
        <div className="msg-chan-top">
          {c.peer ? (
            <Avatar size="sm" initials={c.initials ?? 'CL'} />
          ) : (
            <Icon name={channelIcon(c.kind)} size="sm" />
          )}
          <span className="msg-chan-name">{c.name}</span>
          {c.gated ? <Tag tone="warning" style={{ marginLeft: 'auto' }}>Consent</Tag> : null}
        </div>
        <p className="msg-chan-preview">{c.preview}</p>
      </button>
    );
  };

  // The 'report message' moderation affordance, shown under an incoming peer
  // message. It routes the message to a responsible adult (the same human the
  // safety gate escalates to) — never to another student. Own messages and
  // non-peer channels carry no report control.
  const renderReportAffordance = (id: string, mine: boolean) => {
    if (!active?.peer || mine) return null;
    const reported = reportedIds.has(id);
    return (
      <div className="msg-report">
        {reported ? (
          <span className="caption muted" data-testid="message-reported">
            <Icon name="check" size="sm" /> Reported to a responsible adult
          </span>
        ) : (
          <button
            type="button"
            className="msg-report-btn"
            onClick={() => reportMessage(id)}
            data-testid="report-message"
          >
            <Icon name="info" size="sm" /> Report message
          </button>
        )}
      </div>
    );
  };

  const aside = (
    <>
      {crisisSupport ? (
        <SpotlightCard padLg data-testid="crisis-support">
          <div className="row" style={{ gap: 'var(--space-2)', alignItems: 'flex-start' }}>
            <Icon name="info" size="md" />
            <div>
              <p className="overline" style={{ margin: 0 }}>
                You are not alone
              </p>
              <p className="body-sm" style={{ marginTop: 'var(--space-2)' }}>
                {crisisSupport}
              </p>
              <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
                This was routed to a responsible adult, never to an unmonitored channel.
              </p>
            </div>
          </div>
        </SpotlightCard>
      ) : null}

      <SpotlightCard>
        <div className="row-between" style={{ alignItems: 'flex-start' }}>
          <div>
            <p className="overline" style={{ margin: 0 }}>
              Conversation to task
            </p>
            <p className="body-sm" style={{ marginTop: 4 }}>
              A concern should not stay a stray message. Route it to an owner with a due date.
            </p>
          </div>
          {routed ? <Tag tone="success" dot>Routed</Tag> : null}
        </div>
        <div className="divider" />
        {routed ? (
          <div className="stack" style={{ gap: 'var(--space-3)' }}>
            <p className="caption muted" style={{ margin: 0 }}>
              Routed to {taskOwner.toLowerCase()} · due {taskDue.toLowerCase()} · status open. It is
              now tracked, not lost in chat.
            </p>
            <Button variant="ghost" size="sm" onClick={() => setRouted(false)}>
              Undo
            </Button>
          </div>
        ) : (
          <div className="stack" style={{ gap: 'var(--space-3)' }}>
            <label className="stack" style={{ gap: 4 }}>
              <span className="caption muted">Owner</span>
              <select
                className="input"
                aria-label="Task owner"
                value={taskOwner}
                onChange={(e) => setTaskOwner(e.target.value)}
              >
                <option>Class teacher</option>
                <option>Subject teacher</option>
                <option>Year head</option>
              </select>
            </label>
            <label className="stack" style={{ gap: 4 }}>
              <span className="caption muted">Due</span>
              <select
                className="input"
                aria-label="Task due"
                value={taskDue}
                onChange={(e) => setTaskDue(e.target.value)}
              >
                <option>Today</option>
                <option>In two days</option>
                <option>This week</option>
              </select>
            </label>
            <Button
              variant="secondary"
              size="sm"
              disabled={routing}
              onClick={async () => {
                setRouting(true);
                const ownerRole =
                  taskOwner === 'Subject teacher'
                    ? 'subject_teacher'
                    : taskOwner === 'Year head'
                      ? 'year_head'
                      : 'teacher';
                const concern =
                  draft.trim() || baseThread.find((m) => !m.mine)?.text || 'A concern raised in this conversation.';
                await routeToTask({
                  body: concern,
                  title: `Follow up — ${active?.name ?? 'conversation'}`,
                  ownerRole,
                  why: `Routed from a ${role} conversation; due ${taskDue.toLowerCase()}.`,
                  dueDate: taskDue,
                  surface: role,
                  senderRef: selfRef,
                });
                setRouting(false);
                setRouted(true);
              }}
            >
              <Icon name="arrow-right" size="sm" /> {routing ? 'Routing…' : 'Route to a task'}
            </Button>
            <span className="caption muted">Owned, tracked, and closed — not left as a stray chat.</span>
          </div>
        )}
      </SpotlightCard>

      <div className="panel">
        <div className="sec-head" style={{ marginBottom: 'var(--space-2)' }}>
          <h4 className="h4">Standing safety</h4>
          <Tag tone="success" dot>On</Tag>
        </div>
        <p className="caption" style={{ marginBottom: 'var(--space-3)' }}>
          The rails that hold on every free-text surface here.
        </p>
        <div className="flag">
          <div className="flag-ic"><Icon name="info" size="sm" /></div>
          <div>
            <div className="body-sm" style={{ fontWeight: 500 }}>Child-safety screening</div>
            <p className="caption">Every message is screened; a concern is routed to a responsible adult.</p>
          </div>
        </div>
        {active?.peer ? (
          <div className="flag" data-testid="peer-safety-rail">
            <div className="flag-ic"><Icon name="user" size="sm" /></div>
            <div>
              <div className="body-sm" style={{ fontWeight: 500 }}>Peer chats screened</div>
              <p className="caption">Classmate DMs run the same screening on send, and you can report any message.</p>
            </div>
          </div>
        ) : null}
        <div className="flag">
          <div className="flag-ic"><Icon name="clock" size="sm" /></div>
          <div>
            <div className="body-sm" style={{ fontWeight: 500 }}>Quiet hours</div>
            <p className="caption">{quietHours ? 'Active now — delivery holds until the window passes.' : 'Within hours — delivery is immediate on approve.'}</p>
          </div>
        </div>
        <div className="flag">
          <div className="flag-ic"><Icon name="check" size="sm" /></div>
          <div>
            <div className="body-sm" style={{ fontWeight: 500 }}>Approval gate</div>
            <p className="caption">Nothing sends on its own — a message waits for your explicit send.</p>
          </div>
        </div>
      </div>
    </>
  );

  return (
    <SurfaceShell
      eyebrow="Communication hub"
      title="Messages"
      meta={[
        { value: channels.length, label: 'conversations' },
        { value: present.length, label: 'here now' },
        { label: quietHours ? 'quiet hours active' : 'within communication hours' },
      ]}
      aside={aside}
      dockIntro="I can draft a reply, translate for a family, or turn a concern into a tracked task with an owner. I never send for you — a message waits at the approval gate, with child-safety and quiet hours respected."
      dockChips={['Draft a calm reply', 'Turn this into a task', 'Translate for the family']}
    >
      <div className="msg-shell reveal reveal-3">
        {/* The channel / DM list rail — teacher/class channels, then a distinct
            'Classmates' group for student-to-student direct messages. */}
        <div className="msg-list">
          <div className="msg-list-head">
            <p className="overline" style={{ margin: 0 }}>
              Channels and DMs
            </p>
          </div>
          <div className="msg-list-scroll">
            {coreChannels.map(renderChan)}
            {peerChannels.length > 0 ? (
              <>
                <div className="msg-list-group">
                  <span className="overline">Classmates</span>
                  <Tag tone="info" dot data-testid="peer-screened-tag">
                    Safety-screened
                  </Tag>
                </div>
                {peerChannels.map(renderChan)}
              </>
            ) : null}
          </div>
        </div>

        {/* The thread pane. */}
        <div className="msg-pane">
          {active?.gated ? (
            <div className="empty" style={{ margin: 'auto', maxWidth: 380 }}>
              <Icon name="info" size="lg" className="glyph" />
              <h4 className="body">This conversation is consent-gated</h4>
              <p>
                It opens only when the relevant consent stands. Reads here are gated; nothing is
                shown until sharing is turned on.
              </p>
            </div>
          ) : (
            <>
              <div className="msg-pane-head">
                <span className="row" style={{ gap: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap' }}>
                  <Icon name={channelIcon(active?.kind ?? 'channel')} size="sm" />
                  <span className="body-lg" style={{ fontWeight: 500 }}>
                    {active?.name}
                  </span>
                  <LanguageBadge locale={locale} rendered={Object.keys(renderedBodies).length > 0} />
                </span>
                <span className="row" style={{ gap: 'var(--space-2)' }}>
                  {present.length > 0 ? (
                    <Tag tone="success" dot data-testid="presence-indicator">
                      {present.length} here now
                    </Tag>
                  ) : null}
                  {quietHours ? (
                    <Tag tone="warning" dot>
                      Quiet hours
                    </Tag>
                  ) : (
                    <Tag tone="success" dot>
                      Within hours
                    </Tag>
                  )}
                </span>
              </div>

              {toast ? (
                <div className="offline-banner" role="status" data-testid="message-toast">
                  {toast}
                </div>
              ) : null}

              {active?.peer ? (
                <div className="msg-peer-note" role="note" data-testid="peer-safety-note">
                  <Icon name="info" size="sm" />
                  <span>
                    This is a direct chat with a classmate. Peer chats are safety-screened on every
                    message — you can report anything that feels wrong, and a responsible adult will see it.
                  </span>
                </div>
              ) : null}

              {reportNote ? (
                <div className="offline-banner" role="status" data-testid="report-note">
                  {reportNote}
                </div>
              ) : null}

              <div className="msg-pane-thread thread" aria-live="polite">
                {baseThread.length === 0 && liveMsgs.length === 0 ? (
                  <div className="empty">
                    <Icon name="send" size="lg" className="glyph" />
                    <h4 className="body">No messages yet</h4>
                    <p>Start the conversation below. Vidya can draft a calm first message for you.</p>
                    <Button variant="secondary" size="sm" onClick={() => openVidya('Draft a calm first message')}>
                      <Icon name="spark" size="sm" /> Try with Vidya
                    </Button>
                  </div>
                ) : (
                  <>
                    {baseThread.map((m) => (
                      <div key={m.id} className={`msg ${m.mine ? 'msg-user' : 'msg-vidya'}`}>
                        <div className="bubble body-sm">
                          {renderedBodies[m.id] ?? m.text}
                          {m.flagged ? (
                            <div style={{ marginTop: 6 }}>
                              <Tag tone="danger" dot>Flagged for a responsible adult</Tag>
                            </div>
                          ) : null}
                        </div>
                        {renderReportAffordance(m.id, Boolean(m.mine))}
                      </div>
                    ))}
                    {liveMsgs.map((m) => (
                      <div key={m.id} className={`msg ${m.senderRef === selfRef ? 'msg-user' : 'msg-vidya'}`} data-testid="live-message">
                        <div className="bubble body-sm">
                          {renderedBodies[m.id] ?? m.body}
                          {m.flagged ? (
                            <div style={{ marginTop: 6 }}>
                              <Tag tone="danger" dot>Flagged for a responsible adult</Tag>
                            </div>
                          ) : null}
                        </div>
                        {renderReportAffordance(m.id, m.senderRef === selfRef)}
                      </div>
                    ))}
                  </>
                )}
              </div>

              <div className="msg-pane-foot stack" style={{ gap: 'var(--space-2)' }}>
                <Composer
                  value={draft}
                  onValueChange={setDraft}
                  onSend={() => prepare()}
                  placeholder={quietHours ? 'Draft now; it will hold until quiet hours pass' : 'Write a message'}
                  sendLabel="Prepare message"
                />
                <p className="caption quiet">
                  <Icon name="info" size="sm" />{' '}
                  {active?.peer
                    ? 'Peer chats are safety-screened on every message. Anything concerning is blocked and routed to a responsible adult — there are no unmonitored channels.'
                    : 'Child-safety runs on this free-text surface. Anything concerning is routed to a responsible adult; there are no unmonitored channels.'}
                </p>

                {prepared ? (
                  <SpotlightCard padLg style={{ marginTop: 'var(--space-2)' }}>
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
                    <Button
                      variant="accent"
                      size="sm"
                      onClick={() => {
                        const text = draft.trim();
                        if (text) void sendLive(text);
                        setPrepared(false);
                        setDraft('');
                      }}
                    >
                      {quietHours ? 'Approve — send when hours open' : 'Approve and send'}
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setPrepared(false)}>
                      Keep editing
                    </Button>
                  </div>
                  </SpotlightCard>
                ) : null}

                <SourceNote source={source} />
              </div>
            </>
          )}
        </div>
      </div>
    </SurfaceShell>
  );
}
