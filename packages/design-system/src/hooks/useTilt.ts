"use client";

import { useCallback, useRef, type PointerEvent as ReactPointerEvent } from 'react';
import { useReducedMotion } from './useReducedMotion';

export interface TiltHandlers<T extends HTMLElement> {
  ref: React.RefObject<T | null>;
  onPointerMove: (event: ReactPointerEvent<T>) => void;
  onPointerLeave: (event: ReactPointerEvent<T>) => void;
}

export interface TiltOptions {
  /** Maximum tilt angle in degrees on each axis. Default 6 — restrained. */
  max?: number;
}

/**
 * 3D tilt for .c-tilt cards. Maps pointer position over the element to a small
 * rotateX/rotateY, applied via transform. Restrained by default (6deg) to stay
 * European-minimal — never a toy. Honors prefers-reduced-motion (no-op).
 *
 * Usage:
 *   const tilt = useTilt<HTMLDivElement>({ max: 6 });
 *   <div className="card c-tilt" {...tilt} />
 */
export function useTilt<T extends HTMLElement = HTMLDivElement>(
  options: TiltOptions = {},
): TiltHandlers<T> {
  const { max = 6 } = options;
  const ref = useRef<T>(null);
  const reduced = useReducedMotion();

  const onPointerMove = useCallback(
    (event: ReactPointerEvent<T>) => {
      if (reduced) return;
      const el = ref.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const px = (event.clientX - rect.left) / rect.width;
      const py = (event.clientY - rect.top) / rect.height;
      const rotateY = (px - 0.5) * 2 * max;
      const rotateX = -(py - 0.5) * 2 * max;
      el.style.transform = `perspective(800px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg)`;
    },
    [reduced, max],
  );

  const onPointerLeave = useCallback(() => {
    const el = ref.current;
    if (el) el.style.transform = '';
  }, []);

  return { ref, onPointerMove, onPointerLeave };
}