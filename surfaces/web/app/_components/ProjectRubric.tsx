'use client';

import { useMemo } from 'react';
import { ConfidenceBand, Icon, Tag } from '@classess/design-system';
import { EvidenceDrawer } from './EvidenceDrawer';
import { SourceNote } from './SourceNote';
import type { ProjectRubric as ProjectRubricData, SubmissionRow, ReadSource } from '@/lib/vizData';

/* ============================================================================
   ProjectRubric — the six-dimension criteria × Level 1–4 grid + submission
   tracking. The v2 project rubric, carried into v3.

   The criteria matrix is the TEACHER-ONLY diagnostic lens (the six dimensions
   made explicit, the awarded level highlighted per row, the level descriptors
   readable as plain language — never a bare number). Submission tracking shows
   who has submitted with a calm status, and a % submitted from plain counts.

   v3 grammar: evidence-first (a ConfidenceBand + EvidenceDrawer behind the
   read), the subject's cool accent (never the signature, never coral), depth =
   hairline + tonal step only, NO shadow, reduced-motion safe. Pure + data-driven.
   ============================================================================ */

const LEVELS = [1, 2, 3, 4] as const;

const STATUS_META: Record<SubmissionRow['status'], { label: string; tone: 'success' | 'info' | 'warning'; icon: 'success' | 'clock' | 'minus' }> = {
  submitted: { label: 'Submitted', tone: 'success', icon: 'success' },
  'in-progress': { label: 'In progress', tone: 'info', icon: 'clock' },
  'not-submitted': { label: 'Not yet', tone: 'warning', icon: 'minus' },
};

export interface ProjectRubricProps {
  data: ProjectRubricData;
  source?: ReadSource;
}

export function ProjectRubric({ data, source = 'fallback' }: ProjectRubricProps) {
  const submittedCount = useMemo(
    () => data.submissions.filter((s) => s.status === 'submitted').length,
    [data.submissions],
  );
  const submittedPct =
    data.submissions.length > 0 ? Math.round((submittedCount / data.submissions.length) * 100) : 0;

  const subjectStyle = { ['--subject' as string]: `var(--${data.subject})` } as React.CSSProperties;

  return (
    <div
      className="stack viz-card subject-tinted"
      data-subject={data.subject}
      style={{ gap: 'var(--space-5)', ...subjectStyle }}
    >
      <div className="sec-head">
        <div>
          <p className="overline" style={{ margin: 0 }}>Project rubric · {data.classLabel}</p>
          <h4 className="h4" style={{ margin: '4px 0 0' }}>{data.title}</h4>
        </div>
        <ConfidenceBand level={data.confidence} />
      </div>

      {/* ── Criteria × Level 1–4 matrix ── */}
      <div className="rubric-scroll">
        <table className="rubric-table">
          <thead>
            <tr>
              <th scope="col" className="rubric-criterion-head">Criterion</th>
              {LEVELS.map((lvl) => (
                <th scope="col" key={lvl}>Level {lvl}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.criteria.map((crit) => (
              <tr key={crit.label}>
                <th scope="row" className="rubric-criterion">{crit.label}</th>
                {LEVELS.map((lvl) => {
                  const awarded = crit.awarded === lvl;
                  return (
                    <td
                      key={lvl}
                      className={`rubric-cell${awarded ? ' awarded' : ''}`}
                      aria-current={awarded ? 'true' : undefined}
                    >
                      <span className="rubric-cell-text">{crit.levels[lvl - 1]}</span>
                      {awarded ? (
                        <span className="rubric-awarded-mark" aria-label={`Awarded Level ${lvl}`}>
                          <Icon name="check" size="sm" />
                        </span>
                      ) : null}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Submission tracking ── */}
      <div className="stack" style={{ gap: 'var(--space-3)' }}>
        <div className="sec-head">
          <h5 className="h5" style={{ margin: 0 }}>Submissions</h5>
          <Tag tone={submittedPct === 100 ? 'success' : 'info'}>{submittedPct}% submitted</Tag>
        </div>
        <div className="progress" style={{ ['--bar' as string]: `var(--${data.subject})` } as React.CSSProperties}>
          <span style={{ width: `${submittedPct}%`, background: `var(--${data.subject})` }} />
        </div>
        <ul className="rubric-submissions">
          {data.submissions.map((row) => {
            const meta = STATUS_META[row.status];
            return (
              <li className="rubric-submission" key={row.label}>
                <Icon name={meta.icon} size="sm" />
                <span className="rubric-submission-label">{row.label}</span>
                <Tag tone={meta.tone}>{meta.label}</Tag>
                <span className="caption muted rubric-submission-when">{row.when}</span>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="row" style={{ gap: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap' }}>
        <EvidenceDrawer
          claim="How the rubric levels are read"
          confidence={data.confidence}
          evidence={[
            'Each criterion is judged against four plain-language level descriptors, not a number.',
            'The highlighted level is the one the work most clearly demonstrates, with the others left visible for context.',
            'The independence criterion is the keystone — how much was self-directed versus prompted.',
          ]}
          whySeeing="Showing the full level descriptors keeps the judgement explainable: a level is a described standard the work met, never an opaque mark."
        />
        <span className="caption quiet">{submittedCount} of {data.submissions.length} in</span>
      </div>

      <SourceNote source={source} />
    </div>
  );
}
