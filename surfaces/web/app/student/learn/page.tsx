'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Button, Icon, Tag, Textarea } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { EvidenceDrawer } from '../../_components/EvidenceDrawer';
import { masteryEvidence } from '../../_components/MasteryConclusion';
import { IgniteCard, Panel, FlagRow, HandnotePanel, SecHead } from '../../_components/StudentComposed';
import { CourseBrowser } from '../../_components/CourseBrowser';
import { FlashcardDeck } from '../../_components/PracticeFormats';
import { useDeepReads } from '@/lib/useDeepReads';
import { useEmit } from '@/lib/useEmit';
import { EVENT_PURPOSE } from '@/lib/events';
import { BAND_SHORT } from '@/lib/engine';
import { topicInfo, LOOP_TOPIC_ID, LOOP_DEPENDENT_TOPIC_ID } from '@/lib/loopData';

/**
 * Learn — a single topic, taught POSE -> STRUGGLE -> REVEAL. Never explain-first:
 * the learner meets the problem, attempts it, and only then is the idea revealed.
 * The assistance ladder is visible and FADES with mastery — its default rung is
 * seeded from the live read (gateway-first, engine fallback). The lesson works
 * offline (a pre-synced pack). Composed dense: the lesson is the main column, an
 * aside carries the live read, the prerequisite, and what this unlocks.
 */

const LADDER = ['Learn', 'Coach', 'Hint', 'Work-with-me', 'Check-my-work', 'Independent'] as const;
type Rung = (typeof LADDER)[number];

const RUNG_HELP: Record<Rung, string> = {
  Learn: 'A full worked example, shown to you.',
  Coach: 'Step-by-step alongside you as you work.',
  Hint: 'A nudge — you do the work.',
  'Work-with-me': 'We build the answer together.',
  'Check-my-work': 'You produce it; the system checks after.',
  Independent: 'No help. This is the demonstration that counts.',
};

type Phase = 'pose' | 'struggle' | 'reveal';

const TOPIC = topicInfo(LOOP_TOPIC_ID);
const DEPENDENT = topicInfo(LOOP_DEPENDENT_TOPIC_ID);

/** Support fades as mastery grows: seed the default rung from the live reading. */
function seedRung(composite: number): Rung {
  if (composite >= 0.55) return 'Independent';
  if (composite >= 0.45) return 'Check-my-work';
  if (composite >= 0.3) return 'Hint';
  return 'Coach';
}

export default function LearnPage() {
  const { phase: readPhase, reads, source } = useDeepReads([LOOP_TOPIC_ID]);
  const reading = reads.find((r) => r.topicId === LOOP_TOPIC_ID);
  const { emit } = useEmit();

  const [phase, setPhase] = useState<Phase>('pose');
  const [rung, setRung] = useState<Rung>('Hint');
  const [attempt, setAttempt] = useState('');
  const [seeded, setSeeded] = useState(false);
  // Three ways into Learn: the pose→struggle→reveal lesson, a quick flashcard
  // warm-up, and the full hierarchical course browser (every chapter/topic).
  const [lens, setLens] = useState<'lesson' | 'flashcards' | 'browse'>('lesson');

  const seededRung = useMemo(
    () => seedRung(reading?.mastery.reading.composite ?? 0),
    [reading],
  );

  // Seed the ladder once the live read lands; the learner can still move it.
  useEffect(() => {
    if (readPhase === 'ready' && !seeded) {
      setRung(seededRung);
      setSeeded(true);
    }
  }, [readPhase, seeded, seededRung]);

  // The surface viewed event — attributed, consent-stamped.
  useEffect(() => {
    if (readPhase === 'ready')
      emit({ type: 'surface.viewed', purpose: EVENT_PURPOSE.learning, payload: { surface: 'student.learn', source } });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [readPhase]);

  const evaluating = rung === 'Independent';
  // Degrade is not a blocker for the lesson — it ships offline as a synced pack.
  const degraded =
    readPhase === 'offline' || readPhase === 'error' || readPhase === 'permission-denied' || source === 'fallback';

  function reveal() {
    setPhase('reveal');
    emit({
      type: 'attempt',
      purpose: EVENT_PURPOSE.learning,
      payload: {
        topic_id: LOOP_TOPIC_ID,
        mode: evaluating ? 'independent' : 'supported',
        assistance_level: rung,
        committed_prediction: attempt.trim().length > 0,
      },
    });
  }

  return (
    <SurfaceShell
      breadcrumb={[
        { label: 'Learning', href: '/student' },
        { label: TOPIC.subjectName },
        { label: 'Learn' },
      ]}
      eyebrow={`${TOPIC.subjectName} · ${TOPIC.chapterName}`}
      title={TOPIC.name}
      meta={[
        { label: 'taught by trying first' },
        { value: rung, label: 'help level' },
        { label: evaluating ? 'this attempt counts' : 'a supported attempt' },
      ]}
      tabs={[
        { label: 'The lesson', active: lens === 'lesson', onClick: () => setLens('lesson') },
        { label: 'Flashcards', active: lens === 'flashcards', onClick: () => setLens('flashcards') },
        { label: 'Browse all topics', active: lens === 'browse', onClick: () => setLens('browse') },
      ]}
      dockIntro="We never explain first. You meet the problem, give it a go, and then the idea is revealed — it sticks far better that way. Slide the support down as you get stronger."
      dockChips={['I do not know where to start', 'Give me a smaller hint', 'Show me a worked example']}
      aside={
        readPhase !== 'loading' ? (
          <>
            {reading ? (
              reading.mastery.reading.independent ? (
                <IgniteCard
                  when="The spark"
                  who="You can do this on your own"
                  detail="A real, unaided demonstration — verified across attempts. This is the line that matters."
                />
              ) : (
                <Panel title="Where you are" meta={<Tag tone="info">live read</Tag>}>
                  <p className="body-sm" style={{ margin: '0 0 var(--space-2)' }}>
                    {capitalise(reading.mastery.plainLanguage)}.
                  </p>
                  <p className="caption muted" style={{ margin: '0 0 var(--space-3)' }}>
                    {BAND_SHORT[reading.mastery.reading.band]} · your help level starts from here.
                  </p>
                  <EvidenceDrawer
                    evidence={masteryEvidence(reading.mastery, reading.gaps)}
                    whySeeing="Your help level starts from your latest reading — more help when it is newer to you, less as you show you can do it alone."
                  />
                </Panel>
              )
            ) : null}

            <Panel title="What this builds" meta={<span className="overline">unlocks next</span>}>
              <FlagRow
                flag={{
                  icon: 'target',
                  title: DEPENDENT.name,
                  caption: 'Built on these ratios — doing them unaided opens it next.',
                  href: `/student/topic/${LOOP_DEPENDENT_TOPIC_ID}`,
                }}
              />
              <FlagRow
                flag={{
                  icon: 'chart',
                  title: 'See where you are',
                  caption: 'The full evidence behind this topic, in plain language.',
                  href: `/student/topic/${LOOP_TOPIC_ID}`,
                }}
              />
            </Panel>

            <HandnotePanel>try before you peek — the struggle is where it sticks</HandnotePanel>
          </>
        ) : undefined
      }
    >
      {readPhase === 'loading' ? (
        <section className="stack" aria-busy="true" aria-label="Preparing your lesson">
          <div className="skeleton" style={{ height: 96 }} />
          <div className="skeleton" style={{ height: 220 }} />
        </section>
      ) : lens === 'browse' ? (
        <section className="stack reveal reveal-2">
          <SecHead title="Your course" meta={<span className="overline">subject · term · chapter · topic</span>} />
          <p className="caption quiet" style={{ maxWidth: 560 }}>
            Every chapter and topic, expandable. Each topic opens three ways in — the shared material, a
            lesson, or practice. Pick anything to jump straight there.
          </p>
          <CourseBrowser defaultOpenSubject={TOPIC.subjectId} />
        </section>
      ) : lens === 'flashcards' ? (
        <section className="stack reveal reveal-2">
          <SecHead title="Quick recall" meta={<span className="overline">warm up</span>} />
          <p className="caption quiet" style={{ maxWidth: 560 }}>
            A fast flip-through to prime the idea before you meet the problem. Rate your own recall — no marks.
          </p>
          <FlashcardDeck />
        </section>
      ) : (
        <>
          {degraded ? (
            <div className="offline-banner" role="status">
              {readPhase === 'permission-denied'
                ? 'Showing a synced lesson — your live reading is not shared with you right now.'
                : 'Showing a synced lesson — your live reading will refresh when the connection is back.'}
            </div>
          ) : null}

          <section className="stack">
            <div className="row-between">
              <p className="overline" style={{ margin: 0 }}>
                How much help do you want?
              </p>
              <span className={`mode-banner ${evaluating ? 'evaluating' : 'helping'}`}>
                <Icon name={evaluating ? 'target' : 'spark'} size="sm" />
                {evaluating ? 'This is a real, unaided demonstration' : 'The system is helping you learn'}
              </span>
            </div>

            <div className="ladder" role="group" aria-label="Assistance level">
              {LADDER.map((r) => (
                <button
                  key={r}
                  type="button"
                  className={`ladder-rung${r === 'Independent' ? ' evaluating' : ''}${r === rung ? ' active' : ''}`}
                  onClick={() => setRung(r)}
                  title={RUNG_HELP[r]}
                >
                  {r}
                </button>
              ))}
            </div>
            <p className="caption quiet">
              {RUNG_HELP[rung]} The support fades left-to-right as you grow
              {reading ? ' — your start point is set from where you are now.' : '.'}
            </p>
          </section>

          <section>
            <div className="pose">
              <p className="overline" style={{ margin: 0 }}>
                Pose
              </p>
              <h3 className="body-lg" style={{ marginTop: 'var(--space-3)' }}>
                In a right triangle, the side opposite an acute angle θ is 3 and the hypotenuse is 5.
                What is sin θ, and what is cos θ?
              </h3>

              {phase === 'pose' ? (
                <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
                  <Button variant="primary" size="sm" onClick={() => setPhase('struggle')}>
                    Give it a go
                    <Icon name="arrow-right" size="sm" />
                  </Button>
                  <span className="caption muted">Try before you see the idea — that is the point.</span>
                </div>
              ) : null}

              {phase === 'struggle' ? (
                <div className="stack" style={{ marginTop: 'var(--space-4)' }}>
                  <p className="overline" style={{ margin: 0 }}>
                    Struggle
                  </p>
                  {rung !== 'Independent' ? (
                    <p className="caption quiet">
                      {rung === 'Hint' || rung === 'Coach'
                        ? 'Nudge: sine is opposite over hypotenuse. What is the third side?'
                        : 'Work it through — write what you can, even if it is partial.'}
                    </p>
                  ) : (
                    <p className="caption quiet">No help on this one — this is the demonstration that counts.</p>
                  )}
                  <Textarea
                    value={attempt}
                    onChange={(e) => setAttempt(e.target.value)}
                    placeholder="Write your working here"
                    rows={4}
                  />
                  <div className="rec-actions">
                    <Button variant="accent" size="sm" disabled={attempt.trim().length === 0} onClick={reveal}>
                      {evaluating ? 'Submit my unaided answer' : 'I have tried — reveal the idea'}
                    </Button>
                    {attempt.trim().length === 0 ? (
                      <span className="caption muted">Commit a prediction first — even a rough one. That is what makes it stick.</span>
                    ) : null}
                  </div>
                </div>
              ) : null}

              {phase === 'reveal' ? (
                <div className="reveal">
                  <p className="overline" style={{ margin: 0 }}>
                    Reveal
                  </p>
                  <p className="body" style={{ marginTop: 'var(--space-3)' }}>
                    The third side is 4 (since 3² + 4² = 5²). So <strong>sin θ = 3/5</strong> (opposite
                    over hypotenuse) and <strong>cos θ = 4/5</strong> (adjacent over hypotenuse).
                  </p>
                  <p className="caption quiet" style={{ marginTop: 'var(--space-2)' }}>
                    {evaluating
                      ? 'Because this was unaided, it counts toward showing you can do this on your own.'
                      : 'This was a supported attempt — it helps you learn, and the next unaided try is what shows mastery.'}
                  </p>
                  {reading ? (
                    <EvidenceDrawer
                      evidence={masteryEvidence(reading.mastery, reading.gaps)}
                      whySeeing="This attempt joins the evidence behind your reading on this topic."
                    />
                  ) : null}
                  <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => {
                        setPhase('pose');
                        setAttempt('');
                      }}
                    >
                      Try another, with less help
                    </Button>
                    <Link href="/student/practice" className="btn btn-ghost btn-sm">
                      Practise this on my own
                      <Icon name="arrow-right" size="sm" />
                    </Link>
                  </div>
                </div>
              ) : null}
            </div>
          </section>
        </>
      )}
    </SurfaceShell>
  );
}

function capitalise(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
