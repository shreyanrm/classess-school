'use client';

import { useEffect, useMemo } from 'react';
import { Cell, type Confidence, Matrix, Stat } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ReadStates } from '../../_components/ReadStates';
import { SourceNote } from '../../_components/SourceNote';
import { RecommendationItem } from '../../_components/RecommendationItem';
import { useClassInsights } from '@/lib/useClassInsights';
import { useProactive } from '@/lib/useProactive';
import { useEmit } from '@/lib/useEmit';
import { EVENT_PURPOSE } from '@/lib/events';
import { gapLabel } from '@/lib/engine';
import type { StudentTopicRead } from '@/lib/classRead';
import type { Recommendation } from '@/lib/mock';
import { CLASS_LABEL, CLASS_REF } from '@/lib/loopData';

/**
 * Class insights — the loop's rolled-up intelligence view (the proactive feed).
 * Reads the class summary + the needing-attention list GATEWAY-FIRST from the
 * SPINE (intelligence-views: class-insights), falling back to the TS engine only
 * on degrade. Manage-by-exception: each item is a RecommendationItem carrying
 * full provenance — evidence · confidence · owner · due · consequence — and an
 * Approve that runs the PREPARED action through the permission ladder (it never
 * auto-fires). Every conclusion opens an EvidenceDrawer. All five states ship.
 */

/** Map the engine's numeric gap confidence (0-1) to a plain band — never a raw number. */
function confidenceBand(value: number): Confidence {
  if (value >= 0.66) return 'high';
  if (value >= 0.4) return 'middle';
  return 'low';
}

/**
 * Turn a needing-attention read into a manage-by-exception recommendation —
 * computed from the corroborated gaps on that read, never a single score.
 */
function toRecommendation(r: StudentTopicRead): Recommendation {
  const top = r.confirmedGaps[0]!;
  const label = gapLabel(top.evidence.gapType);
  return {
    id: `${r.studentRef}-${r.topic.id}`,
    title: `${r.studentLabel} · ${r.topic.name}: ${label.toLowerCase()}`,
    gapType: top.evidence.gapType,
    evidenceSummary: top.evidence.rationale,
    evidence: r.confirmedGaps.map(
      (g) => `${gapLabel(g.evidence.gapType)} — ${g.evidence.rationale}`,
    ),
    confidence: confidenceBand(top.evidence.confidence),
    owner: 'You (Class 10-B teacher)',
    due: `Before the next ${r.topic.subjectName} class`,
    consequence: `The gap on ${r.topic.name} hardens and widens into the next unit.`,
    whySeeing: `Flagged from ${r.confirmedGaps.length} corroborated ${
      r.confirmedGaps.length === 1 ? 'signal' : 'signals'
    } — never a single bad score. Approve to run the prepared remedial; it waits for you.`,
    // Assigning a remedial to a learner is consequential -> the ApprovalControl,
    // commit on Approve only (the permission ladder). A support-dependency gap
    // closing is the independent-mastery moment (CrystallizeNode + gap.resolved).
    actionLabel: 'Assign the remedial',
    consequential: true,
    target: '/teacher/assign',
    crystallizes:
      top.evidence.gapType === 'support-dependency'
        ? `${r.studentLabel} can now do ${r.topic.name} on their own`
        : undefined,
  };
}

export default function ClassInsightsPage() {
  const { phase, insights, source, refresh } = useClassInsights();
  const { emit } = useEmit();
  // The same proactive loop write the approval queue uses — Approve/Execute on a
  // prepared remedial runs through the wall here too (gateway-first, degrade-safe).
  const { actioned } = useProactive(CLASS_REF);

  const summary = insights?.summary;
  const recs = useMemo(
    () => (insights?.needingAttention ?? []).map(toRecommendation),
    [insights],
  );

  useEffect(() => {
    if (phase === 'ready') {
      emit({
        type: 'surface.viewed',
        purpose: EVENT_PURPOSE.teaching,
        payload: { surface: 'teacher.insights', source, items: recs.length },
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  return (
    <SurfaceShell
      eyebrow={CLASS_LABEL}
      title="Class insights"
      dockIntro="Everything Classess found for this class, with evidence and an owner. Each item is prepared — Approve runs it through the permission ladder; nothing fires on its own. Ask me to explain any item, or to draft a remedial."
      dockChips={['Explain the top gap', 'Draft a remedial for the application gap', 'What changed since yesterday']}
    >
      {phase !== 'ready' ? (
        <ReadStates phase={phase} onRetry={refresh} />
      ) : (
        <>
          <section>
            <p className="overline">The class, in plain language</p>
            <Matrix columns={4}>
              <Cell>
                <Stat label="Working independently" value={summary?.working_independently ?? 0} />
                <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
                  reads, across touched topics
                </p>
              </Cell>
              <Cell>
                <Stat label="Still need support" value={summary?.need_support ?? 0} />
                <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
                  not yet on their own
                </p>
              </Cell>
              <Cell>
                <Stat label="Confirmed gaps" value={summary?.confirmed_gaps ?? 0} />
                <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
                  corroborated, not single scores
                </p>
              </Cell>
              <Cell>
                <Stat label="Revision due" value={summary?.revision_due ?? 0} />
                <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
                  evidence has decayed
                </p>
              </Cell>
            </Matrix>
          </section>

          <section className="stack">
            <p className="overline">What needs you — manage by exception</p>
            {recs.length === 0 ? (
              <div className="empty">
                <h4 className="body">Nothing needs you</h4>
                <p>No confirmed gaps from corroborated evidence. The class is on track.</p>
              </div>
            ) : (
              recs.map((rec) => <RecommendationItem key={rec.id} rec={rec} onActioned={actioned} />)
            )}
            <SourceNote source={source} />
          </section>
        </>
      )}
    </SurfaceShell>
  );
}
