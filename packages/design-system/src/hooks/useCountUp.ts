"use client";

import { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from './useReducedMotion';

export interface CountUpOptions {
  /** Animation duration in ms. Default 1100 (matches playground.js). */
  duration?: number;
  /** Start the count only when the element scrolls into view. Default true. */
  onView?: boolean;
}

export interface CountUp {
  /** The current animated value, ready to render. */
  value: number;
  /** Attach to the displaying element to gate the start on visibility. */
  ref: React.RefObject<HTMLSpanElement | null>;
}

/**
 * Count-up readout. Eases an integer from 0 to `to` over `duration`. Ports the
 * countUp + IntersectionObserver behavior from playground.js: by default it
 * waits until the element is in view, then counts once. Under
 * prefers-reduced-motion it jumps straight to the final value.
 */
export function useCountUp(to: number, options: CountUpOptions = {}): CountUp {
  const { duration = 1100, onView = true } = options;
  const reduced = useReducedMotion();
  const ref = useRef<HTMLSpanElement>(null);
  const [value, setValue] = useState(reduced ? to : 0);
  const startedRef = useRef(false);

  useEffect(() => {
    if (reduced) {
      setValue(to);
      return;
    }

    let raf = 0;
    const run = () => {
      if (startedRef.current) return;
      startedRef.current = true;
      let start: number | null = null;
      const step = (t: number) => {
        if (start === null) start = t;
        const k = Math.min((t - start) / duration, 1);
        setValue(Math.round(k * to));
        if (k < 1) raf = requestAnimationFrame(step);
      };
      raf = requestAnimationFrame(step);
    };

    if (!onView) {
      run();
      return () => cancelAnimationFrame(raf);
    }

    const el = ref.current;
    if (!el || typeof IntersectionObserver === 'undefined') {
      run();
      return () => cancelAnimationFrame(raf);
    }

    const obs = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          run();
          obs.unobserve(entry.target);
        }
      });
    });
    obs.observe(el);
    return () => {
      obs.disconnect();
      cancelAnimationFrame(raf);
    };
  }, [to, duration, onView, reduced]);

  return { value, ref };
}