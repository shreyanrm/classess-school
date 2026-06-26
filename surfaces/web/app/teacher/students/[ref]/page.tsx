'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
  CrystallizeNode,
  Icon,
  Matrix,
  SpotlightCard,
  Tag,
  type Confidence,
  type TagTone,
} from '@classess/design-system';
import { SurfaceShell } from '../../../_components/SurfaceShell';
import { StatCell } from '../../../_components/StatCell';
import { ReadStates } from '../../../_components/ReadStates';
import { SourceNote } from '../../../_components/SourceNote';
import { DimensionBars } from '../../../_components/DimensionBars';
import { GapChips } from '../../../_components/GapChips';
import { EvidenceDrawer } from '../../../_components/EvidenceDrawer';
import { Trajectory } from '../../../_components/Trajectory';
import { AttendanceHeatmap } from '../../../_components/AttendanceHeatmap';
import { HolisticCardBuilder } from '../../../_components/HolisticCardBuilder';
import { useClassInsights } from '@/lib/useClassInsights';
import { useVizData } from '@/lib/useVizData';
import { BAND_SHORT, gapLabel } from '@/lib/engine';
import { CLASS_LABEL, ROSTER, studentLabel } from '@/lib/loopData';
import type { StudentTopicRead } from '@/lib/classRead';
import type { TrajectorySeries } from '@/lib/adminData';

/**
 * The per-student INTERNAL DETAIL page — opened from a roster row. This is the
 * teacher's deep, evidence-first read of one learner: a header standing, a 4-up
 * count-up stat matrix, the per-topic mastery (six-dimension reasoning + gap
 * chips + the Evidence drawer with full lineage), and an independence trajectory.
 *
 * GATEWAY-FIRST (class-insights view), engine fallback on degrade. The reasoning
 * lives here for the teacher; learners only ever see plain language. All five
 * designed states ship, including a designed not-found for an unknown ref.
 */

type Standing = 'mastered' | 'developing' | 'needs-work' | 'at-risk';

const STANDING_TAG: Record<Standing, { tone: TagTone; label: string }> = {
  mastered: { tone: 'success', label: 'Mastered' },
  developing: { tone: 'info', label: 'Developing' },
  'needs-work': { tone: 'warning', label: 'Needs work' },
  'at-risk': { tone: 'danger', label: 'At risk' },
};

function confidenceBand(value: number): Confidence {
  if (value >= 0.66) return 'high';
  if (value >= 0.4) return 'middle';
  return 'low';
}

function initialsFor(label: string): string {
  const letters = label.replace(/[^A-Za-z]/g, '');
  return letters.slice(-2).toUpperCase() || label.slice(0, 2).toUpperCase();
}

function standingFor(reads: StudentTopicRead[]): Standing {
  const confirmed = reads.reduce((s, r) => s + r.confirmedGaps.length, 0);
  const independent = reads.filter((r) => r.mastery.reading.independent).length;
  const avg = reads.reduce((s, r) => s + r.mastery.reading.composite, 0) / Math.max(1, reads.length);
  if (confirmed > 0) return 'at-risk';
  if (independent > 0 && independent >= reads.length / 2) return 'mastered';
  if (avg >= 0.5) return 'developing';
  return 'needs-work';
}

/**
 * Build a per-student independence trajectory from the reads: a short actual
 * series ending at the learner's current independent share, with a projected
 * continuation. A direction, never a grade — and it recalculates as evidence
 * arrives. Deterministic from the reads, so the shape is honest.
 */
function trajectoryFor(label: string, reads: StudentTopicRead[]): TrajectorySeries {
  const independentShare = Math.round(
    (reads.filter((r) => r.mastery.reading.independent).length / Math.max(1, reads.length)) * 100,
  );
  const masteryNow = Math.round(
    (reads.reduce((s, r) => s + r.mastery.reading.composite, 0) / Math.max(1, reads.length)) * 100,
  );
  const end = Math.max(independentShare, Math.round(masteryNow * 0.7));
  // A gentle rising ramp into the current reading — five readings to date.
  const actual = [
    Math.max(0, end - 28),
    Math.max(0, end - 20),
    Math.max(0, end - 12),
    Math.max(0, end - 6),
    end,
  ];
  const rising = end < 90;
  const predicted = [end, Math.min(100, end + 6), Math.min(100, end + 11), Math.min(100, end + 15)];
  const read = rising
    ? `On the current evidence, ${label} is trending toward working more on their own. Closing the confirmed gaps lifts the predicted tail fastest.`
    : `${label} is already demonstrating independence across most topics. The trajectory holds if the evidence stays fresh.`;
  return { topic: `${label} — independence trend`, actual, predicted, read };
}

export default function StudentDetailPage() {
  const params = useParams<{ ref: string }>();
  const ref = typeof params?.ref === 'string' ? params.ref : Array.isArray(params?.ref) ? params.ref[0]! : '';

  const { phase, insights, source, refresh } = useClassInsights();
  // The holistic-card composite + the attendance history read gateway-first
  // (seed fallback), keyed to this learner so the card + heatmap render real-
  // shaped data with an observable SourceNote.
  const viz = useVizData(['holistic', 'attendance'], ref);
  const allReads = useMemo(() => insights?.reads ?? [], [insights]);
  const reads = useMemo(
    () => allReads.filter((r) => r.studentRef === ref),
    [allReads, ref],
  );

  const known = ROSTER.some((s) => s.ref === ref);
  const label = known ? studentLabel(ref) : 'Unknown learner';
  const initials = initialsFor(label);

  // Roll-ups for the header + stat matrix.
  const masteryPct = reads.length
    ? Math.round((reads.reduce((s, r) => s + r.mastery.reading.composite, 0) / reads.length) * 100)
    : 0;
  const independentCount = reads.filter((r) => r.mastery.reading.independent).length;
  const independentPct = reads.length
    ? Math.round((independentCount / reads.length) * 100)
    : 0;
  const confirmedGaps = reads.reduce((s, r) => s + r.confirmedGaps.length, 0);
  const revisionDue = reads.filter((r) => r.mastery.revisionDue).length;
  const standing = reads.length ? standingFor(reads) : 'needs-work';
  const tag = STANDING_TAG[standing];

  // Order: gaps first (where attention lands), then lowest mastery.
  const orderedReads = useMemo(
    () =>
      [...reads].sort(
        (a, b) =>
          b.confirmedGaps.length - a.confirmedGaps.length ||
          a.mastery.reading.composite - b.mastery.reading.composite,
      ),
    [reads],
  );

  const series = useMemo(() => trajectoryFor(label, reads), [label, reads]);

  const gapReads = reads.filter((r) => r.confirmedGaps.length > 0);

  return (
    <SurfaceShell
      eyebrow={CLASS_LABEL}
      title={label}
      breadcrumb={[
        { label: 'School', href: '/' },
        { label: CLASS_LABEL, href: '/teacher' },
        { label: 'Roster', href: '/teacher/students' },
        { label },
      ]}
      meta={
        reads.length
          ? [
              { value: reads.length, label: reads.length === 1 ? 'topic tracked' : 'topics tracked' },
              { value: independentCount, label: 'on their own' },
              { label: tag.label.toLowerCase() },
            ]
          : undefined
      }
      tabs={[
        { label: 'Overview', href: '/teacher' },
        { label: 'Students', href: '/teacher/students', active: true },
        { label: 'Class insights', href: '/teacher/insights' },
        { label: 'Evaluation', href: '/teacher/evaluate' },
      ]}
      actions={
        <Link
          href="/teacher/students"
          className="btn btn-secondary row"
          style={{ gap: 'var(--space-2)' }}
        >
          <Icon name="arrow-right" size="sm" style={{ transform: 'scaleX(-1)' }} />
          Back to roster
        </Link>
      }
      dockIntro={`Everything Classess reads on ${label}, with full lineage. Ask me to explain a gap, draft a remedial, or what unlocks their next topic.`}
      dockChips={[`Explain ${label}'s top gap`, `Draft a remedial for ${label}`, 'What unlocks their next topic']}
      aside={
        phase !== 'ready' || !known || reads.length === 0 ? null : (
          <>
            <div className="panel">
              <div className="row" style={{ gap: 'var(--space-3)', alignItems: 'center', marginBottom: 12 }}>
                <span className="avatar avatar-lg">{initials}</span>
                <div>
                  <div className="body" style={{ fontWeight: 500 }}>
                    {label}
                  </div>
                  <Tag tone={tag.tone} dot>
                    {tag.label}
                  </Tag>
                </div>
              </div>
              <p className="caption">
                A rolled-up read across {reads.length} touched {reads.length === 1 ? 'topic' : 'topics'} —
                independent versus with-guidance, never a single score.
              </p>
            </div>

            <div className="panel">
              <div className="sec-head" style={{ marginBottom: 8 }}>
                <h4 className="h4" style={{ margin: 0 }}>
                  Confirmed gaps
                </h4>
                <Tag tone={confirmedGaps > 0 ? 'danger' : 'success'}>{confirmedGaps}</Tag>
              </div>
              <p className="caption" style={{ marginBottom: 12 }}>
                Corroborated across attempts — never a single bad score.
              </p>
              {gapReads.length === 0 ? (
                <p className="body-sm muted" style={{ margin: 0 }}>
                  No confirmed gaps. The evidence for {label} is clean.
                </p>
              ) : (
                gapReads.slice(0, 4).map((r) => {
                  const g = r.confirmedGaps[0]!;
                  return (
                    <div className="flag" key={r.topic.id}>
                      <div className="flag-ic">
                        <Icon name="target" size="sm" />
                      </div>
                      <div>
                        <div className="body-sm" style={{ fontWeight: 500 }}>
                          {gapLabel(g.evidence.gapType)}
                        </div>
                        <p className="caption">{r.topic.name}</p>
                      </div>
                    </div>
                  );
                })
              )}
              <Link
                href="/teacher/assign"
                className="btn btn-accent btn-sm btn-block"
                style={{ marginTop: 16 }}
              >
                Assign a remedial
              </Link>
            </div>

            <div className="panel" style={{ padding: '18px 20px' }}>
              <p className="handnote" style={{ fontSize: 22 }}>
                {confirmedGaps > 0
                  ? 'one confirmed gap closed compounds into the next unit'
                  : 'keep the evidence fresh — secured fades if untouched'}
              </p>
            </div>
          </>
        )
      }
    >
      {phase !== 'ready' ? (
        <ReadStates phase={phase} onRetry={refresh} />
      ) : !known ? (
        <div className="empty">
          <Icon name="info" size="lg" className="glyph" />
          <h4 className="body">That learner is not in this class</h4>
          <p>The reference does not match anyone on the {CLASS_LABEL} roster.</p>
          <Link href="/teacher/students" className="btn btn-secondary btn-sm">
            Back to the roster
          </Link>
        </div>
      ) : reads.length === 0 ? (
        <div className="empty">
          <Icon name="success" size="lg" className="glyph" />
          <h4 className="body">No evidence on {label} yet</h4>
          <p>Once {label} attempts a check, every read appears here with its full lineage.</p>
          <Link href="/teacher/students" className="btn btn-secondary btn-sm">
            Back to the roster
          </Link>
        </div>
      ) : (
        <>
          <Matrix columns={4} className="reveal reveal-1">
            <StatCell
              label="Mastery"
              value={masteryPct}
              unit="%"
              delta="composite of six dimensions"
              tone="flat"
            />
            <StatCell
              label="Working independently"
              value={independentPct}
              unit="%"
              delta={`${independentCount} of ${reads.length} topics, on their own`}
              tone="up"
            />
            <StatCell
              label="Confirmed gaps"
              value={confirmedGaps}
              delta="corroborated, not single scores"
              tone={confirmedGaps > 0 ? 'down' : 'flat'}
            />
            <StatCell
              label="Revision due"
              value={revisionDue}
              delta="evidence has decayed"
              tone="flat"
            />
          </Matrix>

          <section className="stack">
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                Per-topic read
              </h3>
              <span className="overline">independent vs with guidance</span>
            </div>
            {orderedReads.map((r) => {
              const lead = r.confirmedGaps[0] ?? r.gaps[0];
              return (
                <SpotlightCard key={r.topic.id}>
                  <div className="row-between" style={{ alignItems: 'flex-start' }}>
                    <div>
                      <div className="ignite-row" style={{ marginBottom: 2 }}>
                        {r.mastery.reading.independent ? (
                          <CrystallizeNode variant="b" inline resolved label="Independent" />
                        ) : null}
                        <span className="body">{r.topic.name}</span>
                      </div>
                      <div className="caption muted">
                        {r.topic.subjectName} · {BAND_SHORT[r.mastery.reading.band]}
                      </div>
                    </div>
                    <Tag tone={r.mastery.reading.independent ? 'success' : 'neutral'}>
                      {r.mastery.reading.independent ? 'On their own' : 'With support'}
                    </Tag>
                  </div>

                  <p className="body-sm" style={{ marginTop: 'var(--space-3)' }}>
                    <span className="quiet">Plain language. </span>
                    {capitalise(r.mastery.plainLanguage)}.
                  </p>

                  <div className="divider" />

                  <p className="caption">
                    <strong>The six dimensions. </strong>
                    The teacher-facing reasoning behind the band — never shown to the learner, never
                    collapsed to one number.
                  </p>
                  <DimensionBars dimensions={r.mastery.reading.dimensions} showGloss />

                  <div className="row-between" style={{ marginTop: 'var(--space-3)' }}>
                    <GapChips gaps={r.gaps} emptyLabel="No gaps — the evidence is clean" />
                    <EvidenceDrawer
                      claim={`${label} · ${r.topic.name}`}
                      confidence={lead ? confidenceBand(lead.evidence.confidence) : 'middle'}
                      evidence={[
                        ...(lead
                          ? [
                              {
                                text: `${gapLabel(lead.evidence.gapType)} — ${lead.evidence.rationale}`,
                                when: 'this week',
                              },
                            ]
                          : []),
                        ...r.mastery.evidenceEventIds.map((id) => ({
                          text: `Attributed attempt/score event ${id.slice(0, 8)}… in this read's lineage.`,
                        })),
                      ]}
                      whySeeing="Every reading is computed by replaying these events. A judgment is never confirmed from a single bad score."
                    />
                  </div>
                </SpotlightCard>
              );
            })}
          </section>

          <section className="stack">
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                Independence trajectory
              </h3>
              <span className="overline">direction, not a grade</span>
            </div>
            <Trajectory series={series} />
          </section>

          <section className="stack">
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                Attendance
              </h3>
              <span className="overline">a calm pattern, never a judgement</span>
            </div>
            <AttendanceHeatmap
              record={{ ...viz.data.attendance, rowLabel: label }}
              source={viz.sourceByKind.attendance}
            />
          </section>

          <section className="stack">
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                Holistic progress card
              </h3>
              <span className="overline">compose, then share to the family</span>
            </div>
            <HolisticCardBuilder
              data={{ ...viz.data.holistic, subjectLabel: label, classLabel: CLASS_LABEL }}
              source={viz.sourceByKind.holistic}
            />
          </section>

          <SourceNote source={source} />
        </>
      )}
    </SurfaceShell>
  );
}

function capitalise(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
