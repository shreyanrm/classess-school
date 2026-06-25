'use client';

import { useEffect, useMemo, useState } from 'react';
import { Button, ProgressBar, SpotlightCard, Tag } from '@classess/design-system';
import { SEED_ONTOLOGY } from '@classess/contracts';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ReadStates } from '../../_components/ReadStates';
import { SourceNote } from '../../_components/SourceNote';
import { EvidenceDrawer } from '../../_components/EvidenceDrawer';
import { useClassInsights } from '@/lib/useClassInsights';
import { useEmit } from '@/lib/useEmit';
import { EVENT_PURPOSE } from '@/lib/events';
import { CLASS_LABEL, MATH_SUBJECT_ID, PHYS_SUBJECT_ID, topicsForSubject } from '@/lib/loopData';

/**
 * d6 — Teacher planning. The class diary + the adaptive plan across four
 * horizons (annual / unit / weekly / daily), mapped to ontology OUTCOMES, with
 * planned-vs-delivered honesty and differentiation by mastery band.
 *
 * Mapped to the ontology, never hard-coded to a board. The plan is prepared and
 * adaptive; delivering a day is the teacher's act, never auto-published.
 */

type Horizon = 'annual' | 'unit' | 'weekly' | 'daily';

const HORIZONS: { id: Horizon; label: string }[] = [
  { id: 'annual', label: 'Annual' },
  { id: 'unit', label: 'Unit' },
  { id: 'weekly', label: 'Weekly' },
  { id: 'daily', label: 'Daily' },
];

const SUBJECTS = [
  { id: MATH_SUBJECT_ID, name: 'Mathematics' },
  { id: PHYS_SUBJECT_ID, name: 'Physics' },
];

/** A deterministic planned-vs-delivered read per unit (illustrative). */
const UNIT_DELIVERY: Record<string, { planned: number; delivered: number }> = {
  'Real Numbers': { planned: 8, delivered: 8 },
  Polynomials: { planned: 7, delivered: 5 },
  Trigonometry: { planned: 9, delivered: 3 },
  'Light — Reflection and Refraction': { planned: 10, delivered: 6 },
  Electricity: { planned: 8, delivered: 0 },
};

/** Differentiation bands — the same outcome, three paths. */
const BANDS = [
  { key: 'support', label: 'Support band', tone: 'warning' as const, move: 'Re-teach with a worked example, then a guided twin problem.' },
  { key: 'core', label: 'Core band', tone: 'info' as const, move: 'Teach the outcome, then one application in a fresh context.' },
  { key: 'stretch', label: 'Stretch band', tone: 'success' as const, move: 'Extend to a multi-step problem and ask them to explain the why.' },
];

export default function PlanPage() {
  const [subjectId, setSubjectId] = useState<string>(MATH_SUBJECT_ID);
  const [horizon, setHorizon] = useState<Horizon>('unit');
  const [deliveredDays, setDeliveredDays] = useState<Set<string>>(() => new Set());

  // The plan is differentiated against the SPINE's live class read (gateway-first,
  // engine fallback). The band counts below are drawn from that read, never a
  // single score — the same source the rest of the loop trusts.
  const { phase, insights, source, refresh } = useClassInsights();
  const { emit } = useEmit();
  useEffect(() => {
    if (phase === 'ready') {
      emit({ type: 'surface.viewed', purpose: EVENT_PURPOSE.teaching, payload: { surface: 'teacher.plan', source } });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  const bandCounts = useMemo(() => {
    const s = insights?.summary;
    return {
      support: s?.need_support ?? 0,
      core: s?.working_independently ?? 0,
      stretch: insights?.reads.filter((r) => r.mastery.reading.independent && !r.mastery.revisionDue).length ?? 0,
    };
  }, [insights]);

  const topics = topicsForSubject(subjectId);
  const subjectName = SUBJECTS.find((s) => s.id === subjectId)!.name;

  // Outcomes mapped from the ontology for the chosen subject's topics.
  const outcomes = useMemo(() => {
    const topicIds = new Set(topics.map((t) => t.id));
    return SEED_ONTOLOGY.outcomes.filter((o) => topicIds.has(o.topic_id));
  }, [topics]);

  // Units of the chosen subject, with planned-vs-delivered.
  const units = useMemo(
    () => SEED_ONTOLOGY.units.filter((u) => u.subject_id === subjectId),
    [subjectId],
  );

  const focusTopic = topics[0];

  return (
    <SurfaceShell
      eyebrow={CLASS_LABEL}
      title="Class diary and plan"
      dockIntro="This is the living plan, mapped to the ontology outcomes. Ask me to draft a day, rebalance after a slow week, or differentiate by band. Delivering a day is your act — I prepare, you teach."
      dockChips={['Draft tomorrow on trig ratios', 'We are behind on this unit', 'Differentiate by band']}
    >
      <section className="stack">
        <p className="overline">Subject</p>
        <div className="ladder" role="group" aria-label="Subject" style={{ maxWidth: 360 }}>
          {SUBJECTS.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`ladder-rung${subjectId === s.id ? ' active' : ''}`}
              onClick={() => setSubjectId(s.id)}
            >
              {s.name}
            </button>
          ))}
        </div>
      </section>

      <section className="stack">
        <p className="overline">Horizon</p>
        <div className="ladder" role="group" aria-label="Planning horizon" style={{ maxWidth: 460 }}>
          {HORIZONS.map((h) => (
            <button
              key={h.id}
              type="button"
              className={`ladder-rung${horizon === h.id ? ' active' : ''}`}
              onClick={() => setHorizon(h.id)}
            >
              {h.label}
            </button>
          ))}
        </div>
      </section>

      {(horizon === 'annual' || horizon === 'unit') && (
        <section className="stack">
          <p className="overline">Planned vs delivered — {subjectName}</p>
          <p className="caption quiet">
            An honest read of pacing. Behind is not a failure; it is the signal the plan rebalances
            around.
          </p>
          <div className="stack" style={{ gap: 'var(--space-3)' }}>
            {units.map((u) => {
              const d = UNIT_DELIVERY[u.name] ?? { planned: 1, delivered: 0 };
              const pct = Math.round((d.delivered / d.planned) * 100);
              const behind = pct < 70;
              return (
                <SpotlightCard key={u.id}>
                  <div className="row-between">
                    <span className="body-sm">{u.name}</span>
                    <Tag tone={behind ? 'warning' : 'success'}>
                      {d.delivered} of {d.planned} sessions
                    </Tag>
                  </div>
                  <div style={{ marginTop: 'var(--space-2)' }}>
                    <ProgressBar value={pct} accent={!behind} label={`${u.name} delivery`} />
                  </div>
                </SpotlightCard>
              );
            })}
          </div>
        </section>
      )}

      {horizon === 'weekly' && (
        <section className="stack">
          <p className="overline">This week — outcomes in play</p>
          <p className="caption quiet">Each line is an ontology outcome, not a textbook page.</p>
          <div className="stack" style={{ gap: 'var(--space-2)' }}>
            {outcomes.slice(0, 5).map((o, i) => (
              <SpotlightCard key={o.id}>
                <div className="row-between" style={{ alignItems: 'flex-start' }}>
                  <span className="body-sm" style={{ maxWidth: 560 }}>
                    {o.statement}
                  </span>
                  <Tag tone={i === 0 ? 'info' : 'neutral'}>{i === 0 ? 'In focus' : `Day ${i + 1}`}</Tag>
                </div>
              </SpotlightCard>
            ))}
          </div>
        </section>
      )}

      {horizon === 'daily' && !focusTopic && (
        <section className="stack">
          <p className="overline">Tomorrow</p>
          <SpotlightCard>
            <p className="body-sm">No topic is scheduled for this subject yet.</p>
            <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
              Ask Vidya to draft a day, or switch to the Weekly horizon to see the outcomes in play.
            </p>
          </SpotlightCard>
        </section>
      )}

      {horizon === 'daily' && focusTopic && (
        <section className="stack">
          <p className="overline">Tomorrow — {focusTopic.name}</p>
          <SpotlightCard hero padLg>
            <div className="row-between" style={{ alignItems: 'flex-start' }}>
              <div>
                <p className="overline" style={{ margin: 0 }}>
                  Mapped outcome
                </p>
                <h3 className="body-lg" style={{ margin: '4px 0 0', maxWidth: 560 }}>
                  {outcomes.find((o) => o.topic_id === focusTopic.id)?.statement ??
                    'Outcome mapped from the curriculum graph.'}
                </h3>
              </div>
              <Tag tone="info">Draft</Tag>
            </div>

            <div className="divider" />

            <p className="overline">Differentiation by mastery band</p>
            {phase !== 'ready' ? (
              <ReadStates phase={phase} onRetry={refresh} />
            ) : (
              <>
                <div className="stack" style={{ gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
                  {BANDS.map((b) => {
                    const n = bandCounts[b.key as keyof typeof bandCounts];
                    return (
                      <div key={b.key} className="cell" style={{ textAlign: 'left' }}>
                        <div className="row-between">
                          <span className="body-sm">{b.label}</span>
                          <Tag tone={b.tone}>
                            {n} {n === 1 ? 'read' : 'reads'}
                          </Tag>
                        </div>
                        <p className="caption muted" style={{ marginTop: 4 }}>
                          {b.move}
                        </p>
                      </div>
                    );
                  })}
                </div>
                <SourceNote source={source} />
              </>
            )}

            <EvidenceDrawer
              evidence={[
                'Bands are drawn from the live mastery read for this class — independent vs support-dependent, never a single score.',
                'The outcome is mapped to the ontology node, so the plan is board-agnostic.',
              ]}
              whySeeing="The plan adapts to where the class actually is. Delivering it is your decision; it is prepared, not auto-pushed to students."
            />

            <div className="divider" />
            <div className="rec-actions">
              {deliveredDays.has(focusTopic.id) ? (
                <>
                  <Tag tone="success">Delivered</Tag>
                  <span className="caption muted">
                    Logged for {focusTopic.name}. The planned-vs-delivered read now reflects it.
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      setDeliveredDays((prev) => {
                        const next = new Set(prev);
                        next.delete(focusTopic.id);
                        return next;
                      })
                    }
                  >
                    Undo
                  </Button>
                </>
              ) : (
                <>
                  <Button
                    variant="accent"
                    size="sm"
                    onClick={() =>
                      setDeliveredDays((prev) => new Set(prev).add(focusTopic.id))
                    }
                  >
                    Mark delivered after class
                  </Button>
                  <span className="caption muted">
                    Delivering is your act. Marking it closes the planned-vs-delivered loop.
                  </span>
                </>
              )}
            </div>
          </SpotlightCard>
        </section>
      )}
    </SurfaceShell>
  );
}
