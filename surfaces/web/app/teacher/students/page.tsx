'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { Icon, Matrix, Tag, type Confidence, type TagTone } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { StatCell } from '../../_components/StatCell';
import { ReadStates } from '../../_components/ReadStates';
import { SourceNote } from '../../_components/SourceNote';
import { EvidenceDrawer } from '../../_components/EvidenceDrawer';
import { useClassInsights } from '@/lib/useClassInsights';
import { CLASS_LABEL, ROSTER } from '@/lib/loopData';
import { gapLabel } from '@/lib/engine';
import type { StudentTopicRead } from '@/lib/classRead';

/**
 * The class roster — recomposed to the beauty bar: a sticky chrome, a big
 * page-head with a mono meta line, a 4-up count-up stat matrix, a segmented
 * filter, then a DENSE roster TABLE (one row per learner, rolled up from every
 * touched-topic read), each row a link into the per-student internal detail
 * page. The aside carries the manage-by-exception panel + a handnote.
 *
 * Every read is GATEWAY-FIRST from the spine (class-insights view), falling back
 * to the faithful TS engine on degrade. The teacher sees the reasoning; learners
 * never do. All five designed states ship.
 */

type Standing = 'mastered' | 'developing' | 'needs-work' | 'at-risk';
type Filter = 'all' | 'at-risk' | 'mastered';

/** One roster row — a learner rolled up across every topic they have evidence on. */
interface RosterRow {
  studentRef: string;
  studentLabel: string;
  initials: string;
  focusTopic: string;
  subjectName: string;
  masteryPct: number;
  independentPct: number;
  topicCount: number;
  confirmedGaps: number;
  leadGap: string | null;
  leadConfidence: Confidence;
  evidence: { text: string; when?: string }[];
  standing: Standing;
}

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

/** Roll the per-topic reads into one row per learner — the roster the teacher scans. */
function rollupRoster(reads: StudentTopicRead[]): RosterRow[] {
  const byStudent = new Map<string, StudentTopicRead[]>();
  for (const r of reads) {
    const list = byStudent.get(r.studentRef) ?? [];
    list.push(r);
    byStudent.set(r.studentRef, list);
  }

  const rows: RosterRow[] = [];
  for (const student of ROSTER) {
    const list = byStudent.get(student.ref);
    if (!list || list.length === 0) continue;

    const avgMastery =
      list.reduce((s, r) => s + r.mastery.reading.composite, 0) / list.length;
    const independentCount = list.filter((r) => r.mastery.reading.independent).length;
    const confirmed = list.reduce((s, r) => s + r.confirmedGaps.length, 0);

    // The current focus = the lowest-mastery touched topic (where attention lands).
    const focus = [...list].sort(
      (a, b) => a.mastery.reading.composite - b.mastery.reading.composite,
    )[0]!;

    // The lead gap drives the standing tag + the evidence drawer lineage.
    const gapReads = list.filter((r) => r.confirmedGaps.length > 0);
    const lead = gapReads.length
      ? [...gapReads].sort(
          (a, b) => b.confirmedGaps[0]!.evidence.confidence - a.confirmedGaps[0]!.evidence.confidence,
        )[0]!
      : null;
    const leadGapEvidence = lead?.confirmedGaps[0]?.evidence ?? null;

    let standing: Standing;
    if (confirmed > 0) standing = 'at-risk';
    else if (independentCount > 0 && independentCount >= list.length / 2) standing = 'mastered';
    else if (avgMastery >= 0.5) standing = 'developing';
    else standing = 'needs-work';

    const evidence = (gapReads.length ? gapReads : list).slice(0, 3).map((r) => {
      const g = r.confirmedGaps[0] ?? r.gaps[0];
      return {
        text: g
          ? `${gapLabel(g.evidence.gapType)} on ${r.topic.name} — ${g.evidence.rationale}`
          : `${r.topic.name}: ${r.mastery.plainLanguage}.`,
        when: 'this week',
      };
    });

    rows.push({
      studentRef: student.ref,
      studentLabel: student.label,
      initials: initialsFor(student.label),
      focusTopic: focus.topic.name,
      subjectName: focus.topic.subjectName,
      masteryPct: Math.round(avgMastery * 100),
      independentPct: Math.round((independentCount / list.length) * 100),
      topicCount: list.length,
      confirmedGaps: confirmed,
      leadGap: leadGapEvidence ? gapLabel(leadGapEvidence.gapType) : null,
      leadConfidence: leadGapEvidence ? confidenceBand(leadGapEvidence.confidence) : 'middle',
      evidence,
      standing,
    });
  }
  // Attention first (most confirmed gaps), then by lowest mastery.
  return rows.sort(
    (a, b) => b.confirmedGaps - a.confirmedGaps || a.masteryPct - b.masteryPct,
  );
}

export default function ClassRosterPage() {
  const { phase, insights, source, refresh } = useClassInsights();
  const reads = useMemo(() => insights?.reads ?? [], [insights]);
  const roster = useMemo(() => rollupRoster(reads), [reads]);
  const [filter, setFilter] = useState<Filter>('all');

  const filtered = useMemo(() => {
    if (filter === 'at-risk') return roster.filter((r) => r.standing === 'at-risk');
    if (filter === 'mastered') return roster.filter((r) => r.standing === 'mastered');
    return roster;
  }, [roster, filter]);

  const atRisk = roster.filter((r) => r.standing === 'at-risk');
  const masteredCount = roster.filter((r) => r.standing === 'mastered').length;
  const classMasteryPct =
    roster.length > 0
      ? Math.round(roster.reduce((s, r) => s + r.masteryPct, 0) / roster.length)
      : 0;
  const classIndependentPct =
    roster.length > 0
      ? Math.round(roster.reduce((s, r) => s + r.independentPct, 0) / roster.length)
      : 0;

  return (
    <SurfaceShell
      eyebrow={CLASS_LABEL}
      title="Class roster"
      breadcrumb={[
        { label: 'School', href: '/' },
        { label: 'Grade 10', href: '/teacher' },
        { label: CLASS_LABEL },
      ]}
      meta={[
        { value: roster.length || '—', label: 'learners with evidence' },
        { value: atRisk.length, label: 'need you now' },
        { label: 'open any learner for the full read' },
      ]}
      tabs={[
        { label: 'Overview', href: '/teacher' },
        { label: 'Students', active: true },
        { label: 'Class insights', href: '/teacher/insights' },
        { label: 'Evaluation', href: '/teacher/evaluate' },
      ]}
      dockIntro="The roster is read live from the spine. Ask me to explain any learner, rank the attention list, or who is closest to independence."
      dockChips={['Who needs attention and why', 'Who is closest to independence', 'Explain the at-risk learners']}
      aside={
        phase !== 'ready' ? null : (
          <>
            <div className="panel">
              <div className="sec-head" style={{ marginBottom: 8 }}>
                <h4 className="h4" style={{ margin: 0 }}>
                  Needs you now
                </h4>
                <Tag tone={atRisk.length > 0 ? 'danger' : 'success'}>{atRisk.length}</Tag>
              </div>
              <p className="caption" style={{ marginBottom: 12 }}>
                Learners with a confirmed gap — corroborated evidence, never a single bad score.
              </p>
              {atRisk.length === 0 ? (
                <p className="body-sm muted" style={{ margin: 0 }}>
                  Nobody is at risk from corroborated evidence. The class is on track.
                </p>
              ) : (
                atRisk.slice(0, 4).map((r) => (
                  <Link
                    href={`/teacher/students/${r.studentRef}`}
                    className="flag flag-link"
                    key={r.studentRef}
                  >
                    <div className="flag-ic">
                      <Icon name="target" size="sm" />
                    </div>
                    <div>
                      <div className="body-sm" style={{ fontWeight: 500 }}>
                        {r.studentLabel}
                      </div>
                      <p className="caption">
                        {r.leadGap ?? 'Confirmed gap'} · {r.focusTopic}
                      </p>
                    </div>
                  </Link>
                ))
              )}
              <Link
                href="/teacher/insights"
                className="btn btn-secondary btn-sm btn-block"
                style={{ marginTop: 16 }}
              >
                Review interventions
              </Link>
            </div>

            <div className="panel">
              <div className="sec-head" style={{ marginBottom: 8 }}>
                <h4 className="h4" style={{ margin: 0 }}>
                  Standing
                </h4>
                <span className="overline">class spread</span>
              </div>
              <div className="sched" style={{ borderBottom: '0.5px solid var(--border)' }}>
                <Tag tone="success">{masteredCount}</Tag>
                <p className="caption" style={{ margin: 0, alignSelf: 'center' }}>
                  on their own across most topics
                </p>
              </div>
              <div className="sched" style={{ borderBottom: '0.5px solid var(--border)' }}>
                <Tag tone="info">{roster.filter((r) => r.standing === 'developing').length}</Tag>
                <p className="caption" style={{ margin: 0, alignSelf: 'center' }}>
                  developing, still with guidance
                </p>
              </div>
              <div className="sched" style={{ borderBottom: 0 }}>
                <Tag tone="danger">{atRisk.length}</Tag>
                <p className="caption" style={{ margin: 0, alignSelf: 'center' }}>
                  at risk from a confirmed gap
                </p>
              </div>
            </div>

            <div className="panel" style={{ padding: '18px 20px' }}>
              <p className="handnote" style={{ fontSize: 22 }}>
                start with the at-risk three — small now, hard later
              </p>
            </div>
          </>
        )
      }
    >
      {phase !== 'ready' ? (
        <ReadStates phase={phase} onRetry={refresh} />
      ) : roster.length === 0 ? (
        <div className="empty">
          <Icon name="user" size="lg" className="glyph" />
          <h4 className="body">No learners with evidence yet</h4>
          <p>As students work, each learner&apos;s rolled-up read will appear here with full lineage.</p>
        </div>
      ) : (
        <>
          <Matrix columns={4} className="reveal reveal-1">
            <StatCell
              label="Learners"
              value={roster.length}
              delta="with evidence this week"
              tone="flat"
            />
            <StatCell
              label="Class mastery"
              value={classMasteryPct}
              unit="%"
              delta="composite of six dimensions"
              tone="flat"
            />
            <StatCell
              label="Working independently"
              value={classIndependentPct}
              unit="%"
              delta="of touched topics, on their own"
              tone="up"
            />
            <StatCell
              label="Need you now"
              value={atRisk.length}
              delta="confirmed gaps, corroborated"
              tone={atRisk.length > 0 ? 'down' : 'flat'}
            />
          </Matrix>

          <section>
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                Students
              </h3>
              <div className="segmented" role="tablist" aria-label="Filter the roster">
                <button
                  type="button"
                  className={filter === 'all' ? 'active' : ''}
                  aria-selected={filter === 'all'}
                  onClick={() => setFilter('all')}
                >
                  All
                </button>
                <button
                  type="button"
                  className={filter === 'at-risk' ? 'active' : ''}
                  aria-selected={filter === 'at-risk'}
                  onClick={() => setFilter('at-risk')}
                >
                  At risk
                </button>
                <button
                  type="button"
                  className={filter === 'mastered' ? 'active' : ''}
                  aria-selected={filter === 'mastered'}
                  onClick={() => setFilter('mastered')}
                >
                  Mastered
                </button>
              </div>
            </div>

            {filtered.length === 0 ? (
              <div className="empty">
                <Icon name="success" size="lg" className="glyph" />
                <h4 className="body">Nobody in this band</h4>
                <p>No learners match this filter right now. Switch back to All to see the roster.</p>
              </div>
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Student</th>
                      <th>Current focus</th>
                      <th className="num">Mastery</th>
                      <th className="num">Independent</th>
                      <th>Standing</th>
                      <th>Evidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((r) => {
                      const tag = STANDING_TAG[r.standing];
                      return (
                        <tr key={r.studentRef}>
                          <td>
                            <Link
                              href={`/teacher/students/${r.studentRef}`}
                              className="row roster-name"
                              style={{ gap: 'var(--space-3)' }}
                            >
                              <span className="avatar avatar-sm">{r.initials}</span>
                              <span>
                                {r.studentLabel}
                                <span className="caption quiet roster-sub">
                                  {r.topicCount} {r.topicCount === 1 ? 'topic' : 'topics'} tracked
                                </span>
                              </span>
                            </Link>
                          </td>
                          <td className="muted">
                            {r.focusTopic}
                            <span className="caption quiet roster-sub">{r.subjectName}</span>
                          </td>
                          <td className="num">
                            <span className="data">{r.masteryPct}%</span>
                          </td>
                          <td className="num">
                            <span className="data">{r.independentPct}%</span>
                          </td>
                          <td>
                            <Tag tone={tag.tone} dot>
                              {tag.label}
                            </Tag>
                          </td>
                          <td>
                            {r.evidence.length > 0 ? (
                              <EvidenceDrawer
                                claim={`${r.studentLabel} · ${r.focusTopic}`}
                                confidence={r.leadConfidence}
                                evidence={r.evidence}
                                whySeeing={`Rolled up from ${r.topicCount} touched ${
                                  r.topicCount === 1 ? 'topic' : 'topics'
                                }${
                                  r.confirmedGaps > 0
                                    ? ` and ${r.confirmedGaps} corroborated ${
                                        r.confirmedGaps === 1 ? 'signal' : 'signals'
                                      }`
                                    : ''
                                } — never a single bad score.`}
                              />
                            ) : (
                              <span className="caption quiet">clean</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            <SourceNote source={source} />
          </section>
        </>
      )}
    </SurfaceShell>
  );
}
