'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import {
  ConfidenceBand,
  Icon,
  Matrix,
  ProgressBar,
  Tag,
  type Confidence,
  type SubjectAccent,
  type TagTone,
} from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { StatCell } from '../_components/StatCell';
import { EvidenceDrawer } from '../_components/EvidenceDrawer';
import { ReadStates } from '../_components/ReadStates';
import { SourceNote } from '../_components/SourceNote';
import { useClassInsights } from '@/lib/useClassInsights';
import { CLASS_LABEL } from '@/lib/loopData';
import type { StudentTopicRead } from '@/lib/classRead';

/** Map the engine's numeric gap confidence (0-1) to a plain band — never a raw number. */
function confidenceBand(value: number): Confidence {
  if (value >= 0.66) return 'high';
  if (value >= 0.4) return 'middle';
  return 'low';
}

/** The status tag for a read — its plain band, as a tag tone + label. */
function statusTag(read: StudentTopicRead): { tone: TagTone; label: string } {
  if (read.confirmedGaps.length > 0) return { tone: 'danger', label: 'At risk' };
  if (read.mastery.reading.independent) return { tone: 'success', label: 'Mastered' };
  if (read.mastery.reading.composite >= 0.5) return { tone: 'info', label: 'Developing' };
  return { tone: 'warning', label: 'Needs work' };
}

/** A subject roll-up — the class-average mastery + its current focus topic. */
interface SubjectRollup {
  subjectId: string;
  name: string;
  code: string;
  accent: SubjectAccent;
  focusTopic: string;
  focusBlurb: string;
  averagePct: number;
}

function rollupBySubject(reads: StudentTopicRead[]): SubjectRollup[] {
  const bySubject = new Map<string, StudentTopicRead[]>();
  for (const r of reads) {
    if (!r.topic.subjectId) continue;
    const list = bySubject.get(r.topic.subjectId) ?? [];
    list.push(r);
    bySubject.set(r.topic.subjectId, list);
  }
  const out: SubjectRollup[] = [];
  for (const [subjectId, list] of bySubject) {
    const first = list[0]!;
    const avg = list.reduce((s, r) => s + r.mastery.reading.composite, 0) / list.length;
    // The focus topic = the lowest-mastery touched topic in the subject.
    const focus = [...list].sort(
      (a, b) => a.mastery.reading.composite - b.mastery.reading.composite,
    )[0]!;
    out.push({
      subjectId,
      name: first.topic.subjectName,
      code: first.topic.subjectName.slice(0, 3).toUpperCase(),
      accent: first.topic.accent,
      focusTopic: focus.topic.name,
      focusBlurb: focus.topic.chapterName || 'Current focus across the class.',
      averagePct: Math.round(avg * 100),
    });
  }
  return out;
}

/** The CSS subject-card with the colour band + animated, subject-coloured bar. */
function SubjectMasteryCard({ rollup, index }: { rollup: SubjectRollup; index: number }) {
  return (
    <div
      className={`subject-card reveal reveal-${index + 1}`}
      style={
        {
          '--subject': `var(--${rollup.accent})`,
          '--subject-ink': `var(--${rollup.accent}-ink)`,
        } as React.CSSProperties
      }
    >
      <div className="band">
        <span className="name">{rollup.name}</span>
        <span className="code">{rollup.code}</span>
      </div>
      <div className="body">
        <div className="display-sm" style={{ fontSize: 22 }}>
          {rollup.focusTopic}
        </div>
        <p className="caption" style={{ marginTop: 5 }}>
          {rollup.focusBlurb}
        </p>
        <div className="progress animate" style={{ margin: '14px 0 8px' }}>
          <span style={{ width: `${rollup.averagePct}%`, background: `var(--${rollup.accent})` }} />
        </div>
        <div className="data">{rollup.averagePct}% · class average</div>
      </div>
    </div>
  );
}

/**
 * The teacher day — recomposed to the sample-page bar: a sticky chrome, a big
 * page-head with a mono meta line, a 4-up count-up stat matrix, then a cols
 * layout (subject cards + the student table on the main, the ignite moment +
 * the Vidya-flagged panel + today's timetable + a handnote on the 320px aside).
 * Every read is GATEWAY-FIRST from the spine (intelligence-views), falling back
 * to the faithful TS engine on degrade. All five designed states ship.
 */
export default function TeacherDayPage() {
  const { phase, insights, source, refresh } = useClassInsights();
  const summary = insights?.summary;
  const reads = useMemo(() => insights?.reads ?? [], [insights]);
  const attention = insights?.needingAttention ?? [];
  const subjects = useMemo(() => rollupBySubject(reads), [reads]);

  // Plain headline numbers for the meta line + the stat matrix.
  const learners = useMemo(
    () => new Set(reads.map((r) => r.studentRef)).size,
    [reads],
  );
  const independentPct = summary
    ? Math.round(
        (summary.working_independently /
          Math.max(1, summary.working_independently + summary.need_support)) *
          100,
      )
    : 0;
  const classMasteryPct =
    reads.length > 0
      ? Math.round(
          (reads.reduce((s, r) => s + r.mastery.reading.composite, 0) / reads.length) * 100,
        )
      : 0;

  // A small, deterministic timetable for the day's aside (today's plan).
  const schedule = [
    { t: '09:00', subject: 'Mathematics', note: 'Trigonometry — heights and distances.' },
    { t: '11:30', subject: 'Physics', note: 'Kinematics — guided practice.' },
    { t: '14:00', subject: 'Intervention', note: `Confirmed gaps — ${attention.length} to review.` },
  ];

  return (
    <SurfaceShell
      eyebrow={CLASS_LABEL}
      title="Your day"
      breadcrumb={[
        { label: 'School', href: '/' },
        { label: 'Grade 10', href: '/teacher' },
        { label: CLASS_LABEL },
      ]}
      meta={[
        { value: learners || '—', label: 'learners with evidence' },
        { value: subjects.length || '—', label: 'subjects in motion' },
        { label: 'manage by exception' },
      ]}
      tabs={[
        { label: 'Overview', active: true },
        { label: 'Students', href: '/teacher/students' },
        { label: 'Class insights', href: '/teacher/insights' },
        { label: 'Evaluation', href: '/teacher/evaluate' },
      ]}
      actions={
        <>
          <Link href="/teacher/insights" className="btn btn-secondary row" style={{ gap: 'var(--space-2)' }}>
            <Icon name="chart" size="sm" />
            Class insights
          </Link>
          <Link href="/teacher/assign" className="btn btn-accent row" style={{ gap: 'var(--space-2)' }}>
            <Icon name="plus" size="sm" />
            New quick check
          </Link>
        </>
      }
      dockIntro="The attention list is read live from the spine — ask me to explain any student, or build the next quick check."
      dockChips={['Who needs attention and why', 'Build a quick check', 'What changed since yesterday']}
      aside={
        phase !== 'ready' ? null : (
          <>
            <div className="ignite-card reveal reveal-2">
              <div className="row-between" style={{ marginBottom: 14 }}>
                <span className="overline">Just now</span>
                <Icon name="flame" size="md" style={{ color: 'var(--accent)' }} />
              </div>
              <div className="who">
                {summary?.working_independently ?? 0} reads now stand on their own
              </div>
              <p className="body-sm" style={{ opacity: 0.8, marginTop: 8 }}>
                Independent demonstration — corroborated across attempts, no prompts. The class is
                compounding.
              </p>
            </div>

            <div className="panel">
              <div className="sec-head" style={{ marginBottom: 8 }}>
                <h4 className="h4" style={{ margin: 0 }}>
                  Vidya flagged
                </h4>
                <Tag tone="info">{attention.length}</Tag>
              </div>
              <p className="caption" style={{ marginBottom: 12 }}>
                Confirmed gaps this week, ranked by corroboration — never a single bad score.
              </p>
              {attention.length === 0 ? (
                <p className="body-sm muted" style={{ margin: 0 }}>
                  Nothing flagged from corroborated evidence. The class is on track.
                </p>
              ) : (
                attention.slice(0, 3).map((r) => {
                  const gap = r.confirmedGaps[0]!;
                  return (
                    <div className="flag" key={`${r.studentRef}-${r.topic.id}`}>
                      <div className="flag-ic">
                        <Icon name="target" size="sm" />
                      </div>
                      <div>
                        <div className="body-sm" style={{ fontWeight: 500 }}>
                          {r.topic.name}
                        </div>
                        <p className="caption">{gap.evidence.rationale}</p>
                      </div>
                    </div>
                  );
                })
              )}
              <Link
                href="/teacher/students"
                className="btn btn-secondary btn-sm btn-block"
                style={{ marginTop: 16 }}
              >
                Review interventions
              </Link>
            </div>

            <div className="panel">
              <div className="sec-head" style={{ marginBottom: 8 }}>
                <h4 className="h4" style={{ margin: 0 }}>
                  Today
                </h4>
                <span className="overline">timetable</span>
              </div>
              {schedule.map((s) => (
                <div className="sched" key={s.t}>
                  <span className="t">{s.t}</span>
                  <div>
                    <div className="body-sm" style={{ fontWeight: 500 }}>
                      {s.subject}
                    </div>
                    <p className="caption">{s.note}</p>
                  </div>
                </div>
              ))}
            </div>

            <div className="panel" style={{ padding: '18px 20px' }}>
              <p className="handnote" style={{ fontSize: 22 }}>
                review the confirmed gaps before the next class — small now, hard later
              </p>
            </div>
          </>
        )
      }
    >
      {phase !== 'ready' ? (
        <ReadStates phase={phase} onRetry={refresh} />
      ) : (
        <>
          <Matrix columns={4} className="reveal reveal-1">
            <StatCell
              label="Class mastery"
              value={classMasteryPct}
              unit="%"
              delta="composite of six dimensions"
              tone="flat"
            />
            <StatCell
              label="Working independently"
              value={independentPct}
              unit="%"
              delta={`${summary?.working_independently ?? 0} reads on their own`}
              tone="up"
            />
            <StatCell
              label="Confirmed gaps"
              value={summary?.confirmed_gaps ?? 0}
              delta="corroborated, not single scores"
              tone={summary && summary.confirmed_gaps > 0 ? 'down' : 'flat'}
            />
            <StatCell
              label="Revision due"
              value={summary?.revision_due ?? 0}
              delta="evidence has decayed"
              tone="flat"
            />
          </Matrix>

          <section>
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                Subjects
              </h3>
              <span className="overline">mastery by subject</span>
            </div>
            {subjects.length === 0 ? (
              <div className="empty">
                <Icon name="book" size="lg" className="glyph" />
                <h4 className="body">No subjects in motion yet</h4>
                <p>As evidence arrives, each subject's class-average mastery will surface here.</p>
              </div>
            ) : (
              <Matrix columns={2}>
                {subjects.map((s, i) => (
                  <SubjectMasteryCard key={s.subjectId} rollup={s} index={i} />
                ))}
              </Matrix>
            )}
          </section>

          <section>
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                Students
              </h3>
              <Link href="/teacher/students" className="btn btn-ghost btn-sm">
                See all insights
              </Link>
            </div>
            {reads.length === 0 ? (
              <div className="empty">
                <Icon name="success" size="lg" className="glyph" />
                <h4 className="body">No reads today</h4>
                <p>Nothing to show yet. As students work, their reads will appear here.</p>
              </div>
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Student</th>
                      <th>Current focus</th>
                      <th className="num">Mastery</th>
                      <th>Standing</th>
                      <th>Evidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reads.slice(0, 8).map((r) => {
                      const tag = statusTag(r);
                      const pct = Math.round(r.mastery.reading.composite * 100);
                      const evidence = (r.confirmedGaps.length > 0 ? r.confirmedGaps : r.gaps).map(
                        (g) => ({
                          text: `${g.evidence.gapType.replace(/-/g, ' ')} — ${g.evidence.rationale}`,
                          when: 'this week',
                        }),
                      );
                      const lead = (r.confirmedGaps[0] ?? r.gaps[0])?.evidence;
                      return (
                        <tr key={`${r.studentRef}-${r.topic.id}`}>
                          <td>
                            <div className="row" style={{ gap: 'var(--space-3)' }}>
                              <span className="avatar avatar-sm">
                                {r.studentLabel.replace(/[^A-Za-z]/g, '').slice(-2).toUpperCase()}
                              </span>
                              {r.studentLabel}
                            </div>
                          </td>
                          <td className="muted">{r.topic.name}</td>
                          <td className="num">
                            <span className="data">{pct}%</span>
                          </td>
                          <td>
                            <Tag tone={tag.tone}>{tag.label}</Tag>
                          </td>
                          <td>
                            {evidence.length > 0 ? (
                              <EvidenceDrawer
                                claim={`${r.studentLabel} · ${r.topic.name}`}
                                confidence={lead ? confidenceBand(lead.confidence) : 'middle'}
                                evidence={evidence}
                                whySeeing={`Flagged from ${
                                  r.confirmedGaps.length || r.gaps.length
                                } ${
                                  (r.confirmedGaps.length || r.gaps.length) === 1
                                    ? 'signal'
                                    : 'signals'
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
