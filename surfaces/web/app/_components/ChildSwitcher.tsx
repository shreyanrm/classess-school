'use client';

import { Icon } from '@classess/design-system';
import { PARENT_CHILDREN, type ParentChild } from '@/lib/parentData';

export interface ChildSwitcherProps {
  /** The currently selected child id. */
  selectedId: string;
  /** One-click switch — the caller re-renders the surface for the new child. */
  onSelect: (id: string) => void;
}

/**
 * The Child switcher (parent). A one-click switch that re-renders the entire
 * surface for the selected child. Generic labels only — never a real name. A
 * child whose view has not been consented is shown as locked, plainly, never as
 * an error: a parent sees only what consent permits.
 *
 * v4: sharp corners, no shadow, one vivid accent. The active child carries the
 * surface accent; consent-gated children read quietly.
 */
export function ChildSwitcher({ selectedId, onSelect }: ChildSwitcherProps) {
  return (
    <div
      className="child-switcher"
      role="tablist"
      aria-label="Choose which child to view"
    >
      {PARENT_CHILDREN.map((child: ParentChild) => {
        const active = child.id === selectedId;
        const locked = !child.consentGranted;
        return (
          <button
            key={child.id}
            type="button"
            role="tab"
            aria-selected={active}
            className={`child-chip${active ? ' active' : ''}${locked ? ' locked' : ''}`}
            onClick={() => onSelect(child.id)}
            title={
              locked
                ? `${child.label} — sharing is not turned on yet`
                : `View ${child.label}`
            }
          >
            <span className="child-chip-label">{child.label}</span>
            <span className="child-chip-section caption">
              {locked ? (
                <>
                  <Icon name="info" size="sm" /> Not shared yet
                </>
              ) : (
                child.section
              )}
            </span>
          </button>
        );
      })}
    </div>
  );
}
