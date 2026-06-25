'use client';

import { useEffect, useMemo, useState } from 'react';
import { Button, CrystallizeNode, Icon, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ReadStates } from '../../_components/ReadStates';
import { SourceNote } from '../../_components/SourceNote';
import { MasteryConclusion } from '../../_components/MasteryConclusion';
import { useDeepReads } from '@/lib/useDeepReads';
import { useGenerator } from '@/lib/useGenerator';
import { useEmit } from '@/lib/useEmit';
import { EVENT_PURPOSE } from '@/lib/events';
import { computeMastery, type EngineEvent } from '@/lib/engine';
import type { Worksheet } from '@/lib/generate';
import {
  CURRENT_STUDENT,
  LOOP_TOPIC_ID,
  SCENARIO_NOW,
  liveEventId,
  topicInfo,
} from '@/lib/loopData';

/**
 * Practice — adaptive and mistake-based. The items come from the verified
 * worksheet/practice generator (gateway-first via /api/generate); difficulty is
 * still seeded from the LIVE read of the learner's mastery. When the generator is
 * unavailable the surface degrades to a fixed verified set, marked with an
 * OBSERVABLE SourceNote — never served as if live. Each item is attempted
 * independently or with support; a miss repeats the idea, a clean independent
 * success advances. Plain language only; the mastery moment is the green spark.
 */

interface Item {
  id: string;
  prompt: string;
  answer: string;
  difficulty: number;
}

/** The fixed verified set — the DEGRADE fallback when the generator is silent. */
const FALLBACK_ITEMS: Item[] = [
  { id: 'p1', prompt: 'Given sin θ = 3/5 in a right triangle, find cos θ.', answer: '4/5', difficulty: 0.4 },
  { id: 'p2', prompt: 'Find tan θ when sin θ = 3/5 and cos θ = 4/5.', answer: '3/4', difficulty: 0.5 },
  { id: 'p3', prompt: 'Evaluate sin 30° + cos 60°.', answer: '1', difficulty: 0.5 },
  { id: 'p4', prompt: 'If cos θ = 1/2, find θ for an acute angle.', answer: '60°', difficulty: 0.6 },
];

/** Difficulty gradient across the generated set — warm-up -> core -> stretch. */
function difficultyAt(i: number, n: number): number {
  if (n <= 1) return 0.5;
  return 0.4 + (0.5 * i) / (n - 1);
}

const TOPIC = topicInfo(LOOP_TOPIC_ID);
const SUBJECT = CURRENT_STUDENT.ref;

export default function PracticePage() {
  // The baseline reading — gateway-first, engine fallback. Seeds difficulty.
  const { phase, reads, source } = useDeepReads([LOOP_TOPIC_ID]);
  const baseline = reads.find((r) => r.topicId === LOOP_TOPIC_ID);
  // The verified practice set — gateway-first (SourceNote degrade). Length is
  // seeded from mastery: a stronger learner gets a longer, harder set.
  const worksheet = useGenerator<Worksheet>('worksheet');
  const { emit } = useEmit();

  const [events, setEvents] = useState<EngineEvent[]>([]);
  const [index, setIndex] = useState(0);
  const [supported, setSupported] = useState(false);
  const [done, setDone] = useState(false);

  // Difficulty seeded from the baseline: a stronger learner starts at Core/Stretch.
  const startIndex = useMemo(() => {
    const comp = baseline?.mastery.reading.composite ?? 0;
    if (comp >= 0.55) return 2;
    if (comp >= 0.4) return 1;
    return 0;
  }, [baseline]);

  // Generate the verified set once the baseline is in — count seeded from mastery.
  useEffect(() => {
    if (phase !== 'ready') return;
    const comp = baseline?.mastery.reading.composite ?? 0;
    worksheet.run({ topic: LOOP_TOPIC_ID, count: comp >= 0.55 ? 6 : 4 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, baseline?.mastery.reading.composite]);

  // The live items: the verified generated set, or the fixed fallback set.
  const ITEMS: Item[] = useMemo(() => {
    const w = worksheet.artifact;
    if (worksheet.phase === 'ready' && w && w.items.length > 0) {
      return w.items.map((it) => ({
        id: `w${it.index}`,
        prompt: it.prompt,
        answer: it.answer,
        difficulty: difficultyAt(it.index - 1, w.items.length),
      }));
    }
    return FALLBACK_ITEMS;
  }, [worksheet.phase, worksheet.artifact]);

  // The generator either served (gateway/fallback) or is unavailable -> the fixed
  // set, marked as a fallback. Never present the static set as if it were live.
  const itemsSource: 'gateway' | 'fallback' =
    worksheet.phase === 'ready' && (worksheet.artifact?.items.length ?? 0) > 0
      ? worksheet.source
      : 'fallback';

  useEffect(() => {
    setIndex(startIndex);
  }, [startIndex, ITEMS]);

  const item = ITEMS[Math.min(index, ITEMS.length - 1)]!;
  // The in-session reading folds this session's live attempts over the baseline.
  const mastery = useMemo(
    () => computeMastery(events, SUBJECT, LOOP_TOPIC_ID, SCENARIO_NOW),
    [events],
  );

  function record(correct: boolean) {
    const mode = supported ? 'supported' : 'independent';
    const ev: EngineEvent = {
      event_id: liveEventId(),
      occurred_at: new Date(SCENARIO_NOW - (ITEMS.length - index) * 3_600_000).toISOString(),
      canonical_uuid: SUBJECT,
      type: 'attempt.recorded',
      payload: {
        attempt_id: liveEventId(),
        ontology: { topic_id: LOOP_TOPIC_ID },
        mode,
        assistance_level: supported ? 'Hint' : 'Independent',
        correct,
        score: correct ? (supported ? 0.85 : 1) : 0.35,
        difficulty: item.difficulty,
        time_taken_ms: supported ? 58_000 : 50_000,
        attempt_number: 1,
      },
    };
    setEvents((prev) => [...prev, ev]);

    // The attempt event — attributed, consent-stamped, with the independence flag.
    emit({
      type: 'attempt',
      purpose: EVENT_PURPOSE.learning,
      payload: { topic_id: LOOP_TOPIC_ID, mode, correct, difficulty: item.difficulty, assistance_level: ev.payload.assistance_level },
    });

    if (correct) {
      emit({ type: 'practice.item.completed', purpose: EVENT_PURPOSE.learning, payload: { item_id: item.id, mode } });
      if (index + 1 >= ITEMS.length) setDone(true);
      else setIndex((i) => i + 1);
    }
    // On a miss we stay on the same item (repeat the idea at this level).
  }

  function restart() {
    setEvents([]);
    setIndex(startIndex);
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
      {phase !== 'ready' ? (
        <ReadStates phase={phase} />
      ) : (
        <>
          <section className="stack">
            <p className="overline" style={{ margin: 0 }}>
              Where you are now
            </p>
            <SpotlightCard>
              <MasteryConclusion
                topicName={TOPIC.name}
                mastery={baseline?.mastery ?? mastery}
                gaps={baseline?.gaps ?? []}
                source={source}
              />
            </SpotlightCard>
          </section>

          {done ? (
            <section>
              <SpotlightCard padLg>
                <div className="ignite-row">
                  {mastery.reading.independent ? (
                    <CrystallizeNode variant="b" inline resolved label="Independent mastery" />
                  ) : null}
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
            // VidyaWatch reads the step the learner is on. The active item is a
            // HARD step (worth a quiet nudge) once it is Core/Stretch — Vidya may
            // then offer to walk it through on screen, never just hand the answer.
            <section data-vidya-step={item.id} data-vidya-hard={item.difficulty > 0.4 ? 'true' : 'false'}>
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
                <div style={{ marginTop: 'var(--space-3)' }}>
                  <SourceNote source={itemsSource} />
                </div>
              </SpotlightCard>
            </section>
          )}
        </>
      )}
    </SurfaceShell>
  );
}

function difficultyLabel(d: number): string {
  if (d <= 0.4) return 'Warm-up';
  if (d <= 0.55) return 'Core';
  return 'Stretch';
}
