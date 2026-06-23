"use client";

import { useCallback, useRef, type PointerEvent as ReactPointerEvent } from 'react';
import { useReducedMotion } from './useReducedMotion';

export interface MagneticHandlers<T extends HTMLElement> {
  ref: React.RefObject<T | null>;
  onPointerMove: (event: ReactPointerEvent<T>) => void;
  onPointerLeave: (event: ReactPointerEvent<T>) => void;
}

export interface MagneticOptions {
  /** Horizontal pull strength. Default 0.3 (matches playground.js). */
  strengthX?: number;
  /** Vertical pull strength. Default 0.4 (matches playground.js). */
  strengthY?: number;
}

/**
 * Magnetic pull for buttons and small targets. The element drifts toward the
 * pointer by a fraction of the offset from its centre, then snaps back on
 * leave. Ports the .js-magnet behavior from playground.js (0.3 / 0.4).
 * Honors prefers-reduced-motion (no-op).
 */
export function useMagnetic<T extends HTMLElement = HTMLButtonElement>(
  options: MagneticOptions = {},
): MagneticHandlers<T> {
  const { strengthX = 0.3, strengthY = 0.4 } = options;
  const ref = useRef<T>(null);
  const reduced = useReducedMotion();

  const onPointerMove = useCallback(
    (event: ReactPointerEvent<T>) => {
      if (reduced) return;
      const el = ref.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const dx = (event.clientX - r.left - r.width / 2) * strengthX;
      const dy = (event.clientY - r.top - r.height / 2) * strengthY;
      el.style.transform = `translate(${dx.toFixed(2)}px, ${dy.toFixed(2)}px)`;
    },
    [reduced, strengthX, strengthY],
  );

  const onPointerLeave = useCallback(() => {
    const el = ref.current;
    if (el) el.style.transform = '';
  }, []);

  return { ref, onPointerMove, onPointerLeave };
}