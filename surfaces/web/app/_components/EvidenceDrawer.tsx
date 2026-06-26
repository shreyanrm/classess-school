'use client';

import {
  createContext,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { Button, ConfidenceBand, Icon, type Confidence } from '@classess/design-system';

/* ============================================================================
   EvidenceDrawer — the RIGHT slide-in lineage panel (~420px).

   The promise of the surface: nothing is asserted without a path to its
   evidence. Any "Why this" opens this drawer from the right edge — it carries
   the claim, the dated evidence list, a ConfidenceBand, and a plain-language
   "why am I seeing this". Frosted scrim + hairline border; depth is never a
   shadow. Open/close is buttery (transform + opacity, the kit ease). Escape
   closes; focus is trapped while open; the trigger is restored on close.

   Two ways to use it:
     1. Inline trigger (back-compat): <EvidenceDrawer evidence whySeeing /> — a
        quiet "Show evidence" ghost button that opens the drawer. Existing pages
        keep working unchanged.
     2. Imperative: useEvidenceDrawer().open({ claim, evidence, … }) from any
        "Why this" affordance — mount <EvidenceDrawerHost /> once near the root.
   ============================================================================ */

/** One dated line of evidence — the lineage, never an opaque claim. */
export interface EvidenceLine {
  /** The evidence statement (what was observed / corroborated). */
  text: string;
  /** A short, human date/when token ("Tue 24 Jun", "3 attempts ago"). */
  when?: string;
}

export interface EvidencePayload {
  /** The conclusion this evidence stands behind. */
  claim: string;
  /** The verification confidence — surfaced as a band, never a raw score. */
  confidence?: Confidence;
  /** The dated evidence lines. Strings are accepted and read as undated lines. */
  evidence: Array<EvidenceLine | string>;
  /** Plain-language "why am I seeing this". */
  whySeeing?: string;
  /** Optional footer actions (open the student, dismiss, …). */
  actions?: ReactNode;
}

function normalize(lines: Array<EvidenceLine | string>): EvidenceLine[] {
  return lines.map((l) => (typeof l === 'string' ? { text: l } : l));
}

/* ----------------------------------------------------------------------------
   The presentational drawer — controlled. Slides from the right over a frosted
   scrim. Esc closes; focus is trapped; the body cannot scroll behind it.
   -------------------------------------------------------------------------- */
export interface EvidenceDrawerPanelProps extends EvidencePayload {
  open: boolean;
  onClose: () => void;
}

export function EvidenceDrawerPanel({
  open,
  onClose,
  claim,
  confidence,
  evidence,
  whySeeing,
  actions,
}: EvidenceDrawerPanelProps) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const restoreRef = useRef<HTMLElement | null>(null);
  const titleId = useId();
  const lines = normalize(evidence);

  // Trap focus, claim Escape, lock the page scroll, restore focus on close.
  useEffect(() => {
    if (!open) return;
    restoreRef.current = (document.activeElement as HTMLElement) ?? null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const focusFirst = window.setTimeout(() => {
      const el = panelRef.current?.querySelector<HTMLElement>(
        'button, a[href], input, [tabindex]:not([tabindex="-1"])',
      );
      (el ?? panelRef.current)?.focus();
    }, 30);

    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== 'Tab') return;
      const focusables = panelRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], input:not([disabled]), [tabindex]:not([tabindex="-1"])',
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
    <div className="ev-drawer-root" data-testid="evidence-drawer">
      <div className="ev-drawer-scrim" onClick={onClose} aria-hidden="true" />
      <div
        className="ev-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        ref={panelRef}
        tabIndex={-1}
      >
        <div className="ev-drawer-head">
          <span className="overline" style={{ margin: 0 }}>
            The evidence
          </span>
          <button
            type="button"
            className="rail-btn ev-drawer-close"
            aria-label="Close evidence"
            onClick={onClose}
          >
            <Icon name="close" size="sm" />
          </button>
        </div>

        <div className="ev-drawer-body">
          <h3 id={titleId} className="h4 ev-drawer-claim">
            {claim}
          </h3>

          {confidence ? (
            <div className="ev-drawer-confidence">
              <ConfidenceBand level={confidence} />
            </div>
          ) : null}

          <p className="overline ev-drawer-section">Lineage</p>
          <ol className="ev-drawer-list">
            {lines.map((l, i) => (
              <li className="ev-drawer-item" key={i}>
                <span className="dot" aria-hidden="true" />
                <div>
                  <p className="body-sm" style={{ margin: 0 }}>
                    {l.text}
                  </p>
                  {l.when ? <span className="data ev-drawer-when">{l.when}</span> : null}
                </div>
              </li>
            ))}
          </ol>

          {whySeeing ? (
            <div className="ev-drawer-why">
              <p className="overline ev-drawer-section" style={{ marginTop: 0 }}>
                Why you are seeing this
              </p>
              <p className="body-sm muted" style={{ margin: 0 }}>
                {whySeeing}
              </p>
            </div>
          ) : null}
        </div>

        {actions ? <div className="ev-drawer-foot">{actions}</div> : null}
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------------------
   Inline trigger (back-compat): a quiet "Show evidence" ghost button that opens
   the drawer with the supplied lineage. The same props existing pages already
   pass keep working — now they open a real slide-in panel.
   -------------------------------------------------------------------------- */
export interface EvidenceDrawerProps {
  /** The conclusion the evidence stands behind. Defaults to a generic claim. */
  claim?: string;
  /** The verification confidence — surfaced as a band, never a raw score. */
  confidence?: Confidence;
  /** The linked evidence lines — full lineage, never an opaque claim. */
  evidence: Array<EvidenceLine | string>;
  /** Plain-language "why am I seeing this". */
  whySeeing?: string;
  /** Override the trigger label. */
  label?: string;
  /** Footer actions in the drawer. */
  actions?: ReactNode;
}

export function EvidenceDrawer({
  claim = 'Why you are seeing this',
  confidence,
  evidence,
  whySeeing,
  label = 'Why this',
  actions,
}: EvidenceDrawerProps) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen(true)}
      >
        <Icon name="info" size="sm" />
        {label}
      </Button>
      <EvidenceDrawerPanel
        open={open}
        onClose={() => setOpen(false)}
        claim={claim}
        confidence={confidence}
        evidence={evidence}
        whySeeing={whySeeing}
        actions={actions}
      />
    </>
  );
}

/* ----------------------------------------------------------------------------
   Imperative API — open the drawer from anywhere. Mount <EvidenceDrawerHost />
   once near the app root, then call useEvidenceDrawer().open(payload).
   -------------------------------------------------------------------------- */
interface EvidenceDrawerContextValue {
  open: (payload: EvidencePayload) => void;
  close: () => void;
}

const EvidenceDrawerContext = createContext<EvidenceDrawerContextValue | null>(null);

export function EvidenceDrawerHost({ children }: { children?: ReactNode }) {
  const [payload, setPayload] = useState<EvidencePayload | null>(null);
  const value: EvidenceDrawerContextValue = {
    open: (p) => setPayload(p),
    close: () => setPayload(null),
  };
  return (
    <EvidenceDrawerContext.Provider value={value}>
      {children}
      <EvidenceDrawerPanel
        open={payload != null}
        onClose={() => setPayload(null)}
        claim={payload?.claim ?? ''}
        confidence={payload?.confidence}
        evidence={payload?.evidence ?? []}
        whySeeing={payload?.whySeeing}
        actions={payload?.actions}
      />
    </EvidenceDrawerContext.Provider>
  );
}

export function useEvidenceDrawer(): EvidenceDrawerContextValue {
  const ctx = useContext(EvidenceDrawerContext);
  if (!ctx) {
    // A no-op fallback keeps callers safe when the host is not mounted.
    return { open: () => undefined, close: () => undefined };
  }
  return ctx;
}
