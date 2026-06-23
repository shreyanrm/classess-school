'use client';

import Link from 'next/link';
import { Cell, ConfidenceBand, Matrix, SpotlightCard, Stat, Tag, type Confidence } from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { BriefingCard } from '../_components/BriefingCard';
import { EvidenceDrawer } from '../_components/EvidenceDrawer';
import { GapChips } from '../_components/GapChips';
import { BRIEFINGS } from '@/lib/mock';
import {
  computeClassReads,
  studentsNeedingAttention,
  summariseClass,
} from '@/lib/classRead';
import { CLASS_LABEL } from '@/lib/loopData';

/** Map the engine's numeric gap confidence (0-1) to a plain band — never a raw number. */
function confidenceBand(value: number): Confidence {
  if (value >= 0.66) return 'high';
  if (value >= 0.4) return 'middle';
  return 'low';
}

/**
 * The teacher day — next class, pending evaluations, students needing attention.
 * The attention list is computed LIVE from the seed evidence through the engine,
 * so it reflects real confirmed gaps (never a single bad score). Manage by
 * exception: review, act, track outcome.
 */
export default function TeacherDayPage() {
  const reads = computeClassReads();
  const attention = studentsNeedingAttention(reads);
  const summary = summariseClass(reads);

  return (
    <SurfaceShell
      eyebrow={CLASS_LABEL}
      title="Your day"
      dockIntro="Here is your day with Class 10-B. The attention list is computed from real evidence — ask me to explain any student, or build the next quick check."
      dockChips={['Who needs attention and why', 'Build a quick check', 'What changed since yesterday']}
    >
      <section>
        <p className="overline">The class, in plain language</p>
        <Matrix columns={4}>
          <Cell>
            <Stat label="Working independently" value={summary.working_independently} />
            <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
              reads, across touched topics
            </p>
          </Cell>
          <Cell>
            <Stat label="Still need support" value={summary.need_support} />
            <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
              not yet on their own
            </p>
          </Cell>
          <Cell>
            <Stat label="Confirmed gaps" value={summary.confirmed_gaps} />
            <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
              corroborated, not single scores
            </p>
          </Cell>
          <Cell>
            <Stat label="Revision due" value={summary.revision_due} />
            <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
              evidence has decayed
            </p>
          </Cell>
        </Matrix>
      </section>

      <section className="stack">
        <p className="overline">Today</p>
        {BRIEFINGS.map((b) => (
          <BriefingCard key={b.id} briefing={b} />
        ))}
      </section>

      <section className="stack">
        <div className="row-between">
          <p className="overline" style={{ margin: 0 }}>
            Students needing attention
          </p>
          <Link href="/teacher/students" className="btn btn-ghost btn-sm">
            See all student insights
          </Link>
        </div>
        {attention.length === 0 ? (
          <div className="empty">
            <h4 className="body">No confirmed gaps today</h4>
            <p>Nothing is flagged from corroborated evidence. The class is on track.</p>
          </div>
        ) : (
          attention.map((r) => {
            const gap = r.confirmedGaps[0]!;
            const band = confidenceBand(gap.evidence.confidence);
            // Full evidence lineage from every confirmed gap on this read.
            const evidence = r.confirmedGaps.map(
              (g) => `${g.evidence.gapType.replace('-', ' ')} — ${g.evidence.rationale}`,
            );
            return (
              <SpotlightCard key={`${r.studentRef}-${r.topic.id}`}>
                <div className="row-between" style={{ alignItems: 'flex-start' }}>
                  <div>
                    <div className="body" style={{ marginBottom: 2 }}>
                      {r.studentLabel} · {r.topic.name}
                    </div>
                    <div className="caption muted">{r.topic.subjectName}</div>
                  </div>
                  <Tag tone="info">{gap.evidence.gapType.replace('-', ' ')}</Tag>
                </div>
                <p className="body-sm" style={{ marginTop: 'var(--space-3)' }}>
                  {gap.evidence.rationale}
                </p>

                <div className="rec-meta">
                  <div>
                    <div className="k">Confidence</div>
                    <div className="v">
                      <ConfidenceBand level={band} />
                    </div>
                  </div>
                  <div>
                    <div className="k">Owner</div>
                    <div className="v">You (Class 10-B teacher)</div>
                  </div>
                  <div>
                    <div className="k">Due</div>
                    <div className="v">Before the next {r.topic.subjectName} class</div>
                  </div>
                  <div>
                    <div className="k">If ignored</div>
                    <div className="v">
                      The gap on {r.topic.name} hardens and widens into the next unit.
                    </div>
                  </div>
                </div>

                <EvidenceDrawer
                  evidence={evidence}
                  whySeeing={`This is flagged from ${r.confirmedGaps.length} corroborated ${
                    r.confirmedGaps.length === 1 ? 'signal' : 'signals'
                  } — never a single bad score.`}
                />

                <div className="row-between" style={{ marginTop: 'var(--space-4)' }}>
                  <GapChips gaps={r.gaps} />
                  <Link href="/teacher/students" className="btn btn-secondary btn-sm">
                    Open evidence
                  </Link>
                </div>
              </SpotlightCard>
            );
          })
        )}
      </section>

      <section>
        <SpotlightCard hero>
          <div className="row-between">
            <div>
              <p className="overline" style={{ margin: 0 }}>
                One private coaching insight
              </p>
              <p className="body-sm" style={{ marginTop: 'var(--space-2)' }}>
                Your questioning ran ahead of the support-dependent group on Tuesday. A small change
                lifts the third still leaning on prompts.
              </p>
            </div>
            <Link href="/teacher/growth" className="btn btn-ghost btn-sm">
              See the suggestion
            </Link>
          </div>
        </SpotlightCard>
      </section>
    </SurfaceShell>
  );
}
