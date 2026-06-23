import { forwardRef, type HTMLAttributes } from 'react';
import { cx } from './cx';

export interface IgniteDotProps extends HTMLAttributes<HTMLSpanElement> {
  /** Accessible label describing what ignited (e.g. "Mastery reached"). */
  label?: string;
}

/**
 * The ignite — the signature mastery moment. An ultramarine core with a ring
 * that expands and fades outward, continuously. This is one of the two places
 * the ultramarine signature is allowed (the other is the brand mark); never
 * use it as decoration. Honors reduced motion (the ring is suppressed).
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
