'use client';

import { useState } from 'react';
import { Cell, Icon, Matrix, ProgressBar, SpotlightCard, Stat, SuggestionChip, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { EvidenceDrawer } from '../../_components/EvidenceDrawer';
import { ReadStates } from '../../_components/ReadStates';
import { SourceNote } from '../../_components/SourceNote';
import { StudyQuadrant } from '../../_components/StudyQuadrant';
import { Trajectory } from '../../_components/Trajectory';
import { useAdminConfig } from '@/lib/adminConfig';
import { useGatewaySource } from '@/lib/useGatewaySource';
import { SCHOOL_STATS, SCHOOL_TRENDS } from '@/lib/mock';
import { ADMIN_CONCERNS, ADMIN_INTERVENTIONS } from '@/lib/mock';
import { PACING_ROWS, TRAJECTORY, pacingSummary, type QuadrantBand, type QuadrantPoint } from '@/lib/adminData';
import { openVidya } from '../../_components/VidyaOrb';

const DIRECTION: Record<'up' | 'flat' | 'down', { tone: string; word: string; icon: 'arrow-up-right' | 'arrow-right' }> = {
  up: { tone: 'var(--success)', word: 'Improving', icon: 'arrow-up-right' },
  flat: { tone: 'var(--text-tertiary)', word: 'Holding', icon: 'arrow-right' },
  down: { tone: 'var(--hot-red)', word: 'Slipping', icon: 'arrow-right' },
};

/**
 * School-wide intelligence — three action-first lenses (Academics / Behaviour /
 * Care). The Academics lens carries the live intelligence views the spec names:
 * the study quadrant (tap a band to launch a remedial set), the trajectory
 * (actual solid / predicted dotted), pacing protection, and the plain-language
 * mastery trends — every conclusion opening an EvidenceDrawer. The ask-anything
 * chips answer inline from the same shared data layer; Vidya stays docked for
 * the open follow-up. Never a raw score or a formula.
 */
type Lens = 'academics' | 'behaviour' | 'care';
type Query = 'behind' | 'slipping' | 'support' | 'improved';

const LENSES: { id: Lens; label: string }[] = [
  { id: 'academics', label: 'Academics' },
  { id: 'behaviour', label: 'Behaviour' },
  { id: 'care', label: 'Care' },
];

const QUERIES: { id: Query; label: string }[] = [
  { id: 'behind', label: 'Which sections are behind' },
  { id: 'slipping', label: 'What is slipping this fortnight' },
  { id: 'support', label: 'Where is teacher support most needed' },
  { id: 'improved', label: 'What improved after the May resets' },
];

function answerFor(q: Query): string {
  const behind = SCHOOL_STATS.find((s) => s.label === 'Sections behind');
  const teacherSupport = SCHOOL_STATS.find((s) => s.label === 'Teachers needing support');
  const slipping = SCHOOL_TRENDS.filter((t) => t.direction === 'down');
  const improving = SCHOOL_TRENDS.filter((t) => t.direction === 'up');
  switch (q) {
    case 'behind':
      return behind
        ? `${behind.value} sections are behind — ${behind.detail}. They are flagged here so you can manage by exception rather than read every section.`
        : 'Every section is inside the calm band against the current pacing plan right now.';
    case 'slipping':
      return slipping.length > 0
        ? `${slipping.map((t) => t.topic).join(' and ')} ${slipping.length === 1 ? 'is' : 'are'} slipping. ${slipping[0]!.note}`
        : 'Nothing is slipping this fortnight — the trends are holding or improving.';
    case 'support':
      return teacherSupport
        ? `${teacherSupport.value} teachers are surfaced from the coaching layer as possibly needing support — a private note, never a performance score. Start with the longest-stalled evaluation flow.`
        : 'No teacher is flagged for support right now.';
    case 'improved':
      return improving.length > 0
        ? `${improving.map((t) => t.topic).join(' and ')} improved. ${improving[0]!.note}`
        : 'No clear improvement has registered since the resets yet — give it another fortnight of evidence.';
  }
}

export default function AdminIntelligencePage() {
  // The chosen lens is governed config: rehydrated from the event store (a
  // persisted lens wins over the default), so the leader returns to the view they
  // last worked in. Switching lens is authorized at the wall and appended to the
  // immutable store. The hook also carries the five designed read states.
  const surface = useAdminConfig('intelligence');
  const savedLens = surface.config.lens;
  const lens: Lens =
    savedLens === 'behaviour' || savedLens === 'care' || savedLens === 'academics'
      ? (savedLens as Lens)
      : 'academics';
  const setLens = (l: Lens) => {
    void surface.set('lens', l);
  };
  const [query, setQuery] = useState<Query | null>(null);
  const pacing = pacingSummary();
  // The school-wide stats / trends / pacing / trajectory are the spine's
  // intelligence-views reads. Probe the wall so the OBSERVABLE source marker sits
  // on the STATS themselves — these seed views render either way, but never as if
  // they were live when the spine did not answer.
  const { source } = useGatewaySource('intelligence-views', { view: 'class-insights' });

  // The drill that ACTS — launch the suggested remedial/grouping set for a band
  // by handing the group to Vidya, which prepares it within the permission
  // ladder. Never a dead end; the human approves the prepared set there.
  function startSet(band: QuadrantBand, group: QuadrantPoint[]) {
    openVidya(
      `Prepare the suggested set for the ${group.length} learners in the "${band}" band (${group
        .map((p) => `${p.label} ${p.section}`)
        .join(', ')}). I will approve it before it runs.`,
    );
  }

  return (
    <SurfaceShell
      eyebrow="Campus North"
      title="School-wide intelligence"
      dockIntro="Ask the school anything. Which sections are behind, which topics are slipping, what unlocks a unit — I will answer in plain language and show the evidence."
      dockChips={[
        'Which sections are behind',
        'What is slipping this fortnight',
        'Where is teacher support most needed',
        'What improved after the May resets',
      ]}
    >
      {surface.phase !== 'ready' ? (
        <ReadStates phase={surface.phase} onRetry={surface.refresh} />
      ) : (
      <>
      <section className="stack">
        <div className="ladder" role="tablist" aria-label="Intelligence lens" style={{ maxWidth: 420 }}>
          {LENSES.map((l) => (
            <button
              key={l.id}
              type="button"
              role="tab"
              aria-selected={lens === l.id}
              className={`ladder-rung${lens === l.id ? ' active' : ''}`}
              onClick={() => setLens(l.id)}
            >
              {l.label}
            </button>
          ))}
        </div>
        <p className="caption quiet">
          Action-first, never routine stats. Each lens surfaces what needs a look, with the evidence
          one tap away.{' '}
          {surface.source === 'gateway'
            ? 'Your lens is read back from the event store, so you return to the view you last worked in.'
            : 'Your lens records to the event store when it is reachable.'}
        </p>
      </section>

      <section className="stack">
        <p className="overline">Ask the school</p>
        <p className="caption quiet">
          A plain-language read, answered here from the same intelligence the views below show. For a
          deeper follow-up, keep the conversation going with Vidya.
        </p>
        <div className="home-chips" style={{ justifyContent: 'flex-start' }}>
          {QUERIES.map((q) => (
            <SuggestionChip key={q.id} spark onClick={() => setQuery(q.id)}>
              {q.label}
            </SuggestionChip>
          ))}
        </div>
        {query ? (
          <SpotlightCard>
            <p className="overline" style={{ margin: 0 }}>
              Answer
            </p>
            <p className="body" style={{ marginTop: 'var(--space-3)' }}>
              {answerFor(query)}
            </p>
            <EvidenceDrawer
              evidence={[
                'Read from the school-wide signals in the intelligence views below — counts and directions, never a raw score.',
                'Each section/topic links back to its own class read and the attempts behind it.',
              ]}
              whySeeing="You asked the school a direct question; this is the plain-language read with its lineage, so you can act without a deeper drill."
            />
          </SpotlightCard>
        ) : null}
      </section>

      {lens === 'academics' ? (
        <>
          <section className="stack">
            <p className="overline">Across the school, this week</p>
            <Matrix columns={3}>
              {SCHOOL_STATS.map((s) => (
                <Cell key={s.label}>
                  <Stat label={s.label} value={s.value} />
                  <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
                    {s.detail}
                  </p>
                </Cell>
              ))}
            </Matrix>
            <SourceNote source={source} />
          </section>

          <section className="stack">
            <p className="overline">Study quadrant</p>
            <p className="caption quiet">
              Learners grouped by how independently and how consistently they are working. Tap a band
              to see the group and launch the suggested set.
            </p>
            <StudyQuadrant onStartSet={startSet} />
          </section>

          <section className="stack">
            <p className="overline">Prediction and trajectory</p>
            <p className="caption quiet">{TRAJECTORY.topic}</p>
            <Trajectory series={TRAJECTORY} />
          </section>

          <section className="stack">
            <p className="overline">Pacing protection</p>
            <div className="cols-2">
              <Stat label="Sections" value={pacing.sections} />
              <Stat label="Behind plan" value={pacing.behind} />
              <Stat label="Periods lost" value={pacing.periodsLost} />
              <Stat label="Low-risk to recover" value={pacing.autoEligible} />
            </div>
            <div className="stack" style={{ gap: 'var(--space-3)' }}>
              {PACING_ROWS.map((row) => {
                const pct = Math.round((row.delivered / row.planned) * 100);
                const behind = row.delivered < row.planned;
                return (
                  <SpotlightCard key={row.id}>
                    <div className="row-between" style={{ alignItems: 'flex-start' }}>
                      <div>
                        <h3 className="body-lg" style={{ margin: 0 }}>
                          {row.section} — {row.subject}
                        </h3>
                        <p className="caption muted" style={{ marginTop: 4 }}>
                          {row.delivered} of {row.planned} periods delivered
                        </p>
                      </div>
                      <Tag tone={behind ? 'warning' : 'success'} dot>
                        {behind ? 'Behind plan' : 'On plan'}
                      </Tag>
                    </div>
                    <ProgressBar
                      value={pct}
                      accent={!behind}
                      label={`Delivered against plan for ${row.section}`}
                      style={{ marginTop: 'var(--space-3)' }}
                    />
                    {behind ? (
                      <>
                        <p className="body-sm" style={{ marginTop: 'var(--space-3)' }}>
                          <span className="quiet">Recovery. </span>
                          {row.recovery}
                        </p>
                        <div className="row" style={{ gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
                          <Tag tone={row.lowRisk ? 'success' : 'neutral'}>
                            {row.lowRisk ? 'Low-risk — automatable within policy' : 'Needs a review first'}
                          </Tag>
                        </div>
                        <EvidenceDrawer
                          evidence={[
                            `Planned ${row.planned} periods to date; ${row.delivered} delivered — the gap is instructional time lost.`,
                            row.lowRisk
                              ? 'The recovery stays inside the pacing policy, so it can be automated once you approve the approach.'
                              : 'The gap is large enough that the recovery is held for a coordinator review before anything commits.',
                          ]}
                          whySeeing="Pacing protection tracks planned versus delivered so a behind section is recovered early, not discovered at exam time."
                        />
                      </>
                    ) : (
                      <p className="caption muted" style={{ marginTop: 'var(--space-3)' }}>
                        Inside the calm band — no recovery needed.
                      </p>
                    )}
                  </SpotlightCard>
                );
              })}
            </div>
          </section>

          <section className="stack">
            <p className="overline">Mastery trends, in plain language</p>
            <div className="admin-list">
              {SCHOOL_TRENDS.map((t) => {
                const d = DIRECTION[t.direction];
                return (
                  <div key={t.topic} className="admin-list-row">
                    <div>
                      <div className="body-sm">{t.topic}</div>
                      <div className="caption muted">{t.note}</div>
                    </div>
                    <span className="row" style={{ gap: 'var(--space-2)', color: d.tone, whiteSpace: 'nowrap' }}>
                      <Icon name={d.icon} size="sm" />
                      <span className="caption">{d.word}</span>
                    </span>
                  </div>
                );
              })}
            </div>
            <EvidenceDrawer
              evidence={[
                'Each trend reads what learners can now do unprompted versus with support, aggregated across sections.',
                'A direction is shown — improving, holding, slipping — never a number or a formula.',
              ]}
              whySeeing="Trends tell you where to put attention next; the evidence keeps the curriculum explainable, not a black box."
            />
          </section>
        </>
      ) : lens === 'behaviour' ? (
        <section className="stack">
          <p className="overline">Engagement and behaviour</p>
          <p className="caption quiet">
            Surfaced for support, not judgement — the few learners whose engagement shifted, with the
            signal behind it.
          </p>
          {ADMIN_INTERVENTIONS.map((iv) => (
            <SpotlightCard key={iv.id}>
              <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-4)' }}>
                <div>
                  <h3 className="body-lg" style={{ margin: 0 }}>
                    {iv.label} — {iv.section}
                  </h3>
                  <p className="body-sm muted" style={{ marginTop: 'var(--space-2)' }}>
                    {iv.reason}
                  </p>
                </div>
                <Tag tone={iv.confidence === 'high' ? 'warning' : 'info'} dot>
                  Needs a look
                </Tag>
              </div>
              <EvidenceDrawer
                evidence={[
                  'Drawn from attendance and engagement signals over the last fortnight, against this learner’s own baseline.',
                  'A signal to act on early, not a label — the read is private and supportive.',
                ]}
                whySeeing="Behaviour shifts often precede an academic dip; surfacing them early lets you reach the student before it shows in results."
              />
            </SpotlightCard>
          ))}
        </section>
      ) : (
        <section className="stack">
          <p className="overline">Care and wellbeing</p>
          <p className="caption quiet">
            Open concerns and care items in your queue. Each routes to a human; nothing acts on its own.
          </p>
          <div className="admin-list">
            {ADMIN_CONCERNS.map((c) => (
              <div key={c.id} className="admin-list-row">
                <div>
                  <div className="body-sm">{c.topic}</div>
                  <div className="caption muted">
                    {c.from} · raised {c.raised}
                  </div>
                </div>
                <Tag tone={c.status === 'new' ? 'warning' : 'info'}>
                  {c.status === 'new' ? 'New' : 'In review'}
                </Tag>
              </div>
            ))}
          </div>
          <EvidenceDrawer
            evidence={[
              'Concerns are raised by families through the messaging surface and queued here with their context.',
              'Care items carry only a generic relationship label, never personal information.',
            ]}
            whySeeing="Care sits alongside academics so a learner is seen as a whole person, and no concern quietly falls through."
          />
        </section>
      )}
      </>
      )}
    </SurfaceShell>
  );
}
