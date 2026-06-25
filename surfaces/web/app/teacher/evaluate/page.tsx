'use client';

import { useMemo, useState } from 'react';
import { Button, ConfidenceBand, Icon, SpotlightCard, Tag, type Confidence } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ReadStates } from '../../_components/ReadStates';
import { SourceNote } from '../../_components/SourceNote';
import { ApprovalControl } from '../../_components/ApprovalControl';
import { useSurfaceState } from '@/lib/useSurfaceState';
import { useGatewaySource } from '@/lib/useGatewaySource';
import { CLASS_LABEL, CURRENT_STUDENT, topicInfo, LOOP_TOPIC_ID } from '@/lib/loopData';

/**
 * The evaluation review table — confidence-banded, per-response rows. CORE:
 * correctness is existential. Two structural rules are visible here:
 *   - consequential marks are HUMAN-FINAL — nothing is final until the teacher
 *     confirms it (permission ladder: grading needs explicit approval),
 *   - middle/low confidence MUST be reviewed; high may stand provisionally.
 * Handwriting/scan quality never reduces a mark — illegible flags review.
 */

type AnswerState = 'correct' | 'incomplete' | 'misunderstood';

interface ResponseRow {
  id: string;
  question: string;
  state: AnswerState;
  rubric: string; // e.g. "3 / 4"
  band: Confidence;
  rationale: string;
}

const TOPIC = topicInfo(LOOP_TOPIC_ID);

const ROWS: ResponseRow[] = [
  {
    id: 'q1',
    question: 'Write the six trigonometric ratios for the given right triangle.',
    state: 'correct',
    rubric: '4 / 4',
    band: 'high',
    rationale: 'All six ratios correct and matched to the right sides. Deterministic check passed; second model agreed.',
  },
  {
    id: 'q2',
    question: 'Evaluate sin 30° + cos 60° and simplify.',
    state: 'incomplete',
    rubric: '2 / 4',
    band: 'middle',
    rationale: 'Correct values recalled but the final simplification step is missing. Method is sound; stopped short.',
  },
  {
    id: 'q3',
    question: 'A student wrote tan θ = sin θ × cos θ. Identify and correct the error.',
    state: 'misunderstood',
    rubric: '1 / 4',
    band: 'low',
    rationale: 'The relationship tan θ = sin θ / cos θ is inverted — a conceptual slip. Handwriting was clear; this is not a legibility issue.',
  },
  {
    id: 'q4',
    question: 'Compute cos θ given sin θ = 3/5 in a right triangle.',
    state: 'correct',
    rubric: '4 / 4',
    band: 'high',
    rationale: 'Used the Pythagorean relationship correctly; arrived at 4/5. Both checks passed.',
  },
];

const STATE_TONE: Record<AnswerState, 'success' | 'warning' | 'danger'> = {
  correct: 'success',
  incomplete: 'warning',
  misunderstood: 'danger',
};

const STATE_LABEL: Record<AnswerState, string> = {
  correct: 'Correct',
  incomplete: 'Incomplete',
  misunderstood: 'Misunderstood',
};

type RowDecision = 'pending' | 'confirmed' | 'adjusted';

export default function EvaluatePage() {
  // The submission read carries the five designed states from one place.
  const { phase: readPhase, refresh } = useSurfaceState();
  // The per-response rows are the spine's coursework evaluation read. Probe the
  // wall so the OBSERVABLE source marker sits on the table — these seed rows
  // render either way, but never as if they were live when the spine was silent.
  const { source } = useGatewaySource('coursework');
  const [decisions, setDecisions] = useState<Record<string, RowDecision>>({});
  const [returned, setReturned] = useState(false);

  const needingReview = useMemo(() => ROWS.filter((r) => r.band !== 'high'), []);
  const pendingReviewCount = needingReview.filter((r) => (decisions[r.id] ?? 'pending') === 'pending').length;

  function decide(id: string, d: RowDecision) {
    setDecisions((prev) => ({ ...prev, [id]: d }));
  }

  const allReviewed = pendingReviewCount === 0;

  return (
    <SurfaceShell
      eyebrow={`${CLASS_LABEL} · ${TOPIC.subjectName}`}
      title="Evaluation review"
      dockIntro="Per-response review for this submission. High confidence can stand; building and needs-review must be confirmed by you. Nothing is final until you sign off — that is the rule for any mark."
      dockChips={['Explain the misunderstood answer', 'Read marks by voice', 'Why is this flagged for review']}
    >
      {readPhase !== 'ready' ? (
        <ReadStates phase={readPhase} onRetry={refresh} />
      ) : (
      <>
      <section className="stack">
        <div className="row-between">
          <div>
            <p className="overline" style={{ margin: 0 }}>
              {CURRENT_STUDENT.label} · {TOPIC.name}
            </p>
            <p className="body-sm muted" style={{ marginTop: 'var(--space-2)' }}>
              {ROWS.length} responses · {needingReview.length} flagged for your review
            </p>
          </div>
          <Tag tone={allReviewed ? 'success' : 'warning'}>
            {allReviewed ? 'All reviews complete' : `${pendingReviewCount} awaiting review`}
          </Tag>
        </div>

        <SpotlightCard>
          <div className="table-scroll">
          <table className="eval-table">
            <thead>
              <tr>
                <th style={{ width: '38%' }}>Question</th>
                <th>Answer state</th>
                <th>Rubric</th>
                <th>Confidence</th>
                <th style={{ width: '22%' }}>Human-final</th>
              </tr>
            </thead>
            <tbody>
              {ROWS.map((r) => {
                const d = decisions[r.id] ?? 'pending';
                const mustReview = r.band !== 'high';
                const rowClass = mustReview && d === 'pending' ? 'needs-review' : '';
                return (
                  <tr key={r.id} className={rowClass}>
                    <td>
                      <div className="body-sm">{r.question}</div>
                      <div className="caption quiet" style={{ marginTop: 4 }}>
                        {r.rationale}
                      </div>
                    </td>
                    <td>
                      <span className={`state-pill ${r.state}`}>
                        <span className="dot" aria-hidden="true" />
                        <Tag tone={STATE_TONE[r.state]}>{STATE_LABEL[r.state]}</Tag>
                      </span>
                    </td>
                    <td>
                      <span className="body-sm" style={{ fontVariantNumeric: 'tabular-nums' }}>
                        {r.rubric}
                      </span>
                    </td>
                    <td>
                      <ConfidenceBand level={r.band} />
                    </td>
                    <td>
                      {d === 'pending' ? (
                        mustReview ? (
                          <div className="row" style={{ gap: 'var(--space-2)', flexWrap: 'wrap' }}>
                            <Button variant="accent" size="sm" onClick={() => decide(r.id, 'confirmed')}>
                              Confirm
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => decide(r.id, 'adjusted')}>
                              Adjust
                            </Button>
                          </div>
                        ) : (
                          <div className="row" style={{ gap: 'var(--space-2)' }}>
                            <span className="caption muted">Provisional — confirm to finalise</span>
                            <Button variant="ghost" size="sm" onClick={() => decide(r.id, 'confirmed')}>
                              Confirm
                            </Button>
                          </div>
                        )
                      ) : (
                        <span className="caption" style={{ color: 'var(--success-ink)' }}>
                          {d === 'adjusted' ? 'Adjusted and final' : 'Confirmed — final'}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
        </SpotlightCard>

        <p className="caption quiet">
          A mark is never final from a single low score, and handwriting or scan quality never lowers
          a mark — illegible work is flagged for review, not penalised. The engine recommends; you
          confirm.
        </p>
        <SourceNote source={source} />
      </section>

      <section>
        {returned ? (
          <SpotlightCard hero>
            <div className="row-between">
              <div>
                <p className="overline" style={{ margin: 0 }}>
                  Marks published
                </p>
                <p className="body-sm" style={{ marginTop: 'var(--space-2)' }}>
                  Feedback returned to {CURRENT_STUDENT.label}. They will see it on their next visit,
                  and these marks now feed mastery + gaps.
                </p>
              </div>
              <Tag tone="success">Returned</Tag>
            </div>
          </SpotlightCard>
        ) : !allReviewed ? (
          <div className="empty">
            <Icon name="info" size="lg" className="glyph" />
            <h4 className="body">Review the flagged responses first</h4>
            <p>
              Publishing a mark is consequential, so it waits behind a confirmed review. Confirm the
              flagged responses above and the approval gate opens.
            </p>
          </div>
        ) : (
          // Publishing a grade is CONSEQUENTIAL — the permission ladder. Nothing
          // is final or returned to the learner until the teacher approves here;
          // approval emits an attributed, consent-stamped `score` audit event.
          <ApprovalControl
            kind="Publish marks · the permission ladder"
            summary={`Return ${ROWS.length} reviewed responses to ${CURRENT_STUDENT.label}`}
            consequence={`The marks become final, are returned to ${CURRENT_STUDENT.label}, and feed the mastery + gap engine. Grading is human-final — this approval is what makes it so.`}
            eventType="score"
            approveLabel="Approve and publish marks"
            payload={{ surface: 'teacher.evaluate', topicId: TOPIC.id, responses: ROWS.length }}
            evidence={[
              'Every response carries a separated state (correct / incomplete / misunderstood) and a confidence band; middle/low were confirmed by you above.',
              'Handwriting or scan quality never lowered a mark — illegible work is flagged for review, not penalised.',
            ]}
            whySeeing="A mark sent to a learner is consequential. The engine recommends; you confirm; only your approval publishes it."
            onApprove={() => setReturned(true)}
          />
        )}
      </section>
      </>
      )}
    </SurfaceShell>
  );
}
