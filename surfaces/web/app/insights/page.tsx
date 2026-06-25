'use client';

import { useMemo } from 'react';
import { Cell, Matrix, Stat, SubjectCard } from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { MasteryView } from '../_components/MasteryView';
import { ReadStates } from '../_components/ReadStates';
import { SourceNote } from '../_components/SourceNote';
import { useClassInsights } from '@/lib/useClassInsights';
import type { StudentTopicRead } from '@/lib/classRead';
import { CLASS_STATS, MASTERY_ROWS, SUBJECTS, BAND_PHRASE, type MasteryRow } from '@/lib/mock';

/**
 * Subject and cohort rollup — a class-wide read organised by subject, distinct
 * from the per-student "Student insights" engine on /teacher/students. This view
 * answers "where does the whole class stand, by subject," in plain language —
 * never a raw number or formula.
 *
 * The cohort stats and the per-topic mastery rows are read GATEWAY-FIRST from the
 * SPINE (intelligence-views: class-insights) through the governed seam, derived
 * from the live per-(student, topic) reads; the static mock (CLASS_STATS /
 * MASTERY_ROWS) is the degrade-only fallback when the read returns nothing. Vidya
 * stays docked to keep driving the page. All five designed states ship.
 */

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
    // The most frequent band stands for the topic (deterministic, no formula shown).
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

  // Live cohort stats from the spine's class summary; degrade to the static seed.
  const stats = useMemo(() => {
    const s = insights?.summary;
    if (!s) return null;
    return [
      { label: 'Working independently', value: s.working_independently, detail: 'reads, across touched topics' },
      { label: 'Need support', value: s.need_support, detail: 'not yet on their own' },
      { label: 'Confirmed gaps', value: s.confirmed_gaps, detail: 'corroborated, not single scores' },
      { label: 'Revision now due', value: s.revision_due, detail: 'evidence has decayed' },
    ];
  }, [insights]);

  // Live per-topic mastery rows; degrade to the static seed when empty.
  const masteryRows = useMemo(() => {
    const live = topicMasteryRows(insights?.reads ?? []);
    return live.length > 0 ? live : MASTERY_ROWS;
  }, [insights]);

  const cohortStats = stats ?? CLASS_STATS;

  // Group mastery rows by subject for the per-subject cards.
  const bySubject = SUBJECTS.map((s) => ({
    subject: s,
    rows: masteryRows.filter((r) => r.subject === s.accent),
  })).filter((g) => g.rows.length > 0);

  return (
    <SurfaceShell
      eyebrow="Class 10-B"
      title="Subject and cohort rollup"
      dockIntro="This is the subject-by-subject rollup for Class 10-B, read live from the spine. Ask how a subject is trending, or which topics the cohort has secured. For a single student, open Student insights."
      dockChips={['How is Mathematics trending', 'Which topics are secured', 'Where is the cohort still supported']}
    >
      {phase !== 'ready' ? (
        <ReadStates phase={phase} onRetry={refresh} />
      ) : (
        <>
          <section>
            <p className="overline">This week, in plain language</p>
            <Matrix columns={4}>
              {cohortStats.map((s) => (
                <Cell key={s.label}>
                  <Stat label={s.label} value={s.value} />
                  <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
                    {s.detail}
                  </p>
                </Cell>
              ))}
            </Matrix>
          </section>

          <section className="stack">
            <p className="overline">Where the class stands</p>
            <MasteryView rows={masteryRows} />
            <p className="caption quiet">
              Independent means a student can do it on their own, consistently. Everything else still
              leans on support. No scores or formulas are shown — only what a learner can do.
            </p>
          </section>

          <section>
            <p className="overline">By subject</p>
            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
              {bySubject.map(({ subject, rows }) => (
                <SubjectCard key={subject.code} name={subject.name} code={subject.code} accent={subject.accent}>
                  <ul className="stack" style={{ margin: 0, paddingLeft: '1.1rem' }}>
                    {rows.map((r) => (
                      <li key={r.topic} className="body-sm">
                        {r.topic} — <span className="muted">{BAND_PHRASE[r.band]}</span>
                      </li>
                    ))}
                  </ul>
                </SubjectCard>
              ))}
            </div>
          </section>

          <SourceNote source={source} />
        </>
      )}
    </SurfaceShell>
  );
}
