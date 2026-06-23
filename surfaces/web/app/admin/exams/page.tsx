'use client';

import { useState } from 'react';
import { Button, Icon, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { EvidenceDrawer } from '../../_components/EvidenceDrawer';
import { SCAN_ROWS } from '@/lib/examsData';

/**
 * d10 — Exam operations (admin). Scheduling, seating, secure-print packaging,
 * and OMR/scan intake. Every consequential step sits behind an Approval control
 * (permission ladder: prepare -> human approves -> execute). Scan intake is
 * human-final and NEVER penalises a student for scan quality — a poor scan is
 * flagged for a human, not marked wrong.
 */

type Stage = 'schedule' | 'seating' | 'print' | 'intake';

const STAGES: { id: Stage; label: string; icon: 'calendar' | 'grid' | 'send' | 'check' }[] = [
  { id: 'schedule', label: 'Schedule', icon: 'calendar' },
  { id: 'seating', label: 'Seating', icon: 'grid' },
  { id: 'print', label: 'Secure print', icon: 'send' },
  { id: 'intake', label: 'Scan intake', icon: 'check' },
];

export default function ExamsPage() {
  const [stage, setStage] = useState<Stage>('schedule');
  const [approved, setApproved] = useState<Record<Stage, boolean>>({
    schedule: false,
    seating: false,
    print: false,
    intake: false,
  });

  function approve(s: Stage) {
    setApproved((prev) => ({ ...prev, [s]: true }));
  }

  const stageMeta: Record<Stage, { title: string; prepared: string; consequence: string; cta: string }> = {
    schedule: {
      title: 'Exam timetable',
      prepared: 'A clash-free schedule across grades and halls is prepared, respecting the calendar and accommodations.',
      consequence: 'Publishing the schedule notifies staff and families. It waits for your approval.',
      cta: 'Approve and publish schedule',
    },
    seating: {
      title: 'Seating plan',
      prepared: 'A seating arrangement is prepared per hall, spacing students from the same section.',
      consequence: 'Approving locks the plan for printing on hall lists. Nothing prints until you approve.',
      cta: 'Approve seating plan',
    },
    print: {
      title: 'Secure-print package',
      prepared: 'Papers are packaged for secure printing — sealed counts per hall, with a chain-of-custody label.',
      consequence: 'Approving releases the package to the secure printer. This is the most sensitive step.',
      cta: 'Approve and release to print',
    },
    intake: {
      title: 'OMR and scan intake',
      prepared: 'Scanned sheets are read and matched. Low-quality scans are flagged for a human, never marked wrong.',
      consequence: 'Confirming intake sends clean reads to the gradebook; flagged sheets wait for a human read.',
      cta: 'Confirm clean reads',
    },
  };

  const meta = stageMeta[stage];

  return (
    <SurfaceShell
      eyebrow="Examination"
      title="Exam operations"
      dockIntro="I prepare each step — schedule, seating, secure print, scan intake — and hold it at the approval gate. Nothing publishes, prints, or grades on its own. A poor scan is flagged for a human, never penalised."
      dockChips={['Prepare the timetable', 'Why is this sheet flagged', 'Package for secure print']}
    >
      <section className="stack">
        <div className="ladder" role="group" aria-label="Exam stage" style={{ maxWidth: 520 }}>
          {STAGES.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`ladder-rung${stage === s.id ? ' active' : ''}`}
              onClick={() => setStage(s.id)}
            >
              {s.label}
            </button>
          ))}
        </div>
      </section>

      <section>
        <SpotlightCard padLg>
          <div className="row-between" style={{ alignItems: 'flex-start' }}>
            <div>
              <p className="overline" style={{ margin: 0 }}>
                The approval control
              </p>
              <h3 className="body-lg" style={{ margin: '4px 0 0' }}>
                {meta.title}
              </h3>
            </div>
            <Tag tone={approved[stage] ? 'success' : 'info'}>
              {approved[stage] ? 'Approved' : 'Prepared — awaiting approval'}
            </Tag>
          </div>

          <p className="body-sm muted" style={{ marginTop: 'var(--space-3)', maxWidth: 600 }}>
            {meta.prepared}
          </p>

          {stage === 'seating' ? (
            <div className="cols-2" style={{ marginTop: 'var(--space-3)' }}>
              {['Hall 1', 'Hall 2'].map((h) => (
                <div key={h} className="cell" style={{ textAlign: 'left' }}>
                  <div className="row-between">
                    <span className="body-sm">{h}</span>
                    <Tag tone="neutral">30 seats</Tag>
                  </div>
                  <p className="caption muted" style={{ marginTop: 4 }}>
                    Sections interleaved; aisle gaps preserved.
                  </p>
                </div>
              ))}
            </div>
          ) : null}

          {stage === 'intake' ? (
            <div className="stack" style={{ gap: 'var(--space-2)', marginTop: 'var(--space-3)' }}>
              {SCAN_ROWS.map((row) => (
                <div key={row.id} className="cell" style={{ textAlign: 'left' }}>
                  <div className="row-between">
                    <span className="body-sm">{row.label}</span>
                    <Tag tone={row.state === 'read' ? 'success' : 'warning'}>
                      {row.state === 'read' ? 'Read cleanly' : 'Needs a human read'}
                    </Tag>
                  </div>
                  <p className="caption muted" style={{ marginTop: 4 }}>
                    {row.quality === 'low'
                      ? 'Scan quality is low. Sent to a person to read — the student is never penalised for a faint scan.'
                      : 'High-confidence read, ready for the gradebook on your confirm.'}
                  </p>
                </div>
              ))}
            </div>
          ) : null}

          <EvidenceDrawer
            evidence={[
              'Every step is prepared deterministically and held at the approval gate; agents hold no credentials.',
              'Scan intake is human-final: a low-quality scan is routed to a person, never auto-marked wrong.',
            ]}
            whySeeing={meta.consequence}
          />

          <div className="divider" />
          {approved[stage] ? (
            <div className="rec-actions">
              <span className="body-sm">
                {stage === 'intake'
                  ? 'Clean reads sent to the gradebook. Flagged sheets are waiting for a human read.'
                  : `${meta.title} approved. The downstream steps stay gated behind their own approvals.`}
              </span>
              <Button variant="ghost" size="sm" onClick={() => setApproved((p) => ({ ...p, [stage]: false }))}>
                Reopen
              </Button>
            </div>
          ) : (
            <div className="rec-actions">
              <Button variant="accent" size="sm" onClick={() => approve(stage)}>
                {meta.cta}
              </Button>
              <span className="caption muted">
                Nothing happens until you approve. You hold the authority at every gate.
              </span>
            </div>
          )}
        </SpotlightCard>
      </section>
    </SurfaceShell>
  );
}
