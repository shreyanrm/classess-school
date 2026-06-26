'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Icon, Matrix, ProgressBar, SpotlightCard, SuggestionChip, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { StatCell } from '../../_components/StatCell';
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
 * School-wide intelligence — recomposed to the sample-page bar. The three
 * action-first lenses (Academics / Behaviour / Care) ride a tab strip; the
 * Academics lens carries the live intelligence views the spec names: a count-up
 * school stat matrix, the study quadrant, the actual/predicted trajectory,
 * pacing protection, and the colour-banded mastery trends — every conclusion
 * opening an EvidenceDrawer. The Academics lens lays out as cols with a composed
 * aside (the improvement ignite-card, a what-is-slipping flag panel, a
 * handnote). The lens persists through the wall; the ask-anything chips answer
 * inline. Never a raw score or a formula.
 */
type Lens = 'academics' | 'behaviour' | 'care';
type Query = 'behind' | 'slipping' | 'support' | 'improved';

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
  const { source } = useGatewaySource('intelligence-views', { view: 'class-insights' });

  function startSet(band: QuadrantBand, group: QuadrantPoint[]) {
    openVidya(
      `Prepare the suggested set for the ${group.length} learners in the "${band}" band (${group
        .map((p) => `${p.label} ${p.section}`)
        .join(', ')}). I will approve it before it runs.`,
    );
  }

  // Plain headline school numbers for the count-up matrix.
  const onTrack = SCHOOL_STATS.find((s) => s.label === 'Sections on track');
  const behind = SCHOOL_STATS.find((s) => s.label === 'Sections behind');
  const independent = SCHOOL_STATS.find((s) => s.label === 'Students working independently');
  const needSupport = SCHOOL_STATS.find((s) => s.label === 'Students needing support');
  const slipping = SCHOOL_TRENDS.filter((t) => t.direction === 'down');
  const improving = SCHOOL_TRENDS.filter((t) => t.direction === 'up');

  const aside =
    surface.phase !== 'ready' || lens !== 'academics' ? null : (
      <>
        <div className="ignite-card reveal reveal-2">
          <div className="row-between" style={{ marginBottom: 14 }}>
            <span className="overline">Trending up</span>
            <Icon name="flame" size="md" style={{ color: 'var(--accent)' }} />
          </div>
          <div className="who">
            {improving[0]?.topic ?? 'Independence'} is moving school-wide
          </div>
          <p className="body-sm" style={{ opacity: 0.8, marginTop: 8 }}>
            {improving[0]?.note ??
              'More sections can now start unprompted after the targeted resets.'}
          </p>
        </div>

        <div className="panel">
          <div className="sec-head" style={{ marginBottom: 8 }}>
            <h4 className="h4" style={{ margin: 0 }}>
              Slipping this fortnight
            </h4>
            <Tag tone={slipping.length > 0 ? 'warning' : 'success'}>{slipping.length}</Tag>
          </div>
          <p className="caption" style={{ marginBottom: 12 }}>
            The few topics losing ground — surfaced first so you act before exam time.
          </p>
          {slipping.length === 0 ? (
            <p className="body-sm muted" style={{ margin: 0 }}>
              Nothing is slipping. The trends are holding or improving.
            </p>
          ) : (
            slipping.map((t) => (
              <div className="flag" key={t.topic}>
                <div className="flag-ic">
                  <Icon name="target" size="sm" />
                </div>
                <div>
                  <div className="body-sm" style={{ fontWeight: 500 }}>
                    {t.topic}
                  </div>
                  <p className="caption">{t.note}</p>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="panel" style={{ padding: '18px 20px' }}>
          <p className="handnote" style={{ fontSize: 22 }}>
            recover the two behind sections early — small now, a full unit later
          </p>
        </div>
      </>
    );

  return (
    <SurfaceShell
      eyebrow="Campus North"
      title="School-wide intelligence"
      breadcrumb={[{ label: 'School', href: '/' }, { label: 'Intelligence' }]}
      meta={[
        { value: onTrack ? Number(onTrack.value) + (behind ? Number(behind.value) : 0) : '—', label: 'sections watched' },
        { value: behind ? Number(behind.value) : 0, label: 'behind plan' },
        { label: 'action-first, never routine' },
      ]}
      tabs={[
        { label: 'Academics', active: lens === 'academics', onClick: () => setLens('academics') },
        { label: 'Behaviour', active: lens === 'behaviour', onClick: () => setLens('behaviour') },
        { label: 'Care', active: lens === 'care', onClick: () => setLens('care') },
      ]}
      actions={
        <Link href="/admin" className="btn btn-secondary row" style={{ gap: 'var(--space-2)' }}>
          <Icon name="arrow-right" size="sm" />
          Back to briefing
        </Link>
      }
      dockIntro="Ask the school anything. Which sections are behind, which topics are slipping, what unlocks a unit — I will answer in plain language and show the evidence."
      dockChips={[
        'Which sections are behind',
        'What is slipping this fortnight',
        'Where is teacher support most needed',
        'What improved after the May resets',
      ]}
      aside={aside}
    >
      {surface.phase !== 'ready' ? (
        <ReadStates phase={surface.phase} onRetry={surface.refresh} />
      ) : (
        <>
          <p className="caption quiet" style={{ margin: 0 }}>
            Each lens surfaces what needs a look, with the evidence one tap away.{' '}
            {surface.source === 'gateway'
              ? 'Your lens is read back from the event store, so you return to the view you last worked in.'
              : 'Your lens records to the event store when it is reachable.'}
          </p>

          <section>
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                Ask the school
              </h3>
              <span className="overline">plain language</span>
            </div>
            <div className="home-chips" style={{ justifyContent: 'flex-start' }}>
              {QUERIES.map((q) => (
                <SuggestionChip key={q.id} spark onClick={() => setQuery(q.id)}>
                  {q.label}
                </SuggestionChip>
              ))}
            </div>
            {query ? (
              <SpotlightCard style={{ marginTop: 'var(--space-3)' }}>
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
              <Matrix columns={2} className="reveal reveal-1">
                <StatCell
                  label="Sections on track"
                  value={onTrack ? Number(onTrack.value) : 0}
                  delta={onTrack?.detail}
                  tone="up"
                />
                <StatCell
                  label="Sections behind"
                  value={behind ? Number(behind.value) : 0}
                  delta={behind?.detail}
                  tone={behind && Number(behind.value) > 0 ? 'down' : 'flat'}
                />
                <StatCell
                  label="Working independently"
                  value={independent ? Number(independent.value) : 0}
                  delta={independent?.detail}
                  tone="up"
                />
                <StatCell
                  label="Needing support"
                  value={needSupport ? Number(needSupport.value) : 0}
                  delta={needSupport?.detail}
                  tone="flat"
                />
              </Matrix>
              <SourceNote source={source} />

              <section>
                <div className="sec-head">
                  <h3 className="h3" style={{ margin: 0 }}>
                    Study quadrant
                  </h3>
                  <span className="overline">independence × consistency</span>
                </div>
                <p className="caption quiet" style={{ marginTop: 'calc(var(--space-4) * -1)', marginBottom: 'var(--space-4)' }}>
                  Learners grouped by how independently and how consistently they are working. Tap a band
                  to see the group and launch the suggested set.
                </p>
                <StudyQuadrant onStartSet={startSet} />
              </section>

              <section>
                <div className="sec-head">
                  <h3 className="h3" style={{ margin: 0 }}>
                    Prediction and trajectory
                  </h3>
                  <span className="overline">actual solid · predicted dotted</span>
                </div>
                <p className="caption quiet" style={{ marginTop: 'calc(var(--space-4) * -1)', marginBottom: 'var(--space-4)' }}>
                  {TRAJECTORY.topic}
                </p>
                <Trajectory series={TRAJECTORY} />
              </section>

              <section>
                <div className="sec-head">
                  <h3 className="h3" style={{ margin: 0 }}>
                    Pacing protection
                  </h3>
                  <span className="overline">planned vs delivered</span>
                </div>
                <Matrix columns={4}>
                  <StatCell label="Sections" value={pacing.sections} />
                  <StatCell label="Behind plan" value={pacing.behind} tone={pacing.behind > 0 ? 'down' : 'flat'} />
                  <StatCell label="Periods lost" value={pacing.periodsLost} tone="down" />
                  <StatCell label="Low-risk to recover" value={pacing.autoEligible} tone="up" />
                </Matrix>
                <div className="stack" style={{ gap: 'var(--space-3)', marginTop: 'var(--space-4)' }}>
                  {PACING_ROWS.map((row) => {
                    const pct = Math.round((row.delivered / row.planned) * 100);
                    const isBehind = row.delivered < row.planned;
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
                          <Tag tone={isBehind ? 'warning' : 'success'} dot>
                            {isBehind ? 'Behind plan' : 'On plan'}
                          </Tag>
                        </div>
                        <ProgressBar
                          value={pct}
                          accent={!isBehind}
                          label={`Delivered against plan for ${row.section}`}
                          style={{ marginTop: 'var(--space-3)' }}
                        />
                        {isBehind ? (
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

              <section>
                <div className="sec-head">
                  <h3 className="h3" style={{ margin: 0 }}>
                    Mastery trends
                  </h3>
                  <span className="overline">in plain language</span>
                </div>
                <Matrix columns={3}>
                  {SCHOOL_TRENDS.map((t, i) => {
                    const d = DIRECTION[t.direction];
                    return (
                      <div
                        key={t.topic}
                        className={`subject-card reveal reveal-${i + 1}`}
                        style={
                          {
                            '--subject': `var(--${t.subject})`,
                            '--subject-ink': `var(--${t.subject}-ink)`,
                          } as React.CSSProperties
                        }
                      >
                        <div className="band">
                          <span className="name">{t.topic}</span>
                          <span className="code">{d.word}</span>
                        </div>
                        <div className="body">
                          <span className="row" style={{ gap: 'var(--space-2)', color: d.tone }}>
                            <Icon name={d.icon} size="sm" />
                            <span className="caption" style={{ fontWeight: 500 }}>
                              {d.word}
                            </span>
                          </span>
                          <p className="caption" style={{ marginTop: 6 }}>
                            {t.note}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </Matrix>
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
            <section>
              <div className="sec-head">
                <h3 className="h3" style={{ margin: 0 }}>
                  Engagement and behaviour
                </h3>
                <span className="overline">surfaced for support</span>
              </div>
              <p className="caption quiet" style={{ marginTop: 'calc(var(--space-4) * -1)', marginBottom: 'var(--space-4)' }}>
                Surfaced for support, not judgement — the few learners whose engagement shifted, with
                the signal behind it.
              </p>
              <div className="stack" style={{ gap: 'var(--space-3)' }}>
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
              </div>
            </section>
          ) : (
            <section>
              <div className="sec-head">
                <h3 className="h3" style={{ margin: 0 }}>
                  Care and wellbeing
                </h3>
                <span className="overline">routes to a human</span>
              </div>
              <p className="caption quiet" style={{ marginTop: 'calc(var(--space-4) * -1)', marginBottom: 'var(--space-4)' }}>
                Open concerns and care items in your queue. Each routes to a human; nothing acts on its
                own.
              </p>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Concern</th>
                      <th>Raised by</th>
                      <th>When</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ADMIN_CONCERNS.map((c) => (
                      <tr key={c.id}>
                        <td>{c.topic}</td>
                        <td className="muted">{c.from}</td>
                        <td className="muted">{c.raised}</td>
                        <td>
                          <Tag tone={c.status === 'new' ? 'warning' : 'info'} dot>
                            {c.status === 'new' ? 'New' : 'In review'}
                          </Tag>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
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
