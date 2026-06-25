import React, { useEffect, useRef, useState } from "react";

/**
 * ConversationHome — the conversation-first home, on every role (the Gemini
 * shape, on v4.1). Calm greeting + a single composer + proactive suggestion
 * chips, over an extremely subtle living ambient bloom. Role-shaping changes only
 * the greeting, the chips, and the role line — the shell is identical.
 *
 * Props:
 *   name, roleLine
 *   chips    — [{ id, label, dot, query }]  (real proactive next-actions)
 *   onSubmit(query), onVoice()
 *
 * Reference: prototype/vidya-experience.html (.home). No exclamation marks in copy.
 */
export default function ConversationHome({ name = "there", roleLine, chips = [], onSubmit, onVoice }) {
  const [value, setValue] = useState("");
  const canvasRef = useRef(null);

  // ambient bloom — atmosphere only, very low alpha
  useEffect(() => {
    const cv = canvasRef.current;
    const ctx = cv.getContext("2d");
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    let w, h, raf;
    const size = () => { w = cv.width = cv.offsetWidth * devicePixelRatio; h = cv.height = cv.offsetHeight * devicePixelRatio; };
    size(); window.addEventListener("resize", size);
    const blobs = [
      { x: 0.42, y: 0.62, r: 0.42, c: [255, 77, 26], a: 0.05 },
      { x: 0.6, y: 0.5, r: 0.5, c: [31, 53, 224], a: 0.06 },
      { x: 0.5, y: 0.7, r: 0.36, c: [122, 47, 242], a: 0.04 },
    ];
    let t = 0;
    const frame = () => {
      t += 0.0024; ctx.clearRect(0, 0, w, h);
      blobs.forEach((b, i) => {
        const cx = (b.x + Math.sin(t + i * 1.7) * 0.05) * w;
        const cy = (b.y + Math.cos(t * 0.9 + i) * 0.04) * h;
        const rr = b.r * Math.min(w, h);
        const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, rr);
        g.addColorStop(0, `rgba(${b.c[0]},${b.c[1]},${b.c[2]},${b.a})`);
        g.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
      });
      if (!reduce) raf = requestAnimationFrame(frame);
    };
    frame();
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", size); };
  }, []);

  const submit = (q) => { const text = (q ?? value).trim(); if (text) { onSubmit?.(text); setValue(""); } };

  return (
    <section className="home">
      <div className="home__ambient"><canvas ref={canvasRef} /></div>
      <div className="home__center">
        <h1 className="home__greet">Where would you like to begin, <span>{name}</span></h1>
        <p className="home__sub">Ask anything, or pick up where you left off</p>

        <div className="home__composer">
          <button className="home__plus" title="Attach" aria-label="Attach">
            <svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14" /></svg>
          </button>
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
            placeholder="Ask Vidya, or describe what you want to do"
          />
          <button className="home__model">Auto<svg viewBox="0 0 24 24"><path d="m6 9 6 6 6-6" /></svg></button>
          <button className="home__mic" title="Voice (or hold Space)" aria-label="Voice" onClick={onVoice}>
            <svg viewBox="0 0 24 24"><path d="M12 4a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0V7a3 3 0 0 1 3-3Z" /><path d="M6 11a6 6 0 0 0 12 0M12 17v3" /></svg>
          </button>
        </div>

        <div className="home__chips">
          {chips.map((c) => (
            <button key={c.id} className="home__chip" onClick={() => submit(c.query)}>
              <span className="home__dot" style={{ background: c.dot }} />{c.label}
            </button>
          ))}
        </div>
      </div>
      {roleLine && <div className="home__role">{roleLine}</div>}

      <style>{`
        .home{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;position:relative;padding:0 24px;overflow:hidden}
        .home__ambient{position:absolute;inset:0;pointer-events:none;z-index:0;opacity:.9}
        .home__ambient canvas{width:100%;height:100%;display:block}
        .home__center{position:relative;z-index:2;width:100%;max-width:720px;text-align:center}
        .home__greet{font-size:46px;font-weight:300;letter-spacing:-.025em;line-height:1.05;margin:0;color:var(--text-primary)}
        .home__sub{margin-top:14px;color:var(--text-secondary);font-size:16px}
        .home__composer{margin-top:38px;background:var(--bg-raised);border:.5px solid var(--border-strong);border-radius:16px;
          padding:8px;display:flex;align-items:center;gap:8px;transition:border-color var(--dur) var(--ease)}
        .home__composer:focus-within{border-color:var(--signature)}
        .home__plus,.home__mic{width:40px;height:40px;border:0;background:transparent;border-radius:12px;display:grid;
          place-items:center;cursor:pointer;color:var(--text-secondary);transition:background var(--dur) var(--ease),color var(--dur) var(--ease)}
        .home__plus:hover{background:var(--bg-sunken);color:var(--text-primary)}
        .home__mic:hover{background:var(--molten-tint);color:var(--molten-ink)}
        .home__composer input{flex:1;border:0;background:transparent;outline:none;font-family:var(--font-sans);
          font-size:16px;color:var(--text-primary);padding:0 4px}
        .home__composer input::placeholder{color:var(--text-tertiary)}
        .home__model{display:flex;align-items:center;gap:6px;font-size:13px;color:var(--text-secondary);padding:8px 10px;
          border:0;background:transparent;border-radius:10px;cursor:pointer;font-family:var(--font-sans);transition:background var(--dur) var(--ease)}
        .home__model:hover{background:var(--bg-sunken)}
        .home__composer svg,.home__model svg{width:20px;height:20px;stroke:currentColor;stroke-width:1.5;fill:none;stroke-linecap:round;stroke-linejoin:round}
        .home__model svg{width:16px;height:16px}
        .home__chips{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:20px}
        .home__chip{font-size:13px;color:var(--text-secondary);background:var(--bg-surface);border:.5px solid var(--border);
          padding:7px 13px;border-radius:var(--radius-sm);cursor:pointer;position:relative;overflow:hidden;z-index:0;
          transition:color var(--dur) var(--ease),border-color var(--dur) var(--ease)}
        .home__chip::before{content:"";position:absolute;inset:0;background:var(--signature);transform:translateY(100%);
          transition:transform .3s var(--ease);z-index:-1}
        .home__chip:hover{color:#fff;border-color:var(--signature)}
        .home__chip:hover::before{transform:translateY(0)}
        .home__dot{display:inline-block;width:6px;height:6px;border-radius:50%;margin-right:7px;vertical-align:middle}
        .home__role{position:absolute;top:20px;left:26px;font-family:var(--font-mono);font-size:11px;letter-spacing:.14em;
          text-transform:uppercase;color:var(--text-tertiary)}
      `}</style>
    </section>
  );
}
