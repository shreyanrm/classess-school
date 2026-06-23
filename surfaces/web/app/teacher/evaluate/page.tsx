'use client';

import { useMemo, useState } from 'react';
import { Button, ConfidenceBand, SpotlightCard, Tag, type Confidence } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
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
  const [decisions, setDecisions] = useState<Record<string, RowDecision>>({});

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
        </SpotlightCard>

        <p className="caption quiet">
          A mark is never final from a single low score, and handwriting or scan quality never lowers
          a mark — illegible work is flagged for review, not penalised. The engine recommends; you
          confirm.
        </p>
      </section>

      <section>
        <SpotlightCard>
          <div className="row-between">
            <div>
              <p className="overline" style={{ margin: 0 }}>
                Return feedback
              </p>
              <p className="body-sm" style={{ marginTop: 'var(--space-2)' }}>
                {allReviewed
                  ? 'All flagged responses are confirmed. Feedback is ready to return to the student.'
                  : 'Review the flagged responses before feedback can be returned.'}
              </p>
            </div>
            <Button variant="accent" size="sm" disabled={!allReviewed}>
              Return feedback
            </Button>
          </div>
        </SpotlightCard>
      </section>
    </SurfaceShell>
  );
}
