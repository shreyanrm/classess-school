'use client';

import { useEffect, useId, useRef, type ReactNode } from 'react';
import { Icon } from '@classess/design-system';

/* ============================================================================
   BottomSheet — the layered actions / approvals / voice surface.

   Rises from the bottom edge over a frosted scrim. The home of consequential
   actions (an approval to confirm, a quick action menu, a voice prompt) — it
   keeps the page calm and hands the user a focused tray to act in. Buttery open
   (transform + opacity, the kit ease); Escape closes; focus is trapped while
   open; the page scroll is locked and focus is restored on close. Depth is the
   hairline top border + frost — never a shadow. Honours reduced-motion via CSS.
   ============================================================================ */

export interface BottomSheetProps {
  open: boolean;
  onClose: () => void;
  /** A mono overline kicker (e.g. "APPROVAL", "QUICK ACTIONS"). */
  eyebrow?: string;
  /** The sheet's heading. */
  title: string;
  /** Optional supporting line beneath the title. */
  description?: ReactNode;
  /** The sheet body — the actions, the form, the voice affordance. */
  children: ReactNode;
  /** Footer row (the confirm / cancel pair, etc.). */
  footer?: ReactNode;
  /** Test hook. */
  'data-testid'?: string;
}

export function BottomSheet({
  open,
  onClose,
  eyebrow,
  title,
  description,
  children,
  footer,
  'data-testid': testId = 'bottom-sheet',
}: BottomSheetProps) {
  const sheetRef = useRef<HTMLDivElement | null>(null);
  const restoreRef = useRef<HTMLElement | null>(null);
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    restoreRef.current = (document.activeElement as HTMLElement) ?? null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const focusFirst = window.setTimeout(() => {
      const el = sheetRef.current?.querySelector<HTMLElement>(
        'button, a[href], input, textarea, select, [tabindex]:not([tabindex="-1"])',
      );
      (el ?? sheetRef.current)?.focus();
    }, 30);

    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== 'Tab') return;
      const focusables = sheetRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (!focusables || focusables.length === 0) return;
      const first = focusables[0]!;
      const last = focusables[focusables.length - 1]!;
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
    document.addEventListener('keydown', onKey, true);
    return () => {
      window.clearTimeout(focusFirst);
      document.removeEventListener('keydown', onKey, true);
      document.body.style.overflow = prevOverflow;
      restoreRef.current?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="sheet-root" data-testid={testId}>
      <div className="sheet-scrim" onClick={onClose} aria-hidden="true" />
      <div
        className="sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        ref={sheetRef}
        tabIndex={-1}
      >
        <div className="sheet-grip" aria-hidden="true" />
        <div className="sheet-head">
          <div>
            {eyebrow ? (
              <p className="overline" style={{ margin: '0 0 var(--space-1)' }}>
                {eyebrow}
              </p>
            ) : null}
            <h3 id={titleId} className="h4" style={{ margin: 0 }}>
              {title}
            </h3>
            {description ? (
              <p className="body-sm muted" style={{ margin: 'var(--space-2) 0 0', maxWidth: '52ch' }}>
                {description}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            className="rail-btn sheet-close"
            aria-label="Close"
            onClick={onClose}
          >
            <Icon name="close" size="sm" />
          </button>
        </div>
        <div className="sheet-body">{children}</div>
        {footer ? <div className="sheet-foot">{footer}</div> : null}
      </div>
    </div>
  );
}
