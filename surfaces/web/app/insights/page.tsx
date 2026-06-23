'use client';

import { Cell, Matrix, Stat, SubjectCard } from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { MasteryView } from '../_components/MasteryView';
import { CLASS_STATS, MASTERY_ROWS, SUBJECTS, BAND_PHRASE } from '@/lib/mock';

/**
 * Subject and cohort rollup — a class-wide read organised by subject, distinct
 * from the per-student "Student insights" engine on /teacher/students. This view
 * answers "where does the whole class stand, by subject," in plain language —
 * never a raw number or formula. Vidya stays docked to keep driving the page.
 */
export default function InsightsPage() {
  // Group mastery rows by subject for the per-subject cards.
  const bySubject = SUBJECTS.map((s) => ({
    subject: s,
    rows: MASTERY_ROWS.filter((r) => r.subject === s.accent),
  })).filter((g) => g.rows.length > 0);

  return (
    <SurfaceShell
      eyebrow="Class 10-B"
      title="Subject and cohort rollup"
      dockIntro="This is the subject-by-subject rollup for Class 10-B. Ask how a subject is trending, or which topics the cohort has secured. For a single student, open Student insights."
      dockChips={['How is Mathematics trending', 'Which topics are secured', 'Where is the cohort still supported']}
    >
      <section>
        <p className="overline">This week, in plain language</p>
        <Matrix columns={4}>
          {CLASS_STATS.map((s) => (
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
        <MasteryView rows={MASTERY_ROWS} />
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
    </SurfaceShell>
  );
}
