'use client';

import { useMemo } from 'react';
import { ConfidenceBand, Icon, ProgressBar, SubjectCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { ReadStates } from '../_components/ReadStates';
import { SourceNote } from '../_components/SourceNote';
import {
  StatMatrix,
  IgniteCard,
  Panel,
  FlagRow,
  SchedRow,
  HandnotePanel,
  SecHead,
  type FlagModel,
} from '../_components/StudentComposed';
import { openVidya } from '../_components/VidyaOrb';
import { useClassInsights } from '@/lib/useClassInsights';
import type { StudentTopicRead } from '@/lib/classRead';
import { CLASS_STATS, MASTERY_ROWS, SUBJECTS, BAND_PHRASE, type MasteryRow } from '@/lib/mock';

/* ============================================================================
   /insights — the subject + cohort rollup, recomposed to the sample-page bar.

   A count-up stat matrix opens the page; the body rides on .cols (1fr + 320px):
   the left holds the colour-band subject grid (the one hit of pigment, cool
   hues only) and a dense needing-attention table; the right aside carries the
   dark ignite-card (the independent-mastery moment), a Vidya-flagged panel, a
   today timetable, and a Caveat handnote — exactly the sample page's shape.

   Read GATEWAY-FIRST from the spine (intelligence-views: class-insights), with
   the engine fallback when the spine is silent. All five designed states ship.
   No raw scores or formulas — only what a learner can do, in plain language.
   ============================================================================ */

const BAND_TONE: Record<MasteryRow['band'], 'success' | 'info' | 'warning' | 'danger' | 'neutral'> = {
  independent: 'success',
  secure: 'info',
  developing: 'warning',
  emerging: 'warning',
  'not-started': 'danger',
};

/** A relative fill for a band — a plain read of how far, never a mark/score. */
const BAND_FILL: Record<MasteryRow['band'], number> = {
  independent: 92,
  secure: 74,
  developing: 56,
  emerging: 38,
  'not-started': 12,
};

/** Roll the live per-(student, topic) reads up to one plain-language row per
 *  topic: the share working independently decides the row's independent flag,
 *  and the most common band stands for the topic — never a raw number. */
function topicMasteryRows(reads: StudentTopicRead[]): MasteryRow[] {
  const byTopic = new Map<string, StudentTopicRead[]>();
  for (const r of reads) {
    const arr = byTopic.get(r.topic.id) ?? [];
    arr.push(r);
    byTopic.set(r.topic.id, arr);
  }
  const rows: MasteryRow[] = [];
  for (const group of byTopic.values()) {
    const first = group[0]!;
    const independentCount = group.filter((g) => g.mastery.reading.independent).length;
    const majorityIndependent = independentCount * 2 >= group.length;
    const bandCounts = new Map<MasteryRow['band'], number>();
    for (const g of group) {
      const b = g.mastery.reading.band;
      bandCounts.set(b, (bandCounts.get(b) ?? 0) + 1);
    }
    let band: MasteryRow['band'] = first.mastery.reading.band;
    let best = 0;
    for (const [b, n] of bandCounts) {
      if (n > best) {
        best = n;
        band = b;
      }
    }
    rows.push({
      topic: first.topic.name,
      subject: first.topic.accent,
      band,
      independent: majorityIndependent,
      note: majorityIndependent
        ? 'Most of the class can now do this on their own.'
        : 'Most of the class still leans on support here.',
    });
  }
  return rows;
}

export default function InsightsPage() {
  const { phase, insights, source, refresh } = useClassInsights();

  const stats = useMemo(() => {
    const s = insights?.summary;
    if (!s) return null;
    return [
      { label: 'Working independently', value: s.working_independently, deltaDir: 'up' as const, delta: 'on their own' },
      { label: 'Need support', value: s.need_support, deltaDir: 'flat' as const, delta: 'not yet alone' },
      { label: 'Confirmed gaps', value: s.confirmed_gaps, deltaDir: 'down' as const, delta: 'corroborated' },
      { label: 'Revision due', value: s.revision_due, deltaDir: 'flat' as const, delta: 'evidence decayed' },
    ];
  }, [insights]);

  const masteryRows = useMemo(() => {
    const live = topicMasteryRows(insights?.reads ?? []);
    return live.length > 0 ? live : MASTERY_ROWS;
  }, [insights]);

  // Group mastery rows by subject for the per-subject colour cards.
  const bySubject = SUBJECTS.map((s) => ({
    subject: s,
    rows: masteryRows.filter((r) => r.subject === s.accent),
  })).filter((g) => g.rows.length > 0);

  // The needing-attention list, rolled to one plain-language row per (student, topic).
  const attention = (insights?.needingAttention ?? []).slice(0, 6);

  // The single independent-mastery moment, if any — the ignite card.
  const igniteRead = (insights?.reads ?? []).find((r) => r.mastery.reading.independent);

  const cohortStats =
    stats ??
    CLASS_STATS.map((s) => ({ label: s.label, value: s.value, deltaDir: 'flat' as const, delta: 'steady' }));

  // The flagged panel — the lowest-band topics, ranked by impact.
  const flags: FlagModel[] = masteryRows
    .filter((r) => r.band === 'emerging' || r.band === 'not-started' || r.band === 'developing')
    .slice(0, 3)
    .map((r) => ({
      icon: r.band === 'not-started' ? 'clock' : r.band === 'emerging' ? 'spark' : 'target',
      title: r.topic,
      caption: r.note,
    }));

  const aside = (
    <>
      {igniteRead ? (
        <IgniteCard
          when="Just now"
          who={`${igniteRead.studentLabel} secured ${igniteRead.topic.name}`}
          detail="Independent mastery — demonstrated unaided, on fresh evidence, not a single lucky score."
        />
      ) : (
        <IgniteCard
          when="This week"
          who="The cohort is building toward independence"
          detail="No independent moment has crystallised yet. The reads below show where the class still leans on support."
        />
      )}

      <Panel title="Vidya flagged" meta={<Tag tone="info" dot>{String(flags.length)}</Tag>}>
        <p className="caption" style={{ marginBottom: 'var(--space-3)' }}>
          Gaps detected this week, ranked by impact.
        </p>
        {flags.length > 0 ? (
          flags.map((f, i) => <FlagRow key={i} flag={f} />)
        ) : (
          <p className="caption muted">No gaps flagged — the cohort evidence is clean so far.</p>
        )}
        <button
          type="button"
          className="btn btn-secondary btn-sm btn-block"
          style={{ marginTop: 'var(--space-4)' }}
          onClick={() => openVidya('Walk me through the flagged gaps for Class 10-B')}
        >
          Review interventions
        </button>
      </Panel>

      <Panel title="Today" meta={<span className="overline">timetable</span>}>
        <SchedRow row={{ t: '09:00', title: 'Mathematics', caption: 'Trigonometry — heights and distances.' }} />
        <SchedRow row={{ t: '11:30', title: 'Chemistry', caption: 'Mole concept — guided practice.' }} />
        <SchedRow row={{ t: '14:00', title: 'Intervention', caption: 'Integer operations — small group.' }} />
      </Panel>

      <HandnotePanel>two reads are due for revision — the evidence has gone stale</HandnotePanel>
    </>
  );

  return (
    <SurfaceShell
      eyebrow="Class 10-B"
      title="Subject and cohort rollup"
      meta={[
        { value: bySubject.length, label: 'subjects' },
        { value: masteryRows.length, label: 'topics tracked' },
        { label: 'read live from the spine' },
      ]}
      tabs={[
        { label: 'Overview', active: true },
        { label: 'Student insights', href: '/teacher/students' },
        { label: 'Interventions', href: '/proactive' },
      ]}
      aside={phase === 'ready' ? aside : undefined}
      dockIntro="This is the subject-by-subject rollup for Class 10-B, read live from the spine. Ask how a subject is trending, or which topics the cohort has secured. For a single student, open Student insights."
      dockChips={['How is Mathematics trending', 'Which topics are secured', 'Where is the cohort still supported']}
    >
      {phase !== 'ready' ? (
        <ReadStates phase={phase} onRetry={refresh} />
      ) : (
        <>
          <StatMatrix stats={cohortStats} columns={4} />

          <section className="stack reveal reveal-3" style={{ marginTop: 'var(--space-6)' }}>
            <SecHead title="By subject" meta={<span className="overline">mastery by subject</span>} />
            <div className="matrix" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
              {bySubject.map(({ subject, rows }, i) => {
                const lead = rows[0]!;
                const fill = Math.round(rows.reduce((a, r) => a + BAND_FILL[r.band], 0) / rows.length);
                const indep = rows.filter((r) => r.independent).length;
                return (
                  <SubjectCard
                    key={subject.code}
                    name={subject.name}
                    code={subject.code}
                    accent={subject.accent}
                    className={`reveal reveal-${Math.min(i + 1, 8)}`}
                  >
                    <div className="display-sm" style={{ fontSize: 20 }}>
                      {lead.topic}
                    </div>
                    <p className="caption" style={{ marginTop: 5 }}>
                      {indep > 0 ? `${indep} of ${rows.length} topics on their own.` : `${rows.length} topics in progress.`}
                    </p>
                    <ProgressBar
                      value={fill}
                      animate
                      label={`${subject.name} progress`}
                      style={{ margin: '14px 0 8px', ['--subject-fill' as string]: `var(--${subject.accent})` }}
                      className="subject-progress"
                    />
                    <div className="data">{BAND_PHRASE[lead.band].toLowerCase()} · class read</div>
                  </SubjectCard>
                );
              })}
            </div>
          </section>

          <section className="stack reveal reveal-4" style={{ marginTop: 'var(--space-6)' }}>
            <SecHead
              title="Where the class stands"
              meta={<span className="overline">topic by topic</span>}
            />
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Topic</th>
                    <th>Subject</th>
                    <th>Where the cohort is</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {masteryRows.map((r) => (
                    <tr key={r.topic}>
                      <td>{r.topic}</td>
                      <td className="muted">
                        <span className="row" style={{ gap: 'var(--space-2)' }}>
                          <span
                            aria-hidden="true"
                            style={{
                              width: 8,
                              height: 8,
                              borderRadius: 2,
                              background: `var(--${r.subject})`,
                              flex: 'none',
                            }}
                          />
                          {SUBJECTS.find((s) => s.accent === r.subject)?.name ?? '—'}
                        </span>
                      </td>
                      <td className="muted">{BAND_PHRASE[r.band]}</td>
                      <td>
                        <Tag tone={BAND_TONE[r.band]} dot>
                          {r.independent ? 'On their own' : 'Supported'}
                        </Tag>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="caption quiet">
              Independent means a student can do it on their own, consistently. Everything else still
              leans on support. No scores or formulas are shown — only what a learner can do.
            </p>
          </section>

          {attention.length > 0 ? (
            <section className="stack reveal reveal-5" style={{ marginTop: 'var(--space-6)' }}>
              <SecHead title="Needing attention" meta={<Tag tone="warning" dot>{String(attention.length)}</Tag>} />
              <div className="matrix" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
                {attention.map((a, i) => (
                  <div className="cell" key={`${a.studentRef}-${a.topic.id}-${i}`}>
                    <div className="row-between" style={{ alignItems: 'flex-start' }}>
                      <div className="cell-label">{a.studentLabel}</div>
                      <ConfidenceBand
                        level={
                          a.mastery.reading.dimensions.reliability >= 0.7
                            ? 'high'
                            : a.mastery.reading.dimensions.reliability >= 0.5
                              ? 'middle'
                              : 'low'
                        }
                      />
                    </div>
                    <div className="body-sm" style={{ fontWeight: 500, marginTop: 4 }}>
                      {a.topic.name}
                    </div>
                    <p className="caption muted" style={{ marginTop: 4 }}>
                      {a.mastery.plainLanguage}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          <SourceNote source={source} />
        </>
      )}
    </SurfaceShell>
  );
}
