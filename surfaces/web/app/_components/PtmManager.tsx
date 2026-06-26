'use client';

import { useMemo, useState } from 'react';
import { Button, ConfidenceBand, Icon, Tag } from '@classess/design-system';
import { EvidenceDrawer } from './EvidenceDrawer';
import { SourceNote } from './SourceNote';
import type { PtmQuery, PtmSlot, TeacherPtm, ReadSource } from '@/lib/vizData';

/* ============================================================================
   PtmManager — the TEACHER side of parent-teacher meetings, the counterpart to
   the parent's /parent/together. Three calm panels:
     · Slot availability — the day's slots with their status (open / requested /
       booked). A slot is held only when a request is matched — the teacher
       confirms a requested slot; nothing is auto-booked.
     · Parent queries — incoming questions, each with a PREPARED talking point
       the teacher can mark as prepared before the meeting.
     · Meeting summaries — calm, plain records of completed meetings + agreed
       next steps, shareable, never a raw score.

   v3 grammar: no auto-send (confirming a slot is an explicit human action),
   evidence-first (the prepared point is the lineage), subjects on the cool
   accent palette (never the ultramarine signature, never coral), depth =
   hairline + tonal step, NO shadow, reduced-motion safe. Local edits are
   host-owned and never auto-persist.
   ============================================================================ */

const SLOT_META: Record<PtmSlot['status'], { label: string; tone: 'success' | 'warning' | 'info' }> = {
  open: { label: 'Open', tone: 'info' },
  requested: { label: 'Requested', tone: 'warning' },
  booked: { label: 'Booked', tone: 'success' },
};

export interface PtmManagerProps {
  data: TeacherPtm;
  source?: ReadSource;
}

export function PtmManager({ data, source = 'fallback' }: PtmManagerProps) {
  // Local, session-only state — confirming a slot or marking a query prepared is
  // an explicit teacher action; nothing here writes to a learner or auto-fires.
  const [confirmed, setConfirmed] = useState<Set<string>>(new Set());
  const [opened, setOpened] = useState<Set<string>>(new Set());
  const [closed, setClosed] = useState<Set<string>>(new Set());
  const [prepared, setPrepared] = useState<Record<string, boolean>>({});

  const slotStatus = (slot: PtmSlot): PtmSlot['status'] => {
    if (closed.has(slot.id)) return 'open';
    if (confirmed.has(slot.id)) return 'booked';
    if (opened.has(slot.id)) return 'open';
    return slot.status;
  };

  const queryPrepared = (q: PtmQuery): boolean => prepared[q.id] ?? q.prepared;

  const counts = useMemo(() => {
    let open = 0;
    let requested = 0;
    let booked = 0;
    for (const s of data.slots) {
      const st = slotStatus(s);
      if (st === 'open') open++;
      else if (st === 'requested') requested++;
      else booked++;
    }
    const preparedQueries = data.queries.filter((q) => queryPrepared(q)).length;
    return { open, requested, booked, preparedQueries };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, confirmed, opened, closed, prepared]);

  return (
    <div className="stack" style={{ gap: 'var(--space-6)' }}>
      {/* ── Slot availability ──────────────────────────────────────────────── */}
      <section className="stack viz-card" style={{ gap: 'var(--space-5)' }}>
        <div className="sec-head">
          <div>
            <p className="overline" style={{ margin: 0 }}>Slot availability · {data.classLabel}</p>
            <h4 className="h4" style={{ margin: '4px 0 0' }}>{data.day}</h4>
          </div>
          <ConfidenceBand level={data.confidence} />
        </div>

        <div className="row" style={{ gap: 'var(--space-4)', flexWrap: 'wrap' }}>
          <span className="caption muted"><strong style={{ color: 'var(--text-primary)' }}>{counts.open}</strong> open</span>
          <span className="caption muted"><strong style={{ color: 'var(--text-primary)' }}>{counts.requested}</strong> requested</span>
          <span className="caption muted"><strong style={{ color: 'var(--text-primary)' }}>{counts.booked}</strong> booked</span>
        </div>

        <ul className="ptm-slots">
          {data.slots.map((slot) => {
            const st = slotStatus(slot);
            const meta = SLOT_META[st];
            return (
              <li className={`ptm-slot ptm-slot-${st}`} key={slot.id}>
                <span className="ptm-slot-time">
                  <Icon name="clock" size="sm" />
                  {slot.time}
                </span>
                <span className="ptm-slot-with">
                  {st === 'open' ? (
                    <span className="caption muted">No one assigned</span>
                  ) : (
                    <span className="body-sm">{slot.withLabel}</span>
                  )}
                </span>
                <Tag tone={meta.tone}>{meta.label}</Tag>
                <span className="ptm-slot-action">
                  {st === 'requested' ? (
                    <Button variant="accent" size="sm" onClick={() => setConfirmed((p) => new Set(p).add(slot.id))}>
                      Confirm slot
                    </Button>
                  ) : st === 'booked' ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setConfirmed((p) => { const n = new Set(p); n.delete(slot.id); return n; });
                        setClosed((p) => new Set(p).add(slot.id));
                      }}
                    >
                      Release
                    </Button>
                  ) : (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setOpened((p) => new Set(p).add(slot.id));
                        setClosed((p) => { const n = new Set(p); n.delete(slot.id); return n; });
                      }}
                    >
                      Keep open
                    </Button>
                  )}
                </span>
              </li>
            );
          })}
        </ul>
        <p className="caption quiet" style={{ margin: 0 }}>
          A slot is held only when you confirm a request — nothing is auto-booked. Confirming notifies
          the parent that their requested time is held.
        </p>
      </section>

      {/* ── Parent queries ─────────────────────────────────────────────────── */}
      <section className="stack">
        <div className="sec-head">
          <h3 className="h3" style={{ margin: 0 }}>Parent queries</h3>
          <Tag tone={counts.preparedQueries === data.queries.length ? 'success' : 'warning'}>
            {counts.preparedQueries} of {data.queries.length} prepared
          </Tag>
        </div>
        {data.queries.length === 0 ? (
          <div className="empty">
            <Icon name="success" size="lg" className="glyph" />
            <h4 className="body">No queries waiting</h4>
            <p>No parent has sent a question ahead of the meeting day.</p>
          </div>
        ) : (
          <ul className="ptm-queries">
            {data.queries.map((q) => {
              const isPrepared = queryPrepared(q);
              return (
                <li className="ptm-query subject-tinted" data-subject={q.subject} key={q.id}>
                  <div className="ptm-query-head">
                    <span className="row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
                      <span className="subject-dot" style={{ background: `var(--${q.subject})` }} aria-hidden="true" />
                      <span className="body-sm" style={{ fontWeight: 'var(--fw-medium)' }}>{q.fromLabel}</span>
                    </span>
                    <Tag tone={isPrepared ? 'success' : 'info'}>{isPrepared ? 'Prepared' : 'To prepare'}</Tag>
                  </div>
                  <p className="body-sm ptm-query-question">“{q.question}”</p>
                  <div className="ptm-query-prepared">
                    <span className="overline">Prepared talking point</span>
                    <p className="body-sm" style={{ margin: '4px 0 0' }}>{q.preparedPoint}</p>
                  </div>
                  <div className="rec-actions">
                    {isPrepared ? (
                      <Button variant="ghost" size="sm" onClick={() => setPrepared((p) => ({ ...p, [q.id]: false }))}>
                        Reopen
                      </Button>
                    ) : (
                      <Button variant="accent" size="sm" onClick={() => setPrepared((p) => ({ ...p, [q.id]: true }))}>
                        Mark prepared
                      </Button>
                    )}
                    <EvidenceDrawer
                      claim={q.question}
                      confidence={data.confidence}
                      evidence={[
                        'The prepared talking point draws on the same evidence-first read the parent sees — a band and its lineage, never a raw mark.',
                        'Marking a query prepared is a private note to you; it sends nothing to the parent.',
                      ]}
                      whySeeing="A parent question is paired with a prepared, evidence-first point so the meeting starts from a shared, calm read — not a defensive number."
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {/* ── Meeting summaries ──────────────────────────────────────────────── */}
      <section className="stack">
        <div className="sec-head">
          <h3 className="h3" style={{ margin: 0 }}>Meeting summaries</h3>
          <span className="overline">calm, shareable records</span>
        </div>
        {data.summaries.length === 0 ? (
          <div className="empty">
            <Icon name="calendar" size="lg" className="glyph" />
            <h4 className="body">No meetings recorded yet</h4>
            <p>After a meeting, a plain summary and the agreed next steps will sit here.</p>
          </div>
        ) : (
          <ul className="ptm-summaries">
            {data.summaries.map((m) => (
              <li className="ptm-summary" key={m.id}>
                <div className="ptm-summary-head">
                  <span className="body-sm" style={{ fontWeight: 'var(--fw-medium)' }}>{m.withLabel}</span>
                  <span className="caption muted">{m.when}</span>
                </div>
                <p className="body-sm" style={{ margin: 'var(--space-2) 0 0' }}>{m.note}</p>
                {m.agreed.length > 0 ? (
                  <ul className="ptm-summary-agreed">
                    {m.agreed.map((a, i) => (
                      <li key={i} className="ptm-summary-agreed-item">
                        <Icon name="check" size="sm" />
                        <span className="body-sm">{a}</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
        )}
        <p className="caption quiet" style={{ margin: 0 }}>
          Summaries are plain language and never carry a raw score — they record what was agreed, so the
          next conversation can pick up where this one left off.
        </p>
      </section>

      <SourceNote source={source} />
    </div>
  );
}
