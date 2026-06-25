import { describe, it, expect } from 'vitest';
import {
  decideWatch,
  thresholdsForLevel,
  watchLevelFromPreference,
  type WatchObservation,
  type WatchInput,
} from '../vidyaWatch';

/** Build a run of observations on one hard step, spaced `gapMs` apart, ending at
 *  `now`. `interactedAt` indices carry an interaction; the rest are dwell ticks. */
function run(
  count: number,
  opts: { gapMs?: number; now?: number; hard?: boolean; step?: string; path?: string; interactedAt?: number[] } = {},
): { observations: WatchObservation[]; now: number } {
  const gapMs = opts.gapMs ?? 4_000;
  const now = opts.now ?? 100_000;
  const step = opts.step ?? 'p2';
  const path = opts.path ?? '/student/practice';
  const hard = opts.hard ?? true;
  const interactedAt = new Set(opts.interactedAt ?? []);
  const observations: WatchObservation[] = [];
  for (let i = 0; i < count; i++) {
    const at = now - (count - 1 - i) * gapMs;
    observations.push({ path, step, hard, interacted: interactedAt.has(i), at });
  }
  return { observations, now };
}

const ATTENTIVE = thresholdsForLevel('attentive');

describe('watchLevelFromPreference — the tunable derives from the existing boolean', () => {
  it('off only when proactive is explicitly false; default-on otherwise', () => {
    expect(watchLevelFromPreference(false)).toBe('off');
    expect(watchLevelFromPreference(true)).toBe('attentive');
    expect(watchLevelFromPreference(undefined)).toBe('attentive');
  });
});

describe('decideWatch — calm-first invariants', () => {
  it('never offers when the level is off', () => {
    const { observations, now } = run(8, { interactedAt: [0, 2, 4, 6] });
    expect(decideWatch({ level: 'off', observations, dismissals: [], now })).toBeNull();
  });

  it('stays calm on an empty or stale window', () => {
    expect(decideWatch({ level: 'attentive', observations: [], dismissals: [], now: 0 })).toBeNull();
    // All observations older than the window are ignored.
    const stale = run(4, { now: ATTENTIVE.windowMs + 50_000, gapMs: 1_000 });
    const allStale: WatchInput = {
      level: 'attentive',
      observations: stale.observations.map((o) => ({ ...o, at: 0 })),
      dismissals: [],
      now: ATTENTIVE.windowMs + 50_000,
    };
    expect(decideWatch(allStale)).toBeNull();
  });

  it('never offers on a step the page did not mark HARD', () => {
    const { observations, now } = run(6, { hard: false, interactedAt: [0, 1, 2, 3, 4, 5] });
    expect(decideWatch({ level: 'attentive', observations, dismissals: [], now })).toBeNull();
  });

  it('never offers when there is no declared step', () => {
    const { observations, now } = run(6, { interactedAt: [0, 1, 2, 3] });
    const noStep = observations.map((o) => ({ ...o, step: undefined }));
    expect(decideWatch({ level: 'attentive', observations: noStep, dismissals: [], now })).toBeNull();
  });
});

describe('decideWatch — REPEATING (grinding the same hard step)', () => {
  it('offers repeating once interactions on the step reach the threshold', () => {
    const { observations, now } = run(5, { interactedAt: [0, 1, 2] }); // 3 interactions
    const offer = decideWatch({ level: 'attentive', observations, dismissals: [], now });
    expect(offer?.signal).toBe('repeating');
    // It hands off a TEACH prompt (nudge, not the answer) carrying the step.
    expect(offer?.step).toBe('p2');
    expect(offer?.prompt.toLowerCase()).toContain("don't just give the answer");
  });

  it('does not offer below the repeat threshold', () => {
    const { observations, now } = run(5, { interactedAt: [0, 1] }); // only 2
    expect(decideWatch({ level: 'attentive', observations, dismissals: [], now })).toBeNull();
  });
});

describe('decideWatch — IDLE (dwelling on a hard step, no interaction)', () => {
  it('offers idle after the idle dwell with no interaction', () => {
    // Span >= idleMs across the step, zero interactions.
    const count = Math.ceil(ATTENTIVE.idleMs / 4_000) + 1;
    const { observations, now } = run(count, { gapMs: 4_000 });
    const offer = decideWatch({ level: 'attentive', observations, dismissals: [], now });
    expect(offer?.signal).toBe('idle');
  });

  it('does not offer idle before the dwell threshold', () => {
    const { observations, now } = run(2, { gapMs: 4_000 }); // ~4s dwell, < idleMs
    expect(decideWatch({ level: 'attentive', observations, dismissals: [], now })).toBeNull();
  });

  it('any interaction on the step suppresses idle (it becomes a repeat read instead)', () => {
    const count = Math.ceil(ATTENTIVE.idleMs / 4_000) + 1;
    const { observations, now } = run(count, { gapMs: 4_000, interactedAt: [0] }); // 1 interaction
    const offer = decideWatch({ level: 'attentive', observations, dismissals: [], now });
    // One interaction is below the repeat threshold, and it is not idle (it
    // interacted) — so the calm default holds: no offer.
    expect(offer).toBeNull();
  });
});

describe('decideWatch — dismissal cool-off (never a nag)', () => {
  it('mutes a dismissed signal+step for the cool-off window', () => {
    const { observations, now } = run(5, { interactedAt: [0, 1, 2] });
    const muted = decideWatch({
      level: 'attentive',
      observations,
      dismissals: [{ signal: 'repeating', step: 'p2', at: now - 1_000 }],
      now,
    });
    expect(muted).toBeNull();
  });

  it('a dismissal on a DIFFERENT step does not mute the real one', () => {
    const { observations, now } = run(5, { interactedAt: [0, 1, 2] });
    const offer = decideWatch({
      level: 'attentive',
      observations,
      dismissals: [{ signal: 'repeating', step: 'p9', at: now - 1_000 }],
      now,
    });
    expect(offer?.signal).toBe('repeating');
  });

  it('the cool-off expires — a long-ago dismissal no longer mutes', () => {
    const { observations, now } = run(5, { interactedAt: [0, 1, 2] });
    const offer = decideWatch({
      level: 'attentive',
      observations,
      dismissals: [{ signal: 'repeating', step: 'p2', at: now - ATTENTIVE.coolOffMs - 1 }],
      now,
    });
    expect(offer?.signal).toBe('repeating');
  });
});

describe('decideWatch — gentle waits longer than attentive', () => {
  it('the same window that triggers attentive may stay calm on gentle', () => {
    const { observations, now } = run(3, { interactedAt: [0, 1, 2] }); // 3 interactions
    expect(decideWatch({ level: 'attentive', observations, dismissals: [], now })?.signal).toBe('repeating');
    // gentle needs 4 — same window stays calm.
    expect(decideWatch({ level: 'gentle', observations, dismissals: [], now })).toBeNull();
  });
});
