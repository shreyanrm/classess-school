import React, { useEffect, useRef, useState } from "react";

/**
 * CrystallizeNode — the signature mastery moment that replaces the ignite ring.
 *
 * A concept node resolves from soft + grainy to crisp ultramarine and locks into
 * the knowledge lattice. Three variants:
 *   "a" lattice lock-in  — resolve + glint, then hairline edges draw to neighbors (default, knowledge view)
 *   "b" facet bloom      — fill rises into the facet + glint (inline single concept)
 *   "c" constellation    — node snaps crisp, light runs out along each wire (the rare big unlock)
 *
 * Props:
 *   variant   — "a" | "b" | "c" (default "a")
 *   resolved  — controlled state; when it flips false->true, the moment plays
 *   label     — caption under the node
 *   neighbors — [{ x, y, label }] relative offsets for variants a/c
 *
 * Tokens only. Reduced-motion shows the resolved end-state with no animation.
 * Reference: prototype/signature-and-motion.html.
 */
export default function CrystallizeNode({ variant = "a", resolved = false, label, neighbors = [] }) {
  const [play, setPlay] = useState(false);
  const [lit, setLit] = useState(resolved);
  const prev = useRef(resolved);

  useEffect(() => {
    if (resolved && !prev.current) {
      const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (reduce) { setLit(true); }
      else {
        setPlay(true);
        const t1 = setTimeout(() => setLit(true), variant === "c" ? 120 : 360);
        const t2 = setTimeout(() => setPlay(false), 1000);
        return () => { clearTimeout(t1); clearTimeout(t2); };
      }
    }
    prev.current = resolved;
  }, [resolved, variant]);

  const cx = 130, cy = 90;
  return (
    <div className={`xtal xtal--${variant}${play ? " is-play" : ""}${lit ? " is-lit" : ""}`}>
      <svg className="xtal__wires" viewBox="0 0 260 180" preserveAspectRatio="none">
        {neighbors.map((n, i) => (
          <path key={i} className="xtal__edge" d={`M${cx} ${cy} L${n.x} ${n.y}`} pathLength="1" />
        ))}
        {variant === "c" && neighbors.map((n, i) => (
          <path key={"p" + i} className="xtal__pulse" d={`M${cx} ${cy} L${n.x} ${n.y}`} />
        ))}
      </svg>

      {neighbors.map((n, i) => (
        <Node key={i} x={n.x} y={n.y} kind="neighbor" label={n.label} />
      ))}
      <Node x={cx} y={cy} kind={`center${resolved ? " resolved" : ""}`} label={label} glint />

      <style>{`
        .xtal{position:relative;width:260px;height:180px}
        .xtal__wires{position:absolute;inset:0;width:100%;height:100%;overflow:visible}
        .xtal__edge{stroke:var(--signature);stroke-width:1.25;fill:none;stroke-dasharray:1;stroke-dashoffset:1;opacity:0;
          transition:stroke-dashoffset .6s var(--ease),opacity .3s var(--ease)}
        .xtal.is-lit .xtal__edge{opacity:.55;stroke-dashoffset:0}
        .xtal--c .xtal__edge{opacity:.28;stroke-dashoffset:0;stroke-dasharray:none}
        .xtal__pulse{stroke:#fff;stroke-width:2;fill:none;stroke-linecap:round;opacity:0}
        .xtal--c.is-play .xtal__pulse{animation:xtalPulse .8s var(--ease) both}
        .xnode{position:absolute;width:34px;height:34px;transform:translate(-50%,-50%)}
        .xnode .facet{width:100%;height:100%}
        .xnode .facet polygon{transition:fill .5s var(--ease),stroke .5s var(--ease),opacity .5s var(--ease)}
        .xnode .facet polygon{fill:var(--bg-sunken);stroke:var(--border-strong);stroke-width:1;opacity:.5}
        .xnode.neighbor .facet polygon{fill:var(--signature-tint);stroke:var(--signature);opacity:.85}
        .xnode.resolved .facet polygon{fill:var(--signature);stroke:var(--ultra-ink);opacity:1}
        .xnode .grain{position:absolute;inset:0;opacity:.5;transition:opacity .5s var(--ease);
          background:radial-gradient(circle at 30% 30%, rgba(0,0,0,.08) 1px, transparent 1.5px) 0 0/6px 6px}
        .xnode.resolved .grain{opacity:0}
        .xnode .glint{position:absolute;top:-4px;bottom:-4px;left:-30%;width:14px;opacity:0;transform:skewX(-18deg);
          background:linear-gradient(90deg,transparent,rgba(255,255,255,.9),transparent)}
        .xtal.is-play .xnode.center .facet{animation:xtalResolve .5s cubic-bezier(.34,1.4,.5,1) both}
        .xtal.is-play .xnode.center .glint{animation:xtalGlint .7s var(--ease) .15s both}
        .xnode .cap{position:absolute;top:38px;left:50%;transform:translateX(-50%);white-space:nowrap;
          font-size:11px;color:var(--text-secondary);font-weight:500}
        @keyframes xtalResolve{0%{transform:scale(.86)}60%{transform:scale(1.08)}100%{transform:scale(1)}}
        @keyframes xtalGlint{0%{left:-30%;opacity:0}25%{opacity:.95}100%{left:130%;opacity:0}}
        @keyframes xtalPulse{0%{opacity:0;stroke-dasharray:0 120}25%{opacity:1}60%{opacity:1;stroke-dasharray:30 120}
          100%{opacity:0;stroke-dasharray:0 120;stroke-dashoffset:-120}}
        @media (prefers-reduced-motion:reduce){.xtal *{animation:none!important}}
      `}</style>
    </div>
  );
}

function Node({ x, y, kind, label, glint }) {
  return (
    <div className={`xnode ${kind}`} style={{ left: x, top: y }}>
      <div className="facet">
        <svg viewBox="0 0 34 34"><polygon points="17,2 32,11 32,23 17,32 2,23 2,11" /></svg>
      </div>
      <div className="grain" />
      {glint && <div className="glint" />}
      {label && <div className="cap">{label}</div>}
    </div>
  );
}
