'use client';

/* ============================================================================
   lib/useVidyaWatch.ts — the React binding for VidyaWatch (the ambient layer).

   It continuously samples the IN-APP state (route + the hard step the user is
   on + whether they just interacted) into a small rolling window, runs the PURE
   detector (lib/vidyaWatch.decideWatch), and exposes the single quiet offer plus
   accept/dismiss. Accepting HANDS OFF to the existing orb (openVidya with the
   detector's prompt) — never a second Vidya. It also exposes the EXPLAIN-ON-
   SCREEN helper: a function the surface calls when the user points at an element,
   which hands Vidya that element's plain-language context to explain in place.

   It is gated by the existing `preferences.proactive` switch (settings 19) and by
   personalization consent: with proactivity off, or consent off, the window is
   never sampled and no offer ever forms. Everything is local and side-effect-free
   apart from the openVidya hand-off the user explicitly triggers.

   THE WINDOW IS TINY (a handful of recent ticks) and PII-free: it holds a route,
   an opaque step id, and interaction booleans — never content, never pixels.
   ============================================================================ */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';
import { openVidya } from '@/app/_components/VidyaOrb';
import { useStore } from './useStore';
import {
  decideWatch,
  watchLevelFromPreference,
  type WatchObservation,
  type WatchOffer,
  type WatchDismissal,
} from './vidyaWatch';

/** How often the binding samples the in-app state into the window (ms). A calm
 *  cadence — the detector still needs the dwell/repeat thresholds to fire. */
const SAMPLE_MS = 4_000;
/** The rolling window only needs the recent tail; we cap it so it never grows. */
const MAX_OBSERVATIONS = 24;

/**
 * The current ambient STEP the page is on, declared by the surface. A page that
 * has a hard step (a quiz item, a derivation, a wizard rung) sets this via the
 * `data-vidya-step` / `data-vidya-hard` attributes on its root, OR by calling
 * `markStep`. The watch reads the attribute form first (zero-wiring for a page),
 * falling back to the imperative one. Absent => the page is calm, no offer forms.
 */
function readDeclaredStep(): { step?: string; hard: boolean } {
  if (typeof document === 'undefined') return { hard: false };
  const el = document.querySelector<HTMLElement>('[data-vidya-step]');
  if (!el) return { hard: false };
  const step = el.getAttribute('data-vidya-step') || undefined;
  const hard = el.getAttribute('data-vidya-hard') === 'true';
  return { step, hard };
}

export interface UseVidyaWatchResult {
  /** The single quiet offer to surface, or null (stay calm). */
  offer: WatchOffer | null;
  /** Accept the offer: hand the prompt to the orb (teach / guide / explain). */
  accept: () => void;
  /** Dismiss the offer: mute this signal+step for the cool-off (never a nag). */
  dismiss: () => void;
  /**
   * EXPLAIN-ON-SCREEN: the user pointed at an element and wants it explained.
   * Hands Vidya the element's plain-language context (its label/text, the route),
   * so Vidya explains it from on-screen context. Safe + consent-gated like the
   * rest; a no-op when proactivity/consent is off only insofar as the offer is —
   * an explicit "explain this" is always honoured (it is user-initiated).
   */
  explain: (context: string) => void;
}

/**
 * Drive the ambient watch. Mounted ONCE alongside the orb (in VidyaOrb's root) so
 * there is a single ambient layer for the whole app, persisting across routes.
 */
export function useVidyaWatch(): UseVidyaWatchResult {
  const pathname = usePathname() ?? '/';
  const { preferences, consent } = useStore();

  // The gate: proactivity preference -> level, AND personalization consent. With
  // either off we never sample and never offer (the ambient layer is dormant).
  const level = watchLevelFromPreference(preferences?.proactive);
  const consented = consent?.personalization === true;
  const active = level !== 'off' && consented;

  const observationsRef = useRef<WatchObservation[]>([]);
  const interactedRef = useRef(false);
  const [dismissals, setDismissals] = useState<WatchDismissal[]>([]);
  const [offer, setOffer] = useState<WatchOffer | null>(null);

  // Track whether the user interacted since the last sample. Cheap, passive —
  // capture-phase listeners that only flip a boolean (never read content).
  useEffect(() => {
    if (!active) return;
    const mark = () => {
      interactedRef.current = true;
    };
    window.addEventListener('keydown', mark, true);
    window.addEventListener('pointerdown', mark, true);
    window.addEventListener('input', mark, true);
    return () => {
      window.removeEventListener('keydown', mark, true);
      window.removeEventListener('pointerdown', mark, true);
      window.removeEventListener('input', mark, true);
    };
  }, [active]);

  // A route change retires any stale offer and clears the window — the watch
  // reads each surface fresh (the detector also guards on path, belt + braces).
  useEffect(() => {
    observationsRef.current = [];
    interactedRef.current = false;
    setOffer(null);
  }, [pathname]);

  // Sample the in-app state on a calm interval, then run the PURE detector.
  useEffect(() => {
    if (!active) {
      observationsRef.current = [];
      setOffer(null);
      return;
    }
    const tick = () => {
      const { step, hard } = readDeclaredStep();
      const now = Date.now();
      const obs: WatchObservation = {
        path: pathname,
        step,
        hard,
        interacted: interactedRef.current,
        at: now,
      };
      interactedRef.current = false;
      const next = [...observationsRef.current, obs].slice(-MAX_OBSERVATIONS);
      observationsRef.current = next;

      const decided = decideWatch({ level, observations: next, dismissals, now });
      const latestStep = next[next.length - 1]?.step;
      // Keep an already-shown offer steady (do not re-mount it — that would
      // restart its calm entrance) while it is still relevant; retire it the
      // moment the detector goes calm AND the user has left the step it was for.
      setOffer((prev) => {
        if (!decided) return prev && prev.step === latestStep ? prev : null;
        if (prev && prev.signal === decided.signal && prev.step === decided.step) return prev;
        return decided;
      });
    };
    const id = window.setInterval(tick, SAMPLE_MS);
    return () => window.clearInterval(id);
  }, [active, level, pathname, dismissals]);

  const accept = useCallback(() => {
    if (!offer) return;
    // Hand off to the SAME orb path — Vidya guides / teaches-by-drawing / explains
    // on screen from here, with the permission ladder + verification it already has.
    openVidya(offer.prompt);
    setOffer(null);
    // Briefly mute this signal so accepting does not immediately re-offer it.
    setDismissals((prev) => [
      ...prev.slice(-9),
      { signal: offer.signal, step: offer.step, at: Date.now() },
    ]);
  }, [offer]);

  const dismiss = useCallback(() => {
    if (!offer) return;
    setOffer(null);
    setDismissals((prev) => [
      ...prev.slice(-9),
      { signal: offer.signal, step: offer.step, at: Date.now() },
    ]);
  }, [offer]);

  const explain = useCallback((context: string) => {
    const trimmed = context.trim().slice(0, 280);
    if (!trimmed) return;
    // Explain-on-screen is user-initiated, so it is always honoured: hand Vidya
    // the pointed-at element's plain-language context to explain it in place.
    openVidya(`Explain this from what's on my screen: "${trimmed}". Keep it short and plain, and point at it if it helps.`);
  }, []);

  return useMemo(() => ({ offer, accept, dismiss, explain }), [offer, accept, dismiss, explain]);
}
