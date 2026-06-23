"use client";

import { forwardRef, useImperativeHandle, type HTMLAttributes, type ReactNode } from 'react';
import { cx } from './cx';
import { useSpotlight } from '../hooks/useSpotlight';

export interface SpotlightCardProps extends HTMLAttributes<HTMLDivElement> {
  /** Larger padding (space-6 instead of space-5). */
  padLg?: boolean;
  /**
   * Opt in to THE signature cursor-tracking radial glow. Reserved for at most
   * one or two genuine hero moments per surface. Without it, the card renders
   * a calm, premium resting + hover state (hairline strengthen, faint surface
   * raise) — NO radial wash. Per the v4 brand law: subtle, not on every card.
   */
  hero?: boolean;
  children?: ReactNode;
}

/**
 * THE spotlight card — the signature hover of the system.
 *
 * An ultramarine radial wash at 10% alpha follows the pointer across the
 * surface (a 180px circle anchored to --mx/--my, fading to transparent at
 * 60%). The hairline strengthens on hover. Corners stay sharp; the glow is
 * clipped by overflow:hidden, so it never bleeds or becomes a drop shadow.
 *
 * Honors prefers-reduced-motion via useSpotlight: when reduced, the pointer
 * handlers no-op and the glow stays centred and calm.
 *
 * The visual treatment lives in .c-spot (motion.css); this component wires the
 * pointer math (useSpotlight) onto a .card.
 *
 *   <SpotlightCard>
 *     <h3>Mastery check</h3>
 *     <p>Move your pointer across this card.</p>
 *   </SpotlightCard>
 */
export const SpotlightCard = forwardRef<HTMLDivElement, SpotlightCardProps>(
  function SpotlightCard({ padLg, hero, className, children, ...rest }, ref) {
    const spot = useSpotlight<HTMLDivElement>();
    // Expose the internal node to a forwarded ref without losing the hook's.
    useImperativeHandle(ref, () => spot.ref.current as HTMLDivElement, [spot.ref]);

    return (
      <div
        ref={spot.ref}
        className={cx('card', 'c-spot', hero && 'c-spot--hero', padLg && 'card-pad-lg', className)}
        onPointerMove={spot.onPointerMove}
        onPointerLeave={spot.onPointerLeave}
        {...rest}
      >
        {children}
      </div>
    );
  },
);