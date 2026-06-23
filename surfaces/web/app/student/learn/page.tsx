'use client';

import { useState } from 'react';
import { Button, Icon, SpotlightCard, Textarea } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { topicInfo, LOOP_TOPIC_ID } from '@/lib/loopData';

/**
 * Learn — POSE -> STRUGGLE -> REVEAL. Never explain-first: the learner meets the
 * problem, attempts it, and only then is the idea revealed. The assistance
 * ladder is visible and fades from Learn -> Coach -> Hint -> Work-with-me ->
 * Check-my-work -> Independent as competence grows. A mode banner makes it
 * explicit whether the system is HELPING (everything except Independent) or
 * EVALUATING (Independent only) — the learner always knows which.
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

export default function LearnPage() {
  const [phase, setPhase] = useState<Phase>('pose');
  const [rung, setRung] = useState<Rung>('Hint');
  const [attempt, setAttempt] = useState('');

  const evaluating = rung === 'Independent';

  return (
    <SurfaceShell
      eyebrow={`${TOPIC.subjectName} · ${TOPIC.chapterName}`}
      title="Learn it by trying first"
      dockIntro="We never explain first. You meet the problem, give it a go, and then the idea is revealed — it sticks far better that way. Slide the support down as you get stronger."
      dockChips={['I do not know where to start', 'Give me a smaller hint', 'Show me a worked example']}
    >
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
        <p className="caption quiet">{RUNG_HELP[rung]} The support fades left-to-right as you grow.</p>
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
                <Button variant="accent" size="sm" onClick={() => setPhase('reveal')}>
                  {evaluating ? 'Submit my unaided answer' : 'I have tried — reveal the idea'}
                </Button>
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
              </div>
            </div>
          ) : null}
        </div>
      </section>
    </SurfaceShell>
  );
}
