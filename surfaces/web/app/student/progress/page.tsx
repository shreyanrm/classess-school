'use client';

import { useEffect, useMemo, useState } from 'react';
import { Icon, SpotlightCard, SuggestionChip, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ReadStates } from '../../_components/ReadStates';
import { MasteryConclusion } from '../../_components/MasteryConclusion';
import { useDeepReads, type TopicRead } from '@/lib/useDeepReads';
import { useEmit } from '@/lib/useEmit';
import { EVENT_PURPOSE } from '@/lib/events';
import { BAND_SHORT, gapLabel } from '@/lib/engine';
import {
  topicInfo,
  topicsForSubject,
  MATH_SUBJECT_ID,
  PHYS_SUBJECT_ID,
} from '@/lib/loopData';

/**
 * Progress — the knowledge profile in plain language: what you can do on your
 * own versus with support. Read gateway-first from the SPINE (mastery/gaps),
 * falling back to the TS engine only on degrade; never a number, never the
 * formula. Every conclusion opens an EvidenceDrawer. Queryable in plain
 * language; the ignite marks a genuine, independent mastery moment.
 */

const PROFILE_TOPICS = [
  ...topicsForSubject(MATH_SUBJECT_ID).map((t) => t.id),
  ...topicsForSubject(PHYS_SUBJECT_ID).map((t) => t.id),
];

type Query = 'weakest' | 'unlocks' | 'independent' | null;

export default function ProgressPage() {
  const { phase, reads, source } = useDeepReads(PROFILE_TOPICS);
  const { emit } = useEmit();
  const [query, setQuery] = useState<Query>(null);

  // Only show topics we have evidence on (the spine omits the rest too).
  const rows = useMemo(() => reads.filter((r) => r.mastery.observationCount > 0), [reads]);
  const independent = rows.filter((r) => r.mastery.reading.independent);
  const withSupport = rows.filter((r) => !r.mastery.reading.independent);
  const weakest = [...rows].sort(
    (a, b) => a.mastery.reading.composite - b.mastery.reading.composite,
  )[0];

  // The surface viewed event — attributed, consent-stamped (learning purpose).
  useEffect(() => {
    if (phase === 'ready') emit({ type: 'surface.viewed', purpose: EVENT_PURPOSE.learning, payload: { surface: 'student.progress', source } });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  function ask(q: Exclude<Query, null>) {
    setQuery(q);
    emit({ type: 'knowledge.queried', purpose: EVENT_PURPOSE.learning, payload: { query: q } });
  }

  return (
    <SurfaceShell
      eyebrow="Your progress"
      title="What you can do"
      dockIntro="This is your profile in plain language — what you can do on your own, and what still leans on support. Ask me anything about it."
      dockChips={['What am I weakest at', 'What unlocks identities', 'What can I do on my own']}
    >
      {phase !== 'ready' ? (
        <ReadStates phase={phase} />
      ) : rows.length === 0 ? (
        <div className="empty">
          <Icon name="target" size="lg" className="glyph" />
          <h4 className="body">Let us find where to start</h4>
          <p>
            There is no evidence on your map yet. A short diagnostic seeds it, and from then on this
            view grows from your real attempts.
          </p>
        </div>
      ) : (
        <>
          <section className="stack">
            <p className="overline">Ask about your progress</p>
            <div className="home-chips" style={{ justifyContent: 'flex-start' }}>
              <SuggestionChip spark onClick={() => ask('weakest')}>
                What am I weakest at
              </SuggestionChip>
              <SuggestionChip spark onClick={() => ask('unlocks')}>
                What unlocks the next topic
              </SuggestionChip>
              <SuggestionChip spark onClick={() => ask('independent')}>
                What can I do on my own
              </SuggestionChip>
            </div>
            {query ? (
              <SpotlightCard>
                <p className="overline" style={{ margin: 0 }}>
                  Answer
                </p>
                <p className="body" style={{ marginTop: 'var(--space-3)' }}>
                  {answerFor(query, { weakest, independent: independent.length })}
                </p>
              </SpotlightCard>
            ) : null}
          </section>

          <section className="stack">
            <p className="overline">You can do these on your own</p>
            {independent.length === 0 ? (
              <p className="body-sm quiet">
                Not yet — but you are close on at least one. The green spark appears the moment you
                do one unaided.
              </p>
            ) : (
              independent.map((r) => (
                <SpotlightCard key={r.topicId}>
                  <MasteryConclusion
                    topicName={topicInfo(r.topicId).name}
                    mastery={r.mastery}
                    gaps={r.gaps}
                    source={r.source}
                  />
                  <div className="row" style={{ marginTop: 'var(--space-2)' }}>
                    <Tag tone="success">On your own</Tag>
                  </div>
                </SpotlightCard>
              ))
            )}
          </section>

          <section className="stack">
            <p className="overline">These still lean on support</p>
            {withSupport.length === 0 ? (
              <p className="body-sm quiet">Nothing here right now.</p>
            ) : (
              withSupport.map((r) => (
                <SpotlightCard key={r.topicId}>
                  <MasteryConclusion
                    topicName={topicInfo(r.topicId).name}
                    mastery={r.mastery}
                    gaps={r.gaps}
                    source={r.source}
                  />
                  <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
                    {topicInfo(r.topicId).subjectName} · {BAND_SHORT[r.mastery.reading.band]}
                    {r.mastery.revisionDue ? ' · revision is due' : ''}
                  </p>
                </SpotlightCard>
              ))
            )}
          </section>
        </>
      )}
    </SurfaceShell>
  );
}

function answerFor(
  q: Exclude<Query, null>,
  ctx: { weakest?: TopicRead; independent: number },
): string {
  switch (q) {
    case 'weakest': {
      if (!ctx.weakest) return 'You do not have a clear weak spot yet — keep practising and this will sharpen.';
      const gap = ctx.weakest.gaps.find((g) => g.evidence.confirmed) ?? ctx.weakest.gaps[0];
      const name = topicInfo(ctx.weakest.topicId).name;
      return `Right now, ${name} needs the most attention${
        gap ? ` — the focus is ${gapLabel(gap.evidence.gapType).toLowerCase()}` : ''
      }. That is where a little practice goes furthest.`;
    }
    case 'unlocks':
      return 'Doing Trigonometric Ratios on your own unlocks Trigonometric Identities — the identities are built on the ratios, so the ratios come first.';
    case 'independent':
      return ctx.independent > 0
        ? `You can do ${ctx.independent} ${ctx.independent === 1 ? 'topic' : 'topics'} on your own so far. Each one is a real, unaided demonstration — not a lucky score.`
        : 'You are close on at least one topic. The moment you do one unaided, it moves into "on your own".';
  }
}
