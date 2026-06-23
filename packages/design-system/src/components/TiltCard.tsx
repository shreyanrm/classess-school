"use client";

import { forwardRef, useImperativeHandle, type HTMLAttributes, type ReactNode } from 'react';
import { cx } from './cx';
import { useTilt } from '../hooks/useTilt';

export interface TiltCardProps extends HTMLAttributes<HTMLDivElement> {
  /** Maximum tilt angle in degrees. Default 6 — restrained. */
  max?: number;
  /** Larger padding (space-6 instead of space-5). */
  padLg?: boolean;
  children?: ReactNode;
}

/**
 * A card that tilts in 3D toward the pointer (.c-tilt). Restrained by default
 * so it reads precise, not playful. Honors prefers-reduced-motion.
 */
export const TiltCard = forwardRef<HTMLDivElement, TiltCardProps>(function TiltCard(
  { max = 6, padLg, className, children, ...rest },
  ref,
) {
  const tilt = useTilt<HTMLDivElement>({ max });
  useImperativeHandle(ref, () => tilt.ref.current as HTMLDivElement, [tilt.ref]);

  return (
    <div
      ref={tilt.ref}
      className={cx('card', 'c-tilt', padLg && 'card-pad-lg', className)}
      onPointerMove={tilt.onPointerMove}
      onPointerLeave={tilt.onPointerLeave}
      {...rest}
    >
      {children}
    </div>
  );
});