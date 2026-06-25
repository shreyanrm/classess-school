import React, { useEffect, useRef } from "react";

/**
 * VoiceBloom — the Siri-like voice mode overlay.
 *
 * The bottom ~62vh fills with a living, flowing warm field (molten / tangerine /
 * ultramarine / violet radial blobs drifting on a canvas, additively blended and
 * blurred, masked to fade toward the top). The v4.1 translation of the Claude
 * voice bloom — warm, organic, on-brand, frosted, no shadow. Must feel buttery.
 *
 * Props:
 *   open        — boolean, controls visibility + animation
 *   transcript  — live STT text (wire to the AI fabric STT path in prod)
 *   onClose     — called on esc / click-out
 *
 * Reference: prototype/vidya-experience.html (.voice). Reduced-motion renders a
 * static frosted field.
 */
export default function VoiceBloom({ open, transcript = "", onClose }) {
  const canvasRef = useRef(null);
  const rafRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const cv = canvasRef.current;
    const ctx = cv.getContext("2d");
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    let w, h;
    const size = () => {
      w = cv.width = cv.offsetWidth * devicePixelRatio;
      h = cv.height = cv.offsetHeight * devicePixelRatio;
    };
    size();
    window.addEventListener("resize", size);
    const dark = document.documentElement.dataset.theme === "dark";
    const blobs = [
      { x: 0.3, y: 0.95, r: 0.55, c: [255, 77, 26] },
      { x: 0.55, y: 1.02, r: 0.62, c: [255, 138, 0] },
      { x: 0.72, y: 0.96, r: 0.5, c: [31, 53, 224] },
      { x: 0.45, y: 1.05, r: 0.46, c: [122, 47, 242] },
      { x: 0.88, y: 1.0, r: 0.4, c: [236, 28, 45] },
    ];
    let t = 0;
    const frame = () => {
      t += 0.006;
      ctx.clearRect(0, 0, w, h);
      ctx.globalCompositeOperation = "lighter";
      const a = dark ? 0.5 : 0.42;
      blobs.forEach((b, i) => {
        const cx = (b.x + Math.sin(t * 1.1 + i * 1.3) * 0.06) * w;
        const cy = (b.y + Math.cos(t * 0.8 + i * 0.8) * 0.05) * h;
        const rr = b.r * Math.max(w, h) * (0.9 + 0.1 * Math.sin(t + i));
        const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, rr);
        g.addColorStop(0, `rgba(${b.c[0]},${b.c[1]},${b.c[2]},${a})`);
        g.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, w, h);
      });
      ctx.globalCompositeOperation = "source-over";
      if (!reduce) rafRef.current = requestAnimationFrame(frame);
    };
    frame();
    const onKey = (e) => { if (e.key === "Escape") onClose?.(); };
    window.addEventListener("keydown", onKey);
    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener("resize", size);
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  return (
    <div className={`voice-bloom${open ? " is-open" : ""}`} aria-hidden={!open}>
      <div className="voice-bloom__field" onClick={onClose}>
        <canvas ref={canvasRef} />
      </div>
      <div className="voice-bloom__panel" role="status" aria-live="polite">
        <span className="voice-bloom__spark" aria-hidden>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
            <path d="M12 2v20M2 12h20M5 5l14 14M19 5 5 19" />
          </svg>
        </span>
        <div className="voice-bloom__label">
          Listening — press <kbd>esc</kbd> to stop
        </div>
        <div className="voice-bloom__transcript">{transcript}</div>
      </div>
      <style>{`
        .voice-bloom{position:fixed;inset:0;z-index:80;display:none;pointer-events:none}
        .voice-bloom.is-open{display:block}
        .voice-bloom__field{position:absolute;left:0;right:0;bottom:0;height:62vh;pointer-events:auto;
          -webkit-mask-image:linear-gradient(to top,#000 28%,transparent 100%);
          mask-image:linear-gradient(to top,#000 28%,transparent 100%);
          opacity:0;transition:opacity .5s var(--ease)}
        .voice-bloom.is-open .voice-bloom__field{opacity:1}
        .voice-bloom__field canvas{width:100%;height:100%;display:block;filter:blur(26px) saturate(1.12)}
        .voice-bloom__panel{position:absolute;left:0;right:0;bottom:48px;display:flex;flex-direction:column;
          align-items:center;gap:18px;pointer-events:auto;transform:translateY(14px);opacity:0;
          transition:transform .5s var(--ease),opacity .5s var(--ease)}
        .voice-bloom.is-open .voice-bloom__panel{transform:none;opacity:1}
        .voice-bloom__spark{width:40px;height:40px;color:var(--molten-ink);display:grid;place-items:center}
        .voice-bloom__spark svg{width:40px;height:40px;animation:voiceSpark 2.2s ease-in-out infinite}
        @keyframes voiceSpark{0%,100%{transform:scale(1) rotate(0);opacity:.85}50%{transform:scale(1.12) rotate(8deg);opacity:1}}
        .voice-bloom__label{font-size:17px;color:var(--molten-ink);font-weight:500;display:flex;align-items:center;gap:10px}
        .voice-bloom__label kbd{font-family:var(--font-mono);font-size:11px;background:rgba(92,26,6,.1);
          border:.5px solid rgba(92,26,6,.25);border-radius:4px;padding:2px 6px;color:var(--molten-ink)}
        .voice-bloom__transcript{font-size:15px;color:var(--text-secondary);min-height:22px;max-width:560px;text-align:center}
        [data-theme="dark"] .voice-bloom__label,[data-theme="dark"] .voice-bloom__spark{color:#FFD9C9}
        @media (prefers-reduced-motion:reduce){.voice-bloom__field canvas{filter:blur(30px)}}
      `}</style>
    </div>
  );
}
