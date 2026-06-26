'use client';

import { useMemo, useState } from 'react';
import { Button, ConfidenceBand, Icon, Input, Matrix, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { StatCell } from '../../_components/StatCell';
import { ReadStates } from '../../_components/ReadStates';
import { EvidenceDrawer } from '../../_components/EvidenceDrawer';
import { SourceNote } from '../../_components/SourceNote';
import { QuestionPaperPreview } from '../../_components/QuestionPaperPreview';
import { useVizData } from '@/lib/useVizData';
import {
  CLASS_LABEL,
  MATH_SUBJECT_ID,
  PHYS_SUBJECT_ID,
  topicsForSubject,
  type TopicInfo,
} from '@/lib/loopData';
import { pushAssignedCheck } from '@/lib/workData';
import { useClassInsights } from '@/lib/useClassInsights';
import { useGenerator } from '@/lib/useGenerator';
import { useEmit } from '@/lib/useEmit';
import { EVENT_PURPOSE } from '@/lib/events';
import type { Worksheet } from '@/lib/generate';

/**
 * Assign a quick check — blueprint-lite. The teacher picks ontology topics
 * (mapped, never hard-coded to a board), sets a count, and the system PREPARES
 * a check. The Approval control is the gate: assigning is consequential, so it
 * never auto-sends — it waits for an explicit human decision (permission ladder:
 * Prepare -> Execute-with-permission). Agents hold no credentials.
 */

type Phase = 'compose' | 'prepared' | 'sent';
type Mode = 'check' | 'paper';

const SUBJECTS = [
  { id: MATH_SUBJECT_ID, name: 'Mathematics' },
  { id: PHYS_SUBJECT_ID, name: 'Physics' },
];

export default function AssignPage() {
  const [subjectId, setSubjectId] = useState<string>(MATH_SUBJECT_ID);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [count, setCount] = useState(5);
  const [phase, setPhase] = useState<Phase>('compose');
  const [mode, setMode] = useState<Mode>('check');
  const [paperApproved, setPaperApproved] = useState(false);
  // The prepared exam paper + answer key reads gateway-first (seed fallback).
  const viz = useVizData(['paperPreview']);

  // Gateway-first read of the class gaps (engine fallback on degrade) — so the
  // topics that carry confirmed gaps can be badged and mapped against. The same
  // read carries the five designed states for the surface (one truth, reused).
  const { insights, source, phase: readPhase, refresh } = useClassInsights();
  // The worksheet generator, gateway-first (SourceNote degrade). Preparing the
  // check generates a VERIFIED worksheet inline; assigning it raises the gate.
  const worksheet = useGenerator<Worksheet>('worksheet');
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
  const gapTopicCount = topics.filter((t) => gapTopicIds.has(t.id)).length;

  return (
    <SurfaceShell
      eyebrow={CLASS_LABEL}
      title="Assign a quick check"
      breadcrumb={[
        { label: 'School', href: '/' },
        { label: 'Grade 10', href: '/teacher' },
        { label: 'Assign' },
      ]}
      meta={[
        { value: topics.length, label: 'topics in the graph' },
        { value: selected.size, label: 'selected' },
        { label: 'nothing sends until you approve' },
      ]}
      tabs={[
        { label: 'Overview', href: '/teacher' },
        { label: 'Plan', href: '/teacher/plan' },
        { label: 'Assign', active: true },
        { label: 'Class insights', href: '/teacher/insights' },
      ]}
      dockIntro="Pick the topics and I will prepare a check mapped to the ontology. Nothing is sent until you approve it — assigning is consequential, so it always waits for you."
      dockChips={['Map this to last week’s gaps', 'Make it shorter', 'Add one harder item']}
    >
      {/* Composing is offline-capable (the shell shows the calm offline banner)
          and degrades gracefully, so offline is NOT a dead end — only the read's
          loading/error/permission-denied gate the surface. */}
      {readPhase === 'loading' || readPhase === 'error' || readPhase === 'permission-denied' ? (
        <ReadStates phase={readPhase} onRetry={refresh} />
      ) : (
      <>
      <div className="segmented" role="tablist" aria-label="What to prepare">
        <button type="button" role="tab" aria-selected={mode === 'check'} className={mode === 'check' ? 'active' : ''} onClick={() => setMode('check')}>
          Quick check
        </button>
        <button type="button" role="tab" aria-selected={mode === 'paper'} className={mode === 'paper' ? 'active' : ''} onClick={() => setMode('paper')}>
          Exam paper
        </button>
      </div>

      {mode === 'paper' ? (
        <section className="stack">
          <div className="sec-head">
            <h3 className="h3" style={{ margin: 0 }}>Question paper</h3>
            <span className="overline">section-headed preview · answer key</span>
          </div>
          <p className="caption quiet">
            The prepared exam paper, laid out as a document with its section headings, numbered
            questions, and point values. Switch to the Answer key for the model answers — your key,
            never shown to a learner. The paper waits for your approval before it can be set.
          </p>
          <QuestionPaperPreview
            data={{ ...viz.data.paperPreview, approved: paperApproved || viz.data.paperPreview.approved }}
            source={viz.sourceByKind.paperPreview}
            onApprove={() => setPaperApproved(true)}
          />
        </section>
      ) : (
      <>
      <Matrix columns={3} className="reveal reveal-1">
        <StatCell label="Topics available" value={topics.length} delta="from the curriculum graph" tone="flat" />
        <StatCell
          label="Carry a confirmed gap"
          value={gapTopicCount}
          delta="prioritise these"
          tone={gapTopicCount > 0 ? 'down' : 'flat'}
        />
        <StatCell label="Selected" value={selected.size} delta={`${count} items per learner`} tone="up" />
      </Matrix>

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

          {phase === 'prepared' && worksheet.phase === 'ready' && worksheet.artifact ? (
            <div className="stack" style={{ gap: 'var(--space-2)', marginTop: 'var(--space-3)' }}>
              <div className="row-between" style={{ alignItems: 'flex-start' }}>
                <p className="overline" style={{ margin: 0 }}>
                  Verified worksheet — {worksheet.artifact.topicName}
                </p>
                <ConfidenceBand level={worksheet.confidence} />
              </div>
              {worksheet.artifact.items.map((it) => (
                <div key={it.index} className="row-between cell" style={{ textAlign: 'left' }}>
                  <span className="body-sm">{it.index}. {it.prompt}</span>
                  <ConfidenceBand level={it.confidence} />
                </div>
              ))}
              <SourceNote source={worksheet.source} />
            </div>
          ) : null}

          {phase === 'prepared' && worksheet.phase === 'loading' ? (
            <p className="caption quiet" role="status" style={{ marginTop: 'var(--space-3)' }}>
              Generating and verifying the worksheet…
            </p>
          ) : null}

          {phase === 'prepared' && worksheet.phase === 'error' ? (
            <p className="caption" role="status" style={{ marginTop: 'var(--space-3)', color: 'var(--danger)' }}>
              The generator could not be reached. The check is still prepared; try regenerating.
            </p>
          ) : null}

          {phase !== 'compose' ? (
            <EvidenceDrawer
              evidence={[
                'Every item passes the confidence gate (generate-and-verify) individually before it is shown.',
                'Each item is mapped to a curriculum topic node — board-agnostic.',
                'Independent vs supported is captured per attempt when students respond.',
              ]}
              whySeeing="Assigning is consequential (it publishes work to learners), so it sits at Prepare and waits for your explicit approval."
            />
          ) : null}

          <div className="divider" />

          {phase === 'compose' ? (
            <div className="rec-actions">
              <Button
                variant="primary"
                size="sm"
                disabled={!canPrepare}
                onClick={() => {
                  setPhase('prepared');
                  // Generate-and-verify the worksheet for the first selected topic.
                  worksheet.run({ topic: selectedTopics[0]!.id, count });
                }}
              >
                Prepare the check
                <Icon name="arrow-right" size="sm" />
              </Button>
              <span className="caption muted">Preparing generates a verified draft; it sends nothing.</span>
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
              <Button variant="secondary" size="sm" onClick={() => { setPhase('compose'); worksheet.reset(); }}>
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
      </>
      )}
      </>
      )}
    </SurfaceShell>
  );
}
