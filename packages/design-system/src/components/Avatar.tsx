import { forwardRef, type HTMLAttributes } from 'react';
import { cx } from './cx';
import type { Size } from '../types';

export interface AvatarProps extends HTMLAttributes<HTMLDivElement> {
  /** Initials or short label rendered when no image is provided. */
  initials?: string;
  /** Optional image source. When set, renders an <img> with the given alt. */
  src?: string;
  alt?: string;
  size?: Size;
}

const SIZE_CLASS: Record<Size, string> = { sm: 'avatar-sm', md: '', lg: 'avatar-lg' };

/** A round avatar — initials or image. Hairline border, calm sunken fill. */
export const Avatar = forwardRef<HTMLDivElement, AvatarProps>(function Avatar(
  { initials, src, alt, size = 'md', className, ...rest },
  ref,
) {
  return (
    <div ref={ref} className={cx('avatar', SIZE_CLASS[size], className)} {...rest}>
      {src ? (
        <img src={src} alt={alt ?? ''} style={{ width: '100%', height: '100%', borderRadius: '50%', objectFit: 'cover' }} />
      ) : (
        initials
      )}
    </div>
  );
});
