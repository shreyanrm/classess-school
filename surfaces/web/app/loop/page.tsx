'use client';

import { useMemo, useState } from 'react';
import {
  Button,
  ConfidenceBand,
  IgniteDot,
  SpotlightCard,
  Tag,
  type Confidence,
} from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { DimensionBars } from '../_components/DimensionBars';
import { GapChips } from '../_components/GapChips';
import { EvidenceDrawer } from '../_components/EvidenceDrawer';
import { SavedAffordance } from '../_components/SavedAffordance';
import { useEmit } from '@/lib/useEmit';
import { EVENT_PURPOSE } from '@/lib/events';
import {
  computeMastery,
  detectGaps,
  BAND_SHORT,
  gapLabel,
  type EngineEvent,
} from '@/lib/engine';
import {
  CURRENT_STUDENT,
  EDGES,
  LOOP_TOPIC_ID,
  SCENARIO_NOW,
  liveEventId,
  topicInfo,
} from '@/lib/loopData';

/* ============================================================================
   /loop — the live, in-browser Student <-> Teacher cycle.

   Everything here runs through lib/engine.ts (a faithful port of the spine
   intelligence engine) over real attempt events. Nothing is faked: the mastery
   reading, the six dimensions, the gap classification, and the band all come
   from the engine replaying the event list this page builds as you click.

   The cycle:
     1  teacher assigns a quick check on a Trigonometry topic
     2  student attempts it — a control toggles independent vs supported
     3  an attempt event is emitted (immutable, append-only)
     4  mastery (six dimensions) + gap (one of ten) update LIVE
     5  an intervention is recommended — evidence/confidence/owner/consequence,
        with Approve / Adjust / Decline; it NEVER auto-fires
     6  the student reassesses unaided
     7  mastery updates on the fresh evidence
     8  the teacher view reflects it
   ============================================================================ */

type Stage = 'assign' | 'attempt' | 'classify' | 'intervene' | 'reassess' | 'teacher';

const STAGES: ReadonlyArray<{ id: Stage; label: string }> = [
  { id: 'assign', label: 'Assign' },
  { id: 'attempt', label: 'Attempt' },
  { id: 'classify', label: 'Mastery + gap' },
  { id: 'intervene', label: 'Intervene' },
  { id: 'reassess', label: 'Reassess unaided' },
  { id: 'teacher', label: 'Teacher sees it' },
];

type Decision = 'pending' | 'approved' | 'adjusting' | 'declined';

const TOPIC = topicInfo(LOOP_TOPIC_ID);
const SUBJECT = CURRENT_STUDENT.ref;

/** Build a fresh attempt event at a given offset from the scenario clock. */
function buildAttempt(opts: {
  independent: boolean;
  correct: boolean;
  score: number;
  daysAgo: number;
}): EngineEvent {
  return {
    event_id: liveEventId(),
    occurred_at: new Date(SCENARIO_NOW - opts.daysAgo * 86_400_000).toISOString(),
    canonical_uuid: SUBJECT,
    type: 'attempt.recorded',
    payload: {
      attempt_id: liveEventId(),
      ontology: { topic_id: LOOP_TOPIC_ID },
      mode: opts.independent ? 'independent' : 'supported',
      assistance_level: opts.independent ? 'Independent' : 'Coach',
      correct: opts.correct,
      score: opts.score,
      difficulty: 0.55,
      time_taken_ms: opts.independent ? 64_000 : 58_000,
      attempt_number: 1,
    },
  };
}

export default function LoopPage() {
  // The append-only event log this demo grows as the cycle runs.
  const [events, setEvents] = useState<EngineEvent[]>([]);
  const [stage, setStage] = useState<Stage>('assign');
  const [supported, setSupported] = useState(true);
  const [decision, setDecision] = useState<Decision>('pending');
  const [reassessOutcome, setReassessOutcome] = useState<'unknown' | 'transferred'>('unknown');

  // The live event seam: a real loop attempt is emitted (best-effort) to the
  // immutable platform.events store. It never blocks the cycle; on no-database
  // it stays on the local store and the affordance reads "kept on this device".
  const { saved, savedNote, emit } = useEmit();

  const asof = SCENARIO_NOW;

  // The engine reads, recomputed on every event change. Deterministic.
  const mastery = useMemo(
    () => computeMastery(events, SUBJECT, LOOP_TOPIC_ID, asof),
    [events, asof],
  );
  const gaps = useMemo(
    () => detectGaps(events, SUBJECT, LOOP_TOPIC_ID, EDGES, asof, undefined, mastery),
    [events, asof, mastery],
  );
  const confirmedGap = gaps.find((g) => g.evidence.confirmed);

  function reset() {
    setEvents([]);
    setStage('assign');
    setSupported(true);
    setDecision('pending');
    setReassessOutcome('unknown');
  }

  // 1 -> 2: assign the check (no events yet; just advance).
  function onAssign() {
    setStage('attempt');
  }

  // 2 -> 3: student attempts. Two supported successes then we are mid-trail.
  function onAttempt() {
    // Emit two supported successes (the classic support-dependency setup) or two
    // independent successes if the learner is working alone.
    const first = buildAttempt({ independent: !supported, correct: true, score: supported ? 0.9 : 0.95, daysAgo: 8 });
    const second = buildAttempt({ independent: !supported, correct: true, score: supported ? 0.85 : 1, daysAgo: 5 });
    setEvents((prev) => [...prev, first, second]);
    setStage('classify');
    // Emit the real attempt to the live, immutable event store — best-effort.
    void emit({
      type: 'attempt.recorded',
      purpose: EVENT_PURPOSE.learning,
      canonicalUuid: SUBJECT,
      payload: {
        topic_id: LOOP_TOPIC_ID,
        mode: supported ? 'supported' : 'independent',
        attempts: 2,
      },
    });
  }

  // 3: add one unaided attempt that exposes whether it transfers.
  function onProbeUnaided() {
    // An independent probe that fails when the learner was leaning on support.
    const probe = buildAttempt({
      independent: true,
      correct: !supported,
      score: supported ? 0.3 : 0.95,
      daysAgo: 3,
    });
    setEvents((prev) => [...prev, probe]);
    setStage('intervene');
  }

  // 5: reassess unaided after the intervention.
  function onReassess(transferred: boolean) {
    const fresh = buildAttempt({
      independent: true,
      correct: transferred,
      score: transferred ? 0.95 : 0.4,
      daysAgo: 0,
    });
    setEvents((prev) => [...prev, fresh]);
    setReassessOutcome(transferred ? 'transferred' : 'unknown');
    setStage('teacher');
  }

  const masteryConfidence: Confidence =
    mastery.observationCount >= 3 ? 'high' : mastery.observationCount === 2 ? 'middle' : 'low';

  return (
    <SurfaceShell
      eyebrow={`${TOPIC.subjectName} · ${TOPIC.chapterName}`}
      title="The live loop"
      dockIntro="This runs the whole Student to Teacher cycle in your browser. Every reading you see is computed live by the same engine the spine uses — no mock numbers. Drive it from the buttons, or ask me what each stage proves."
      dockChips={['Why is independence the keystone', 'Explain the gap that fired', 'What does a confirmed gap mean']}
    >
      <section className="stack reveal reveal-2" data-testid="loop-controls">
        <p className="overline">The cycle</p>
        <div className="loop-steps" data-testid="loop-steps">
          {STAGES.map((s, i) => {
            const idx = STAGES.findIndex((x) => x.id === stage);
            const cls = s.id === stage ? 'active' : i < idx ? 'done' : '';
            return (
              <span className="row" key={s.id} style={{ gap: 'var(--space-2)' }}>
                <span className={`loop-step ${cls}`}>
                  <span className="num">{i + 1}</span>
                  {s.label}
                </span>
                {i < STAGES.length - 1 ? <span className="loop-arrow" aria-hidden="true">→</span> : null}
              </span>
            );
          })}
        </div>
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          <Button variant="ghost" size="sm" onClick={reset}>
            Restart the loop
          </Button>
        </div>
      </section>

      {/* The split: the cycle drivers on the left, the live engine read on the right. */}
      <div className="cols-2 reveal reveal-3" data-testid="loop-stage">
        {/* ----- The narrative / driver column ----- */}
        <SpotlightCard padLg>
          {stage === 'assign' ? (
            <div className="stack">
              <Tag tone="info">Teacher</Tag>
              <h3 className="body-lg" style={{ margin: 0 }}>
                Assign a quick check on {TOPIC.name}
              </h3>
              <p className="body-sm muted">
                A two-item check for {CURRENT_STUDENT.label}, mapped to the {TOPIC.subjectName} topic{' '}
                {TOPIC.name}. Nothing is sent until you choose to — this is the start of the loop.
              </p>
              <div className="rec-actions">
                <Button variant="primary" size="sm" onClick={onAssign}>
                  Assign the check
                </Button>
              </div>
            </div>
          ) : null}

          {stage === 'attempt' ? (
            <div className="stack">
              <Tag tone="info">Student</Tag>
              <h3 className="body-lg" style={{ margin: 0 }}>
                {CURRENT_STUDENT.label} attempts the check
              </h3>
              <p className="body-sm muted">
                The single most important bit we capture is not whether it was right — it is{' '}
                <strong>how it was produced</strong>: alone, or with help.
              </p>
              <div>
                <p className="caption quiet" style={{ marginBottom: 'var(--space-2)' }}>
                  How is the student working?
                </p>
                <div className="ladder" role="group" aria-label="Independent or supported">
                  <button
                    type="button"
                    className={`ladder-rung${supported ? ' active' : ''}`}
                    onClick={() => setSupported(true)}
                  >
                    With support (Coach)
                  </button>
                  <button
                    type="button"
                    className={`ladder-rung evaluating${!supported ? ' active' : ''}`}
                    onClick={() => setSupported(false)}
                  >
                    Independent
                  </button>
                </div>
              </div>
              <div className="rec-actions">
                <Button variant="primary" size="sm" onClick={onAttempt}>
                  Record two attempts
                </Button>
              </div>
            </div>
          ) : null}

          {stage === 'classify' ? (
            <div className="stack">
              <Tag tone="info">Engine</Tag>
              <h3 className="body-lg" style={{ margin: 0 }}>
                Two events emitted — now probe the unaided case
              </h3>
              <p className="body-sm muted">
                The engine has weighed the evidence (see the live read). To tell &ldquo;can do with
                help&rdquo; apart from &ldquo;can do alone&rdquo;, the student now tries one item
                with no support.
              </p>
              <div className="rec-actions">
                <Button variant="primary" size="sm" onClick={onProbeUnaided}>
                  Try one unaided
                </Button>
                <SavedAffordance state={saved} note={savedNote} />
              </div>
            </div>
          ) : null}

          {stage === 'intervene' ? (
            <InterventionPanel
              decision={decision}
              setDecision={setDecision}
              gapRationale={confirmedGap?.evidence.rationale}
              gapLabel={confirmedGap ? gapLabel(confirmedGap.evidence.gapType) : 'support gap'}
              confidence={confirmedGap ? bandToConfidence(confirmedGap.evidence.confidence) : 'middle'}
              evidenceIds={confirmedGap?.evidence.evidenceEventIds ?? mastery.evidenceEventIds}
              onContinue={() => setStage('reassess')}
            />
          ) : null}

          {stage === 'reassess' ? (
            <div className="stack">
              <Tag tone="info">Student</Tag>
              <h3 className="body-lg" style={{ margin: 0 }}>
                Reassess unaided
              </h3>
              <p className="body-sm muted">
                Mastery only moves on fresh, unaided evidence. After the support faded, did it
                transfer? Choose an outcome to emit the reassessment.
              </p>
              <div className="rec-actions">
                <Button variant="accent" size="sm" onClick={() => onReassess(true)}>
                  It transferred — solved alone
                </Button>
                <Button variant="secondary" size="sm" onClick={() => onReassess(false)}>
                  Still leaning on support
                </Button>
              </div>
            </div>
          ) : null}

          {stage === 'teacher' ? (
            <div className="stack">
              <Tag tone="info">Teacher</Tag>
              <h3 className="body-lg" style={{ margin: 0 }}>
                The teacher view reflects it
              </h3>
              <p className="body-sm muted">
                {reassessOutcome === 'transferred'
                  ? `${CURRENT_STUDENT.label} now demonstrates ${TOPIC.name} independently. The reading crossed into independent on fresh, unaided evidence — not a single lucky score.`
                  : `${CURRENT_STUDENT.label} still leans on support. The gap stays open and the next step is to fade the scaffold further. No false "secure" is shown.`}
              </p>
              {mastery.reading.independent ? (
                <div className="ignite-row">
                  <IgniteDot label="Independent mastery reached" />
                  <span className="body-sm">A genuine mastery moment — earned independently.</span>
                </div>
              ) : null}
              <div className="rec-actions">
                <Button variant="ghost" size="sm" onClick={reset}>
                  Run it again
                </Button>
              </div>
            </div>
          ) : null}
        </SpotlightCard>

        {/* ----- The live engine read column ----- */}
        <SpotlightCard padLg>
          <div className="row-between">
            <span className="overline" style={{ margin: 0 }}>
              Live read · {CURRENT_STUDENT.label}
            </span>
            <ConfidenceBand level={masteryConfidence} />
          </div>

          {mastery.observationCount === 0 ? (
            <div className="empty">
              <h4 className="body">No evidence yet</h4>
              <p>Assign the check and record an attempt to see the engine compute a reading live.</p>
            </div>
          ) : (
            <div className="stack">
              <div className="ignite-row" style={{ marginTop: 'var(--space-3)' }}>
                {mastery.reading.independent ? <IgniteDot label="Independent" /> : null}
                <span className="body-lg">{BAND_SHORT[mastery.reading.band]}</span>
              </div>
              <p className="caption quiet">
                Plain language for the learner: &ldquo;{mastery.plainLanguage}&rdquo;. The six
                dimensions below are the teacher-facing reasoning — never shown to the learner, and
                never a single number.
              </p>

              <div className="divider" />
              <p className="overline" style={{ margin: 0 }}>
                The six dimensions
              </p>
              <DimensionBars dimensions={mastery.reading.dimensions} />

              <div className="divider" />
              <p className="overline" style={{ margin: 0 }}>
                Gap classification
              </p>
              <GapChips gaps={gaps} emptyLabel="No gap — the evidence is clean so far" />

              <EvidenceDrawer
                evidence={evidenceLines(events)}
                whySeeing="Every reading above is computed by replaying exactly these attempt events — full lineage, nothing asserted without a path to its evidence."
              />
            </div>
          )}
        </SpotlightCard>
      </div>
    </SurfaceShell>
  );
}

// ---------------------------------------------------------------------------
// The intervention panel — the manage-by-exception primitive, scoped to the
// live gap. Never auto-fires: Approve / Adjust / Decline are explicit.
// ---------------------------------------------------------------------------
function InterventionPanel({
  decision,
  setDecision,
  gapRationale,
  gapLabel: gapName,
  confidence,
  evidenceIds,
  onContinue,
}: {
  decision: Decision;
  setDecision: (d: Decision) => void;
  gapRationale?: string;
  gapLabel: string;
  confidence: Confidence;
  evidenceIds: string[];
  onContinue: () => void;
}) {
  return (
    <div className="stack">
      <div className="row-between" style={{ alignItems: 'flex-start' }}>
        <div className="row" style={{ gap: 'var(--space-2)' }}>
          <Tag tone="info">Recommendation</Tag>
          <Tag tone="neutral">{gapName} gap</Tag>
        </div>
        <ConfidenceBand level={confidence} />
      </div>
      <h3 className="body-lg" style={{ margin: 0 }}>
        Fade the support with a scaffolded-autonomy task
      </h3>
      <p className="body-sm muted">
        {gapRationale ??
          'The student performs with help but has not yet demonstrated the same independently.'}
      </p>

      <div className="rec-meta">
        <div>
          <div className="k">Owner</div>
          <div className="v">You (Class 10-B teacher)</div>
        </div>
        <div>
          <div className="k">Permission ladder</div>
          <div className="v">Prepare — waits for your approval</div>
        </div>
        <div>
          <div className="k">Due</div>
          <div className="v">Before the next class</div>
        </div>
        <div>
          <div className="k">If ignored</div>
          <div className="v">Support dependency hardens; the student stays reliant on prompts.</div>
        </div>
      </div>

      <EvidenceDrawer
        evidence={evidenceIds.map((id) => `Attributed event ${id.slice(0, 8)}… in the lineage of this gap.`)}
        whySeeing="A gap was confirmed from at least two corroborating signals — never a single bad score."
      />

      <div className="divider" />

      {decision === 'pending' || decision === 'adjusting' ? (
        <div className="rec-actions">
          <Button variant="accent" size="sm" onClick={() => setDecision('approved')}>
            Approve
          </Button>
          <Button variant="secondary" size="sm" onClick={() => setDecision('adjusting')}>
            Adjust
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setDecision('declined')}>
            Decline
          </Button>
          {decision === 'adjusting' ? (
            <span className="caption muted">Adjust the task in the conversation, then approve when it fits.</span>
          ) : null}
        </div>
      ) : (
        <div className="rec-actions">
          <span className="body-sm">
            {decision === 'approved'
              ? 'Approved. The task is prepared and waiting for you to run it — nothing fired on its own.'
              : 'Declined. Set aside for now.'}
          </span>
          <Button variant="primary" size="sm" onClick={onContinue}>
            Continue to reassessment
          </Button>
        </div>
      )}
    </div>
  );
}

function bandToConfidence(confidence: number): Confidence {
  if (confidence >= 0.75) return 'high';
  if (confidence >= 0.5) return 'middle';
  return 'low';
}

function evidenceLines(events: EngineEvent[]): string[] {
  return events
    .filter((e): e is Extract<EngineEvent, { type: 'attempt.recorded' }> => e.type === 'attempt.recorded')
    .map((e, i) => {
      const a = e.payload;
      const mode = a.mode === 'independent' ? 'unaided' : `with support (${a.assistance_level})`;
      const result = a.correct ? 'correct' : 'incomplete';
      const pct = Math.round((a.score ?? (a.correct ? 1 : 0)) * 100);
      return `Attempt ${i + 1}: ${result} at ${pct}%, ${mode}.`;
    });
}
