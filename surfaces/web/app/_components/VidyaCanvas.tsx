'use client';

/* ============================================================================
   app/_components/VidyaCanvas.tsx — Vidya's on-demand floating canvas.

   The centrepiece. Vidya summons this calm floating panel ONLY when the answer
   needs to be SHOWN — to draw a diagram, work a derivation, or sketch an
   explanation. It is NOT a chatbox and NOT always open: the orb stays the front
   door (voice + short replies); when something must be shown, Vidya opens the
   canvas, renders structured content as SELF-ASSEMBLING SVG, and the human can
   dismiss it.

   v4 brand only: SVG visuals, ink strokes (var(--text-primary)), crisp
   stroke-draw that animates in (like the design system's .c-draw / spark /
   ring), Caveat (script) reserved for a human-style annotation, no shadows,
   sharp corners, generous space, plain language, no emoji, no exclamation.
   prefers-reduced-motion -> everything appears instantly (no stroke draw, no
   stagger). The signature/ignite is NOT used here — this is the working canvas,
   not the rare mastery moment.

   Content is a BOUNDED set of structured primitives (sanitised upstream in
   lib/vidya). The client only ever draws known shapes — never arbitrary HTML.
   data-testids: vidya-canvas, vidya-canvas-close.
   ============================================================================ */

import { useEffect, useRef, useState } from 'react';
import { Icon } from '@classess/design-system';
import type {
  CanvasCardSpec,
  CanvasPrimitive,
  DerivationStep,
} from '@/lib/vidya';

/** Honour prefers-reduced-motion so the assembly never animates against a setting. */
function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(mq.matches);
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener?.('change', onChange);
    return () => mq.removeEventListener?.('change', onChange);
  }, []);
  return reduced;
}

/** A staged reveal counter — assembles `total` items one at a time on a calm
 *  cadence; reduced-motion reveals all at once. */
function useStagedReveal(total: number, reduced: boolean, intervalMs: number, key: unknown): number {
  const [shown, setShown] = useState(reduced ? total : Math.min(1, total));
  useEffect(() => {
    if (reduced) {
      setShown(total);
      return;
    }
    setShown(Math.min(1, total));
    if (total <= 1) return;
    let n = 1;
    const t = setInterval(() => {
      n += 1;
      setShown(n);
      if (n >= total) clearInterval(t);
    }, intervalMs);
    return () => clearInterval(t);
  }, [total, reduced, intervalMs, key]);
  return shown;
}

// SVG coordinate space: content uses 0..100; we render into a 100x100 viewBox so
// the panel can scale it cleanly.
const VB = 100;
const fy = (y: number) => VB - y; // flip so y grows upward, like a graph

function arcPath(cx: number, cy: number, r: number, startDeg: number, endDeg: number): string {
  const a0 = (startDeg * Math.PI) / 180;
  const a1 = (endDeg * Math.PI) / 180;
  const x0 = cx + r * Math.cos(a0);
  const y0 = fy(cy + r * Math.sin(a0));
  const x1 = cx + r * Math.cos(a1);
  const y1 = fy(cy + r * Math.sin(a1));
  const large = Math.abs(endDeg - startDeg) > 180 ? 1 : 0;
  const sweep = endDeg > startDeg ? 0 : 1; // y is flipped, so invert sweep
  return `M ${x0} ${y0} A ${r} ${r} 0 ${large} ${sweep} ${x1} ${y1}`;
}

/** One SVG primitive, drawn with the stroke-draw treatment. */
function Primitive({ p, drawn }: { p: CanvasPrimitive; drawn: boolean }) {
  const cls = `vc-stroke${drawn ? ' is-drawn' : ''}`;
  switch (p.kind) {
    case 'line':
      return (
        <g>
          <line className={cls} x1={p.x1} y1={fy(p.y1)} x2={p.x2} y2={fy(p.y2)} />
          {p.label ? (
            <text className="vc-label" x={(p.x1 + p.x2) / 2} y={fy((p.y1 + p.y2) / 2) - 1.5}>
              {p.label}
            </text>
          ) : null}
        </g>
      );
    case 'arrow': {
      const ang = Math.atan2(fy(p.y2) - fy(p.y1), p.x2 - p.x1);
      const head = 3.2;
      const hx1 = p.x2 - head * Math.cos(ang - Math.PI / 7);
      const hy1 = fy(p.y2) - head * Math.sin(ang - Math.PI / 7);
      const hx2 = p.x2 - head * Math.cos(ang + Math.PI / 7);
      const hy2 = fy(p.y2) - head * Math.sin(ang + Math.PI / 7);
      return (
        <g>
          <line className={cls} x1={p.x1} y1={fy(p.y1)} x2={p.x2} y2={fy(p.y2)} />
          <polyline className={cls} points={`${hx1},${hy1} ${p.x2},${fy(p.y2)} ${hx2},${hy2}`} />
          {p.label ? (
            <text className="vc-label" x={(p.x1 + p.x2) / 2} y={fy((p.y1 + p.y2) / 2) - 1.5}>
              {p.label}
            </text>
          ) : null}
        </g>
      );
    }
    case 'arc':
      return (
        <g>
          <path className={cls} d={arcPath(p.cx, p.cy, p.r, p.startDeg, p.endDeg)} />
          {p.label ? (
            <text className="vc-label" x={p.cx} y={fy(p.cy) - p.r - 1.5}>
              {p.label}
            </text>
          ) : null}
        </g>
      );
    case 'shape': {
      const top = fy(p.y + p.h);
      let node;
      if (p.shape === 'rect') {
        node = <rect className={cls} x={p.x} y={top} width={p.w} height={p.h} />;
      } else if (p.shape === 'circle') {
        const r = Math.min(p.w, p.h) / 2;
        node = <circle className={cls} cx={p.x + p.w / 2} cy={fy(p.y + p.h / 2)} r={r} />;
      } else {
        const pts = `${p.x},${fy(p.y)} ${p.x + p.w},${fy(p.y)} ${p.x + p.w / 2},${top}`;
        node = <polygon className={cls} points={pts} />;
      }
      return (
        <g>
          {node}
          {p.label ? (
            <text className="vc-label" x={p.x + p.w / 2} y={fy(p.y) + 4}>
              {p.label}
            </text>
          ) : null}
        </g>
      );
    }
    case 'numberline': {
      const span = p.to - p.from || 1;
      const sx = (v: number) => 8 + ((v - p.from) / span) * 84;
      const baseY = 50;
      return (
        <g>
          <line className={cls} x1={8} y1={baseY} x2={92} y2={baseY} />
          {p.points?.map((pt, i) => (
            <g key={i}>
              <line className={cls} x1={sx(pt.value)} y1={baseY - 2.5} x2={sx(pt.value)} y2={baseY + 2.5} />
              {pt.label ? (
                <text className="vc-label" x={sx(pt.value)} y={baseY + 8}>
                  {pt.label}
                </text>
              ) : null}
            </g>
          ))}
        </g>
      );
    }
    case 'graph': {
      const pts = p.points.map((pt) => `${8 + (pt.x / 100) * 84},${fy(8 + (pt.y / 100) * 84)}`).join(' ');
      return (
        <g>
          <line className={cls} x1={8} y1={fy(8)} x2={8} y2={fy(92)} />
          <line className={cls} x1={8} y1={fy(8)} x2={92} y2={fy(8)} />
          <polyline className={cls} points={pts} />
          {p.xLabel ? (
            <text className="vc-label" x={88} y={fy(8) + 6}>
              {p.xLabel}
            </text>
          ) : null}
          {p.yLabel ? (
            <text className="vc-label" x={10} y={fy(94)}>
              {p.yLabel}
            </text>
          ) : null}
        </g>
      );
    }
    case 'label':
      return (
        <text
          className={p.annotation ? 'vc-annotation' : 'vc-label vc-label-free'}
          x={p.x}
          y={fy(p.y)}
        >
          {p.text}
        </text>
      );
    default:
      return null;
  }
}

/** A diagram: primitives self-assemble (stroke-draw, one at a time). */
function DiagramCanvas({ primitives, reduced }: { primitives: CanvasPrimitive[]; reduced: boolean }) {
  const shown = useStagedReveal(primitives.length, reduced, 700, primitives);
  return (
    <svg
      className="vc-svg"
      viewBox={`0 0 ${VB} ${VB}`}
      role="img"
      aria-label="A diagram Vidya drew"
      preserveAspectRatio="xMidYMid meet"
    >
      {primitives.slice(0, shown).map((p, i) => (
        <Primitive key={i} p={p} drawn />
      ))}
    </svg>
  );
}

/** A derivation rendered large on the canvas — steps reveal one by one. */
function DerivationCanvas({ steps, reduced }: { steps: DerivationStep[]; reduced: boolean }) {
  const shown = useStagedReveal(steps.length, reduced, 1100, steps);
  return (
    <ol className="vc-derivation" aria-live="polite">
      {steps.slice(0, shown).map((step, i) => (
        <li key={i} className="vc-derivation-step" data-testid="vidya-canvas-step">
          <span className="vc-derivation-index" aria-hidden="true">
            {i + 1}
          </span>
          <span className="vc-derivation-text">
            {step.text}
            {step.check ? (
              <span className="vc-derivation-check" title="Checked">
                <Icon name="check" size="sm" /> checked
              </span>
            ) : null}
          </span>
        </li>
      ))}
    </ol>
  );
}

/** A written explanation that "writes on" — lines appear one at a time. */
function WrittenCanvas({ lines, reduced }: { lines: string[]; reduced: boolean }) {
  const shown = useStagedReveal(lines.length, reduced, 900, lines);
  return (
    <div className="vc-written" aria-live="polite">
      {lines.slice(0, shown).map((line, i) => (
        <p key={i} className="vc-written-line">
          {line}
        </p>
      ))}
    </div>
  );
}

export interface VidyaCanvasProps {
  spec: CanvasCardSpec;
  onClose: () => void;
  /** Follow an "open in its page" link (router.push), if the spec carries one. */
  onOpenHref?: (href: string) => void;
}

/**
 * The floating canvas. Centred by default, repositioned cleanly by dragging its
 * header. It hosts the SVG drawing surface and self-assembles the content. A
 * close control dismisses it; an "open in its page" affordance shows when the
 * content also lives on a real page.
 */
export function VidyaCanvas({ spec, onClose, onOpenHref }: VidyaCanvasProps) {
  const reduced = usePrefersReducedMotion();
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const dragRef = useRef<{ dx: number; dy: number } | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);

  // Close on Escape so the canvas is always dismissible by keyboard.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  function onPointerDown(e: React.PointerEvent) {
    const rect = panelRef.current?.getBoundingClientRect();
    if (!rect) return;
    dragRef.current = { dx: e.clientX - rect.left, dy: e.clientY - rect.top };
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
  }
  function onPointerMove(e: React.PointerEvent) {
    const d = dragRef.current;
    if (!d) return;
    const w = panelRef.current?.offsetWidth ?? 0;
    const h = panelRef.current?.offsetHeight ?? 0;
    const x = Math.max(8, Math.min(window.innerWidth - w - 8, e.clientX - d.dx));
    const y = Math.max(8, Math.min(window.innerHeight - h - 8, e.clientY - d.dy));
    setPos({ x, y });
  }
  function onPointerUp() {
    dragRef.current = null;
  }

  const style: React.CSSProperties = pos
    ? { left: pos.x, top: pos.y, transform: 'none' }
    : {};

  return (
    <div
      ref={panelRef}
      className="vidya-canvas"
      role="dialog"
      aria-label={`Vidya canvas — ${spec.title}`}
      aria-modal="false"
      data-testid="vidya-canvas"
      data-content={spec.content.type}
      style={style}
    >
      <div className="vidya-canvas-head" onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp}>
        <span className="vidya-canvas-title">
          <Icon name="spark" size="sm" />
          <span className="overline" style={{ margin: 0 }}>
            {spec.title}
          </span>
        </span>
        <button
          type="button"
          className="rail-btn"
          aria-label="Close the canvas"
          title="Close the canvas"
          data-testid="vidya-canvas-close"
          onClick={onClose}
        >
          <Icon name="close" size="sm" />
        </button>
      </div>

      <div className="vidya-canvas-body">
        {spec.content.type === 'diagram' ? (
          <DiagramCanvas primitives={spec.content.primitives} reduced={reduced} />
        ) : spec.content.type === 'derivation' ? (
          <DerivationCanvas steps={spec.content.steps} reduced={reduced} />
        ) : (
          <WrittenCanvas lines={spec.content.lines} reduced={reduced} />
        )}
      </div>

      {spec.openHref ? (
        <div className="vidya-canvas-foot">
          <button
            type="button"
            className="vidya-canvas-open body-sm"
            data-testid="vidya-canvas-open"
            onClick={() => onOpenHref?.(spec.openHref!)}
          >
            {spec.openLabel ?? 'Open in its page'}
          </button>
        </div>
      ) : null}
    </div>
  );
}
