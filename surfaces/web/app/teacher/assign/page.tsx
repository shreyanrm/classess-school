'use client';

import { useMemo, useState } from 'react';
import { Button, Icon, Input, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { EvidenceDrawer } from '../../_components/EvidenceDrawer';
import { SourceNote } from '../../_components/SourceNote';
import {
  CLASS_LABEL,
  MATH_SUBJECT_ID,
  PHYS_SUBJECT_ID,
  topicsForSubject,
  type TopicInfo,
} from '@/lib/loopData';
import { pushAssignedCheck } from '@/lib/workData';
import { useClassInsights } from '@/lib/useClassInsights';
import { useEmit } from '@/lib/useEmit';
import { EVENT_PURPOSE } from '@/lib/events';

/**
 * Assign a quick check — blueprint-lite. The teacher picks ontology topics
 * (mapped, never hard-coded to a board), sets a count, and the system PREPARES
 * a check. The Approval control is the gate: assigning is consequential, so it
 * never auto-sends — it waits for an explicit human decision (permission ladder:
 * Prepare -> Execute-with-permission). Agents hold no credentials.
 */

type Phase = 'compose' | 'prepared' | 'sent';

const SUBJECTS = [
  { id: MATH_SUBJECT_ID, name: 'Mathematics' },
  { id: PHYS_SUBJECT_ID, name: 'Physics' },
];

export default function AssignPage() {
  const [subjectId, setSubjectId] = useState<string>(MATH_SUBJECT_ID);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [count, setCount] = useState(5);
  const [phase, setPhase] = useState<Phase>('compose');

  // Gateway-first read of the class gaps (engine fallback on degrade) — so the
  // topics that carry confirmed gaps can be badged and mapped against.
  const { insights, source } = useClassInsights();
  const { emit } = useEmit();
  const gapTopicIds = useMemo(
    () =>
      new Set(
        (insights?.reads ?? [])
          .filter((r) => r.confirmedGaps.length > 0)
          .map((r) => r.topic.id),
      ),
    [insights],
  );

  const topics: TopicInfo[] = topicsForSubject(subjectId);

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    setPhase('compose');
  }

  const selectedTopics = topics.filter((t) => selected.has(t.id));
  const canPrepare = selected.size > 0;

  return (
    <SurfaceShell
      eyebrow={CLASS_LABEL}
      title="Assign a quick check"
      dockIntro="Pick the topics and I will prepare a check mapped to the ontology. Nothing is sent until you approve it — assigning is consequential, so it always waits for you."
      dockChips={['Map this to last week’s gaps', 'Make it shorter', 'Add one harder item']}
    >
      <section className="stack">
        <p className="overline">1 · Choose the subject</p>
        <div className="ladder" role="group" aria-label="Subject" style={{ maxWidth: 360 }}>
          {SUBJECTS.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`ladder-rung${subjectId === s.id ? ' active' : ''}`}
              onClick={() => {
                setSubjectId(s.id);
                setPhase('compose');
              }}
            >
              {s.name}
            </button>
          ))}
        </div>
      </section>

      <section className="stack">
        <p className="overline">2 · Map to topics (blueprint-lite)</p>
        <p className="caption quiet">
          Topics are drawn from the curriculum graph for {CLASS_LABEL} — mapped, never hard-coded to
          a board. Pick what this check assesses.
        </p>
        <div className="cols-2">
          {topics.map((t) => {
            const on = selected.has(t.id);
            return (
              <button
                key={t.id}
                type="button"
                className={`cell${on ? '' : ''}`}
                onClick={() => toggle(t.id)}
                style={{
                  textAlign: 'left',
                  cursor: 'pointer',
                  borderColor: on ? 'var(--accent)' : undefined,
                }}
                aria-pressed={on}
              >
                <div className="row-between">
                  <span className="body-sm">{t.name}</span>
                  {on ? <Icon name="check" size="sm" /> : <Icon name="plus" size="sm" />}
                </div>
                <div className="row-between" style={{ marginTop: 2 }}>
                  <span className="caption muted">{t.chapterName}</span>
                  {gapTopicIds.has(t.id) ? <Tag tone="warning">confirmed gap</Tag> : null}
                </div>
              </button>
            );
          })}
        </div>
        <SourceNote source={source} />
      </section>

      <section className="stack">
        <p className="overline">3 · Length</p>
        <div className="row" style={{ gap: 'var(--space-3)', maxWidth: 220 }}>
          <Button variant="ghost" size="sm" iconOnly aria-label="Fewer items" onClick={() => setCount((c) => Math.max(2, c - 1))}>
            <Icon name="minus" size="sm" />
          </Button>
          <Input
            type="number"
            value={count}
            aria-label="Number of items"
            onChange={(e) => setCount(Math.max(2, Math.min(20, Number(e.target.value) || 2)))}
            style={{ width: 72, textAlign: 'center' }}
          />
          <Button variant="ghost" size="sm" iconOnly aria-label="More items" onClick={() => setCount((c) => Math.min(20, c + 1))}>
            <Icon name="plus" size="sm" />
          </Button>
          <span className="caption muted">items</span>
        </div>
      </section>

      <section>
        <SpotlightCard padLg>
          <div className="row-between" style={{ alignItems: 'flex-start' }}>
            <div>
              <p className="overline" style={{ margin: 0 }}>
                The approval control
              </p>
              <h3 className="body-lg" style={{ margin: '4px 0 0' }}>
                {phase === 'sent' ? 'Check assigned to Class 10-B' : 'Quick check, ready to prepare'}
              </h3>
            </div>
            <Tag tone={phase === 'sent' ? 'success' : 'info'}>
              {phase === 'compose' ? 'Not yet prepared' : phase === 'prepared' ? 'Prepared — awaiting approval' : 'Assigned'}
            </Tag>
          </div>

          <p className="body-sm muted" style={{ marginTop: 'var(--space-3)' }}>
            {selectedTopics.length === 0
              ? 'Select at least one topic to prepare a check.'
              : `${count} items across ${selectedTopics.map((t) => t.name).join(', ')}.`}
          </p>

          {phase !== 'compose' ? (
            <EvidenceDrawer
              evidence={[
                'Generated content passes the confidence gate (generate-and-verify) before it is served.',
                'Each item is mapped to a curriculum topic node — board-agnostic.',
                'Independent vs supported is captured per attempt when students respond.',
              ]}
              whySeeing="Assigning is consequential (it publishes work to learners), so it sits at Prepare and waits for your explicit approval."
            />
          ) : null}

          <div className="divider" />

          {phase === 'compose' ? (
            <div className="rec-actions">
              <Button variant="primary" size="sm" disabled={!canPrepare} onClick={() => setPhase('prepared')}>
                Prepare the check
                <Icon name="arrow-right" size="sm" />
              </Button>
              <span className="caption muted">Preparing does not send anything.</span>
            </div>
          ) : phase === 'prepared' ? (
            <div className="rec-actions">
              <Button
                variant="accent"
                size="sm"
                onClick={() => {
                  // The explicit human approval is what publishes work to learners.
                  // It appends to the shared work list so the check appears in the
                  // student inbox (the visible Student <-> Teacher loop), and emits
                  // an attributed, consent-stamped `assignment.created` audit event.
                  pushAssignedCheck({
                    topicIds: selectedTopics.map((t) => t.id),
                    itemCount: count,
                  });
                  void emit({
                    type: 'assignment.created',
                    purpose: EVENT_PURPOSE.teaching,
                    payload: {
                      surface: 'teacher.assign',
                      topicIds: selectedTopics.map((t) => t.id),
                      itemCount: count,
                      approved: true,
                    },
                  });
                  setPhase('sent');
                }}
              >
                Approve and assign
              </Button>
              <Button variant="secondary" size="sm" onClick={() => setPhase('compose')}>
                Adjust
              </Button>
              <span className="caption muted">
                Nothing is sent until you approve. You hold the authority.
              </span>
            </div>
          ) : (
            <div className="rec-actions">
              <span className="body-sm">
                Assigned to {CLASS_LABEL}. Responses will flow back as attempt events and update the
                live read.
              </span>
              <Button variant="ghost" size="sm" onClick={() => setPhase('compose')}>
                Assign another
              </Button>
            </div>
          )}
        </SpotlightCard>
      </section>
    </SurfaceShell>
  );
}
