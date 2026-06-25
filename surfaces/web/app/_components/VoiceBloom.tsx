'use client';

/* ============================================================================
   app/_components/VoiceBloom.tsx — the Siri-like voice-mode bloom (spec 17.2).

   A fixed full-screen layer. The bottom ~62vh fills with a living, flowing warm
   field — ~5 drifting colored radial blobs (molten / tangerine / ultramarine /
   violet) on a <canvas>, additively blended (globalCompositeOperation='lighter')
   and CSS-blurred, masked to fade out toward the top. Above it, a frosted panel:
   the pulsing signature spark, the listening label, and the live transcript.

   The v4.1 translation of the Claude voice bloom — warm, organic, on-palette,
   frosted, NO hard edges, NO shadow. Reduced-motion renders a static frosted
   warm field (one painted frame, no rAF). Ported from
   updates/.../components-react/VoiceBloom.jsx.

   It is a VISUAL layer over the EXISTING voice path: the orb already drives
   VoiceCapsule into listening (voiceConverse server route). This component is
   driven by `open` (voiceState === 'listening') and shows the live `transcript`.
   Dismiss is delegated up via `onClose` (esc / click the field).
   ============================================================================ */

import { useEffect, useRef } from 'react';

export interface VoiceBloomProps {
  /** Visible + animating while true (wire to voiceState === 'listening'). */
  open: boolean;
  /** Live transcript line as the user speaks (from the STT path). */
  transcript?: string;
  /** Called on esc or a click on the field — the caller stops listening. */
  onClose?: () => void;
}

/** The five drifting blobs, in v4.1 palette order: molten, tangerine,
 *  ultramarine, violet, and a deep red accent. */
const BLOBS: Array<{ x: number; y: number; r: number; c: [number, number, number] }> = [
  { x: 0.3, y: 0.95, r: 0.55, c: [255, 77, 26] }, // molten
  { x: 0.55, y: 1.02, r: 0.62, c: [255, 138, 0] }, // tangerine
  { x: 0.72, y: 0.96, r: 0.5, c: [31, 53, 224] }, // ultramarine
  { x: 0.45, y: 1.05, r: 0.46, c: [122, 47, 242] }, // violet
  { x: 0.88, y: 1.0, r: 0.4, c: [236, 28, 45] }, // deep red
];

export function VoiceBloom({ open, transcript = '', onClose }: VoiceBloomProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (!open) return;
    const cv = canvasRef.current;
    if (!cv) return;
    const ctx = cv.getContext('2d');
    if (!ctx) return;

    const reduce =
      typeof matchMedia === 'function' &&
      matchMedia('(prefers-reduced-motion: reduce)').matches;
    const dpr = typeof devicePixelRatio === 'number' ? devicePixelRatio : 1;

    let w = 0;
    let h = 0;
    const size = () => {
      w = cv.width = cv.offsetWidth * dpr;
      h = cv.height = cv.offsetHeight * dpr;
    };
    size();
    window.addEventListener('resize', size);

    const dark = document.documentElement.dataset.theme === 'dark';
    let t = 0;
    const frame = () => {
      // Long, eased drift — buttery, continuous, GPU-friendly. The heavy CSS blur
      // does the smoothing so the per-frame work stays cheap.
      t += 0.006;
      ctx.clearRect(0, 0, w, h);
      ctx.globalCompositeOperation = 'lighter';
      const a = dark ? 0.5 : 0.42;
      BLOBS.forEach((b, i) => {
        const cx = (b.x + Math.sin(t * 1.1 + i * 1.3) * 0.06) * w;
        const cy = (b.y + Math.cos(t * 0.8 + i * 0.8) * 0.05) * h;
        const rr = b.r * Math.max(w, h) * (0.9 + 0.1 * Math.sin(t + i));
        const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, rr);
        g.addColorStop(0, `rgba(${b.c[0]},${b.c[1]},${b.c[2]},${a})`);
        g.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, w, h);
      });
      ctx.globalCompositeOperation = 'source-over';
      // Reduced-motion: paint exactly one static frame, never schedule another.
      // Hidden tab: hold the last frame, never schedule another (spec 20.4).
      if (!reduce && !document.hidden) rafRef.current = requestAnimationFrame(frame);
    };
    frame();

    const onVisibility = () => {
      if (reduce) return;
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      if (!document.hidden) frame();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', onKey);
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      window.removeEventListener('resize', size);
      window.removeEventListener('keydown', onKey);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [open, onClose]);

  return (
    <div
      className={`voice-bloom${open ? ' is-open' : ''}`}
      aria-hidden={!open}
      data-testid="vidya-voice-bloom"
    >
      <div className="voice-bloom-field" onClick={onClose}>
        <canvas ref={canvasRef} />
      </div>
      <div className="voice-bloom-panel" role="status" aria-live="polite">
        <span className="voice-bloom-spark" aria-hidden="true">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.6}
            strokeLinecap="round"
          >
            <path d="M12 2v20M2 12h20M5 5l14 14M19 5 5 19" />
          </svg>
        </span>
        <div className="voice-bloom-label">
          Listening — press <kbd>esc</kbd> to stop
        </div>
        <div className="voice-bloom-transcript">{transcript}</div>
      </div>
    </div>
  );
}
