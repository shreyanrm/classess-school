'use client';

import { useMemo, useState } from 'react';
import { Icon, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ChildSwitcher } from '../../_components/ChildSwitcher';
import { ConsentGated } from '../../_components/ConsentGated';
import {
  DEFAULT_CHILD_ID,
  findChild,
  selectChildData,
  type ParentReport,
} from '@/lib/parentData';

/**
 * Assignments, exams and reports — with parent-specific feedback, celebration
 * points and next steps. Everything is written in the parent's language, never
 * a raw mark or formula. Reports are published by a human (consequential actions
 * never auto-fire); the parent reads what the school has chosen to share.
 */
export default function ParentReportsPage() {
  const [childId, setChildId] = useState(DEFAULT_CHILD_ID);
  const child = findChild(childId);
  const data = useMemo(() => selectChildData(childId), [childId]);

  return (
    <SurfaceShell
      eyebrow={child ? child.section : 'Reports'}
      title={child ? `${child.label}'s reports and feedback` : 'Reports and feedback'}
      dockIntro="Ask what a report means in plain language, or how to act on a next step at home."
      dockChips={['What does this mean', 'What should we do next', 'Show the celebration points']}
    >
      <section className="stack">
        <p className="overline">Whose reports</p>
        <ChildSwitcher selectedId={childId} onSelect={setChildId} />
      </section>

      {!child || !data ? (
        <ConsentGated label={child?.label} />
      ) : data.reports.length === 0 ? (
        <section className="stack">
          <div className="empty">
            <Icon name="book" size="lg" className="glyph" />
            <h4 className="body">No reports shared yet</h4>
            <p>
              When the school shares an assignment, exam or report for {child.label}, it will appear
              here with feedback you can act on.
            </p>
          </div>
        </section>
      ) : (
        <>
          <section className="stack">
            <p className="overline">Shared with you</p>
            <p className="caption quiet">
              Each report is written for you, in plain language. No raw marks — just what is going
              well and the one next step that helps.
            </p>
            {data.reports.map((r) => (
              <ReportCard key={r.id} report={r} />
            ))}
          </section>

          <p className="caption quiet row" style={{ gap: 'var(--space-2)' }}>
            <Icon name="info" size="sm" />
            Reports are released to you by a teacher — never automatically. You see only what the
            school has chosen to share.
          </p>
        </>
      )}
    </SurfaceShell>
  );
}

function ReportCard({ report }: { report: ParentReport }) {
  return (
    <SpotlightCard padLg>
      <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-4)' }}>
        <h3 className="body-lg" style={{ margin: 0 }}>
          {report.title}
        </h3>
        <span className="caption muted">{report.shared}</span>
      </div>

      <p className="body-sm" style={{ marginTop: 'var(--space-3)' }}>
        {report.feedback}
      </p>

      <div className="parent-report-points">
        <div className="parent-report-point">
          <Tag tone="success">Celebrate</Tag>
          <p className="body-sm" style={{ margin: 0 }}>
            {report.celebration}
          </p>
        </div>
        <div className="parent-report-point">
          <Tag tone="info">Next step</Tag>
          <p className="body-sm" style={{ margin: 0 }}>
            {report.nextStep}
          </p>
        </div>
      </div>

      <p className="caption muted" style={{ marginTop: 'var(--space-4)' }}>
        Shared by {report.publishedBy}
      </p>
    </SpotlightCard>
  );
}
