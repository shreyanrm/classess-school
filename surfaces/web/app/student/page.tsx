'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import { Icon, Tag } from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { ReadStates } from '../_components/ReadStates';
import { SourceNote } from '../_components/SourceNote';
import {
  StatMatrix,
  SubjectGrid,
  IgniteCard,
  Panel,
  FlagRow,
  SchedRow,
  HandnotePanel,
  SecHead,
  type SubjectCardModel,
} from '../_components/StudentComposed';
import { useDeepReads } from '@/lib/useDeepReads';
import { gapLabel } from '@/lib/engine';
import {
  CURRENT_STUDENT,
  LOOP_TOPIC_ID,
  topicInfo,
  topicsForSubject,
  subjectCode,
  bandFill,
  MATH_SUBJECT_ID,
  PHYS_SUBJECT_ID,
} from '@/lib/loopData';

/**
 * The student today — calm and composed. One clear next step and why it matters,
 * a four-up read of where the week sits, the subject-card grid (the hit of cool
 * pigment), and an aside that carries the Crystallize moment, the focuses Vidya
 * flagged, today's timetable, and a human handnote. Never a dashboard of marks.
 *
 * Read GATEWAY-FIRST from the SPINE (mastery + gaps) through the governed seam;
 * the TS engine's faithful port answers only on degrade, and the OBSERVABLE
 * SourceNote keeps the seam honest. All five designed states ship.
 */

// The two subjects' lead topics — the focus the today grid reads against.
const MATH_FOCUS = LOOP_TOPIC_ID;
const PHYS_FOCUS = topicsForSubject(PHYS_SUBJECT_ID)[0]?.id ?? '';
const GRID_TOPICS = [MATH_FOCUS, PHYS_FOCUS].filter(Boolean);

export default function StudentTodayPage() {
  const subject = CURRENT_STUDENT.ref;
  const topic = topicInfo(LOOP_TOPIC_ID);
  // The learner's own live reads — gateway-first, engine on degrade. One hook
  // carries the five designed states and the honest source.
  const { phase, reads, source } = useDeepReads(GRID_TOPICS, subject);

  const lead = reads.find((r) => r.topicId === LOOP_TOPIC_ID) ?? reads[0];
  const mastery = lead?.mastery;
  const gaps = lead?.gaps ?? [];
  const topGap = gaps.find((g) => g.evidence.confirmed) ?? gaps[0];

  // The subject-card grid — built from the live reads, cool hues only.
  const subjects: SubjectCardModel[] = useMemo(
    () =>
      GRID_TOPICS.map((tid) => {
        const info = topicInfo(tid);
        const r = reads.find((x) => x.topicId === tid);
        const band = r?.mastery.reading.band ?? 'not-started';
        return {
          topicId: tid,
          subjectName: info.subjectName,
          code: subjectCode(info.subjectId),
          accent: info.accent,
          focus: info.name,
          caption: r ? capitalise(r.mastery.plainLanguage) : 'Let us find where to start.',
          progress: bandFill(band),
          progressLabel: r?.mastery.reading.independent ? 'On your own' : 'Where you are now',
          independent: r?.mastery.reading.independent,
        };
      }),
    [reads],
  );

  // A calm four-up read of the week — derived from the live reads, never a mark.
  const observed = reads.reduce((n, r) => n + r.mastery.observationCount, 0);
  const independentTopics = reads.filter((r) => r.mastery.reading.independent).length;
  const focuses = reads.reduce(
    (n, r) => n + r.gaps.filter((g) => g.evidence.confirmed).length,
    0,
  );

  return (
    <SurfaceShell
      breadcrumb={[{ label: 'Learning', href: '/student' }, { label: 'Today' }]}
      eyebrow="Today"
      title="Here is your next step"
      meta={[
        { value: 2, label: 'subjects in motion' },
        { value: observed, label: 'pieces of your own work' },
        { label: 'no marks, ever' },
      ]}
      dockIntro="One clear thing to do next, and why it matters. Ask me to explain where you are stuck, or to make it shorter."
      dockChips={['Why this next', 'Make it 10 minutes', 'I am stuck — help me']}
      aside={
        phase === 'ready' ? (
          <>
            <IgniteCard
              when="The goal"
              who={
                independentTopics > 0
                  ? `${independentTopics} ${independentTopics === 1 ? 'topic' : 'topics'} you can now do on your own`
                  : 'One unaided win away from the spark'
              }
              detail="The green spark is a real, unaided demonstration — no hints, verified across attempts. That is what we are building toward."
            />

            <Panel title="What to focus on" meta={<Tag tone="info"><span className="dot" />{focuses || 1}</Tag>}>
              <p className="caption" style={{ marginBottom: 12 }}>
                Focuses, not failings — naming one is how we close it.
              </p>
              <FlagRow
                flag={{
                  icon: 'target',
                  title: topGap ? gapLabel(topGap.evidence.gapType) : 'Doing it on your own',
                  caption: topGap
                    ? plainGap(gapLabel(topGap.evidence.gapType))
                    : 'You are close — the next unaided try is the one that counts.',
                  href: `/student/topic/${LOOP_TOPIC_ID}`,
                }}
              />
              <FlagRow
                flag={{
                  icon: 'clock',
                  title: 'A short review is due',
                  caption: 'Something you had solid is starting to fade — a quick touch-up keeps it.',
                  href: '/student/mocks',
                }}
              />
              <Link href="/student/progress" className="btn btn-secondary btn-sm btn-block" style={{ marginTop: 16 }}>
                See your full progress
              </Link>
            </Panel>

            <Panel title="Today" meta={<span className="overline">your plan</span>}>
              <SchedRow row={{ t: 'Now', title: `${topic.subjectName}`, caption: `${topic.name} — practise on your own.` }} />
              <SchedRow row={{ t: 'Next', title: 'A short check', caption: 'Five quick items, when you are ready.' }} />
              <SchedRow row={{ t: 'Later', title: 'Review', caption: 'Bring back one topic that is fading.' }} />
            </Panel>

            <HandnotePanel>one unaided win today — that is all it takes to light the spark</HandnotePanel>
          </>
        ) : undefined
      }
    >
      {phase !== 'ready' ? (
        <ReadStates phase={phase} />
      ) : (
        <>
          <StatMatrix
            stats={[
              { label: 'On your own', value: independentTopics, delta: independentTopics > 0 ? 'the green spark' : 'almost there', deltaDir: independentTopics > 0 ? 'up' : 'flat' },
              { label: 'In motion', value: 2, suffix: '', delta: 'subjects this week', deltaDir: 'flat' },
              { label: 'Your evidence', value: observed, delta: 'pieces of work', deltaDir: 'up' },
              { label: 'Focuses', value: focuses || 1, delta: 'naming closes them', deltaDir: 'flat' },
            ]}
          />

          <section className="next-step-hero reveal reveal-3">
            <div className="row-between" style={{ alignItems: 'flex-start' }}>
              <div>
                <p className="overline" style={{ margin: 0 }}>
                  {topic.subjectName}
                </p>
                <h2 className="display-sm" style={{ margin: '6px 0 0', fontSize: 28 }}>
                  Practise {topic.name} on your own
                </h2>
              </div>
              <Tag tone="info">Next step</Tag>
            </div>

            <div className="why-grid" style={{ marginTop: 'var(--space-5)' }}>
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

            <div className="rec-actions" style={{ marginTop: 'var(--space-5)' }}>
              <Link href="/student/practice" className="btn btn-accent btn-sm">
                Start practising
                <Icon name="arrow-right" size="sm" />
              </Link>
              <Link href="/student/learn" className="btn btn-secondary btn-sm">
                Learn it first
              </Link>
              <Link href={`/student/topic/${LOOP_TOPIC_ID}`} className="btn btn-ghost btn-sm">
                Where am I on this?
              </Link>
            </div>
          </section>

          <section>
            <SecHead title="Your subjects" meta={<span className="overline">where you are</span>} />
            <SubjectGrid subjects={subjects} />
          </section>

          <section>
            <p className="body-sm muted" style={{ maxWidth: 560 }}>
              {mastery
                ? `${capitalise(mastery.plainLanguage)} on ${topic.name}. No scores, no marks — just what you can do, and the next clear step toward doing it unaided.`
                : 'Let us find where to start — a short diagnostic seeds your map, and from then on this grows from your real work.'}
            </p>
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
    'Support dependency': 'You have it with a nudge — now we fade the nudge.',
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
