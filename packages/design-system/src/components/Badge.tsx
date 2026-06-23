import { forwardRef, type HTMLAttributes, type ReactNode } from 'react';
import { cx } from './cx';

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  /** Neutral (ink) instead of the ultramarine signature fill. */
  neutral?: boolean;
  children?: ReactNode;
}

/** A small count badge. Signature fill by default; neutral for quiet counts. */
export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(function Badge(
  { neutral, className, children, ...rest },
  ref,
) {
  return (
    <span ref={ref} className={cx('badge', neutral && 'badge-neutral', className)} {...rest}>
      {children}
    </span>
  );
});
