'use client';

import { useMemo, useState } from 'react';
import {
  Button,
  ConfidenceBand,
  Icon,
  Matrix,
  SpotlightCard,
  Tag,
  type Confidence,
} from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { StatCell } from '../../_components/StatCell';
import { ReadStates } from '../../_components/ReadStates';
import { SourceNote } from '../../_components/SourceNote';
import { EvidenceDrawer } from '../../_components/EvidenceDrawer';
import { ApprovalControl } from '../../_components/ApprovalControl';
import { AssignmentBoard } from '../../_components/AssignmentBoard';
import { ProjectRubric } from '../../_components/ProjectRubric';
import { BottomSheet } from '../../_components/BottomSheet';
import { useSurfaceState } from '@/lib/useSurfaceState';
import { useGatewaySource } from '@/lib/useGatewaySource';
import { useVizData } from '@/lib/useVizData';
import { CLASS_LABEL, CURRENT_STUDENT, topicInfo, LOOP_TOPIC_ID } from '@/lib/loopData';
import type { AssignmentRow } from '@/lib/vizData';

/**
 * The evaluation review surface — three tabs, in the v3 grammar.
 *   • Submissions — the confidence-banded per-response review (grading is
 *     HUMAN-FINAL; middle/low must be confirmed before a mark can stand).
 *   • Assignments — the chapter-grouped list (Homework / Quiz / Project) with
 *     submissions % from plain counts, due dates, and a calm status. Opening a
 *     project row raises the project rubric.
 *   • Projects — the six-dimension ProjectRubric (criteria × Level 1–4) +
 *     submission tracking, the v2 project rubric carried forward.
 *
 * Marks are never final from a single low score; handwriting/scan quality never
 * lowers a mark — illegible flags review. The engine recommends; you confirm.
 */

type AnswerState = 'correct' | 'incomplete' | 'misunderstood';
type EvalTab = 'submissions' | 'assignments' | 'projects';

interface ResponseRow {
  id: string;
  question: string;
  state: AnswerState;
  rubric: string; // e.g. "3 / 4"
  band: Confidence;
  rationale: string;
  evidence: string[];
}

const TOPIC = topicInfo(LOOP_TOPIC_ID);

const ROWS: ResponseRow[] = [
  {
    id: 'q1',
    question: 'Write the six trigonometric ratios for the given right triangle.',
    state: 'correct',
    rubric: '4 / 4',
    band: 'high',
    rationale:
      'All six ratios correct and matched to the right sides. Deterministic check passed; second model agreed.',
    evidence: [
      'Deterministic ratio check passed on all six entries.',
      'A second model independently agreed on the mark — two checks, not one.',
      'Handwriting was clear; legibility was not a factor.',
    ],
  },
  {
    id: 'q2',
    question: 'Evaluate sin 30° + cos 60° and simplify.',
    state: 'incomplete',
    rubric: '2 / 4',
    band: 'middle',
    rationale:
      'Correct values recalled but the final simplification step is missing. Method is sound; stopped short.',
    evidence: [
      'Both standard values (sin 30°, cos 60°) recalled correctly.',
      'The final simplification step is absent — the work stops one move early.',
      'Method is sound, so this reads incomplete, not misunderstood. Middle confidence — your review decides.',
    ],
  },
  {
    id: 'q3',
    question: 'A student wrote tan θ = sin θ × cos θ. Identify and correct the error.',
    state: 'misunderstood',
    rubric: '1 / 4',
    band: 'low',
    rationale:
      'The relationship tan θ = sin θ / cos θ is inverted — a conceptual slip. Handwriting was clear; this is not a legibility issue.',
    evidence: [
      'The identity is inverted (× where ÷ belongs) — a conceptual error, not arithmetic.',
      'Repeated in the correction step, so it is consistent, not a one-off slip.',
      'Handwriting was clear; this was not lowered for legibility. Low confidence — must be reviewed.',
    ],
  },
  {
    id: 'q4',
    question: 'Compute cos θ given sin θ = 3/5 in a right triangle.',
    state: 'correct',
    rubric: '4 / 4',
    band: 'high',
    rationale: 'Used the Pythagorean relationship correctly; arrived at 4/5. Both checks passed.',
    evidence: [
      'Pythagorean relationship applied correctly to reach cos θ = 4/5.',
      'Both the deterministic check and the second model agreed.',
    ],
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
  // wall so the OBSERVABLE source marker sits on the table.
  const { source } = useGatewaySource('coursework');
  // The assignment board + project rubric read gateway-first (seed fallback).
  const viz = useVizData(['assignments', 'rubric']);
  const [tab, setTab] = useState<EvalTab>('submissions');
  const [decisions, setDecisions] = useState<Record<string, RowDecision>>({});
  const [returned, setReturned] = useState(false);
  const [openProject, setOpenProject] = useState<AssignmentRow | null>(null);

  const needingReview = useMemo(() => ROWS.filter((r) => r.band !== 'high'), []);
  const pendingReviewCount = needingReview.filter(
    (r) => (decisions[r.id] ?? 'pending') === 'pending',
  ).length;
  const reviewedCount = needingReview.length - pendingReviewCount;
  const correctCount = ROWS.filter((r) => r.state === 'correct').length;

  const allAssignments = useMemo(
    () => viz.data.assignments.chapters.flatMap((c) => c.assignments),
    [viz.data.assignments],
  );
  const projectCount = allAssignments.filter((a) => a.kind === 'project').length;
  const openCount = allAssignments.filter((a) => a.status === 'in-window').length;

  function decide(id: string, d: RowDecision) {
    setDecisions((prev) => ({ ...prev, [id]: d }));
  }

  const allReviewed = pendingReviewCount === 0;

  return (
    <SurfaceShell
      eyebrow={`${CLASS_LABEL} · ${TOPIC.subjectName}`}
      title="Evaluation review"
      breadcrumb={[
        { label: 'School', href: '/' },
        { label: CLASS_LABEL, href: '/teacher' },
        { label: 'Evaluation' },
      ]}
      meta={[
        { value: ROWS.length, label: 'responses' },
        { value: allAssignments.length, label: 'assignments' },
        { value: projectCount, label: 'projects' },
      ]}
      tabs={[
        { label: 'Overview', href: '/teacher' },
        { label: 'Students', href: '/teacher/students' },
        { label: 'Class insights', href: '/teacher/insights' },
        { label: 'Evaluation', active: true },
      ]}
      dockIntro="Per-response review, the chapter assignment tracker, and the project rubric. High confidence can stand; building and needs-review must be confirmed by you. Nothing is final until you sign off — that is the rule for any mark."
      dockChips={['Explain the misunderstood answer', 'Who has not submitted the project', 'Why is this flagged for review']}
    >
      {readPhase !== 'ready' ? (
        <ReadStates phase={readPhase} onRetry={refresh} />
      ) : (
        <>
          {/* ── Tabs across the evaluation surfaces ── */}
          <div className="segmented" role="tablist" aria-label="Evaluation view">
            <button type="button" role="tab" aria-selected={tab === 'submissions'} className={tab === 'submissions' ? 'active' : ''} onClick={() => setTab('submissions')}>
              Submissions
            </button>
            <button type="button" role="tab" aria-selected={tab === 'assignments'} className={tab === 'assignments' ? 'active' : ''} onClick={() => setTab('assignments')}>
              Assignments
            </button>
            <button type="button" role="tab" aria-selected={tab === 'projects'} className={tab === 'projects' ? 'active' : ''} onClick={() => setTab('projects')}>
              Projects
            </button>
          </div>

          {tab === 'submissions' ? (
            <>
              <Matrix columns={4} className="reveal reveal-1">
                <StatCell label="Responses" value={ROWS.length} delta={`${CURRENT_STUDENT.label} · ${TOPIC.name}`} tone="flat" />
                <StatCell label="Read correct" value={correctCount} delta="two checks agreed" tone="up" />
                <StatCell label="Flagged for review" value={needingReview.length} delta="middle / low confidence" tone={needingReview.length > 0 ? 'down' : 'flat'} />
                <StatCell label="Reviewed" value={reviewedCount} delta={allReviewed ? 'all confirmed' : `${pendingReviewCount} awaiting you`} tone={allReviewed ? 'up' : 'flat'} />
              </Matrix>

              <section className="stack">
                <div className="sec-head">
                  <h3 className="h3" style={{ margin: 0 }}>Per-response review</h3>
                  <Tag tone={allReviewed ? 'success' : 'warning'}>
                    {allReviewed ? 'All reviews complete' : `${pendingReviewCount} awaiting review`}
                  </Tag>
                </div>

                <SpotlightCard>
                  <div className="table-scroll">
                    <table className="eval-table">
                      <thead>
                        <tr>
                          <th style={{ width: '34%' }}>Question</th>
                          <th>Answer state</th>
                          <th>Rubric</th>
                          <th>Confidence</th>
                          <th>Lineage</th>
                          <th style={{ width: '20%' }}>Human-final</th>
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
                                <div className="caption quiet" style={{ marginTop: 4 }}>{r.rationale}</div>
                              </td>
                              <td>
                                <span className={`state-pill ${r.state}`}>
                                  <span className="dot" aria-hidden="true" />
                                  <Tag tone={STATE_TONE[r.state]}>{STATE_LABEL[r.state]}</Tag>
                                </span>
                              </td>
                              <td>
                                <span className="body-sm" style={{ fontVariantNumeric: 'tabular-nums' }}>{r.rubric}</span>
                              </td>
                              <td><ConfidenceBand level={r.band} /></td>
                              <td>
                                <EvidenceDrawer
                                  claim={r.question}
                                  confidence={r.band}
                                  evidence={r.evidence.map((text) => ({ text, when: 'this submission' }))}
                                  whySeeing={
                                    mustReview
                                      ? 'This response is middle or low confidence, so it must be confirmed by you before the mark can stand. The engine recommends; you decide.'
                                      : 'Two independent checks agreed, so this may stand provisionally — confirm it to finalise.'
                                  }
                                />
                              </td>
                              <td>
                                {d === 'pending' ? (
                                  mustReview ? (
                                    <div className="row" style={{ gap: 'var(--space-2)', flexWrap: 'wrap' }}>
                                      <Button variant="accent" size="sm" onClick={() => decide(r.id, 'confirmed')}>Confirm</Button>
                                      <Button variant="ghost" size="sm" onClick={() => decide(r.id, 'adjusted')}>Adjust</Button>
                                    </div>
                                  ) : (
                                    <div className="row" style={{ gap: 'var(--space-2)' }}>
                                      <span className="caption muted">Provisional</span>
                                      <Button variant="ghost" size="sm" onClick={() => decide(r.id, 'confirmed')}>Confirm</Button>
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
                  A mark is never final from a single low score, and handwriting or scan quality never
                  lowers a mark — illegible work is flagged for review, not penalised. The engine
                  recommends; you confirm.
                </p>
                <SourceNote source={source} />
              </section>

              <section>
                {returned ? (
                  <SpotlightCard hero>
                    <div className="row-between">
                      <div>
                        <p className="overline" style={{ margin: 0 }}>Marks published</p>
                        <p className="body-sm" style={{ marginTop: 'var(--space-2)' }}>
                          Feedback returned to {CURRENT_STUDENT.label}. They will see it on their next
                          visit, and these marks now feed mastery + gaps.
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
                      Publishing a mark is consequential, so it waits behind a confirmed review. Confirm
                      the flagged responses above and the approval gate opens.
                    </p>
                  </div>
                ) : (
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
          ) : null}

          {tab === 'assignments' ? (
            <>
              <Matrix columns={3} className="reveal reveal-1">
                <StatCell label="Assignments" value={allAssignments.length} delta="across the chapters" tone="flat" />
                <StatCell label="Open now" value={openCount} delta="in the submission window" tone="up" />
                <StatCell label="Projects" value={projectCount} delta="open the rubric to evaluate" tone="flat" />
              </Matrix>
              <section className="stack">
                <div className="sec-head">
                  <h3 className="h3" style={{ margin: 0 }}>Assignments by chapter</h3>
                  <span className="overline">submissions from plain counts</span>
                </div>
                <AssignmentBoard
                  data={viz.data.assignments}
                  source={viz.sourceByKind.assignments}
                  onOpen={(a) => { if (a.kind === 'project') { setTab('projects'); setOpenProject(a); } }}
                />
                <p className="caption quiet">
                  Completion is a band of who has submitted, not a mark. Opening a project raises its
                  rubric; opening a homework or quiz routes to the per-response review.
                </p>
              </section>
            </>
          ) : null}

          {tab === 'projects' ? (
            <>
              <Matrix columns={3} className="reveal reveal-1">
                <StatCell label="Projects" value={projectCount} delta="six-dimension rubric each" tone="flat" />
                <StatCell label="Submitted" value={viz.data.rubric.submissions.filter((s) => s.status === 'submitted').length} delta={`of ${viz.data.rubric.submissions.length}`} tone="up" />
                <StatCell label="In progress" value={viz.data.rubric.submissions.filter((s) => s.status === 'in-progress').length} delta="drafts saved, not yet in" tone="flat" />
              </Matrix>
              <section className="stack">
                <div className="sec-head">
                  <h3 className="h3" style={{ margin: 0 }}>Project rubric</h3>
                  <span className="overline">criteria × levels · teacher lens</span>
                </div>
                <ProjectRubric data={viz.data.rubric} source={viz.sourceByKind.rubric} />
                <p className="caption quiet">
                  The six dimensions are the teacher-only diagnostic lens — a level is a described
                  standard the work met, never a bare number, and never shown raw to a learner.
                </p>
              </section>
            </>
          ) : null}
        </>
      )}

      {/* Opening a project from the Assignments tab raises a focused tray with
          the project's standing before the full rubric below. */}
      <BottomSheet
        open={openProject !== null}
        onClose={() => setOpenProject(null)}
        eyebrow="Project"
        title={openProject?.title ?? 'Project'}
        description="This project is read against the six-dimension rubric — the criteria matrix is below, with submission tracking from plain counts."
        footer={
          <Button variant="accent" size="sm" onClick={() => setOpenProject(null)}>
            Review the rubric
          </Button>
        }
      >
        {openProject ? (
          <div className="row" style={{ gap: 'var(--space-3)', flexWrap: 'wrap' }}>
            <Tag tone="info">{openProject.published}</Tag>
            <Tag tone="neutral">{openProject.due}</Tag>
            <Tag tone={openProject.submitted === openProject.total ? 'success' : 'info'}>
              {openProject.submitted}/{openProject.total} submitted
            </Tag>
          </div>
        ) : null}
      </BottomSheet>
    </SurfaceShell>
  );
}
