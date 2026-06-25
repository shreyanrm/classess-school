'use client';

import Link from 'next/link';
import { Icon, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { ReadStates } from '../_components/ReadStates';
import { SourceNote } from '../_components/SourceNote';
import { useDeepReads } from '@/lib/useDeepReads';
import { gapLabel } from '@/lib/engine';
import { CURRENT_STUDENT, LOOP_TOPIC_ID, topicInfo } from '@/lib/loopData';

/**
 * The student today — next step, why, how long, what it builds. Calm and
 * singular: one clear next thing, never a dashboard. The next step is chosen
 * from the learner's own live read (the topic with an open gap), and explained
 * in plain language — never a score, never the formula.
 *
 * Read GATEWAY-FIRST from the SPINE (mastery + gaps) through the governed seam,
 * exactly like its siblings (/student/progress, /student/practice). The TS
 * engine's faithful port answers only on degrade; the OBSERVABLE SourceNote
 * keeps the seam honest. All five designed states ship.
 */
export default function StudentTodayPage() {
  const subject = CURRENT_STUDENT.ref;
  const topic = topicInfo(LOOP_TOPIC_ID);
  // The learner's own live read for today's topic — gateway-first, engine on
  // degrade. The hook carries the five designed states and the honest source.
  const { phase, reads, source } = useDeepReads([LOOP_TOPIC_ID], subject);

  const read = reads.find((r) => r.topicId === LOOP_TOPIC_ID) ?? reads[0];
  const mastery = read?.mastery;
  const gaps = read?.gaps ?? [];
  const topGap = gaps.find((g) => g.evidence.confirmed) ?? gaps[0];

  return (
    <SurfaceShell
      eyebrow="Today"
      title="Here is your next step"
      dockIntro="One clear thing to do next, and why it matters. Ask me to explain where you are stuck, or to make it shorter."
      dockChips={['Why this next', 'Make it 10 minutes', 'I am stuck — help me']}
    >
      {phase !== 'ready' ? (
        <ReadStates phase={phase} />
      ) : (
        <>
          <section>
            <SpotlightCard padLg>
              <div className="row-between" style={{ alignItems: 'flex-start' }}>
                <div>
                  <p className="overline" style={{ margin: 0 }}>
                    {topic.subjectName}
                  </p>
                  <h2 className="display-sm" style={{ margin: '4px 0 0' }}>
                    Practise {topic.name} on your own
                  </h2>
                </div>
                <Tag tone="info">Next step</Tag>
              </div>

              <div className="next-step">
                <div className="why-grid">
                  <div>
                    <div className="k">Why this</div>
                    <div className="v">
                      {topGap
                        ? 'You can do this with help — the goal now is to do it without.'
                        : 'You are close to doing this on your own.'}
                    </div>
                  </div>
                  <div>
                    <div className="k">How long</div>
                    <div className="v">About 12 minutes</div>
                  </div>
                  <div>
                    <div className="k">What it builds</div>
                    <div className="v">Doing this alone unlocks Trigonometric Identities next.</div>
                  </div>
                </div>
              </div>

              <div className="rec-actions" style={{ marginTop: 'var(--space-5)' }}>
                <Link href="/student/practice" className="btn btn-accent btn-sm">
                  Start practising
                  <Icon name="arrow-right" size="sm" />
                </Link>
                <Link href="/student/learn" className="btn btn-ghost btn-sm">
                  Learn it first
                </Link>
              </div>
            </SpotlightCard>
          </section>

          <section className="cols-2">
            <SpotlightCard>
              <p className="overline" style={{ margin: 0 }}>
                Where you are
              </p>
              <p className="body" style={{ marginTop: 'var(--space-3)' }}>
                {mastery ? `${capitalise(mastery.plainLanguage)}.` : 'Let us find where to start.'}
              </p>
              <p className="caption quiet" style={{ marginTop: 'var(--space-2)' }}>
                No scores, no marks — just what you can do. The goal is the green spark: doing it on your
                own.
              </p>
              <Link href="/student/progress" className="btn btn-ghost btn-sm" style={{ marginTop: 'var(--space-3)' }}>
                See your full progress
              </Link>
            </SpotlightCard>

            <SpotlightCard>
              <p className="overline" style={{ margin: 0 }}>
                What we are working on
              </p>
              {topGap ? (
                <>
                  <p className="body" style={{ marginTop: 'var(--space-3)' }}>
                    {plainGap(gapLabel(topGap.evidence.gapType))}
                  </p>
                  <p className="caption quiet" style={{ marginTop: 'var(--space-2)' }}>
                    This is a focus, not a failing. Everyone has these — naming it is how we close it.
                  </p>
                </>
              ) : (
                <p className="body" style={{ marginTop: 'var(--space-3)' }}>
                  Nothing is blocking you right now. Keep going.
                </p>
              )}
            </SpotlightCard>
          </section>

          <SourceNote source={source} />
        </>
      )}
    </SurfaceShell>
  );
}

/** Turn an internal gap label into warm, learner-safe language. */
function plainGap(label: string): string {
  const map: Record<string, string> = {
    'Support dependency': 'Doing this without help — you have it with a nudge, now we fade the nudge.',
    Prerequisite: 'A skill underneath this one needs a little more time.',
    Conceptual: 'Getting the idea itself really solid.',
    Procedural: 'Getting the steps smooth and reliable.',
    Application: 'Using this on harder, less familiar problems.',
    Retention: 'Bringing back something you knew well before.',
    Accuracy: 'Catching small slips so the right method lands right.',
    Speed: 'Getting quicker, now that you are accurate.',
    Confidence: 'Trusting yourself to do it unprompted.',
    Language: 'Making sure the wording is clear, not the maths.',
  };
  return map[label] ?? 'A focused next step.';
}

function capitalise(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
