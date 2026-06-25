'use client';

import { useState, type ReactNode } from 'react';

export interface ExpandingRailItem {
  id: string;
  label?: string;
  icon?: ReactNode;
  route?: string;
  active?: boolean;
  /** Render a hairline separator instead of a nav item. */
  sep?: boolean;
}

export interface ExpandingRailProps {
  items?: ExpandingRailItem[];
  /** React node for the foot cluster (settings/avatar). */
  footer?: ReactNode;
  /** Brand mark node rendered in the rail head. */
  brand?: ReactNode;
  onNavigate?: (item: ExpandingRailItem) => void;
}

/**
 * ExpandingRail — the thin left rail that expands butter-smooth on hover (or
 * stays open when pinned). Width animates on --dur-slow with --ease; labels
 * fade + slide. Animates only width (with will-change) and transform/opacity on
 * labels — never layout-thrash, never lag. Collapsed 64px / expanded 248px.
 * Honors prefers-reduced-motion (transition disabled).
 */
export function ExpandingRail({ items = [], onNavigate, brand, footer }: ExpandingRailProps) {
  const [pinned, setPinned] = useState(false);
  const [hover, setHover] = useState(false);
  const expanded = pinned || hover;

  return (
    <aside
      className={`rail${expanded ? ' is-expanded' : ''}`}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <div className="rail__mark" title="Classess">
        {brand}
      </div>
      <nav className="rail__nav">
        {items.map((it) =>
          it.sep ? (
            <div key={it.id} className="rail__sep" />
          ) : (
            <button
              key={it.id}
              type="button"
              className={`rail__item${it.active ? ' is-active' : ''}`}
              onClick={() => onNavigate?.(it)}
            >
              <span className="rail__icn">{it.icon}</span>
              <span className="rail__label">{it.label}</span>
            </button>
          ),
        )}
      </nav>
      <div className="rail__foot">
        <button type="button" className="rail__pin" onClick={() => setPinned((p) => !p)}>
          <span className="rail__icn">
            <svg
              viewBox="0 0 24 24"
              width="18"
              height="18"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <path d="M9 4v16M4 9h16" />
            </svg>
          </span>
          <span className="rail__label">{pinned ? 'Unpin sidebar' : 'Pin sidebar'}</span>
        </button>
        {footer}
      </div>
      <style>{`
        .rail{--rail-collapsed:64px;--rail-expanded:248px;
          width:var(--rail-collapsed);flex:0 0 var(--rail-collapsed);background:var(--bg-surface);
          border-right:.5px solid var(--border);display:flex;flex-direction:column;padding:14px 0;z-index:40;
          position:relative;transition:width var(--dur-slow) var(--ease);will-change:width}
        .rail.is-expanded{width:var(--rail-expanded);flex-basis:var(--rail-expanded)}
        .rail__mark{width:36px;height:36px;margin:0 14px 22px;border-radius:8px;position:relative;flex:0 0 auto;
          background:radial-gradient(120% 120% at 30% 25%, var(--molten) 0%, var(--ultramarine) 70%)}
        .rail__mark::after{content:"";position:absolute;inset:0;border-radius:8px;border:.5px solid rgba(255,255,255,.25)}
        .rail__nav{display:flex;flex-direction:column;gap:2px;padding:0 12px;flex:1}
        .rail__item{display:flex;align-items:center;gap:14px;height:42px;padding:0 10px;border:0;background:transparent;
          border-radius:var(--radius-sm);color:var(--text-secondary);cursor:pointer;position:relative;overflow:hidden;
          white-space:nowrap;transition:background var(--dur) var(--ease),color var(--dur) var(--ease)}
        .rail__icn{flex:0 0 20px;width:20px;height:20px;display:grid;place-items:center}
        .rail__icn svg{width:20px;height:20px;stroke:currentColor;stroke-width:1.5;fill:none;stroke-linecap:round;stroke-linejoin:round}
        .rail__label{opacity:0;transform:translateX(-6px);font-size:14px;font-weight:450;
          transition:opacity var(--dur) var(--ease),transform var(--dur) var(--ease)}
        .rail.is-expanded .rail__label{opacity:1;transform:none}
        .rail__item:hover{background:var(--bg-sunken);color:var(--text-primary)}
        .rail__item.is-active{color:var(--signature)}
        .rail__item.is-active::before{content:"";position:absolute;left:0;top:9px;bottom:9px;width:2px;
          background:var(--signature);border-radius:2px}
        .rail__sep{height:.5px;background:var(--border);margin:10px 16px}
        .rail__foot{padding:0 12px;display:flex;flex-direction:column;gap:2px}
        .rail__pin{display:flex;align-items:center;gap:14px;height:38px;padding:0 10px;border:0;background:transparent;
          color:var(--text-tertiary);font-size:12px;cursor:pointer;border-radius:var(--radius-sm)}
        .rail__pin:hover{color:var(--text-secondary);background:var(--bg-sunken)}
        @media (prefers-reduced-motion:reduce){.rail,.rail__label{transition:none}}
      `}</style>
    </aside>
  );
}
