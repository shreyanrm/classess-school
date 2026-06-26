'use client';

/* ============================================================================
   MockSession — the full mock-TAKING experience. A real, sectioned board-shaped
   paper a student can sit end to end: Section A objective, Section B short
   answer, per-question marks, a paper total, a duration, a live countdown timer,
   a question navigator, prev/next movement, and submit → a plain-language read.

   v3 GRAMMAR honoured:
     · The paper's TOTAL / DURATION / per-Q MARKS are facts about the exam, so
       they are shown plainly — these are not a judgement of the student.
     · The RESULT is evidence-first: a plain band + one next focus, NEVER a raw
       score or a percentage. Short answers are not machine-graded (no auto-
       judgement of free reasoning) — the student reflects against a model.
     · Hairline + tonal + frost, NEVER a shadow. One accent (the surface hue).
     · Reduced-motion honoured (the timer never animates; reveals use the shared
       reveal utility which snaps under reduced-motion).
   ============================================================================ */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { Button, Icon, Tag, Textarea } from '@classess/design-system';
import { SourceNote } from './SourceNote';
import { EvidenceDrawer } from './EvidenceDrawer';
import {
  paperForBlueprint,
  paperQuestions,
  paperTotalMarks,
  readSitting,
  type MockPaper,
  type MockQuestion,
  type Responses,
} from '@/lib/mockSession';

/* ── The countdown timer ────────────────────────────────────────────────────
   A plain MM:SS countdown. It does NOT auto-submit and does NOT shame — when it
   reaches zero it simply notes that the exam window has closed; the student
   stays in control of when to submit (the permission ladder, even here). */
function useCountdown(minutes: number, running: boolean) {
  const [secondsLeft, setSecondsLeft] = useState(minutes * 60);
  useEffect(() => {
    if (!running || secondsLeft <= 0) return;
    const id = window.setInterval(() => {
      setSecondsLeft((s) => (s <= 1 ? 0 : s - 1));
    }, 1000);
    return () => window.clearInterval(id);
  }, [running, secondsLeft]);
  const reset = useCallback(() => setSecondsLeft(minutes * 60), [minutes]);
  return { secondsLeft, reset };
}

function fmt(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export interface MockSessionProps {
  blueprintId: string;
  /** Closes the session (returns the catalogue to view). */
  onExit: () => void;
}

type Stage = 'sitting' | 'result';

export function MockSession({ blueprintId, onExit }: MockSessionProps) {
  const paper: MockPaper = useMemo(() => paperForBlueprint(blueprintId), [blueprintId]);
  const questions = useMemo(() => paperQuestions(paper), [paper]);
  const total = useMemo(() => paperTotalMarks(paper), [paper]);

  const [responses, setResponses] = useState<Responses>({});
  const [current, setCurrent] = useState(0);
  const [stage, setStage] = useState<Stage>('sitting');
  const { secondsLeft, reset } = useCountdown(paper.durationMinutes, stage === 'sitting');
  const liveRef = useRef<HTMLDivElement>(null);

  const q = questions[Math.min(current, questions.length - 1)]!;
  const answeredCount = questions.filter((item) => {
    const v = responses[item.id];
    return item.kind === 'mcq' ? typeof v === 'number' : typeof v === 'string' && v.trim().length > 0;
  }).length;

  const reading = useMemo(
    () => (stage === 'result' ? readSitting(paper, responses) : null),
    [stage, paper, responses],
  );

  function setMcq(id: string, index: number) {
    setResponses((prev) => ({ ...prev, [id]: index }));
  }
  function setShort(id: string, text: string) {
    setResponses((prev) => ({ ...prev, [id]: text }));
  }

  function submit() {
    setStage('result');
    // Move keyboard focus to the result so a screen reader announces it.
    requestAnimationFrame(() => liveRef.current?.focus());
  }

  function retake() {
    setResponses({});
    setCurrent(0);
    setStage('sitting');
    reset();
  }

  const timeUp = secondsLeft <= 0;

  /* ── Result ─────────────────────────────────────────────────────────────── */
  if (stage === 'result' && reading) {
    return (
      <section className="reveal reveal-2" aria-label="Your sitting, reviewed">
        <div
          className="next-step-hero"
          tabIndex={-1}
          ref={liveRef}
          aria-live="polite"
          style={{ padding: 'var(--space-6)' }}
        >
          <div className="row-between" style={{ alignItems: 'flex-start' }}>
            <div>
              <p className="overline" style={{ margin: 0 }}>
                {paper.subject} mock · reviewed
              </p>
              <h3 className="display-sm" style={{ margin: '6px 0 0', fontSize: 26 }}>
                {reading.headline}
              </h3>
            </div>
            <Tag tone={reading.band === 'strong' ? 'success' : reading.band === 'steady' ? 'info' : 'neutral'}>
              {reading.band === 'strong' ? 'Strong' : reading.band === 'steady' ? 'Steady' : 'Building'}
            </Tag>
          </div>

          <p className="body-sm muted" style={{ marginTop: 'var(--space-4)', maxWidth: 560 }}>
            {reading.read}
          </p>

          <div className="why-grid" style={{ marginTop: 'var(--space-5)' }}>
            <div>
              <div className="k">You worked through</div>
              <div className="v">
                {reading.attempted} of {reading.total} questions
              </div>
            </div>
            <div>
              <div className="k">This was a</div>
              <div className="v">Practice sitting — it feeds your readiness, never a record</div>
            </div>
            <div>
              <div className="k">Worth a look next</div>
              <div className="v">{reading.nextFocusTopic ?? 'Nothing stands out — keep the rhythm'}</div>
            </div>
          </div>

          <div className="rec-actions" style={{ marginTop: 'var(--space-5)' }}>
            {reading.nextFocusTopicId ? (
              <Link href="/student/practice" className="btn btn-accent btn-sm">
                Practise {reading.nextFocusTopic}
                <Icon name="arrow-right" size="sm" />
              </Link>
            ) : null}
            <Button variant="secondary" size="sm" onClick={retake}>
              Sit it again
            </Button>
            <Button variant="ghost" size="sm" onClick={onExit}>
              Back to mocks
            </Button>
          </div>
        </div>

        <div className="stack" style={{ marginTop: 'var(--space-5)' }}>
          <div className="sec-head">
            <h3 className="h3">Question by question</h3>
            <span className="overline">what to learn from it</span>
          </div>
          <p className="caption quiet" style={{ maxWidth: 560 }}>
            A &ldquo;next focus&rdquo; is named, not a failing — it is where a little practice goes furthest.
            Short answers are not machine-marked: compare yours to the model and judge it yourself.
          </p>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: 44 }}>§</th>
                  <th>Question</th>
                  <th>Topic</th>
                  <th>How it went</th>
                  <th>Model answer</th>
                </tr>
              </thead>
              <tbody>
                {reading.review.map((r) => (
                  <tr key={r.id}>
                    <td className="num muted">{r.section}</td>
                    <td>{r.prompt}</td>
                    <td className="muted">{r.topic}</td>
                    <td>
                      <Tag
                        tone={
                          r.outcome === 'right'
                            ? 'success'
                            : r.outcome === 'close'
                              ? 'info'
                              : r.outcome === 'skipped'
                                ? 'neutral'
                                : 'warning'
                        }
                      >
                        <span className="dot" />
                        {r.outcome === 'right'
                          ? 'Got it'
                          : r.outcome === 'close'
                            ? 'Reflect'
                            : r.outcome === 'skipped'
                              ? 'Left blank'
                              : 'Next focus'}
                      </Tag>
                    </td>
                    <td className="muted">{r.model}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <EvidenceDrawer
            evidence={[
              'The objective section is read directly from your selections; the short answers are not machine-graded — you reflect against the model.',
              'The plain band is read from the objective portion, tempered by how much you worked through — it is never surfaced as a mark or a percentage.',
              'A next focus is the topic carrying the most missed weight on this paper, named so a short practice closes it.',
            ]}
            whySeeing="A mock is practice. The read tells you where a little work goes furthest — it is never a record held against you."
          />
          <SourceNote source="fallback" />
        </div>
      </section>
    );
  }

  /* ── Sitting ────────────────────────────────────────────────────────────── */
  return (
    <section className="mock-session" aria-label={`${paper.subject} mock in progress`}>
      {/* The paper header — total, duration, the live timer. */}
      <div className="mock-bar">
        <div className="mock-bar-facts">
          <span className="overline">{paper.subject} mock</span>
          <span className="mock-fact">
            <b>{total}</b> marks
          </span>
          <span className="mock-fact">
            <b>{paper.durationMinutes}</b> min
          </span>
          <span className="mock-fact">
            <b>{answeredCount}</b>/{questions.length} answered
          </span>
        </div>
        <div className={`mock-timer${timeUp ? ' up' : ''}`} role="timer" aria-live="off">
          <Icon name="clock" size="sm" />
          <span className="mono">{fmt(secondsLeft)}</span>
          <span className="caption muted">{timeUp ? 'window closed — finish when ready' : 'time left'}</span>
        </div>
      </div>

      <div className="mock-cols">
        {/* The question navigator — section-grouped, with each section's letter,
            mark total, and per-question marks made plain (the sectioned-paper
            shape a real board paper carries). */}
        <nav className="mock-nav" aria-label="Question navigator">
          {paper.sections.map((section) => {
            const sectionMarks = section.questions.reduce((sum, q) => sum + q.marks, 0);
            return (
              <div key={section.id} className="mock-nav-section">
                <div className="mock-nav-head">
                  <span className="mock-nav-letter" aria-hidden="true">
                    {section.letter}
                  </span>
                  <div className="mock-nav-head-text">
                    <p className="overline" style={{ margin: 0 }}>
                      {section.title}
                    </p>
                    <p className="mock-nav-marks">
                      {section.questions.length} Q · <b>{sectionMarks}</b> marks
                    </p>
                  </div>
                </div>
                <p className="caption quiet mock-nav-instruction">{section.instruction}</p>
                <div className="mock-nav-grid">
                  {section.questions.map((item) => {
                    const idx = questions.findIndex((x) => x.id === item.id);
                    const answered =
                      item.kind === 'mcq'
                        ? typeof responses[item.id] === 'number'
                        : typeof responses[item.id] === 'string' &&
                          (responses[item.id] as string).trim().length > 0;
                    return (
                      <button
                        key={item.id}
                        type="button"
                        className={`mock-nav-cell${idx === current ? ' current' : ''}${answered ? ' answered' : ''}`}
                        onClick={() => setCurrent(idx)}
                        aria-current={idx === current ? 'true' : undefined}
                        aria-label={`Question ${idx + 1}, ${item.marks} mark${item.marks === 1 ? '' : 's'}${answered ? ', answered' : ''}`}
                      >
                        <span className="mock-nav-cell-n">{idx + 1}</span>
                        <span className="mock-nav-cell-m" aria-hidden="true">
                          {item.marks}m
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
          <p className="caption quiet" style={{ marginTop: 'var(--space-3)' }}>
            Each square shows its marks; a filled square is answered. Move freely — nothing is locked.
          </p>
        </nav>

        {/* The active question. */}
        <div className="mock-main">
          <QuestionCard
            q={q}
            index={current}
            count={questions.length}
            sectionTitle={sectionTitleFor(paper, q.id)}
            value={responses[q.id]}
            onMcq={(i) => setMcq(q.id, i)}
            onShort={(t) => setShort(q.id, t)}
          />

          <div className="mock-controls">
            <Button
              variant="secondary"
              size="sm"
              disabled={current === 0}
              onClick={() => setCurrent((c) => Math.max(0, c - 1))}
            >
              Previous
            </Button>
            {current < questions.length - 1 ? (
              <Button variant="primary" size="sm" onClick={() => setCurrent((c) => c + 1)}>
                Next
                <Icon name="arrow-right" size="sm" />
              </Button>
            ) : (
              <Button variant="accent" size="sm" onClick={submit}>
                <Icon name="check" size="sm" />
                Submit the paper
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={onExit}>
              Pause and leave
            </Button>
            {answeredCount < questions.length ? (
              <span className="caption muted">
                {questions.length - answeredCount} unanswered — that is fine, submit when you are ready.
              </span>
            ) : (
              <span className="caption muted">All answered. Review with the navigator, then submit.</span>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function sectionTitleFor(paper: MockPaper, questionId: string): string {
  for (const s of paper.sections) {
    if (s.questions.some((q) => q.id === questionId)) return s.title;
  }
  return '';
}

/* ── One question — MCQ options or a short-answer textarea ──────────────────── */
function QuestionCard({
  q,
  index,
  count,
  sectionTitle,
  value,
  onMcq,
  onShort,
}: {
  q: MockQuestion;
  index: number;
  count: number;
  sectionTitle: string;
  value: number | string | undefined;
  onMcq: (i: number) => void;
  onShort: (t: string) => void;
}) {
  return (
    <article className="next-step-hero" style={{ padding: 'var(--space-6)' }}>
      <div className="row-between" style={{ alignItems: 'flex-start' }}>
        <p className="overline" style={{ margin: 0 }}>
          {sectionTitle} · Question {index + 1} of {count}
        </p>
        <Tag tone="info">
          {q.marks} mark{q.marks === 1 ? '' : 's'}
        </Tag>
      </div>

      <h3 className="body-lg" style={{ marginTop: 'var(--space-4)', fontWeight: 500 }}>
        {q.prompt}
      </h3>

      {q.kind === 'mcq' ? (
        <div className="mock-options" role="radiogroup" aria-label="Answer options" style={{ marginTop: 'var(--space-4)' }}>
          {q.options.map((opt, i) => {
            const selected = value === i;
            return (
              <button
                key={i}
                type="button"
                role="radio"
                aria-checked={selected}
                className={`mock-option${selected ? ' selected' : ''}`}
                onClick={() => onMcq(i)}
              >
                <span className="mock-option-key" aria-hidden="true">
                  {String.fromCharCode(65 + i)}
                </span>
                <span>{opt}</span>
              </button>
            );
          })}
        </div>
      ) : (
        <div style={{ marginTop: 'var(--space-4)' }}>
          <Textarea
            value={typeof value === 'string' ? value : ''}
            onChange={(e) => onShort(e.target.value)}
            placeholder="Write your answer and working here"
            rows={6}
            aria-label="Your short answer"
          />
          <p className="caption quiet" style={{ marginTop: 'var(--space-2)' }}>
            Show your working — the review compares this to a model answer for you to reflect on, not to mark.
          </p>
        </div>
      )}
    </article>
  );
}
