import React, { useEffect, useRef, useState } from "react";

/**
 * GenerativeSurface — the Path-2 pattern: a request becomes a real, interactive
 * component that *takes shape* in the thread. The frame draws itself (border-draw),
 * contents stagger in, bars grow from zero. Every composed component is generated-
 * and-verified before it renders, and carries its own actions (primary rise-fill,
 * "Open in <page>" fill-wipe, "Why this" -> EvidenceDrawer).
 *
 * This is a worked example (a Mathematics mastery view). In production, the inner
 * content is chosen by the generative-UI engine per the taxonomy in doc 16.
 *
 * Props:
 *   accent     — subject hue var, e.g. "var(--violet)"
 *   onPrimary, onOpenPage, onWhy
 *
 * Reference: prototype/vidya-experience.html (.gencard / .viz / .mastery).
 */
export default function GenerativeSurface({ accent = "var(--violet)", onPrimary, onOpenPage, onWhy }) {
  const [drawn, setDrawn] = useState(false);
  const barsRef = useRef(null);

  useEffect(() => {
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const t = setTimeout(() => {
      setDrawn(true);
      const bars = barsRef.current?.querySelectorAll(".gs__fill");
      const vals = ["86%", "78%", "41%"];
      bars?.forEach((b, i) => setTimeout(() => (b.style.width = vals[i]), reduce ? 0 : 200 + i * 140));
    }, 120);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className={`gs${drawn ? " is-drawn" : ""}`} style={{ "--mc": accent }}>
      <svg className="gs__frame" viewBox="0 0 100 100" preserveAspectRatio="none">
        <rect x="0.5" y="0.5" width="99" height="99" rx="5" pathLength="1" />
      </svg>

      <div className="gs__k">Mathematics · independence-aware</div>
      <div className="gs__t">Trigonometry</div>

      <div className="gs__mastery">
        <span className="gs__state">You can solve familiar problems on your own</span>
        <span className="gs__dim">Word-problem ratios are still support-dependent — the next thing to close</span>
      </div>

      <div className="gs__viz" ref={barsRef}>
        {[["Ratios (unaided)", accent], ["Heights & distances", accent], ["Word problems", "var(--molten)"]].map(([nm, c], i) => (
          <div className="gs__bar" key={i}>
            <span className="gs__nm">{nm}</span>
            <span className="gs__trk"><i className="gs__fill" style={{ background: c }} /></span>
          </div>
        ))}
      </div>

      <div className="gs__row">
        <button className="gs__btn gs__btn--rise gs__btn--primary" onClick={onPrimary}>
          Start the 15-minute fix
          <svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
        </button>
        <button className="gs__btn gs__btn--wipe" onClick={onOpenPage}>Open in Progress</button>
        <button className="gs__btn gs__btn--rise" onClick={onWhy}>Why this</button>
      </div>

      <style>{`
        .gs{position:relative;background:var(--bg-surface);border:.5px solid var(--border);border-radius:var(--radius-md);
          padding:22px;overflow:hidden}
        .gs__frame{position:absolute;inset:0;pointer-events:none}
        .gs__frame rect{fill:none;stroke:var(--signature);stroke-width:1.5;vector-effect:non-scaling-stroke;
          stroke-dasharray:1;stroke-dashoffset:1;transition:stroke-dashoffset .7s var(--ease)}
        .gs.is-drawn .gs__frame rect{stroke-dashoffset:0}
        .gs__k{font-family:var(--font-mono);font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--mc)}
        .gs__t{font-size:20px;font-weight:500;letter-spacing:-.015em;margin-top:8px}
        .gs__mastery{display:flex;flex-direction:column;gap:2px;margin-top:18px;padding:14px;border:.5px solid var(--border);
          border-radius:var(--radius-sm);background:var(--bg-canvas)}
        .gs__state{font-size:14px;font-weight:500} .gs__dim{font-size:12.5px;color:var(--text-secondary)}
        .gs__viz{margin-top:18px;display:flex;flex-direction:column;gap:9px}
        .gs__bar{display:flex;align-items:center;gap:12px}
        .gs__nm{width:140px;font-size:12.5px;color:var(--text-secondary)}
        .gs__trk{flex:1;height:7px;background:var(--bg-sunken);border-radius:999px;overflow:hidden}
        .gs__fill{display:block;height:100%;width:0;border-radius:999px;transition:width 1s var(--ease)}
        .gs__row{display:flex;gap:10px;margin-top:18px;flex-wrap:wrap}
        .gs__btn{font-family:var(--font-sans);font-size:13.5px;font-weight:500;border-radius:var(--radius-sm);
          padding:9px 16px;cursor:pointer;border:.5px solid var(--border-strong);background:var(--bg-surface);
          color:var(--text-primary);display:inline-flex;align-items:center;gap:8px;position:relative;overflow:hidden;z-index:0;
          transition:color var(--dur) var(--ease),border-color var(--dur) var(--ease)}
        .gs__btn svg{width:16px;height:16px;stroke:currentColor;stroke-width:1.5;fill:none;stroke-linecap:round;transition:transform .3s var(--ease)}
        .gs__btn--primary{background:var(--signature);color:#fff;border-color:var(--signature)}
        .gs__btn--primary:hover svg{transform:translateX(4px)}
        .gs__btn--rise::before{content:"";position:absolute;inset:0;background:var(--signature);transform:translateY(100%);
          transition:transform .32s var(--ease);z-index:-1}
        .gs__btn--rise:hover{color:#fff;border-color:var(--signature)} .gs__btn--rise:hover::before{transform:translateY(0)}
        .gs__btn--wipe::before{content:"";position:absolute;inset:0;background:var(--signature);transform:scaleX(0);
          transform-origin:left;transition:transform .4s var(--ease);z-index:-1}
        .gs__btn--wipe:hover{color:#fff;border-color:var(--signature)} .gs__btn--wipe:hover::before{transform:scaleX(1)}
        @media (prefers-reduced-motion:reduce){.gs__frame rect{transition:none}.gs__fill{transition:none}}
      `}</style>
    </div>
  );
}
