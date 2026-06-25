'use client';

import { useMemo, useState } from 'react';
import { CrystallizeNode, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ReadStates } from '../../_components/ReadStates';
import { SourceNote } from '../../_components/SourceNote';
import { DimensionBars } from '../../_components/DimensionBars';
import { GapChips } from '../../_components/GapChips';
import { EvidenceDrawer } from '../../_components/EvidenceDrawer';
import { type StudentTopicRead } from '@/lib/classRead';
import { useClassInsights } from '@/lib/useClassInsights';
import { BAND_SHORT } from '@/lib/engine';
import { CLASS_LABEL, ROSTER } from '@/lib/loopData';

/**
 * Student insights — mastery per topic in PLAIN LANGUAGE (independent vs
 * with-guidance), gap chips, and the Evidence drawer that opens the six-
 * dimension reasoning and the lineage. Read GATEWAY-FIRST from the SPINE
 * (class-insights view), falling back to the TS engine only on degrade. The
 * teacher sees the reasoning; learners never do.
 */
export default function StudentInsightsPage() {
  const { phase, insights, source, refresh } = useClassInsights();
  const reads = useMemo(() => insights?.reads ?? [], [insights]);
  const byStudent = useMemo(() => groupByStudent(reads), [reads]);
  const [openKey, setOpenKey] = useState<string | null>(null);

  return (
    <SurfaceShell
      eyebrow={CLASS_LABEL}
      title="Student insights"
      dockIntro="Mastery per topic, in plain language — independent versus with guidance. Open any read for its six-dimension reasoning and the evidence behind it. Ask what unlocks a topic, or who is support-dependent."
      dockChips={['Who is support-dependent', 'What unlocks trig identities', 'Show only confirmed gaps']}
    >
      {phase !== 'ready' ? (
        <ReadStates phase={phase} onRetry={refresh} />
      ) : byStudent.length === 0 ? (
        <div className="empty">
          <h4 className="body">No evidence yet</h4>
          <p>Once students attempt a check, their reads appear here with full lineage.</p>
        </div>
      ) : (
        <>
        {byStudent.map(({ studentRef, studentLabel: label, reads: rows }) => (
          <section className="stack" key={studentRef}>
            <p className="overline">{label}</p>
            {rows.map((r) => {
              const key = `${r.studentRef}-${r.topic.id}`;
              const open = openKey === key;
              return (
                <SpotlightCard key={key}>
                  <div className="row-between" style={{ alignItems: 'flex-start' }}>
                    <div>
                      <div className="ignite-row" style={{ marginBottom: 2 }}>
                        {r.mastery.reading.independent ? <CrystallizeNode variant="b" inline resolved label="Independent" /> : null}
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

                  <div className="row-between" style={{ marginTop: 'var(--space-3)' }}>
                    <GapChips gaps={r.gaps} emptyLabel="No gaps — the evidence is clean" />
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      aria-expanded={open}
                      onClick={() => setOpenKey(open ? null : key)}
                    >
                      {open ? 'Hide reasoning' : 'Open reasoning'}
                    </button>
                  </div>

                  {open ? (
                    <div className="evidence-drawer">
                      <p className="caption">
                        <strong>The six dimensions. </strong>
                        The teacher-facing reasoning behind the band — never shown to the learner,
                        never collapsed to one number.
                      </p>
                      <DimensionBars dimensions={r.mastery.reading.dimensions} showGloss />
                      <EvidenceDrawer
                        evidence={r.mastery.evidenceEventIds.map(
                          (id) => `Attributed attempt/score event ${id.slice(0, 8)}… in this read's lineage.`,
                        )}
                        whySeeing="Every reading is computed by replaying these events. A judgment is never confirmed from a single bad score."
                      />
                    </div>
                  ) : null}
                </SpotlightCard>
              );
            })}
          </section>
        ))}
        <SourceNote source={source} />
        </>
      )}
    </SurfaceShell>
  );
}

interface StudentGroup {
  studentRef: string;
  studentLabel: string;
  reads: StudentTopicRead[];
}

function groupByStudent(reads: StudentTopicRead[]): StudentGroup[] {
  const order = ROSTER.map((s) => s.ref);
  const map = new Map<string, StudentGroup>();
  for (const r of reads) {
    const g = map.get(r.studentRef) ?? { studentRef: r.studentRef, studentLabel: r.studentLabel, reads: [] };
    g.reads.push(r);
    map.set(r.studentRef, g);
  }
  return [...map.values()].sort((a, b) => order.indexOf(a.studentRef) - order.indexOf(b.studentRef));
}

function capitalise(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
