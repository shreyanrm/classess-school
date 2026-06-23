'use client';

import { useState } from 'react';
import { Button, Icon } from '@classess/design-system';

export interface EvidenceDrawerProps {
  /** The linked evidence lines — full lineage, never an opaque claim. */
  evidence: string[];
  /** Plain-language "why am I seeing this." */
  whySeeing?: string;
}

/**
 * Slides open under any conclusion to show the linked evidence and lineage.
 * Nothing is asserted without a path to its evidence. Collapsed by default to
 * keep the surface calm; opens on demand.
 */
export function EvidenceDrawer({ evidence, whySeeing }: EvidenceDrawerProps) {
  const [open, setOpen] = useState(false);

  return (
    <div>
      <Button
        variant="ghost"
        size="sm"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <Icon name={open ? 'chevron-down' : 'chevron-right'} size="sm" />
        {open ? 'Hide evidence' : 'Show evidence'}
      </Button>

      {open ? (
        <div className="evidence-drawer">
          {whySeeing ? (
            <p className="caption">
              <strong>Why you are seeing this. </strong>
              {whySeeing}
            </p>
          ) : null}
          {evidence.map((line, i) => (
            <div className="evidence-item" key={i}>
              <span className="dot" aria-hidden="true" />
              <span className="body-sm">{line}</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
