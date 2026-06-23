import { forwardRef, type HTMLAttributes, type ReactNode } from 'react';
import { cx } from './cx';

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Larger padding (space-6 instead of space-5). */
  padLg?: boolean;
  /** Hairline strengthens on hover; sets cursor to pointer. */
  hover?: boolean;
  children?: ReactNode;
}

/**
 * The base surface. Hairline border, sharp corners, no drop shadow. Depth
 * comes from the tonal step between canvas and surface plus the hairline.
 */
export const Card = forwardRef<HTMLDivElement, CardProps>(function Card(
  { padLg, hover, className, children, ...rest },
  ref,
) {
  return (
    <div
      ref={ref}
      className={cx('card', padLg && 'card-pad-lg', hover && 'card-hover', className)}
      {...rest}
    >
      {children}
    </div>
  );
});

export interface CardHeaderProps extends HTMLAttributes<HTMLDivElement> {
  children?: ReactNode;
}

/** Baseline-aligned header row: title left, meta right. */
export const CardHeader = forwardRef<HTMLDivElement, CardHeaderProps>(function CardHeader(
  { className, children, ...rest },
  ref,
) {
  return (
    <div ref={ref} className={cx('card-header', className)} {...rest}>
      {children}
    </div>
  );
});
