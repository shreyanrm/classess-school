import { forwardRef, type HTMLAttributes } from 'react';
import { cx } from './cx';

export interface IgniteDotProps extends HTMLAttributes<HTMLSpanElement> {
  /** Accessible label describing what ignited (e.g. "Mastery reached"). */
  label?: string;
}

/**
 * The ignite — a compact inline ultramarine dot marking the mastery moment.
 *
 * SUPERSEDED by {@link CrystallizeNode} as the signature mastery moment per
 * v4.1 §17.5 (lattice lock-in instead of an expanding ring). Retained for the
 * inline dot use-case; prefer CrystallizeNode for the knowledge/progress
 * surfaces. This is one of the two places the ultramarine signature is allowed
 * (the other is the brand mark); never use it as decoration. Honors reduced
 * motion (the ring is suppressed).
 *
 * Visual treatment lives in .ignite (motion.css).
 */
export const IgniteDot = forwardRef<HTMLSpanElement, IgniteDotProps>(function IgniteDot(
  { label, className, ...rest },
  ref,
) {
  return (
    <span
      ref={ref}
      className={cx('ignite', className)}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      {...rest}
    />
  );
});
