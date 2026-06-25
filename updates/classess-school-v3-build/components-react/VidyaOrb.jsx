import React from "react";

/**
 * VidyaOrb — the living floating presence of Vidya.
 *
 * A ~52px circle, fixed bottom-right on every surface. The core is a layered
 * radial gradient (molten -> ultramarine -> violet) that drifts and breathes.
 * Click (or the universal shortcut / hold-Space) opens voice mode.
 *
 * Tokens only — see design-system/tokens.css. No shadow; depth = hairline ring
 * + living gradient. Honors prefers-reduced-motion (static, still beautiful).
 *
 * Port note: this is the canonical idle-orb. The collapsed VidyaDock on deep
 * pages reuses it. Reference: prototype/vidya-experience.html (.orb).
 */
export default function VidyaOrb({ onActivate, hint = "Talk to Vidya" }) {
  return (
    <button
      type="button"
      className="vidya-orb"
      aria-label="Talk to Vidya"
      onClick={onActivate}
    >
      <span className="vidya-orb__ring" />
      <span className="vidya-orb__core" />
      <span className="vidya-orb__glass" />
      <span className="vidya-orb__spark" aria-hidden>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
          <path d="M12 3v18M3 12h18M6 6l12 12M18 6 6 18" />
        </svg>
      </span>
      <span className="vidya-orb__hint">
        {hint} · <kbd>Space</kbd>
      </span>
      <style>{`
        .vidya-orb{position:fixed;right:26px;bottom:26px;width:52px;height:52px;border:0;padding:0;
          border-radius:50%;cursor:pointer;z-index:60;display:grid;place-items:center;background:transparent;
          transition:transform var(--dur) var(--ease)}
        .vidya-orb:hover{transform:scale(1.06)} .vidya-orb:active{transform:scale(.96)}
        .vidya-orb__ring{position:absolute;inset:0;border-radius:50%;border:.5px solid var(--border-strong)}
        .vidya-orb__core{position:absolute;inset:6px;border-radius:50%;overflow:hidden;
          background:
            radial-gradient(120% 120% at 30% 22%, var(--molten) 0%, transparent 55%),
            radial-gradient(120% 120% at 72% 78%, var(--ultramarine) 0%, transparent 60%),
            radial-gradient(140% 140% at 50% 50%, var(--violet) 0%, var(--ultramarine) 80%);
          background-size:200% 200%,200% 200%,160% 160%;
          animation:vidyaOrbDrift 7s var(--ease) infinite, vidyaOrbBreath 3.6s ease-in-out infinite;
          filter:saturate(1.05)}
        .vidya-orb__glass{position:absolute;inset:6px;border-radius:50%;
          background:radial-gradient(100% 70% at 32% 22%, rgba(255,255,255,.5), transparent 50%)}
        .vidya-orb__spark{position:absolute;inset:0;display:grid;place-items:center;color:#fff;opacity:.95}
        .vidya-orb__spark svg{width:18px;height:18px}
        .vidya-orb__hint{position:absolute;right:60px;top:50%;transform:translateY(-50%) translateX(6px);opacity:0;
          background:var(--bg-inverse);color:var(--text-inverse);font-size:11.5px;padding:6px 10px;border-radius:6px;
          white-space:nowrap;pointer-events:none;transition:opacity var(--dur) var(--ease),transform var(--dur) var(--ease)}
        .vidya-orb:hover .vidya-orb__hint{opacity:1;transform:translateY(-50%) translateX(0)}
        .vidya-orb__hint kbd{background:rgba(255,255,255,.14);border:.5px solid rgba(255,255,255,.2);
          border-radius:4px;padding:1px 5px;font-family:var(--font-mono);font-size:10px}
        @keyframes vidyaOrbDrift{0%{background-position:0% 30%,100% 70%,50% 50%}
          50%{background-position:100% 60%,0% 40%,60% 55%}100%{background-position:0% 30%,100% 70%,50% 50%}}
        @keyframes vidyaOrbBreath{0%,100%{transform:scale(1)}50%{transform:scale(1.05)}}
        @media (prefers-reduced-motion:reduce){.vidya-orb__core{animation:none}}
      `}</style>
    </button>
  );
}
