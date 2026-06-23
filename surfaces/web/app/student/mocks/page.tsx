'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { Button, Icon, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { EvidenceDrawer } from '../../_components/EvidenceDrawer';
import { MOCK_BLUEPRINTS, type MockBlueprint } from '@/lib/mocksData';
import { studentRevisionPlan } from '@/lib/loopData';

/**
 * d13 — Revision planner, mock tests and exam readiness (student-facing).
 * Blueprint-aligned mocks that mirror the real format, plus a spaced-revision
 * schedule that surfaces a topic when memory is genuinely fading — accurate,
 * never guilt-based. Plain language only: a learner never sees a raw score.
 *
 * Starting a mock is the student's choice; nothing begins on its own.
 */

type Tab = 'mocks' | 'plan';

const WEIGHT_TONE = { light: 'neutral', core: 'info', heavy: 'warning' } as const;

export default function MocksPage() {
  const [tab, setTab] = useState<Tab>('mocks');
  const [started, setStarted] = useState<string | null>(null);
  // Blueprints are static demo data (single source in lib/); the revision plan
  // is DERIVED live from the engine over the seed events — same layer Vidya and
  // /student/progress read, so a topic surfaces only when revision is truly due.
  const mocks: MockBlueprint[] = MOCK_BLUEPRINTS;
  const revision = useMemo(() => studentRevisionPlan(), []);

  return (
    <SurfaceShell
      eyebrow="Exam readiness"
      title="Mocks and study plan"
      dockIntro="Your mocks mirror the real paper, and your revision plan brings a topic back exactly when it is fading — never to nag, only to help it stick. You choose when to begin."
      dockChips={['What should I revise today', 'Start a maths mock', 'Am I ready for trigonometry']}
    >
      <section className="stack">
        <div className="ladder" role="group" aria-label="View" style={{ maxWidth: 360 }}>
          <button type="button" className={`ladder-rung${tab === 'mocks' ? ' active' : ''}`} onClick={() => setTab('mocks')}>
            Mock tests
          </button>
          <button type="button" className={`ladder-rung${tab === 'plan' ? ' active' : ''}`} onClick={() => setTab('plan')}>
            Revision plan
          </button>
        </div>
      </section>

      {tab === 'mocks' ? (
        <section className="stack">
          <p className="overline">Blueprint-aligned mocks</p>
          <p className="caption quiet">
            Each mock mirrors the real format and difficulty. Coverage shows where the weight sits —
            in plain words, never a marks formula.
          </p>
          <div className="stack" style={{ gap: 'var(--space-3)' }}>
            {mocks.map((m) => (
              <SpotlightCard key={m.id} padLg>
                <div className="row-between" style={{ alignItems: 'flex-start' }}>
                  <div>
                    <h3 className="body-lg" style={{ margin: 0 }}>
                      {m.subject} mock
                    </h3>
                    <p className="caption muted" style={{ marginTop: 4 }}>
                      {m.format}
                    </p>
                  </div>
                  <Tag tone={m.state === 'taken' ? 'success' : 'info'}>
                    {m.state === 'taken' ? 'Taken' : 'Ready'}
                  </Tag>
                </div>

                <div className="row" style={{ gap: 'var(--space-2)', flexWrap: 'wrap', marginTop: 'var(--space-3)' }}>
                  {m.coverage.map((c) => (
                    <Tag key={c.unit} tone={WEIGHT_TONE[c.weight]}>
                      {c.unit} · {c.weight}
                    </Tag>
                  ))}
                </div>

                <div className="divider" />
                {started === m.id ? (
                  <div className="rec-actions">
                    <span className="body-sm">
                      Mock in progress. Take your time — this is practice, and it feeds your readiness
                      read, not a record held against you.
                    </span>
                    <Button variant="ghost" size="sm" onClick={() => setStarted(null)}>
                      Pause
                    </Button>
                  </div>
                ) : (
                  <div className="rec-actions">
                    <Button variant="accent" size="sm" onClick={() => setStarted(m.id)}>
                      {m.state === 'taken' ? 'Retake this mock' : 'Begin the mock'}
                    </Button>
                    <span className="caption muted">Nothing starts until you choose to begin.</span>
                  </div>
                )}
              </SpotlightCard>
            ))}
          </div>
        </section>
      ) : (
        <section className="stack">
          <p className="overline">Spaced revision — what to touch, and when</p>
          <p className="caption quiet">
            A topic comes back exactly as memory starts to fade. This is here to help it stick, never
            to make you feel behind.
          </p>
          {revision.length === 0 ? (
            <SpotlightCard>
              <div className="empty">
                <Icon name="success" size="lg" className="glyph" />
                <h4 className="body">Nothing is fading right now</h4>
                <p>Everything you have earned is still fresh. A topic will appear here the moment it starts to fade.</p>
              </div>
            </SpotlightCard>
          ) : (
            <div className="stack" style={{ gap: 'var(--space-2)' }}>
              {revision.map((r) => (
                <SpotlightCard key={r.topicId}>
                  <div className="row-between" style={{ alignItems: 'flex-start' }}>
                    <div>
                      <div className="row" style={{ gap: 'var(--space-2)' }}>
                        <span className="body-sm">{r.topic}</span>
                        <Tag tone={r.urgent ? 'warning' : 'neutral'}>{r.when}</Tag>
                      </div>
                      <p className="caption muted" style={{ marginTop: 4, maxWidth: 520 }}>
                        {r.subject} · {r.why}
                      </p>
                    </div>
                    <Link
                      href="/student/practice"
                      className={`btn btn-${r.urgent ? 'primary' : 'ghost'} btn-sm`}
                    >
                      <Icon name="arrow-right" size="sm" /> Revise
                    </Link>
                  </div>
                </SpotlightCard>
              ))}
            </div>
          )}
          <EvidenceDrawer
            evidence={[
              'The schedule is built from your own practice history against the real forgetting curve — opaque ref only.',
              'A topic surfaces when retention is genuinely fading, not on a fixed nagging timer.',
            ]}
            whySeeing="Your revision plan is shaped to keep what you have already earned. It adapts to time left and where the exam puts its weight."
          />
        </section>
      )}
    </SurfaceShell>
  );
}
