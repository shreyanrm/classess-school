import React, { useEffect, useMemo, useRef, useState } from "react";

/**
 * CommandPalette — the universal Cmd/Ctrl-K launcher.
 *
 * Frosted centered panel over a scrim. Search, jump to a page, ask Vidya, or
 * drop into voice. Mounted once at the app root. Keyboard: open with Cmd/Ctrl-K,
 * Up/Down to move, Enter to run, Esc to close.
 *
 * Props:
 *   commands  — [{ id, type:'voice'|'ask'|'route'|'action', label, sub, icon, run }]
 *   onAsk(query), onVoice() — convenience callbacks for the always-present rows
 *
 * Reference: prototype/vidya-experience.html (.palette). No shadow; frost only.
 */
export default function CommandPalette({ commands = [], onAsk, onVoice }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const inputRef = useRef(null);

  // global shortcut
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) { setQ(""); setSel(0); setTimeout(() => inputRef.current?.focus(), 40); }
  }, [open]);

  const base = useMemo(() => ([
    { id: "voice", type: "voice", label: "Talk to Vidya", sub: "voice", run: () => onVoice?.() },
    { id: "ask", type: "ask", label: q ? `Ask Vidya: "${q}"` : "Ask Vidya a question", sub: "chat", run: () => onAsk?.(q) },
    ...commands,
  ]), [commands, q, onAsk, onVoice]);

  const filtered = useMemo(() => {
    if (!q) return base;
    const t = q.toLowerCase();
    return base.filter((c) => c.type === "ask" || c.label.toLowerCase().includes(t));
  }, [base, q]);

  const onKeyNav = (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, filtered.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
    else if (e.key === "Enter") { filtered[sel]?.run?.(); setOpen(false); }
  };

  if (!open) return null;
  return (
    <>
      <div className="cmdk__scrim" onClick={() => setOpen(false)} />
      <div className="cmdk" role="dialog" aria-label="Command palette">
        <div className="cmdk__head">
          <svg viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
          <input ref={inputRef} value={q} onChange={(e) => { setQ(e.target.value); setSel(0); }}
            onKeyDown={onKeyNav} placeholder="Search, jump to a page, or ask Vidya" />
          <kbd>esc</kbd>
        </div>
        <div className="cmdk__list">
          {filtered.map((c, i) => (
            <div key={c.id} className={`cmdk__opt${i === sel ? " is-sel" : ""}${c.type === "voice" ? " is-voice" : ""}`}
              onMouseEnter={() => setSel(i)} onClick={() => { c.run?.(); setOpen(false); }}>
              <span className="cmdk__icn">{c.icon ?? defaultIcon(c.type)}</span>
              <span className="cmdk__label">{c.label}</span>
              {c.sub && <span className="cmdk__sub">{c.sub}</span>}
            </div>
          ))}
        </div>
        <style>{`
          .cmdk__scrim{position:fixed;inset:0;background:var(--scrim);z-index:90}
          .cmdk{position:fixed;left:50%;top:18%;transform:translateX(-50%);width:min(620px,92vw);z-index:91;
            background:var(--frost-bg);backdrop-filter:var(--frost-blur);-webkit-backdrop-filter:var(--frost-blur);
            border:.5px solid var(--border-strong);border-radius:var(--radius-md);overflow:hidden}
          .cmdk__head{display:flex;align-items:center;gap:12px;padding:16px 18px;border-bottom:.5px solid var(--border)}
          .cmdk__head svg{width:18px;height:18px}
          .cmdk__head input{flex:1;border:0;background:transparent;outline:none;font-family:var(--font-sans);
            font-size:16px;color:var(--text-primary)}
          .cmdk__head kbd{font-family:var(--font-mono);font-size:11px;border:.5px solid var(--border-strong);
            border-radius:4px;padding:2px 6px;color:var(--text-secondary)}
          .cmdk__list{padding:8px 10px;max-height:50vh;overflow:auto}
          .cmdk__opt{display:flex;align-items:center;gap:12px;padding:10px;border-radius:var(--radius-sm);
            cursor:pointer;color:var(--text-primary)}
          .cmdk__opt.is-sel{background:var(--bg-sunken)}
          .cmdk__icn{width:20px;height:20px;display:grid;place-items:center;color:var(--text-secondary)}
          .cmdk__icn svg{width:18px;height:18px;stroke:currentColor;stroke-width:1.5;fill:none;stroke-linecap:round;stroke-linejoin:round}
          .cmdk__opt.is-voice .cmdk__icn{color:var(--molten)}
          .cmdk__label{flex:1;font-size:14px}
          .cmdk__sub{font-size:12px;color:var(--text-tertiary)}
        `}</style>
      </div>
    </>
  );
}

function defaultIcon(type) {
  if (type === "voice")
    return (<svg viewBox="0 0 24 24"><path d="M12 4a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0V7a3 3 0 0 1 3-3Z" /><path d="M6 11a6 6 0 0 0 12 0M12 17v3" /></svg>);
  if (type === "ask")
    return (<svg viewBox="0 0 24 24"><path d="M12 3v18M3 12h18M6 6l12 12" /></svg>);
  return (<svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6" /></svg>);
}
