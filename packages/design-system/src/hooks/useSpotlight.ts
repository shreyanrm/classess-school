"use client";

import { useCallback, useRef, type PointerEvent as ReactPointerEvent } from 'react';
import { useReducedMotion } from './useReducedMotion';

export interface SpotlightHandlers<T extends HTMLElement> {
  /** Attach to the element. Receives the ref and pointer handlers. */
  ref: React.RefObject<T | null>;
  onPointerMove: (event: ReactPointerEvent<T>) => void;
  onPointerLeave: (event: ReactPointerEvent<T>) => void;
}

/**
 * THE spotlight. Tracks the pointer over an element and writes its position
 * into the CSS custom properties --mx / --my (as percentages of the element
 * box). The .c-spot class renders an ultramarine radial-gradient at 10% alpha
 * on ::before, anchored to those vars, so the glow follows the cursor.
 *
 * Honors prefers-reduced-motion: when reduced, the handlers no-op and the vars
 * stay at their 50%/50% default, so the surface reads calm and static.
 *
 * Usage:
 *   const spot = useSpotlight<HTMLDivElement>();
 *   <div className="card c-spot" {...spot} />   // ref + handlers
 */
export function useSpotlight<T extends HTMLElement = HTMLDivElement>(): SpotlightHandlers<T> {
  const ref = useRef<T>(null);
  const reduced = useReducedMotion();

  const onPointerMove = useCallback(
    (event: ReactPointerEvent<T>) => {
      if (reduced) return;
      const el = ref.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const mx = ((event.clientX - rect.left) / rect.width) * 100;
      const my = ((event.clientY - rect.top) / rect.height) * 100;
      el.style.setProperty('--mx', `${mx}%`);
      el.style.setProperty('--my', `${my}%`);
    },
    [reduced],
  );

  const onPointerLeave = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    // Return the glow to centre so the next entry starts neutral.
    el.style.setProperty('--mx', '50%');
    el.style.setProperty('--my', '50%');
  }, []);

  return { ref, onPointerMove, onPointerLeave };
}