'use client';

import { useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';
import { Button, Icon, ProgressBar, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { EvidenceDrawer } from '../_components/EvidenceDrawer';
import { CLASS_LABEL, ROSTER } from '@/lib/loopData';

/**
 * d7 — Classroom delivery. The live, teacher-launched class: the interactive
 * board (a simple infinite stroke canvas), a live poll/quiz with a tally, a
 * device-free check, and attention SIGNALS shown as assistive, never punitive
 * — they assist the teacher and never grade a student from a face.
 *
 * Teacher-launched: the board is ready; the poll only goes live when the teacher
 * launches it. Nothing is broadcast automatically.
 */

type Tool = 'pen' | 'erase';

interface Stroke {
  points: { x: number; y: number }[];
  erase: boolean;
}

const POLL = {
  question: 'In a right triangle, sine of an acute angle is which ratio?',
  options: ['Opposite over hypotenuse', 'Adjacent over hypotenuse', 'Opposite over adjacent', 'Hypotenuse over opposite'],
  correct: 0,
};

/** A calm, assistive attention signal — never a punishment, never a face grade. */
const SIGNALS = [
  { icon: 'spark' as const, label: 'A hand is up', detail: 'Someone near the front has a question.', tone: 'info' as const },
  { icon: 'clock' as const, label: 'Energy dipping', detail: 'A quieter stretch after the last worked example. A quick poll may re-engage.', tone: 'warning' as const },
];

export default function ClassroomPage() {
  // The board — a simple stroke canvas (a stand-in for the infinite board).
  const [strokes, setStrokes] = useState<Stroke[]>([]);
  const [tool, setTool] = useState<Tool>('pen');
  const drawing = useRef(false);
  const svgRef = useRef<SVGSVGElement>(null);

  // The live poll.
  const [pollLive, setPollLive] = useState(false);
  const [tally, setTally] = useState<number[]>([0, 0, 0, 0]);

  // Device-free mode.
  const [deviceFree, setDeviceFree] = useState(false);
  const [scanned, setScanned] = useState(false);

  function point(e: ReactPointerEvent) {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }
  function startStroke(e: ReactPointerEvent) {
    drawing.current = true;
    setStrokes((prev) => [...prev, { points: [point(e)], erase: tool === 'erase' }]);
  }
  function extendStroke(e: ReactPointerEvent) {
    if (!drawing.current) return;
    setStrokes((prev) => {
      const next = prev.slice();
      const last = next[next.length - 1];
      if (last) last.points.push(point(e));
      return next;
    });
  }
  function endStroke() {
    drawing.current = false;
  }

  /** A poll response only counts when the teacher launches it (or scans the room). */
  function simulateResponse(i: number) {
    if (!pollLive) return;
    setTally((prev) => prev.map((v, idx) => (idx === i ? v + 1 : v)));
  }
  const totalVotes = tally.reduce((a, b) => a + b, 0);

  return (
    <SurfaceShell
      eyebrow={`${CLASS_LABEL} · live`}
      title="Classroom delivery"
      dockIntro="The board is ready. I can launch a poll mid-lesson, run a device-free check, and pass you gentle attention signals — assistive only, never a grade from a face. You launch everything."
      dockChips={['Launch a quick poll', 'Run a device-free check', 'What is the room telling me']}
    >
      <section className="stack">
        <p className="overline">The interactive board</p>
        <div className="row" style={{ gap: 'var(--space-2)', marginBottom: 'var(--space-2)' }}>
          <Button variant={tool === 'pen' ? 'primary' : 'secondary'} size="sm" onClick={() => setTool('pen')}>
            <Icon name="spark" size="sm" /> Pen
          </Button>
          <Button variant={tool === 'erase' ? 'primary' : 'secondary'} size="sm" onClick={() => setTool('erase')}>
            <Icon name="close" size="sm" /> Erase
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setStrokes([])}>
            Clear board
          </Button>
        </div>
        <div className="home-canvas" style={{ padding: 0, overflow: 'hidden' }}>
          <svg
            ref={svgRef}
            role="img"
            aria-label="Interactive board canvas"
            style={{ width: '100%', height: 320, touchAction: 'none', cursor: 'crosshair', display: 'block' }}
            onPointerDown={startStroke}
            onPointerMove={extendStroke}
            onPointerUp={endStroke}
            onPointerLeave={endStroke}
          >
            {strokes.map((s, i) => (
              <polyline
                key={i}
                points={s.points.map((p) => `${p.x},${p.y}`).join(' ')}
                fill="none"
                stroke={s.erase ? 'var(--bg)' : 'var(--text-primary)'}
                strokeWidth={s.erase ? 18 : 2}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            ))}
          </svg>
        </div>
        {strokes.length === 0 ? (
          <p className="caption muted">Write or draw anywhere. This is a calm stand-in for the full infinite board.</p>
        ) : null}
      </section>

      <section className="stack">
        <p className="overline">Live poll</p>
        <SpotlightCard padLg>
          <div className="row-between" style={{ alignItems: 'flex-start' }}>
            <h3 className="body-lg" style={{ margin: 0, maxWidth: 520 }}>
              {POLL.question}
            </h3>
            <Tag tone={pollLive ? 'success' : 'neutral'}>{pollLive ? 'Live' : 'Not launched'}</Tag>
          </div>

          <div className="stack" style={{ gap: 'var(--space-2)', marginTop: 'var(--space-3)' }}>
            {POLL.options.map((opt, i) => {
              const pct = totalVotes > 0 ? Math.round((tally[i]! / totalVotes) * 100) : 0;
              return (
                <button
                  key={opt}
                  type="button"
                  className="cell"
                  onClick={() => simulateResponse(i)}
                  disabled={!pollLive}
                  style={{ textAlign: 'left', cursor: pollLive ? 'pointer' : 'default' }}
                >
                  <div className="row-between">
                    <span className="body-sm">{opt}</span>
                    {pollLive ? (
                      <span className="caption muted">
                        {tally[i]} · {pct}%
                      </span>
                    ) : null}
                  </div>
                  {pollLive ? (
                    <div style={{ marginTop: 6 }}>
                      <ProgressBar value={pct} accent={i === POLL.correct} label={opt} />
                    </div>
                  ) : null}
                </button>
              );
            })}
          </div>

          <div className="divider" />
          {!pollLive ? (
            <div className="rec-actions">
              <Button variant="accent" size="sm" onClick={() => setPollLive(true)}>
                Launch the poll
              </Button>
              <span className="caption muted">The poll goes live only when you launch it.</span>
            </div>
          ) : (
            <div className="rec-actions">
              <span className="body-sm">
                {totalVotes === 0
                  ? 'Live — responses will tally here as they come in.'
                  : `${totalVotes} responses so far. The correct option is highlighted for you.`}
              </span>
              <Button variant="ghost" size="sm" onClick={() => { setPollLive(false); setTally([0, 0, 0, 0]); }}>
                Close poll
              </Button>
            </div>
          )}
        </SpotlightCard>
      </section>

      <section className="stack">
        <p className="overline">Device-free check</p>
        <SpotlightCard>
          <p className="body-sm">
            Where students have no device, each holds a unique response card. Photograph the room and
            I propose a read for you to confirm — never an automatic grade.
          </p>
          {!deviceFree ? (
            <div className="rec-actions" style={{ marginTop: 'var(--space-3)' }}>
              <Button variant="primary" size="sm" onClick={() => setDeviceFree(true)}>
                Start device-free mode
              </Button>
            </div>
          ) : (
            <div className="stack" style={{ marginTop: 'var(--space-3)' }}>
              {!scanned ? (
                <Button variant="accent" size="sm" onClick={() => setScanned(true)}>
                  <Icon name="grid" size="sm" /> Photograph the room
                </Button>
              ) : (
                <div className="row-between">
                  <span className="body-sm">
                    Proposed read for {ROSTER.length} cards — yours to confirm.
                  </span>
                  <Tag tone="info">Awaiting your confirm</Tag>
                </div>
              )}
            </div>
          )}
        </SpotlightCard>
      </section>

      <section className="stack">
        <p className="overline">Attention signals</p>
        <p className="caption quiet">Gentle, assistive cues. On-device only; never a grade from a face.</p>
        <div className="stack" style={{ gap: 'var(--space-2)' }}>
          {SIGNALS.map((s) => (
            <SpotlightCard key={s.label}>
              <div className="row-between" style={{ alignItems: 'flex-start' }}>
                <div className="row" style={{ gap: 'var(--space-2)', alignItems: 'flex-start' }}>
                  <Icon name={s.icon} size="sm" />
                  <div>
                    <span className="body-sm">{s.label}</span>
                    <p className="caption muted" style={{ marginTop: 2, maxWidth: 480 }}>
                      {s.detail}
                    </p>
                  </div>
                </div>
                <Tag tone={s.tone}>assist</Tag>
              </div>
            </SpotlightCard>
          ))}
          <EvidenceDrawer
            evidence={[
              'Signals are computed on-device and assist the teacher; no face is stored or used to grade a student.',
              'Engagement is gauged against later performance on the topic, not held against anyone in the moment.',
            ]}
            whySeeing="These are shown to help you read the room and adjust. They are never punitive and never feed a record about a student."
          />
        </div>
      </section>
    </SurfaceShell>
  );
}
