'use client';

/* ============================================================================
   app/_components/VidyaSpotlight.tsx — speak-and-show highlight + annotation.

   Resolves a named, registered region (lib/vidya HIGHLIGHT_REGIONS) to a real
   on-screen element by its data-region / data-testid / id, then draws a calm
   ring around it and, optionally, pins one short margin note beside it — so
   "look at your trigonometry mastery" visibly highlights the right card while
   Vidya speaks. Visual only: it never mutates the page, so it is safe on the
   voice path too. With prefers-reduced-motion the ring does not pulse.

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

  const pad = 6;
  // The ring is a real SVG vector — a rounded rectangle that draws itself in
  // (stroke-dashoffset animates from the full perimeter to 0). The whole Vidya
  // highlight layer is vector, not a CSS box: it reads as a drawn annotation,
  // honours prefers-reduced-motion (the draw-in is disabled there), and never
  // mutates the page. A 2px-inset viewport keeps the stroke from clipping.
  const w = rect.width + pad * 2;
  const h = rect.height + pad * 2;
  const inset = 2;
  const rx = 6;
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
        <rect
          className="vidya-spotlight-ring"
          x={inset}
          y={inset}
          width={w}
          height={h}
          rx={rx}
          ry={rx}
          pathLength={100}
        />
      </svg>
      {label ? (
        <div
          className="vidya-spotlight-label body-sm"
          style={{ top: rect.top - pad - 28, left: rect.left - pad }}
        >
          {label}
        </div>
      ) : null}
      {note ? (
        <div
          className="vidya-spotlight-note body-sm"
          style={{ top: rect.top, left: rect.left + rect.width + pad + 8 }}
          data-testid="vidya-annotation"
        >
          {note}
        </div>
      ) : null}
    </div>
  );
}
