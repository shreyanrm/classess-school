'use client';

import { useMemo, useState } from 'react';
import { Button, Icon, IgniteDot, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { computeMastery, type EngineEvent } from '@/lib/engine';
import {
  CURRENT_STUDENT,
  LOOP_TOPIC_ID,
  SCENARIO_NOW,
  liveEventId,
  topicInfo,
} from '@/lib/loopData';

/**
 * Practice — adaptive and mistake-based. Each item is attempted independently
 * or with support (the learner chooses how they are working), and the next item
 * adapts: a miss repeats the idea at the same level; a clean independent success
 * steps the difficulty up. Every attempt emits an event and the live read
 * updates. Plain language only — the mastery moment is the green spark.
 */

interface Item {
  id: string;
  prompt: string;
  answer: string;
  difficulty: number;
}

const ITEMS: Item[] = [
  { id: 'p1', prompt: 'Given sin θ = 3/5 in a right triangle, find cos θ.', answer: '4/5', difficulty: 0.4 },
  { id: 'p2', prompt: 'Find tan θ when sin θ = 3/5 and cos θ = 4/5.', answer: '3/4', difficulty: 0.5 },
  { id: 'p3', prompt: 'Evaluate sin 30° + cos 60°.', answer: '1', difficulty: 0.5 },
  { id: 'p4', prompt: 'If cos θ = 1/2, find θ for an acute angle.', answer: '60°', difficulty: 0.6 },
];

const TOPIC = topicInfo(LOOP_TOPIC_ID);
const SUBJECT = CURRENT_STUDENT.ref;

export default function PracticePage() {
  const [events, setEvents] = useState<EngineEvent[]>([]);
  const [index, setIndex] = useState(0);
  const [supported, setSupported] = useState(false);
  const [done, setDone] = useState(false);

  const item = ITEMS[Math.min(index, ITEMS.length - 1)]!;
  const mastery = useMemo(
    () => computeMastery(events, SUBJECT, LOOP_TOPIC_ID, SCENARIO_NOW),
    [events],
  );

  function record(correct: boolean) {
    const ev: EngineEvent = {
      event_id: liveEventId(),
      occurred_at: new Date(SCENARIO_NOW - (ITEMS.length - index) * 3_600_000).toISOString(),
      canonical_uuid: SUBJECT,
      type: 'attempt.recorded',
      payload: {
        attempt_id: liveEventId(),
        ontology: { topic_id: LOOP_TOPIC_ID },
        mode: supported ? 'supported' : 'independent',
        assistance_level: supported ? 'Hint' : 'Independent',
        correct,
        score: correct ? (supported ? 0.85 : 1) : 0.35,
        difficulty: item.difficulty,
        time_taken_ms: supported ? 58_000 : 50_000,
        attempt_number: 1,
      },
    };
    setEvents((prev) => [...prev, ev]);

    // Adaptive, mistake-based: a miss repeats the idea; a success advances.
    if (correct) {
      if (index + 1 >= ITEMS.length) setDone(true);
      else setIndex((i) => i + 1);
    }
    // On a miss we stay on the same item (repeat the idea at this level).
  }

  function restart() {
    setEvents([]);
    setIndex(0);
    setDone(false);
    setSupported(false);
  }

  return (
    <SurfaceShell
      eyebrow={`${TOPIC.subjectName} · Practice`}
      title={TOPIC.name}
      dockIntro="Short, adaptive practice. A miss repeats the idea; doing one on your own moves you up. Tell me if an item is too easy or too hard and I will adjust."
      dockChips={['Too easy — go harder', 'I keep missing this one', 'Explain my last mistake']}
    >
      <section className="stack">
        <div className="row-between">
          <p className="overline" style={{ margin: 0 }}>
            Where you are now
          </p>
          <span className="ignite-row">
            {mastery.reading.independent ? <IgniteDot label="On your own" /> : null}
            <span className="body-sm">
              {mastery.observationCount === 0 ? 'Start practising to see this update' : capitalise(mastery.plainLanguage)}
            </span>
          </span>
        </div>
      </section>

      {done ? (
        <section>
          <SpotlightCard padLg>
            <div className="ignite-row">
              {mastery.reading.independent ? <IgniteDot label="Independent mastery" /> : null}
              <h3 className="body-lg" style={{ margin: 0 }}>
                {mastery.reading.independent
                  ? 'You did these on your own'
                  : 'Good work — keep going to do these unprompted'}
              </h3>
            </div>
            <p className="body-sm muted" style={{ marginTop: 'var(--space-3)' }}>
              {mastery.reading.independent
                ? 'That is the green spark — a real, unaided demonstration. This unlocks Trigonometric Identities next.'
                : 'A few more unaided wins and you will be doing these on your own.'}
            </p>
            <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
              <Button variant="ghost" size="sm" onClick={restart}>
                Practise again
              </Button>
            </div>
          </SpotlightCard>
        </section>
      ) : (
        <section>
          <SpotlightCard padLg>
            <div className="row-between" style={{ alignItems: 'flex-start' }}>
              <p className="overline" style={{ margin: 0 }}>
                Item {index + 1} of {ITEMS.length}
              </p>
              <Tag tone="neutral">{difficultyLabel(item.difficulty)}</Tag>
            </div>

            <h3 className="body-lg" style={{ marginTop: 'var(--space-3)' }}>
              {item.prompt}
            </h3>

            <div style={{ marginTop: 'var(--space-4)' }}>
              <p className="caption quiet" style={{ marginBottom: 'var(--space-2)' }}>
                How are you working on this?
              </p>
              <div className="ladder" role="group" aria-label="Independent or supported" style={{ maxWidth: 360 }}>
                <button
                  type="button"
                  className={`ladder-rung evaluating${!supported ? ' active' : ''}`}
                  onClick={() => setSupported(false)}
                >
                  On my own
                </button>
                <button
                  type="button"
                  className={`ladder-rung${supported ? ' active' : ''}`}
                  onClick={() => setSupported(true)}
                >
                  With a hint
                </button>
              </div>
              {supported ? (
                <p className="caption quiet" style={{ marginTop: 'var(--space-2)' }}>
                  Hint: the three sides satisfy a² + b² = c². Working with a hint helps you learn — the
                  unaided try is what shows mastery.
                </p>
              ) : null}
            </div>

            <div className="rec-actions" style={{ marginTop: 'var(--space-5)' }}>
              <Button variant="accent" size="sm" onClick={() => record(true)}>
                <Icon name="check" size="sm" />
                I got it right
              </Button>
              <Button variant="secondary" size="sm" onClick={() => record(false)}>
                I missed it
              </Button>
              <span className="caption muted">A miss repeats the idea; a win moves you on.</span>
            </div>
          </SpotlightCard>
        </section>
      )}
    </SurfaceShell>
  );
}

function difficultyLabel(d: number): string {
  if (d <= 0.4) return 'Warm-up';
  if (d <= 0.55) return 'Core';
  return 'Stretch';
}

function capitalise(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
