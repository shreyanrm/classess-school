'use client';

import { useMemo, useState } from 'react';
import { Button, Icon, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ReadStates } from '../../_components/ReadStates';
import { EvidenceDrawer } from '../../_components/EvidenceDrawer';
import { useSurfaceState } from '@/lib/useSurfaceState';
import { CLASS_LABEL, ROSTER, type Student } from '@/lib/loopData';

/**
 * d8 — Attendance intelligence. Fast, flexible capture: photo-scan, voice
 * roll-call, photo-roster, and absent-only. Every method ASSISTS — it proposes
 * a roll; the teacher CONFIRMS. Attendance is never finalised automatically
 * (permission ladder: propose -> human confirm). Risk flags (consecutive,
 * chronic) are shown calmly, as an early-warning read, never as misconduct.
 *
 * Offline is a designed state: capture works offline and syncs later.
 */

type Method = 'scan' | 'voice' | 'roster' | 'absent-only';
type Mark = 'present' | 'absent';
type Phase = 'capture' | 'proposed' | 'confirmed';

interface MethodInfo {
  id: Method;
  label: string;
  icon: 'grid' | 'spark' | 'book' | 'check';
  blurb: string;
}

const METHODS: MethodInfo[] = [
  { id: 'scan', label: 'Photo-scan', icon: 'grid', blurb: 'Photograph the room; a draft roll is proposed for you to confirm.' },
  { id: 'voice', label: 'Voice roll-call', icon: 'spark', blurb: 'Call the register aloud; I mark as you go, you confirm at the end.' },
  { id: 'roster', label: 'Photo-roster', icon: 'book', blurb: 'Tap each face on the roster grid. Manual is always first-class.' },
  { id: 'absent-only', label: 'Absent-only', icon: 'check', blurb: 'Everyone present by default; mark only the few who are away.' },
];

/** A calm, deterministic risk read per student — an early-warning signal. */
interface RiskInfo {
  kind: 'consecutive' | 'chronic';
  label: string;
  rationale: string;
}

const RISK: Record<string, RiskInfo> = {
  [ROSTER[3]!.ref]: {
    kind: 'consecutive',
    label: 'Away three days running',
    rationale: 'Marked absent the last three sessions. A short catch-up plan and a calm note home may help.',
  },
  [ROSTER[5]!.ref]: {
    kind: 'chronic',
    label: 'Attendance dipping',
    rationale: 'Below the comfortable range across recent weeks, with a post-lunch pattern. Worth watching, not a penalty.',
  },
};

export default function AttendancePage() {
  // The roster read carries the five designed states; capture works offline and
  // syncs later, so offline is a calm last-synced read, never a dead end.
  const { phase: readPhase, refresh } = useSurfaceState();
  const [method, setMethod] = useState<Method>('scan');
  const [phase, setPhase] = useState<Phase>('capture');
  const [marks, setMarks] = useState<Record<string, Mark>>({});

  /** Capture PROPOSES a roll. The teacher then edits and confirms it. */
  function proposeRoll() {
    const proposed: Record<string, Mark> = {};
    ROSTER.forEach((s, i) => {
      // A deterministic, illustrative proposal — never an auto-final read.
      proposed[s.ref] = method === 'absent-only' ? 'present' : i % 7 === 3 ? 'absent' : 'present';
    });
    setMarks(proposed);
    setPhase('proposed');
  }

  function toggle(ref: string) {
    setMarks((prev) => ({ ...prev, [ref]: prev[ref] === 'absent' ? 'present' : 'absent' }));
    if (phase === 'confirmed') setPhase('proposed');
  }

  const counts = useMemo(() => {
    const present = ROSTER.filter((s) => (marks[s.ref] ?? 'present') === 'present').length;
    return { present, absent: ROSTER.length - present };
  }, [marks]);

  const flagged = ROSTER.filter((s) => RISK[s.ref]);

  return (
    <SurfaceShell
      eyebrow={CLASS_LABEL}
      title="Attendance"
      dockIntro="Pick a capture method and I will propose the roll. You confirm it — attendance is never finalised on its own. I will flag consecutive and chronic patterns calmly, never as misconduct."
      dockChips={['Who has been away three days', 'Mark only the absent', 'Why is this flagged']}
    >
      {/* Capture is offline-capable (the shell shows the calm offline banner),
          so offline is NOT a dead end here — only loading/error/permission-denied
          gate the surface; everything else renders and syncs later. */}
      {readPhase === 'loading' || readPhase === 'error' || readPhase === 'permission-denied' ? (
        <ReadStates phase={readPhase} onRetry={refresh} />
      ) : (
      <>
      <section className="stack">
        <p className="overline">1 · Choose a capture method</p>
        <p className="caption quiet">
          Every method assists and proposes — you confirm. Manual marking is always available, and
          capture works offline, syncing when you reconnect.
        </p>
        <div className="cols-2">
          {METHODS.map((m) => {
            const on = method === m.id;
            return (
              <button
                key={m.id}
                type="button"
                className="cell"
                aria-pressed={on}
                onClick={() => {
                  setMethod(m.id);
                  setPhase('capture');
                  setMarks({});
                }}
                style={{ textAlign: 'left', cursor: 'pointer', borderColor: on ? 'var(--accent)' : undefined }}
              >
                <div className="row-between">
                  <span className="row" style={{ gap: 'var(--space-2)' }}>
                    <Icon name={m.icon} size="sm" />
                    <span className="body-sm">{m.label}</span>
                  </span>
                  {on ? <Icon name="check" size="sm" /> : null}
                </div>
                <div className="caption muted" style={{ marginTop: 4 }}>
                  {m.blurb}
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {flagged.length > 0 ? (
        <section className="stack">
          <p className="overline">Early-warning signals</p>
          <div className="stack" style={{ gap: 'var(--space-2)' }}>
            {flagged.map((s) => {
              const r = RISK[s.ref]!;
              return (
                <SpotlightCard key={s.ref}>
                  <div className="row-between" style={{ alignItems: 'flex-start' }}>
                    <div>
                      <div className="row" style={{ gap: 'var(--space-2)' }}>
                        <span className="body-sm">{s.label}</span>
                        <Tag tone={r.kind === 'consecutive' ? 'warning' : 'info'}>{r.label}</Tag>
                      </div>
                      <p className="caption muted" style={{ marginTop: 4, maxWidth: 520 }}>
                        {r.rationale}
                      </p>
                    </div>
                  </div>
                  <EvidenceDrawer
                    evidence={[
                      'Built from the append-only attendance record for this learner — opaque ref only, no personal data.',
                      'A pattern is flagged, never a single absence; conflicting signals (gate vs classroom) go to human review.',
                    ]}
                    whySeeing="Attendance is an early-warning read. This is shown so you can offer support — it is never treated as misconduct and never auto-escalates."
                  />
                </SpotlightCard>
              );
            })}
          </div>
        </section>
      ) : null}

      <section>
        <SpotlightCard padLg>
          <div className="row-between" style={{ alignItems: 'flex-start' }}>
            <div>
              <p className="overline" style={{ margin: 0 }}>
                The confirm control
              </p>
              <h3 className="body-lg" style={{ margin: '4px 0 0' }}>
                {phase === 'confirmed'
                  ? `Roll confirmed — ${counts.present} present, ${counts.absent} away`
                  : phase === 'proposed'
                    ? 'Proposed roll — yours to adjust and confirm'
                    : 'Ready to capture'}
              </h3>
            </div>
            <Tag tone={phase === 'confirmed' ? 'success' : phase === 'proposed' ? 'info' : 'neutral'}>
              {phase === 'capture' ? 'Not captured' : phase === 'proposed' ? 'Awaiting your confirm' : 'Confirmed'}
            </Tag>
          </div>

          {phase === 'capture' ? (
            <p className="body-sm muted" style={{ marginTop: 'var(--space-3)' }}>
              {METHODS.find((m) => m.id === method)!.blurb} Nothing is recorded until you confirm.
            </p>
          ) : (
            <div className="cols-2" style={{ marginTop: 'var(--space-3)' }}>
              {ROSTER.map((s: Student) => {
                const mark = marks[s.ref] ?? 'present';
                const away = mark === 'absent';
                return (
                  <button
                    key={s.ref}
                    type="button"
                    className="cell"
                    onClick={() => toggle(s.ref)}
                    aria-pressed={away}
                    style={{ textAlign: 'left', cursor: 'pointer', borderColor: away ? 'var(--danger)' : undefined }}
                  >
                    <div className="row-between">
                      <span className="body-sm">{s.label}</span>
                      <Tag tone={away ? 'danger' : 'success'}>{away ? 'Away' : 'Present'}</Tag>
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          <div className="divider" />

          {phase === 'capture' ? (
            <div className="rec-actions">
              <Button variant="primary" size="sm" onClick={proposeRoll}>
                Capture with {METHODS.find((m) => m.id === method)!.label.toLowerCase()}
                <Icon name="arrow-right" size="sm" />
              </Button>
              <span className="caption muted">Capturing proposes a roll; it records nothing.</span>
            </div>
          ) : phase === 'proposed' ? (
            <div className="rec-actions">
              <Button variant="accent" size="sm" onClick={() => setPhase('confirmed')}>
                Confirm the roll
              </Button>
              <Button variant="secondary" size="sm" onClick={() => setPhase('capture')}>
                Recapture
              </Button>
              <span className="caption muted">You hold the final word. Nothing is saved until you confirm.</span>
            </div>
          ) : (
            <div className="rec-actions">
              <span className="body-sm">
                Saved for {CLASS_LABEL}. Repeated absence will surface a calm catch-up plan, never an
                automatic penalty.
              </span>
              <Button variant="ghost" size="sm" onClick={() => setPhase('proposed')}>
                Adjust the roll
              </Button>
            </div>
          )}
        </SpotlightCard>
      </section>
      </>
      )}
    </SurfaceShell>
  );
}
