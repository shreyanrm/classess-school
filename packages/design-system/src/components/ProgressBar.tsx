import { forwardRef, type CSSProperties, type HTMLAttributes } from 'react';
import { cx } from './cx';

export interface ProgressBarProps extends HTMLAttributes<HTMLDivElement> {
  /** Completion 0–100. */
  value: number;
  /** Use the ultramarine signature fill instead of ink. */
  accent?: boolean;
  /** Animate the fill from 0 to value (honors reduced motion). */
  animate?: boolean;
  /** Accessible label for the progress semantics. */
  label?: string;
}

/**
 * A thin progress bar. Ink fill by default; `accent` uses the signature.
 * `animate` fills from 0 via the CSS keyframe (driven by the --val variable).
 */
export const ProgressBar = forwardRef<HTMLDivElement, ProgressBarProps>(function ProgressBar(
  { value, accent, animate, label, className, style, ...rest },
  ref,
) {
  const clamped = Math.max(0, Math.min(100, value));
  const fillStyle = { '--val': `${clamped}%`, width: `${clamped}%` } as CSSProperties;
  return (
    <div
      ref={ref}
      className={cx('progress', accent && 'accent', animate && 'animate', className)}
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
      style={style}
      {...rest}
    >
      <span style={fillStyle} />
    </div>
  );
});
