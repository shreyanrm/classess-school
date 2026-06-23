'use client';

/* ============================================================================
   app/_components/VidyaSteps.tsx — the self-assembling derivation.

   Renders an ordered set of generate-and-verified steps that reveal one-by-one,
   staggered with var(--ease), synced to roughly the spoken reply timing. With
   prefers-reduced-motion, every step appears at once (no stagger). Each step is
   already verified by the time it arrives here (parseActions / the server drop
   any step whose deterministic check fails), so nothing unverified is shown.
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
        <span className="overline" style={{ margin: 0 }}>
          {spec.title}
        </span>
      </div>
      <ol className="vidya-steps-list">
        {spec.steps.slice(0, shown).map((step, i) => (
          <li key={i} className="vidya-step" data-testid="vidya-step">
            <span className="vidya-step-index" aria-hidden="true">
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
