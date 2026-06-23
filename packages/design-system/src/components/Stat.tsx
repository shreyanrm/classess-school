"use client";

import { forwardRef, type HTMLAttributes, type ReactNode } from 'react';
import { cx } from './cx';
import { useCountUp } from '../hooks/useCountUp';

export interface StatProps extends HTMLAttributes<HTMLDivElement> {
  /** The metric label. */
  label: ReactNode;
  /**
   * The value. If a number, it animates with a count-up on scroll into view
   * (honoring reduced motion). If a string/node, it renders as-is.
   */
  value: number | ReactNode;
  /** Optional delta string, e.g. "+12%". */
  delta?: ReactNode;
  /** Delta direction tint. */
  deltaDir?: 'up' | 'down';
  /** Prefix/suffix wrapping a numeric value (e.g. "₹", "%"). */
  prefix?: string;
  suffix?: string;
}

function NumberValue({ to, prefix, suffix }: { to: number; prefix?: string; suffix?: string }) {
  const { value, ref } = useCountUp(to);
  return (
    <span ref={ref} className="value">
      {prefix}
      {value}
      {suffix}
    </span>
  );
}

/**
 * A metric card. Lightest surface plus hairline; the number is sans tabular.
 * Numeric values count up once when scrolled into view.
 */
export const Stat = forwardRef<HTMLDivElement, StatProps>(function Stat(
  { label, value, delta, deltaDir, prefix, suffix, className, ...rest },
  ref,
) {
  return (
    <div ref={ref} className={cx('stat', className)} {...rest}>
      <div className="label">{label}</div>
      {typeof value === 'number' ? (
        <NumberValue to={value} prefix={prefix} suffix={suffix} />
      ) : (
        <span className="value">
          {prefix}
          {value}
          {suffix}
        </span>
      )}
      {delta ? <div className={cx('delta', deltaDir)}>{delta}</div> : null}
    </div>
  );
});