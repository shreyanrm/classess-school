'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Button, CrystallizeNode, Icon, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ReadStates } from '../../_components/ReadStates';
import { SourceNote } from '../../_components/SourceNote';
import { EvidenceDrawer } from '../../_components/EvidenceDrawer';
import { masteryEvidence } from '../../_components/MasteryConclusion';
import { BloomTaxonomy } from '../../_components/Charts';
import { StatMatrix, IgniteCard, Panel, FlagRow, HandnotePanel, SecHead } from '../../_components/StudentComposed';
import { PRACTICE_FORMATS, type FormatKey } from '../../_components/PracticeFormats';
import { AchievementBadges, deriveBadges } from '../../_components/AchievementBadges';
import { useDeepReads } from '@/lib/useDeepReads';
import { useGenerator } from '@/lib/useGenerator';
import { useVizData } from '@/lib/useVizData';
import { useEmit } from '@/lib/useEmit';
import { EVENT_PURPOSE } from '@/lib/events';
import { BAND_SHORT, computeMastery, type EngineEvent } from '@/lib/engine';
import type { Worksheet } from '@/lib/generate';
import {
  CURRENT_STUDENT,
  LOOP_TOPIC_ID,
  LOOP_DEPENDENT_TOPIC_ID,
  SCENARIO_NOW,
  liveEventId,
  topicInfo,
} from '@/lib/loopData';

/**
 * Practice — adaptive and mistake-based, composed dense. Items come from the
 * verified worksheet generator (gateway-first via /api/generate); difficulty is
 * seeded from the LIVE read of mastery. When the generator is unavailable the
 * surface degrades to a fixed verified set, marked with an OBSERVABLE SourceNote.
 * A miss repeats the idea; a clean unaided success advances. The aside carries
 * the live read and the Crystallize moment; the mastery moment is the green spark.
 */

interface Item {
  id: string;
  prompt: string;
  answer: string;
  difficulty: number;
}

const FALLBACK_ITEMS: Item[] = [
  { id: 'p1', prompt: 'Given sin θ = 3/5 in a right triangle, find cos θ.', answer: '4/5', difficulty: 0.4 },
  { id: 'p2', prompt: 'Find tan θ when sin θ = 3/5 and cos θ = 4/5.', answer: '3/4', difficulty: 0.5 },
  { id: 'p3', prompt: 'Evaluate sin 30° + cos 60°.', answer: '1', difficulty: 0.5 },
  { id: 'p4', prompt: 'If cos θ = 1/2, find θ for an acute angle.', answer: '60°', difficulty: 0.6 },
];

function difficultyAt(i: number, n: number): number {
  if (n <= 1) return 0.5;
  return 0.4 + (0.5 * i) / (n - 1);
}

const TOPIC = topicInfo(LOOP_TOPIC_ID);
const DEPENDENT = topicInfo(LOOP_DEPENDENT_TOPIC_ID);
const SUBJECT = CURRENT_STUDENT.ref;

export default function PracticePage() {
  const { phase, reads, source } = useDeepReads([LOOP_TOPIC_ID]);
  const baseline = reads.find((r) => r.topicId === LOOP_TOPIC_ID);
  const worksheet = useGenerator<Worksheet>('worksheet');
  // The result review reads gateway-first (seed fallback): the Bloom mix and the
  // per-question, cognitive-level review of this check. Re-labelled to the topic.
  const result = useVizData(['quizResult'], SUBJECT);
  const { emit } = useEmit();

  const [events, setEvents] = useState<EngineEvent[]>([]);
  const [index, setIndex] = useState(0);
  const [supported, setSupported] = useState(false);
  const [done, setDone] = useState(false);
  const [correctCount, setCorrectCount] = useState(0);
  const [unaidedCount, setUnaidedCount] = useState(0);

  // The two ways to practise: the adaptive engine flow, and the varied-format
  // assessment hub (flashcards, fill-blank, matching, and the four named
  // interactions). Both feed the same calm, mark-free read.
  const [tab, setTab] = useState<'adaptive' | 'formats'>('adaptive');
  const [activeFormat, setActiveFormat] = useState<FormatKey | null>(null);
  // A calm tally of confident format rounds — recognition, never a score.
  const [formatWins, setFormatWins] = useState(0);

  const startIndex = useMemo(() => {
    const comp = baseline?.mastery.reading.composite ?? 0;
    if (comp >= 0.55) return 2;
    if (comp >= 0.4) return 1;
    return 0;
  }, [baseline]);

  useEffect(() => {
    if (phase !== 'ready') return;
    const comp = baseline?.mastery.reading.composite ?? 0;
    worksheet.run({ topic: LOOP_TOPIC_ID, count: comp >= 0.55 ? 6 : 4 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, baseline?.mastery.reading.composite]);

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

  const itemsSource: 'gateway' | 'fallback' =
    worksheet.phase === 'ready' && (worksheet.artifact?.items.length ?? 0) > 0
      ? worksheet.source
      : 'fallback';

  // The result review — the Bloom mix as a donut (re-labelled to this topic) and
  // the per-question, cognitive-level review. Bands + plain notes, never a score.
  const quiz = result.data.quizResult;
  const resultBloom = useMemo(
    () => ({
      topicLabel: `${TOPIC.name} — this check`,
      slices: quiz.bloom,
      read: quiz.read,
      confidence: quiz.confidence,
    }),
    [quiz],
  );

  useEffect(() => {
    setIndex(startIndex);
  }, [startIndex, ITEMS]);

  const item = ITEMS[Math.min(index, ITEMS.length - 1)]!;
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

    emit({
      type: 'attempt',
      purpose: EVENT_PURPOSE.learning,
      payload: { topic_id: LOOP_TOPIC_ID, mode, correct, difficulty: item.difficulty, assistance_level: ev.payload.assistance_level },
    });

    if (correct) {
      setCorrectCount((c) => c + 1);
      if (!supported) setUnaidedCount((c) => c + 1);
      emit({ type: 'practice.item.completed', purpose: EVENT_PURPOSE.learning, payload: { item_id: item.id, mode } });
      if (index + 1 >= ITEMS.length) setDone(true);
      else setIndex((i) => i + 1);
    }
  }

  function restart() {
    setEvents([]);
    setIndex(startIndex);
    setDone(false);
    setSupported(false);
    setCorrectCount(0);
    setUnaidedCount(0);
  }

  const liveReading = baseline?.mastery ?? mastery;

  // Badges are read from real evidence, never a mark: the live independent read,
  // this session's unaided wins, and confident format rounds all count honestly.
  const badges = useMemo(
    () =>
      deriveBadges({
        independentTopics: liveReading.reading.independent ? 1 : 0,
        streakDays: 3,
        topicsRevived: 0,
        evidencePieces: liveReading.observationCount + unaidedCount + formatWins,
      }),
    [liveReading, unaidedCount, formatWins],
  );

  return (
    <SurfaceShell
      breadcrumb={[
        { label: 'Learning', href: '/student' },
        { label: TOPIC.subjectName },
        { label: 'Practice' },
      ]}
      eyebrow={`${TOPIC.subjectName} · Practice`}
      title={TOPIC.name}
      meta={[
        { value: ITEMS.length, label: 'items, adaptive' },
        { value: PRACTICE_FORMATS.length, label: 'practice formats' },
        { label: 'a miss repeats the idea' },
      ]}
      tabs={[
        { label: 'Adaptive', active: tab === 'adaptive', onClick: () => setTab('adaptive') },
        { label: 'Practice formats', active: tab === 'formats', onClick: () => setTab('formats') },
      ]}
      dockIntro="Short, adaptive practice. A miss repeats the idea; doing one on your own moves you up. Tell me if an item is too easy or too hard and I will adjust."
      dockChips={['Too easy — go harder', 'I keep missing this one', 'Explain my last mistake']}
      aside={
        phase === 'ready' ? (
          <>
            {liveReading.reading.independent ? (
              <IgniteCard
                when="The spark"
                who="You can do this on your own"
                detail="A real, unaided demonstration — no hints, verified across attempts. This unlocks the next topic."
              />
            ) : (
              <Panel title="Where you are" meta={<Tag tone="info">live read</Tag>}>
                <p className="body-sm" style={{ margin: '0 0 var(--space-2)' }}>
                  {capitalise(liveReading.plainLanguage)}.
                </p>
                <p className="caption muted" style={{ margin: '0 0 var(--space-3)' }}>
                  {BAND_SHORT[liveReading.reading.band]} · the next unaided win is the one that counts.
                </p>
                <EvidenceDrawer
                  evidence={masteryEvidence(liveReading, baseline?.gaps ?? [])}
                  whySeeing="This reading comes from your own attempts and checks, read live from the learning engine."
                />
              </Panel>
            )}

            <Panel title="What this builds" meta={<span className="overline">unlocks next</span>}>
              <FlagRow
                flag={{
                  icon: 'target',
                  title: DEPENDENT.name,
                  caption: 'Doing these ratios unaided opens it next.',
                  href: `/student/topic/${LOOP_DEPENDENT_TOPIC_ID}`,
                }}
              />
            </Panel>

            <AchievementBadges badges={badges} />

            <HandnotePanel>doing it once, on your own — that is the whole game</HandnotePanel>
          </>
        ) : undefined
      }
    >
      {phase !== 'ready' ? (
        <ReadStates phase={phase} />
      ) : tab === 'formats' ? (
        <FormatsHub
          activeFormat={activeFormat}
          onPick={setActiveFormat}
          onConfident={() => setFormatWins((w) => w + 1)}
          wins={formatWins}
        />
      ) : (
        <>
          <StatMatrix
            stats={[
              { label: 'Item', value: `${Math.min(index + 1, ITEMS.length)} / ${ITEMS.length}`, delta: done ? 'finished' : 'in progress', deltaDir: 'flat' },
              { label: 'Got right', value: correctCount, delta: 'this session', deltaDir: correctCount > 0 ? 'up' : 'flat' },
              { label: 'On your own', value: unaidedCount, delta: unaidedCount > 0 ? 'unaided wins' : 'the goal', deltaDir: unaidedCount > 0 ? 'up' : 'flat' },
              { label: 'Where you are', value: <span style={{ fontSize: 15 }}>{capitalise(liveReading.reading.band)}</span>, delta: 'plain language', deltaDir: 'flat' },
            ]}
          />

          {done ? (
            <>
            <section className="next-step-hero reveal reveal-3">
              <div className="ignite-row">
                {mastery.reading.independent ? (
                  <CrystallizeNode variant="b" inline resolved label="Independent mastery" />
                ) : null}
                <h3 className="display-sm" style={{ margin: 0, fontSize: 24 }}>
                  {mastery.reading.independent ? 'You did these on your own' : 'Good work — keep going to do these unprompted'}
                </h3>
              </div>
              <p className="body-sm muted" style={{ marginTop: 'var(--space-3)', maxWidth: 540 }}>
                {mastery.reading.independent
                  ? `That is the green spark — a real, unaided demonstration. This unlocks ${DEPENDENT.name} next.`
                  : 'A few more unaided wins and you will be doing these on your own.'}
              </p>
              <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
                <Button variant="secondary" size="sm" onClick={restart}>
                  Practise again
                </Button>
                {mastery.reading.independent ? (
                  <Link href={`/student/topic/${LOOP_DEPENDENT_TOPIC_ID}`} className="btn btn-accent btn-sm">
                    Open {DEPENDENT.name}
                    <Icon name="arrow-right" size="sm" />
                  </Link>
                ) : null}
              </div>
            </section>

            {/* The result review — a check to LEARN from, not a score. The
                thinking-level mix, then a per-question review tied to the
                cognitive level each one asked of you. Plain language, no %. */}
            <section className="stack">
              <SecHead title="Your check, reviewed" meta={<span className="overline">what you learn from it</span>} />
              <p className="body-sm muted" style={{ maxWidth: 560 }}>
                {quiz.read}
              </p>
              <BloomTaxonomy data={resultBloom} source={result.sourceByKind.quizResult} />
            </section>

            <section>
              <SecHead title="Question by question" meta={<span className="overline">by thinking level</span>} />
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Thinking level</th>
                      <th>How it went</th>
                      <th>On your own</th>
                      <th>What it was</th>
                    </tr>
                  </thead>
                  <tbody>
                    {quiz.questions.map((q, i) => (
                      <tr key={i}>
                        <td>{q.level}</td>
                        <td>
                          <Tag tone={q.outcome === 'right' ? 'success' : q.outcome === 'close' ? 'info' : 'warning'}>
                            <span className="dot" />
                            {q.outcome === 'right' ? 'Got it' : q.outcome === 'close' ? 'So close' : 'Next focus'}
                          </Tag>
                        </td>
                        <td className="muted">{q.unaided ? 'Unaided' : 'With a hint'}</td>
                        <td className="muted">{q.note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="caption quiet" style={{ marginTop: 'var(--space-2)' }}>
                A &ldquo;next focus&rdquo; is named, not a failing — it is exactly where a little practice goes
                furthest. No marks here, ever.
              </p>
              <SourceNote source={result.source} />
            </section>
            </>
          ) : (
            // VidyaWatch reads the step the learner is on; the active item is a HARD
            // step once it is Core/Stretch — Vidya may offer to walk it through.
            <section
              className="next-step-hero reveal reveal-3"
              data-vidya-step={item.id}
              data-vidya-hard={item.difficulty > 0.4 ? 'true' : 'false'}
            >
              <div className="row-between" style={{ alignItems: 'flex-start' }}>
                <p className="overline" style={{ margin: 0 }}>
                  Item {index + 1} of {ITEMS.length}
                </p>
                <Tag tone="info">{difficultyLabel(item.difficulty)}</Tag>
              </div>

              <h3 className="display-sm" style={{ marginTop: 'var(--space-3)', fontSize: 24 }}>
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
            </section>
          )}
        </>
      )}
    </SurfaceShell>
  );
}

/* The gamified assessment HUB — a gallery of varied formats. Picking one opens
   the interaction; finishing a round adds a calm "win" (recognition, not a
   score). Honest framing throughout: no leaderboards, no raw marks. */
function FormatsHub({
  activeFormat,
  onPick,
  onConfident,
  wins,
}: {
  activeFormat: FormatKey | null;
  onPick: (key: FormatKey | null) => void;
  onConfident: () => void;
  wins: number;
}) {
  const active = PRACTICE_FORMATS.find((f) => f.key === activeFormat);

  if (active) {
    const Active = active.Component;
    return (
      <section className="stack reveal reveal-2">
        <div className="row-between">
          <Button variant="ghost" size="sm" onClick={() => onPick(null)}>
            All formats
          </Button>
          <span className="caption muted">{wins} confident rounds this visit</span>
        </div>
        <Active
          onComplete={(signal) => {
            if (signal.confident) onConfident();
          }}
        />
      </section>
    );
  }

  return (
    <section className="stack reveal reveal-2">
      <SecHead title="Choose how to practise" meta={<span className="overline">{PRACTICE_FORMATS.length} formats</span>} />
      <p className="caption quiet" style={{ maxWidth: 560 }}>
        Different ways to meet the same idea — flip a card, drag words, order a proof, or teach it back.
        Each one shows what you can do, never a mark.
      </p>
      <div className="format-hub-grid">
        {PRACTICE_FORMATS.map((f, i) => (
          <button
            key={f.key}
            type="button"
            className={`format-tile reveal reveal-${Math.min(i + 1, 8)}`}
            onClick={() => onPick(f.key)}
          >
            <span className="format-tile-ic" aria-hidden="true">
              <Icon name={FORMAT_ICON[f.key]} size="md" />
            </span>
            <span className="body-sm" style={{ fontWeight: 500 }}>
              {f.name}
            </span>
            <span className="caption muted">{f.blurb}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

const FORMAT_ICON: Record<FormatKey, 'spark' | 'grid' | 'target' | 'check' | 'chart' | 'book'> = {
  flashcard: 'grid',
  'fill-blank': 'check',
  matching: 'grid',
  predict: 'spark',
  assemble: 'chart',
  'missing-step': 'target',
  'teach-back': 'book',
};

function difficultyLabel(d: number): string {
  if (d <= 0.4) return 'Warm-up';
  if (d <= 0.55) return 'Core';
  return 'Stretch';
}

function capitalise(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
