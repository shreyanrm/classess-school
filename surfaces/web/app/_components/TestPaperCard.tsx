'use client';

import { useMemo } from 'react';
import { ConfidenceBand, Tag } from '@classess/design-system';
import { EvidenceDrawer } from './EvidenceDrawer';
import { SourceNote } from './SourceNote';
import { ApprovalControl } from './ApprovalControl';
import type { TestPaper, ReadSource } from '@/lib/vizData';

/* ============================================================================
   TestPaperCard — the v2 Test-Papers detail, in v3.

   A prepared question paper read as its SECTION-WISE mark distribution: per
   section a question type (MCQ / Assertion-Reasoning / Short / Long), a count,
   marks-each, and the section total — plus the paper total, computed from the
   visible parts. The paper is PREPARED and waits behind the approval ladder; it
   is never auto-published. Section marks are a structure, never a learner score.

   v3 grammar: subjects on the cool accent palette (never coral), depth =
   hairline + tonal step, NO shadow, reduced-motion safe. Pure + data-driven.
   ============================================================================ */

export interface TestPaperCardProps {
  data: TestPaper;
  source?: ReadSource;
  /** Approve the prepared paper (permission ladder) — host owns the state. */
  onApprove?: () => void;
}

export function TestPaperCard({ data, source = 'fallback', onApprove }: TestPaperCardProps) {
  const sectionTotals = useMemo(
    () => data.sections.map((s) => s.questions * s.marksEach),
    [data.sections],
  );
  const total = sectionTotals.reduce((a, b) => a + b, 0);
  const totalQuestions = data.sections.reduce((s, sec) => s + sec.questions, 0);

  return (
    <div className="stack viz-card" style={{ gap: 'var(--space-5)' }}>
      <div className="sec-head">
        <div>
          <p className="overline" style={{ margin: 0 }}>{data.kind} · {data.classLabel}</p>
          <h4 className="h4" style={{ margin: '4px 0 0' }}>{data.title}</h4>
        </div>
        <ConfidenceBand level={data.confidence} />
      </div>

      <div className="row" style={{ gap: 'var(--space-4)', flexWrap: 'wrap' }}>
        <span className="caption muted"><strong style={{ color: 'var(--text-primary)' }}>{total}</strong> marks total</span>
        <span className="caption muted"><strong style={{ color: 'var(--text-primary)' }}>{totalQuestions}</strong> questions</span>
        <span className="caption muted"><strong style={{ color: 'var(--text-primary)' }}>{data.sections.length}</strong> sections</span>
      </div>

      {/* ── Section-wise mark distribution ── */}
      <div className="table-scroll">
        <table className="paper-sections-table">
          <thead>
            <tr>
              <th scope="col">Section</th>
              <th scope="col">Question type</th>
              <th scope="col" className="num">Questions</th>
              <th scope="col" className="num">Marks each</th>
              <th scope="col" className="num">Section marks</th>
            </tr>
          </thead>
          <tbody>
            {data.sections.map((s, i) => (
              <tr key={s.label}>
                <th scope="row">
                  <span className="row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
                    <span className="subject-dot" style={{ background: `var(--${s.subject})` }} aria-hidden="true" />
                    {s.label}
                  </span>
                </th>
                <td>{s.questionType}</td>
                <td className="num"><span className="data">{s.questions}</span></td>
                <td className="num"><span className="data">{s.marksEach}</span></td>
                <td className="num"><span className="data">{sectionTotals[i]}</span></td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" colSpan={4}>Total</th>
              <td className="num"><span className="data" style={{ fontWeight: 600 }}>{total}</span></td>
            </tr>
          </tfoot>
        </table>
      </div>

      {/* ── Mark-weight bar (a calm cool ramp of section weight) ── */}
      <div className="paper-weight-bar" role="img" aria-label="Mark weight by section">
        {data.sections.map((s, i) => (
          <span
            key={s.label}
            className="paper-weight-seg"
            style={{ width: `${(sectionTotals[i]! / (total || 1)) * 100}%`, background: `var(--${s.subject})` }}
            title={`${s.label}: ${sectionTotals[i]} marks`}
          />
        ))}
      </div>

      <div className="row" style={{ gap: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap' }}>
        <EvidenceDrawer
          claim="How the paper is structured"
          confidence={data.confidence}
          evidence={[
            'Each section is a question type with a count and marks-each, so the weight is visible — not buried in a single total.',
            'The paper is generated against the unit outcomes and verified before it can reach a class.',
            'Section marks describe the paper; they are never shown to a learner as a score.',
          ]}
          whySeeing="Showing the section-wise distribution keeps the paper auditable — you can see exactly where the marks sit before approving it."
        />
        <span className="caption quiet">Preview · Answer key prepared with the paper</span>
      </div>

      {data.approved ? (
        <Tag tone="success">Approved for use</Tag>
      ) : (
        <ApprovalControl
          kind="Test paper · the permission ladder"
          summary={`Approve the ${data.title} for ${data.classLabel}`}
          consequence="The prepared paper (and its answer key) become available to set for the class. Until you approve, it is a draft only — nothing is published."
          eventType="plan.submitted"
          approveLabel="Approve the paper"
          payload={{ surface: 'teacher.testpaper', title: data.title, total }}
          evidence={[
            'The paper was generated against the unit outcomes and passed the confidence gate before it was shown.',
            'Section-wise marks are visible above, so the weighting is auditable before approval.',
          ]}
          whySeeing="Publishing a paper is consequential, so it is prepared and waits for your explicit approval."
          onApprove={onApprove}
        />
      )}

      <SourceNote source={source} />
    </div>
  );
}
