'use client';

import { useMemo, useState } from 'react';
import { ConfidenceBand, Icon, Tag } from '@classess/design-system';
import { EvidenceDrawer } from './EvidenceDrawer';
import { SourceNote } from './SourceNote';
import { ApprovalControl } from './ApprovalControl';
import type { PaperPreview, PaperQuestion, ReadSource } from '@/lib/vizData';

/* ============================================================================
   QuestionPaperPreview — the v2 paper preview + answer-key render, in v3.

   The prepared paper laid out as a DOCUMENT: a paper header (title, class,
   duration, total marks), section headings with their instruction line, and
   numbered questions — MCQ / assertion-reasoning options (A–D), short and long
   prompts — each with its point value. A Paper / Answer-key toggle reveals the
   MODEL ANSWERS (the teacher's key), which are never shown to a learner.

   v3 grammar: the paper is PREPARED and waits behind the approval ladder; it
   never auto-publishes. Section + question marks describe the paper's
   structure, never a child's score. Subjects on the cool accent palette (never
   the ultramarine signature, never coral), depth = hairline + tonal step, NO
   shadow, reduced-motion safe. Pure + data-driven.
   ============================================================================ */

const OPTION_LETTERS = ['A', 'B', 'C', 'D', 'E', 'F'];

const TYPE_LABEL: Record<PaperQuestion['type'], string> = {
  mcq: 'MCQ',
  short: 'Short answer',
  long: 'Long answer',
  'assertion-reasoning': 'Assertion-Reasoning',
};

export interface QuestionPaperPreviewProps {
  data: PaperPreview;
  source?: ReadSource;
  /** Approve the prepared paper (permission ladder) — host owns the state. */
  onApprove?: () => void;
}

type View = 'paper' | 'key';

export function QuestionPaperPreview({ data, source = 'fallback', onApprove }: QuestionPaperPreviewProps) {
  const [view, setView] = useState<View>('paper');

  const totals = useMemo(() => {
    let marks = 0;
    let questions = 0;
    for (const sec of data.sections)
      for (const q of sec.questions) {
        marks += q.marks;
        questions += 1;
      }
    return { marks, questions };
  }, [data.sections]);

  return (
    <div className="stack viz-card" style={{ gap: 'var(--space-5)' }}>
      <div className="sec-head">
        <div>
          <p className="overline" style={{ margin: 0 }}>{data.kind} · {data.classLabel}</p>
          <h4 className="h4" style={{ margin: '4px 0 0' }}>{data.title}</h4>
        </div>
        <ConfidenceBand level={data.confidence} />
      </div>

      {/* ── Paper / Answer-key toggle ── */}
      <div className="row-between" style={{ flexWrap: 'wrap', gap: 'var(--space-3)' }}>
        <div className="segmented" role="tablist" aria-label="Paper view">
          <button type="button" role="tab" aria-selected={view === 'paper'} className={view === 'paper' ? 'active' : ''} onClick={() => setView('paper')}>
            Question paper
          </button>
          <button type="button" role="tab" aria-selected={view === 'key'} className={view === 'key' ? 'active' : ''} onClick={() => setView('key')}>
            Answer key
          </button>
        </div>
        <div className="row" style={{ gap: 'var(--space-4)', flexWrap: 'wrap' }}>
          <span className="caption muted"><strong style={{ color: 'var(--text-primary)' }}>{totals.marks}</strong> marks</span>
          <span className="caption muted"><strong style={{ color: 'var(--text-primary)' }}>{totals.questions}</strong> questions</span>
          <span className="caption muted"><strong style={{ color: 'var(--text-primary)' }}>{data.duration}</strong></span>
        </div>
      </div>

      {/* ── The rendered paper document ── */}
      <article className="paper-doc" aria-label={view === 'key' ? 'Answer key' : 'Question paper'}>
        <header className="paper-doc-head">
          <h3 className="paper-doc-title">{data.title}</h3>
          <p className="paper-doc-meta">
            {data.classLabel} · {data.kind} · Time: {data.duration} · Maximum marks: {totals.marks}
          </p>
          {view === 'key' ? (
            <Tag tone="info">Answer key — teacher only, never shown to a learner</Tag>
          ) : null}
        </header>

        {data.sections.map((section) => {
          const sectionMarks = section.questions.reduce((s, q) => s + q.marks, 0);
          return (
            <section className="paper-doc-section subject-tinted" data-subject={section.subject} key={section.label}>
              <div className="paper-doc-section-head">
                <span className="subject-dot" style={{ background: `var(--${section.subject})` }} aria-hidden="true" />
                <h4 className="paper-doc-section-title">{section.label}</h4>
                <span className="caption muted">{sectionMarks} marks</span>
              </div>
              <p className="paper-doc-instruction">{section.instruction}</p>

              <ol className="paper-doc-questions">
                {section.questions.map((q) => (
                  <li className="paper-doc-question" key={q.number}>
                    <div className="paper-doc-q-head">
                      <span className="paper-doc-q-num">{q.number}.</span>
                      <span className="paper-doc-q-prompt">{q.prompt}</span>
                      <span className="paper-doc-q-marks">[{q.marks}]</span>
                    </div>
                    <span className="paper-doc-q-type overline">{TYPE_LABEL[q.type]}</span>

                    {q.options && q.options.length > 0 ? (
                      <ol className="paper-doc-options">
                        {q.options.map((opt, i) => (
                          <li className="paper-doc-option" key={i}>
                            <span className="paper-doc-option-letter">{OPTION_LETTERS[i]}</span>
                            <span>{opt}</span>
                          </li>
                        ))}
                      </ol>
                    ) : view === 'paper' ? (
                      <div className="paper-doc-answer-space" aria-hidden="true" />
                    ) : null}

                    {view === 'key' ? (
                      <div className="paper-doc-model">
                        <span className="overline">Model answer</span>
                        <p className="body-sm" style={{ margin: '4px 0 0' }}>{q.modelAnswer}</p>
                      </div>
                    ) : null}
                  </li>
                ))}
              </ol>
            </section>
          );
        })}
      </article>

      <div className="row" style={{ gap: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap' }}>
        <EvidenceDrawer
          claim="How the paper and its key are prepared"
          confidence={data.confidence}
          evidence={[
            'Every question is generated against the unit outcomes and passes the confidence gate before it can be shown.',
            'The answer key is the teacher-facing model answer — it is never rendered to a learner.',
            'Marks describe the paper structure; they are never a learner score.',
          ]}
          whySeeing="Previewing the paper and its key keeps the assessment auditable — you can read exactly what is asked, and how it is marked, before approving it."
        />
        <span className="caption quiet">Section-headed paper · model answers in the key</span>
      </div>

      {data.approved ? (
        <Tag tone="success">Approved for use</Tag>
      ) : (
        <ApprovalControl
          kind="Question paper · the permission ladder"
          summary={`Approve the ${data.title} for ${data.classLabel}`}
          consequence="The prepared paper and its answer key become available to set for the class. Until you approve, it is a draft only — nothing is published to learners."
          eventType="plan.submitted"
          approveLabel="Approve the paper"
          payload={{ surface: 'teacher.paperpreview', title: data.title, marks: totals.marks }}
          evidence={[
            'Each question was generated against the unit outcomes and passed the confidence gate before it was shown.',
            'The full paper and answer key are visible above, so the assessment is auditable before approval.',
          ]}
          whySeeing="Publishing a paper is consequential, so it is prepared and waits for your explicit approval."
          onApprove={onApprove}
        />
      )}

      <SourceNote source={source} />
    </div>
  );
}
