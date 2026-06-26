'use client';

/* ============================================================================
   app/_components/VidyaSpotlight.tsx — speak-and-show highlight + annotation.

   Resolves a named, registered region (lib/vidya HIGHLIGHT_REGIONS) to a real
   on-screen element by its data-region / data-testid / id, then HAND-CIRCLES it
   with an organic, slightly-rough sketched loop (drawn live, like a person with
   a pen — never a clean geometric ring) and, optionally, pins one short margin
   note in the script hand beside it — so "look at your trigonometry mastery"
   visibly highlights the right card while Vidya speaks. Stroke + highlight are
   COOL brand only — ultramarine (the signature) with an acid highlighter wash;
   never coral/molten. Visual only: it never mutates the page, so it is safe on the
   voice path too. With prefers-reduced-motion it renders the resolved end-state
   (the loop fully drawn, no live reveal, no pulse).

   The map of regions is closed (an unknown region is dropped upstream), and the
   resolver only ever reads element geometry — never content — so nothing here
   can leak or change anything.
   ============================================================================ */

import { useEffect, useState } from 'react';
import type { HighlightRegion } from '@/lib/vidya';

/** Candidate selectors for a region, most specific first. A page opts in by
 *  marking an element with data-vidya-region="<region>" (preferred) or a
 *  matching data-testid; we fall back to a small set of stable testids. */
function selectorsFor(region: HighlightRegion): string[] {
  const base = [`[data-vidya-region="${region}"]`, `[data-testid="${region}"]`, `#${region}`];
  const extra: Partial<Record<HighlightRegion, string[]>> = {
    'vidya-steps': ['[data-testid="vidya-steps"]'],
    'mastery-band': ['[data-testid="mastery-band"]', '.mastery-band'],
    'gap-list': ['[data-testid="gap-list"]', '.gap-list'],
    'class-roster': ['[data-testid="class-roster"]'],
    attendance: ['[data-testid="attendance"]'],
  };
  return [...base, ...(extra[region] ?? [])];
}

function findRegion(region: HighlightRegion): HTMLElement | null {
  if (typeof document === 'undefined') return null;
  for (const sel of selectorsFor(region)) {
    try {
      const el = document.querySelector<HTMLElement>(sel);
      if (el) return el;
    } catch {
      // invalid selector — skip
    }
  }
  return null;
}

interface Rect {
  top: number;
  left: number;
  width: number;
  height: number;
}

/* --- Hand-drawn geometry (no dependency) -----------------------------------
   Vidya guides by HAND, not with a clean geometric ring. These build organic,
   slightly-rough SKETCHED paths — the kind a person draws circling a thing on
   screen — so the highlight reads as a human gesture, not a CSS box. The jitter
   is deterministic (seeded) so a given target draws the same loop every time
   (no flicker on re-measure), and a tiny overshoot at the end gives it the lived
   feel of a real pen lifting off. Pure path data; the live "drawn" reveal and
   the cool ultramarine/acid colour live in globals.css. */
function seeded(seed: number): () => number {
  let s = (seed % 2147483647) || 1;
  return () => ((s = (s * 16807) % 2147483647) - 1) / 2147483646;
}

/** A rough, hand-circled loop around a box — an ellipse traced with a wobble
 *  and ~1.12 turns so it overshoots its start, the way a person closes a circle
 *  by hand. Returns SVG path data sized to the given width/height. */
function roughLoopPath(w: number, h: number, seed: number): string {
  const rnd = seeded(seed);
  const cx = w / 2;
  const cy = h / 2;
  const rx = w / 2 - 2;
  const ry = h / 2 - 2;
  const turns = 1.12; // close past the start — a human over-circles slightly
  const steps = 44;
  const start = -0.35 * Math.PI; // begin upper-left, like a right-handed loop
  const pts: Array<[number, number]> = [];
  for (let i = 0; i <= steps; i++) {
    const t = start + (i / steps) * turns * 2 * Math.PI;
    // Wobble: the radius breathes a little and the centre drifts a touch.
    const jr = 1 + (rnd() - 0.5) * 0.07;
    const dx = (rnd() - 0.5) * 1.6;
    const dy = (rnd() - 0.5) * 1.6;
    pts.push([cx + rx * jr * Math.cos(t) + dx, cy + ry * jr * Math.sin(t) + dy]);
  }
  // Smooth the jittered points with a quadratic-through-midpoints path so the
  // stroke stays fluid (a pen, not a polygon) while keeping the organic drift.
  let d = `M ${pts[0]![0].toFixed(2)} ${pts[0]![1].toFixed(2)}`;
  for (let i = 1; i < pts.length - 1; i++) {
    const [x0, y0] = pts[i]!;
    const [x1, y1] = pts[i + 1]!;
    const mx = (x0 + x1) / 2;
    const my = (y0 + y1) / 2;
    d += ` Q ${x0.toFixed(2)} ${y0.toFixed(2)} ${mx.toFixed(2)} ${my.toFixed(2)}`;
  }
  return d;
}

export interface VidyaSpotlightProps {
  region: HighlightRegion;
  label?: string;
  /** A calm one-line margin note (annotate). Optional. */
  note?: string;
  /** Auto-dismiss the ring after this many ms (0 keeps it until replaced). */
  dismissAfterMs?: number;
  onDismiss?: () => void;
}

/**
 * The calm spotlight ring. Tracks the target's position (resize / scroll) so the
 * ring stays pinned, and dismisses if the target is not on the current page.
 */
export function VidyaSpotlight({
  region,
  label,
  note,
  dismissAfterMs = 6000,
  onDismiss,
}: VidyaSpotlightProps) {
  const [rect, setRect] = useState<Rect | null>(null);

  useEffect(() => {
    let raf = 0;
    let tries = 0;

    const measure = () => {
      const el = findRegion(region);
      if (!el) {
        // The target may not be mounted yet (e.g. just navigated). Retry briefly.
        if (tries++ < 20) {
          raf = window.setTimeout(measure, 150) as unknown as number;
        } else {
          setRect(null);
        }
        return;
      }
      const r = el.getBoundingClientRect();
      setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
      // Bring the target into view — guarded, since some environments (and tests)
      // do not implement scrollIntoView.
      if (typeof el.scrollIntoView === 'function') {
        el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
    };

    measure();
    const onMove = () => {
      const el = findRegion(region);
      if (!el) return;
      const r = el.getBoundingClientRect();
      setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
    };
    window.addEventListener('scroll', onMove, true);
    window.addEventListener('resize', onMove);

    const dismiss =
      dismissAfterMs > 0
        ? window.setTimeout(() => onDismiss?.(), dismissAfterMs)
        : undefined;

    return () => {
      window.clearTimeout(raf);
      window.removeEventListener('scroll', onMove, true);
      window.removeEventListener('resize', onMove);
      if (dismiss) window.clearTimeout(dismiss);
    };
  }, [region, dismissAfterMs, onDismiss]);

  if (!rect) return null;

  const pad = 8;
  // The highlight is drawn BY HAND, not as a geometric box. The whole layer is
  // SVG: a rough, hand-circled LOOP that draws itself in live (stroke-dashoffset
  // settles from the full path length to 0), the way a person circles a thing on
  // screen with a pen. We keep an invisible <rect class="vidya-spotlight-ring">
  // as the geometry anchor (the SVG-conversion contract) and overlay the organic
  // loop as the visible stroke. It honours prefers-reduced-motion (draw-in off →
  // resolved end-state), is cool ultramarine/acid only, and never mutates the page. A 4px
  // inset viewport keeps the wobble + overshoot from clipping.
  const w = rect.width + pad * 2;
  const h = rect.height + pad * 2;
  const inset = 4;
  // Seed the wobble from the target box so the same region always draws the same
  // loop (stable across re-measure on scroll/resize — no flicker).
  const seed = Math.round(rect.width + rect.height * 7 + rect.left + rect.top * 3);
  const loop = roughLoopPath(w, h, seed);
  return (
    <div className="vidya-spotlight-layer" aria-hidden="true" data-testid="vidya-spotlight">
      <svg
        className="vidya-spotlight-svg"
        width={w + inset * 2}
        height={h + inset * 2}
        viewBox={`0 0 ${w + inset * 2} ${h + inset * 2}`}
        style={{ position: 'fixed', top: rect.top - pad - inset, left: rect.left - pad - inset }}
        fill="none"
      >
        <g transform={`translate(${inset} ${inset})`}>
          {/* Geometry anchor — invisible <rect>; satisfies the SVG-vector contract
              while the visible mark is the hand-drawn loop below. */}
          <rect className="vidya-spotlight-ring" x={0} y={0} width={w} height={h} rx={6} ry={6} />
          <path className="vidya-spotlight-sketch" d={loop} pathLength={100} />
        </g>
      </svg>
      {label ? (
        <>
          {/* A hand-drawn guide: a slightly-rough stroke + a sketched arrowhead,
              drawn live from the caption down to the spotlit control, so the eye
              is led by HAND to the exact target. Cool ultramarine/acid; reduced-motion
              drops the draw-in (globals.css). */}
          <svg
            className="vidya-spotlight-arrow"
            width={30}
            height={pad + 32}
            viewBox={`0 0 30 ${pad + 32}`}
            style={{ position: 'fixed', top: rect.top - pad - 32, left: rect.left - pad + 8 }}
            fill="none"
            aria-hidden="true"
          >
            <path
              className="vidya-spotlight-arrow-line"
              d={`M7 2 Q1 ${(pad + 32) * 0.4} 6 ${(pad + 32) * 0.62} T 11 ${pad + 28}`}
              pathLength={100}
            />
            <path
              className="vidya-spotlight-arrow-head"
              d={`M5 ${pad + 21} Q9 ${pad + 26} 11 ${pad + 28} Q14 ${pad + 24} 16 ${pad + 20}`}
              pathLength={100}
            />
          </svg>
          <div
            className="vidya-spotlight-label script"
            style={{ top: rect.top - pad - 30, left: rect.left - pad }}
          >
            {label}
          </div>
        </>
      ) : null}
      {note ? (
        <div
          className="vidya-spotlight-note script"
          style={{ top: rect.top, left: rect.left + rect.width + pad + 8 }}
          data-testid="vidya-annotation"
        >
          {note}
        </div>
      ) : null}
    </div>
  );
}
