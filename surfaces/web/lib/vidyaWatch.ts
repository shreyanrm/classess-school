/* ============================================================================
   lib/vidyaWatch.ts — VidyaWatch, the ambient screen-aware detector (PURE).

   Pillar 1: Vidya watches the IN-APP state — not the screen pixels, not a
   camera. It reads the surface the user is on (route), the visible regions, the
   step they are on, and the cadence of their recent interactions, all as
   consent-gated LOCAL context. From that signal it decides — deterministically,
   so it is testable like the other Vidya pure helpers (lib/vidya verifyStep,
   classifyPath) — whether the user looks STUCK, is REPEATING the same action, or
   has gone IDLE on a hard step, and shapes a single QUIET, dismissible offer.

   This module is React-free on purpose: the binding (lib/useVidyaWatch) feeds it
   a rolling window of observations and renders the offer; the DECISION lives here
   so the rule "calm-first, a subtle offer, never a nag" is one truth and unit-
   tested. Nothing here speaks to the network or mutates the page.

   CALM-FIRST INVARIANTS (encoded, not hoped):
     - An offer only forms when proactivity is ON (the existing preference gate).
     - Only ONE signal is ever offered at a time, and only above a dwell/repeat
       threshold — a passing glance never triggers it.
     - After a dismissal the same signal is muted for a cool-off window, so a
       dismissed offer never immediately returns (never a nag).
     - The offer is a HAND-OFF: it carries the prompt Vidya runs when accepted,
       which routes into the SAME orb path (teach-by-drawing / guide / explain),
       never a parallel Vidya.
   ============================================================================ */

/**
 * How forward Vidya's ambient watching is — the tunable (settings 19). It is
 * derived from the existing `preferences.proactive` boolean so we add a knob
 * without a store migration: off -> 'off'; on -> 'attentive'. A future settings
 * pass can widen the boolean to the full ladder; the detector already honours
 * all three levels.
 */
export type WatchLevel = 'off' | 'gentle' | 'attentive';

/** Map the persisted proactive boolean to a watch level (no store migration). */
export function watchLevelFromPreference(proactive: boolean | undefined): WatchLevel {
  // Default ON (matches defaultPreferences().proactive === true): the calm,
  // attentive ambient layer is part of the product, tunable down to off.
  return proactive === false ? 'off' : 'attentive';
}

/** The kind of ambient signal the detector can raise. */
export type WatchSignal = 'stuck' | 'repeating' | 'idle';

/**
 * One observation the binding samples and pushes into the rolling window. It is
 * the in-app state at a moment: where the user is, the step they are on, and
 * whether this tick carried an interaction. No PII, no pixels.
 */
export interface WatchObservation {
  /** The current route (the surface). */
  path: string;
  /** A stable id for the step/region the user is focused on, if the page
   *  declares one (e.g. a quiz item index, a wizard step). Absent on calm pages. */
  step?: string;
  /** Whether the page has marked the current step HARD (worth helping on). A
   *  page opts a step in; the detector never guesses difficulty. */
  hard?: boolean;
  /** Did the user interact since the previous observation (key, click, input)? */
  interacted: boolean;
  /** Monotonic timestamp (ms). */
  at: number;
}

/** The quiet offer the detector shapes — what the surface renders + hands off. */
export interface WatchOffer {
  signal: WatchSignal;
  /** The calm, dismissible one-liner (sentence case, no exclamation, no emoji). */
  caption: string;
  /** The action label on the offer (e.g. "Show me", "Walk me through it"). */
  accept: string;
  /** The prompt handed to Vidya (openVidya) when the user accepts — routes into
   *  the same orb path (guide / teach-by-drawing / explain-on-screen). */
  prompt: string;
  /** The path the offer was raised on, so a route change retires a stale offer. */
  path: string;
  /** The step the offer was raised on (if any), for the same staleness check. */
  step?: string;
}

/** The detector's tunable thresholds. Conservative by default — calm-first. */
export interface WatchThresholds {
  /** Idle dwell (ms) on a HARD step before an idle offer may form. */
  idleMs: number;
  /** Repeats of the same step within the window before a repeating offer forms. */
  repeatCount: number;
  /** Window (ms) the rolling observations span — older ones are irrelevant. */
  windowMs: number;
  /** Cool-off (ms) a dismissed signal stays muted on the same step. */
  coolOffMs: number;
}

/** Gentle waits longer and needs more repetition than attentive — same rules,
 *  higher bar. Off never forms an offer at all. */
export function thresholdsForLevel(level: WatchLevel): WatchThresholds {
  if (level === 'gentle') {
    return { idleMs: 45_000, repeatCount: 4, windowMs: 90_000, coolOffMs: 240_000 };
  }
  // 'attentive' (and the default)
  return { idleMs: 22_000, repeatCount: 3, windowMs: 60_000, coolOffMs: 150_000 };
}

/**
 * A dismissal record: the signal+step the user waved away and when, so the
 * cool-off can mute exactly that offer without muting a different, real one.
 */
export interface WatchDismissal {
  signal: WatchSignal;
  step?: string;
  at: number;
}

/** The full input to the pure decision — the window + level + recent dismissals. */
export interface WatchInput {
  level: WatchLevel;
  observations: WatchObservation[];
  dismissals: WatchDismissal[];
  /** "Now" (ms) — the moment the decision is evaluated. */
  now: number;
}

const STUCK_CAPTION: Record<WatchSignal, { caption: string; accept: string }> = {
  stuck: { caption: 'Looks like a tricky one. Want me to walk it through with you?', accept: 'Walk me through it' },
  repeating: { caption: 'Same step a few times now. I can show the next move, step by step.', accept: 'Show me' },
  idle: { caption: 'Stuck on this part? I can sketch it out — you stay in the driving seat.', accept: 'Sketch it' },
};

/** The hand-off prompt for each signal. Phrased so the orchestrator takes the
 *  TEACH path (productive struggle, never just the answer): it asks Vidya to
 *  guide/derive on-screen from the current context, not to hand over the result. */
function promptFor(signal: WatchSignal, obs: WatchObservation): string {
  const where = obs.step ? `the step I'm on (${obs.step})` : `what's on my screen right now`;
  switch (signal) {
    case 'stuck':
      return `I'm stuck on ${where}. Walk me through it step by step on screen — give me a nudge first, not the whole answer.`;
    case 'repeating':
      return `I've tried ${where} a few times. Show me the next move step by step, and point at what to look at — don't just give the answer.`;
    case 'idle':
      return `Help me get started on ${where}. Sketch out the idea on screen and let me try the next step myself.`;
  }
}

/** True when a signal+step is inside its dismissal cool-off (muted; never a nag). */
function isMuted(signal: WatchSignal, step: string | undefined, input: WatchInput, thr: WatchThresholds): boolean {
  return input.dismissals.some(
    (d) => d.signal === signal && d.step === step && input.now - d.at < thr.coolOffMs,
  );
}

/**
 * The pure ambient decision: from the rolling window of in-app observations,
 * return the single quiet offer to surface, or null for "stay calm". The order
 * of precedence is REPEATING (a clear, confident signal) > STUCK (a wrong/erratic
 * pattern) > IDLE (the softest), so the most certain help is offered first.
 *
 * Deterministic and side-effect-free — the same window always yields the same
 * decision, so the home and any deep page watch identically and it is testable.
 */
export function decideWatch(input: WatchInput): WatchOffer | null {
  if (input.level === 'off') return null;
  const thr = thresholdsForLevel(input.level);

  // Only the in-window observations matter; a stale tail never triggers help.
  const win = input.observations.filter((o) => input.now - o.at <= thr.windowMs);
  if (win.length === 0) return null;

  const latest = win[win.length - 1]!;
  // Ambient help is only offered on a HARD step the page opted in — Vidya never
  // interrupts on an easy or unmarked step.
  if (!latest.hard || !latest.step) return null;

  // Observations on the CURRENT step only — switching steps resets the read.
  const onStep = win.filter((o) => o.step === latest.step && o.path === latest.path);
  if (onStep.length === 0) return null;

  const make = (signal: WatchSignal): WatchOffer | null => {
    if (isMuted(signal, latest.step, input, thr)) return null;
    const copy = STUCK_CAPTION[signal];
    return {
      signal,
      caption: copy.caption,
      accept: copy.accept,
      prompt: promptFor(signal, latest),
      path: latest.path,
      step: latest.step,
    };
  };

  // REPEATING: the user has re-touched the same hard step many times (erratic /
  // grinding). The clearest "they could use a hand" signal.
  const interactions = onStep.filter((o) => o.interacted).length;
  if (interactions >= thr.repeatCount) {
    const offer = make('repeating');
    if (offer) return offer;
  }

  // IDLE: dwelling on a hard step with no interaction for the idle window — they
  // have stalled. Softest signal, offered last.
  const firstOnStep = onStep[0]!;
  const dwell = latest.at - firstOnStep.at;
  const idleNoInteraction = !onStep.some((o) => o.interacted);
  if (idleNoInteraction && dwell >= thr.idleMs) {
    const offer = make('idle');
    if (offer) return offer;
  }

  return null;
}
