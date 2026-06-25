'use client';

/* ============================================================================
   app/_components/VidyaSteps.tsx — the self-assembling derivation.

   Renders an ordered set of generate-and-verified steps that reveal one-by-one,
   staggered with var(--ease), synced to roughly the spoken reply timing. With
   prefers-reduced-motion, every step appears at once (no stagger). Each step is
   already verified by the time it arrives here (parseActions / the server drop
   any step whose deterministic check fails), so nothing unverified is shown.

   Hand-drawn spec: the index is a slightly-rough hand-circled number (an organic
   sketched loop, not a clean ring), the title is a script (Caveat) caption, and a
   verified step gets a hand-drawn underline drawn live beneath it — molten/acid
   only. prefers-reduced-motion renders the resolved end-state.
   ============================================================================ */

import { useEffect, useState } from 'react';
import { Icon } from '@classess/design-system';
import type { StepsCardSpec } from '@/lib/vidya';

/** Honour prefers-reduced-motion so the reveal never animates against a setting. */
function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(mq.matches);
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener?.('change', onChange);
    return () => mq.removeEventListener?.('change', onChange);
  }, []);
  return reduced;
}

/** A small hand-circled loop around the step index — organic, slightly rough,
 *  ~1.1 turns so it over-circles its start like a person closing a loop by hand.
 *  Deterministic per index so it never re-jitters on re-render. Draws itself in
 *  live via globals.css; reduced-motion settles to the resolved end-state. */
function HandCircleNum({ n }: { n: number }) {
  let s = (n * 9301 + 49297) % 233280 || 1;
  const rnd = () => ((s = (s * 9301 + 49297) % 233280) / 233280);
  const cx = 11;
  const cy = 11;
  const turns = 1.1;
  const steps = 26;
  const start = -0.4 * Math.PI;
  const pts: Array<[number, number]> = [];
  for (let i = 0; i <= steps; i++) {
    const t = start + (i / steps) * turns * 2 * Math.PI;
    const jr = 1 + (rnd() - 0.5) * 0.12;
    pts.push([cx + 8.4 * jr * Math.cos(t) + (rnd() - 0.5), cy + 8.4 * jr * Math.sin(t) + (rnd() - 0.5)]);
  }
  let d = `M ${pts[0]![0].toFixed(1)} ${pts[0]![1].toFixed(1)}`;
  for (let i = 1; i < pts.length - 1; i++) {
    const [x0, y0] = pts[i]!;
    const [x1, y1] = pts[i + 1]!;
    const mx = (x0 + x1) / 2;
    const my = (y0 + y1) / 2;
    d += ` Q ${x0.toFixed(1)} ${y0.toFixed(1)} ${mx.toFixed(1)} ${my.toFixed(1)}`;
  }
  return (
    <svg className="vidya-step-loop" viewBox="0 0 22 22" aria-hidden="true">
      <path d={d} pathLength={100} />
    </svg>
  );
}

export interface VidyaStepsProps {
  spec: StepsCardSpec;
  /** Per-step reveal interval in ms (synced to the calm spoken cadence). */
  intervalMs?: number;
}

/**
 * The compact derivation overlay shown inside the orb panel. Steps reveal one at
 * a time; reduced-motion reveals all at once. Calm, certain, never bouncy.
 */
export function VidyaSteps({ spec, intervalMs = 1100 }: VidyaStepsProps) {
  const reduced = usePrefersReducedMotion();
  const total = spec.steps.length;
  const [shown, setShown] = useState(reduced ? total : Math.min(1, total));

  useEffect(() => {
    // Reset for a new derivation, then stagger the reveal.
    if (reduced) {
      setShown(total);
      return;
    }
    setShown(Math.min(1, total));
    if (total <= 1) return;
    let n = 1;
    const t = setInterval(() => {
      n += 1;
      setShown(n);
      if (n >= total) clearInterval(t);
    }, intervalMs);
    return () => clearInterval(t);
  }, [spec, total, reduced, intervalMs]);

  if (total === 0) return null;

  return (
    <div className="vidya-steps" data-testid="vidya-steps" aria-live="polite">
      <div className="vidya-steps-head">
        <Icon name="spark" size="sm" />
        <span className="vidya-steps-title script">{spec.title}</span>
      </div>
      <ol className="vidya-steps-list">
        {spec.steps.slice(0, shown).map((step, i) => (
          <li key={i} className="vidya-step" data-testid="vidya-step">
            <span className="vidya-step-index" aria-hidden="true">
              <HandCircleNum n={i + 1} />
              {i + 1}
            </span>
            <span className="vidya-step-text body-sm">
              {step.text}
              {step.check ? (
                <span className="vidya-step-check" title="Checked">
                  <Icon name="check" size="sm" /> checked
                </span>
              ) : null}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
