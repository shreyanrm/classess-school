'use client';

/* ============================================================================
   app/_components/RoleLanding.tsx — the conversation-first HOME, every role.

   The calm Gemini shape on v4.1 (spec 16.1 / prototype vidya-experience.html):
   thin ExpandingRail (left), a topbar (mono role/context line + command button
   + theme toggle, no page title), ONE light-300 large greeting (sentence case,
   no exclamation), a quiet sub-line, an ambient bloom canvas behind the composer
   (very low alpha; static under prefers-reduced-motion), ONE composer row
   (+ attach, text field, Auto model selector, mic), 3–5 proactive suggestion
   chips (the role's real next actions), and the bottom hint bar.

   Role-shaping changes ONLY the greeting, the chips, and the role line (per the
   persona module / mock). The shell is identical for every role. The floating
   Vidya orb (root layout) stays fixed bottom-right; this home routes into it via
   openVidya — one Vidya send path, never a second conversation surface.

   Ported from updates/.../components-react/ConversationHome.jsx, adapted to the
   existing repo: v4.1 tokens only, no shadows, reuses Rail / openVidya /
   openCommandPalette / useTheme / the persona-shaped GREETING + HOME_CHIPS.
   ============================================================================ */

import { useEffect, useRef, useState } from 'react';
import { Icon, useTheme } from '@classess/design-system';
import { Rail } from './Rail';
import { openVidya, newVidyaConversation } from './VidyaOrb';
import { openCommandPalette } from './CommandPalette';
import { useOnline } from '@/lib/useOnline';
import { useRole } from '@/lib/RoleContext';
import { useT } from '@/lib/i18n';
import { useProactive } from '@/lib/useProactive';
import { GREETING, HOME_CHIPS, ROLE_LABELS } from '@/lib/mock';

/** The living COOL bloom behind the composer — ultramarine (the v3 brand
   signature) at the heart, soft cobalt + violet on the flanks, a cool cyan
   drift. Gemini-soft, NO coral/warm tones anywhere. Additively blended +
   blurred so it reads as one soft, alive field of light, not three discs. */
const BLOOM_BLOBS: Array<{ x: number; y: number; r: number; c: [number, number, number]; a: number }> = [
  { x: 0.46, y: 0.56, r: 0.54, c: [60, 92, 240], a: 0.17 },   // ultramarine — brand signature heart
  { x: 0.58, y: 0.52, r: 0.48, c: [92, 138, 246], a: 0.13 },  // soft cobalt blue
  { x: 0.40, y: 0.52, r: 0.46, c: [124, 88, 232], a: 0.12 },  // violet flank
  { x: 0.54, y: 0.64, r: 0.50, c: [72, 172, 214], a: 0.09 },  // cool cyan drift
];

/** A small dot hue per chip slot — purely decorative, cool brand palette only. */
const CHIP_DOTS = ['var(--signature)', 'var(--cobalt-ink)', 'var(--violet-ink)'];

/* Hairline inline glyphs for the two affordances the icon registry does not
   carry (mic, sun/moon). currentColor stroke; no fill, no shadow. */
const MIC_SVG = (
  <svg className="ch-glyph" viewBox="0 0 24 24" aria-hidden="true">
    <path d="M12 4a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0V7a3 3 0 0 1 3-3Z" />
    <path d="M6 11a6 6 0 0 0 12 0M12 17v3" />
  </svg>
);
const SUN_SVG = (
  <svg className="ch-glyph" viewBox="0 0 24 24" aria-hidden="true">
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M19 5l-1.5 1.5M6.5 17.5 5 19" />
  </svg>
);
const MOON_SVG = (
  <svg className="ch-glyph" viewBox="0 0 24 24" aria-hidden="true">
    <path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z" />
  </svg>
);

export function RoleLanding() {
  const online = useOnline();
  const { role, setRole } = useRole();
  const { theme, toggleTheme } = useTheme();
  const { t } = useT();
  const [value, setValue] = useState('');
  // The suggestion chips are real next actions drawn from the proactive loop
  // (spec 16.1 / 13 b11): gateway-first via the recommend endpoint, falling back
  // to the persona-shaped HOME_CHIPS while the feed loads / is unavailable. Each
  // chip seeds Vidya with that prepared action — the decision still happens in
  // the conversation or the approval queue (never auto-fires here).
  const proactive = useProactive();
  const liveChips =
    proactive.phase === 'ready' && proactive.recommendations.length > 0
      ? proactive.recommendations.slice(0, 5).map((r) => ({ key: r.id, label: r.actionLabel, prompt: r.title }))
      : null;
  const chips =
    liveChips ?? HOME_CHIPS[role].map((c) => ({ key: c, label: c, prompt: c }));
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  // The "Auto" model selector — a small anchored frosted popover (spec 16.3 /
  // 16.4). Config only: it picks how the turn is routed, never price or scope;
  // the spine still decides the concrete model. Auto = let Vidya choose best-fit.
  const [modelOpen, setModelOpen] = useState(false);
  const [model, setModel] = useState('Auto');
  const MODELS = ['Auto', 'Fast', 'Deep reasoning'];

  // Ambient bloom — atmosphere only. Honours prefers-reduced-motion: one static
  // paint, no animation frame. Otherwise the blobs drift on a slow ~7s loop.
  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    const ctx = cv.getContext('2d');
    if (!ctx) return;
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    let w = 0;
    let h = 0;
    let raf = 0;
    let t = 0;
    const dpr = window.devicePixelRatio || 1;
    const size = () => {
      w = cv.width = cv.offsetWidth * dpr;
      h = cv.height = cv.offsetHeight * dpr;
    };
    const paint = () => {
      ctx.clearRect(0, 0, w, h);
      // Additive blend so the warm + cool blobs sum into one living field of
      // light (Claude-bloom style) rather than three flat discs.
      ctx.globalCompositeOperation = 'lighter';
      BLOOM_BLOBS.forEach((b, i) => {
        const cx = (b.x + (reduce ? 0 : Math.sin(t + i * 1.7) * 0.06)) * w;
        const cy = (b.y + (reduce ? 0 : Math.cos(t * 0.9 + i) * 0.05)) * h;
        const rr = b.r * Math.max(w, h);
        const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, rr);
        g.addColorStop(0, `rgba(${b.c[0]},${b.c[1]},${b.c[2]},${b.a})`);
        g.addColorStop(0.6, `rgba(${b.c[0]},${b.c[1]},${b.c[2]},${b.a * 0.35})`);
        g.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, w, h);
      });
      ctx.globalCompositeOperation = 'source-over';
    };
    const frame = () => {
      t += 0.0024;
      paint();
      raf = requestAnimationFrame(frame);
    };
    // Pause the loop when the tab is hidden (spec 20.4) — no point burning a
    // background-tab frame budget on an atmosphere layer no one can see.
    const onVisibility = () => {
      if (reduce) return;
      cancelAnimationFrame(raf);
      if (!document.hidden) frame();
    };
    size();
    window.addEventListener('resize', size);
    document.addEventListener('visibilitychange', onVisibility);
    if (reduce) paint();
    else frame();
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', size);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, []);

  // Every chip and the composer route into the ONE Vidya send path (the orb).
  const ask = (q?: string) => {
    const text = (q ?? value).trim();
    if (!text) return;
    openVidya(text);
    setValue('');
  };

  return (
    <div className="app-frame" data-surface={role}>
      <Rail role={role} onRoleChange={setRole} onNewConversation={newVidyaConversation} />

      <main className="app-main">
        {/* Topbar — no page title. Mono role/context line (left); command button
            + theme toggle (right). */}
        <div className="ch-topbar">
          <span className="ch-roleline">
            {ROLE_LABELS[role]} · {t('landing.homeSuffix')}
          </span>
          <span className="ch-topbar-actions">
            <button
              type="button"
              className="ch-cmd"
              onClick={openCommandPalette}
              aria-label="Open command palette"
              title="Command palette (⌘K)"
            >
              <Icon name="search" size="sm" />
              <kbd className="ch-kbd">⌘K</kbd>
            </button>
            <button
              type="button"
              className="rail-btn"
              onClick={toggleTheme}
              aria-label="Toggle theme"
              title={theme === 'dark' ? 'Switch to light' : 'Switch to dark'}
            >
              {theme === 'dark' ? SUN_SVG : MOON_SVG}
            </button>
          </span>
        </div>

        {!online ? (
          <div className="offline-banner" role="status">
            {t('landing.offline')}
          </div>
        ) : null}

        <section className="ch-home" data-testid="role-landing">
          <div className="ch-ambient" aria-hidden="true">
            <canvas ref={canvasRef} />
          </div>

          <div className="ch-center">
            <h1 className="ch-greet">{GREETING[role]}</h1>
            <p className="ch-sub">{t('landing.sub')}</p>

            <div className="ch-composer">
              <button className="ch-icon-btn" title="Attach" aria-label="Attach" onClick={() => openVidya()}>
                <Icon name="plus" size="sm" />
              </button>
              <input
                value={value}
                onChange={(e) => setValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') ask();
                }}
                placeholder={t('landing.askPlaceholder')}
                aria-label={t('landing.askPlaceholder')}
                data-testid="home-composer-input"
              />
              {/* Auto model selector — config-only affordance; routing is decided
                  in the spine. A click opens a small anchored frosted popover. */}
              <div className="ch-model-wrap">
                <button
                  className="ch-model"
                  onClick={() => setModelOpen((o) => !o)}
                  title={`Model: ${model}`}
                  aria-haspopup="menu"
                  aria-expanded={modelOpen}
                >
                  {model}
                  <Icon name="chevron-down" size="sm" />
                </button>
                {modelOpen ? (
                  <>
                    <div className="ch-model-scrim" onClick={() => setModelOpen(false)} aria-hidden="true" />
                    <div className="ch-model-pop" role="menu" aria-label="Model">
                      {MODELS.map((m) => (
                        <button
                          key={m}
                          role="menuitemradio"
                          aria-checked={m === model}
                          className={`ch-model-opt${m === model ? ' is-sel' : ''}`}
                          onClick={() => {
                            setModel(m);
                            setModelOpen(false);
                          }}
                        >
                          {m}
                        </button>
                      ))}
                    </div>
                  </>
                ) : null}
              </div>
              <button className="ch-icon-btn ch-mic" title="Voice (or hold Space)" aria-label="Voice" onClick={() => openVidya()}>
                {MIC_SVG}
              </button>
            </div>

            <div className="ch-chips">
              {chips.map((chip, i) => (
                <button
                  key={chip.key}
                  className="ch-chip"
                  onClick={() => ask(chip.prompt)}
                  title={liveChips ? chip.prompt : undefined}
                >
                  <span className="ch-dot" style={{ background: CHIP_DOTS[i % CHIP_DOTS.length] }} />
                  {chip.label}
                </button>
              ))}
            </div>
          </div>

          {/* Bottom hint bar — the quiet affordances (spec 16.1). */}
          <div className="ch-hints" aria-hidden="true">
            <span><kbd className="ch-kbd">⌘K</kbd> commands</span>
            <span><kbd className="ch-kbd">Space</kbd> talk to Vidya</span>
            <span>Tap the orb anytime</span>
            <span>Hover the rail to expand</span>
          </div>
        </section>
      </main>

      <style>{`
        .ch-topbar{display:flex;align-items:center;justify-content:space-between;padding:var(--space-4) var(--space-6);}
        .ch-roleline{font-family:var(--font-mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--text-tertiary);}
        .ch-topbar-actions{display:flex;align-items:center;gap:var(--space-2);}
        .ch-cmd{display:flex;align-items:center;gap:var(--space-2);height:32px;padding:0 var(--space-3);border:var(--border-width) solid var(--border);
          background:var(--bg-surface);border-radius:var(--radius-sm);color:var(--text-secondary);cursor:pointer;
          transition:border-color var(--dur) var(--ease),color var(--dur) var(--ease);}
        .ch-cmd:hover{border-color:var(--border-strong);color:var(--text-primary);}
        .ch-kbd{font-family:var(--font-mono);font-size:10px;letter-spacing:.04em;color:var(--text-tertiary);
          border:var(--border-width) solid var(--border);border-radius:4px;padding:1px 5px;background:var(--bg-sunken);}

        .ch-home{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;position:relative;padding:0 var(--space-6);overflow:hidden;}
        .ch-ambient{position:absolute;inset:0;pointer-events:none;z-index:0;
          -webkit-mask-image:radial-gradient(58% 52% at 50% 57%,#000 22%,transparent 92%);
          mask-image:radial-gradient(58% 52% at 50% 57%,#000 22%,transparent 92%);}
        .ch-ambient canvas{width:100%;height:100%;display:block;filter:blur(62px) saturate(1.05);opacity:.78;}
        .ch-center{position:relative;z-index:2;width:100%;max-width:720px;text-align:center;}
        .ch-greet{font-size:46px;font-weight:300;letter-spacing:-.025em;line-height:1.08;margin:0;color:var(--text-primary);}
        .ch-sub{margin-top:var(--space-4);color:var(--text-secondary);font-size:16px;}

        .ch-composer{margin-top:var(--space-7);background:var(--bg-raised);border:var(--border-width) solid var(--border-strong);
          border-radius:var(--radius-md);padding:var(--space-2);display:flex;align-items:center;gap:var(--space-2);
          transition:border-color var(--dur) var(--ease);}
        .ch-composer:focus-within{border-color:var(--signature);}
        .ch-composer input{flex:1;border:0;background:transparent;outline:none;font-family:var(--font-sans);font-size:16px;
          color:var(--text-primary);padding:0 var(--space-1);}
        .ch-composer input::placeholder{color:var(--text-tertiary);}
        .ch-icon-btn{width:40px;height:40px;border:0;background:transparent;border-radius:var(--radius-sm);display:grid;place-items:center;
          cursor:pointer;color:var(--text-secondary);transition:background var(--dur) var(--ease),color var(--dur) var(--ease);}
        .ch-icon-btn:hover{background:var(--bg-sunken);color:var(--text-primary);}
        .ch-glyph{width:20px;height:20px;stroke:currentColor;stroke-width:1.5;fill:none;stroke-linecap:round;stroke-linejoin:round;}
        .ch-mic:hover{background:var(--bg-sunken);color:var(--signature);}
        .ch-model{display:flex;align-items:center;gap:var(--space-1);font-size:13px;color:var(--text-secondary);padding:var(--space-2) var(--space-3);
          border:0;background:transparent;border-radius:var(--radius-sm);cursor:pointer;font-family:var(--font-sans);
          transition:background var(--dur) var(--ease);}
        .ch-model:hover{background:var(--bg-sunken);}
        .ch-model-wrap{position:relative;}
        .ch-model-scrim{position:fixed;inset:0;z-index:40;}
        .ch-model-pop{position:absolute;bottom:calc(100% + var(--space-2));right:0;z-index:41;min-width:160px;
          background:var(--frost-bg);backdrop-filter:var(--frost-blur);-webkit-backdrop-filter:var(--frost-blur);
          border:var(--border-width) solid var(--border);border-radius:var(--radius-sm);padding:var(--space-1);
          display:flex;flex-direction:column;gap:2px;}
        .ch-model-opt{text-align:left;font-size:13px;color:var(--text-secondary);background:transparent;border:0;
          padding:var(--space-2) var(--space-3);border-radius:var(--radius-sm);cursor:pointer;font-family:var(--font-sans);
          transition:background var(--dur) var(--ease),color var(--dur) var(--ease);}
        .ch-model-opt:hover{background:var(--bg-sunken);color:var(--text-primary);}
        .ch-model-opt.is-sel{color:var(--signature);}

        .ch-chips{display:flex;flex-wrap:wrap;gap:var(--space-2);justify-content:center;margin-top:var(--space-5);}
        .ch-chip{font-size:13px;color:var(--text-secondary);background:var(--bg-surface);border:var(--border-width) solid var(--border);
          padding:7px 13px;border-radius:var(--radius-sm);cursor:pointer;position:relative;overflow:hidden;z-index:0;
          transition:color var(--dur) var(--ease),border-color var(--dur) var(--ease);}
        .ch-chip::before{content:"";position:absolute;inset:0;background:var(--signature);transform:translateY(100%);
          transition:transform var(--dur) var(--ease);z-index:-1;}
        .ch-chip:hover{color:#fff;border-color:var(--signature);}
        .ch-chip:hover::before{transform:translateY(0);}
        .ch-dot{display:inline-block;width:6px;height:6px;border-radius:50%;margin-right:7px;vertical-align:middle;}

        .ch-hints{position:absolute;bottom:var(--space-5);left:0;right:0;z-index:2;display:flex;flex-wrap:wrap;gap:var(--space-5);
          justify-content:center;font-size:12px;color:var(--text-tertiary);}
        .ch-hints span{display:inline-flex;align-items:center;gap:var(--space-2);}

        @media (prefers-reduced-motion: reduce){
          .ch-chip,.ch-chip::before,.ch-composer,.ch-cmd,.ch-icon-btn,.ch-model{transition:none;}
        }
        @media (max-width: 720px){
          .ch-greet{font-size:34px;}
          .ch-hints{display:none;}
        }
      `}</style>
    </div>
  );
}
