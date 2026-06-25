'use client';

/* ============================================================================
   app/_components/CommandPalette.tsx — the universal Cmd/Ctrl-K launcher.

   A fast launcher available EVERYWHERE (spec 17.3). Mounted once at the app root
   beside the orb. Cmd/Ctrl-K (or the topbar command button, via the open event)
   toggles a centered-near-top FROSTED panel over a scrim — hairline border,
   radius-md, NO shadow. The keyboard twin of the orb.

   It REUSES the existing Vidya entry points rather than rebuilding any of it:
     - Talk to Vidya (voice) → openVidya() with no prompt → the orb opens
       voice-first and the VoiceBloom blooms (spec 17.2).
     - Ask Vidya → openVidya(query) → the orb opens a thread with the query.
     - Go to → router.push(route) (and the orb stays mounted as the dock).
   The route set + plain-language labels are the single source of truth in
   lib/vidya.ts (NAV_TARGETS / NAV_LABELS) — the same set the orchestrator
   validates against, so the palette can never jump anywhere Vidya cannot.

   Keyboard (spec 17.4): Up/Down move, Enter runs, Esc closes (top-most overlay
   first — the palette claims Escape while open and stops propagation so the orb
   does not also close). Cmd/Ctrl-/ opens the shortcut cheatsheet. The first
   option is pre-selected; mouse hover selects. prefers-reduced-motion: the open
   transition is dropped in CSS.
   ============================================================================ */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Icon } from '@classess/design-system';
import { NAV_TARGETS, NAV_LABELS, type NavTarget } from '@/lib/vidya';
import { openVidya } from './VidyaOrb';

/** The window event the topbar command button dispatches to open the palette. */
export const PALETTE_OPEN_EVENT = 'palette:open';

/** Open the command palette from anywhere (e.g. a topbar button). */
export function openCommandPalette(): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(PALETTE_OPEN_EVENT));
}

/** One row in the palette. `run` performs the action; `section` groups it. */
interface PaletteItem {
  id: string;
  section: 'suggested' | 'go';
  label: string;
  sub?: string;
  icon: 'spark' | 'send' | 'arrow-right' | 'search';
  run: () => void;
}

/** The universal shortcut cheatsheet (spec 17.4) — documented, never hidden. */
const SHORTCUTS: Array<{ keys: string; label: string }> = [
  { keys: '⌘ K', label: 'Open the command palette' },
  { keys: 'Hold Space', label: 'Talk to Vidya (when not typing)' },
  { keys: 'Esc', label: 'Close the top-most overlay' },
  { keys: '⌘ /', label: 'Show this shortcut list' },
];

export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [cheatsheet, setCheatsheet] = useState(false);
  const [q, setQ] = useState('');
  const [sel, setSel] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);

  // The universal shortcuts (spec 17.4). Cmd/Ctrl-K toggles the palette; Cmd/Ctrl-/
  // shows the cheatsheet. Registered once at the root so they work on every surface.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setCheatsheet(false);
        setOpen((o) => !o);
      } else if (mod && e.key === '/') {
        e.preventDefault();
        setCheatsheet((c) => !c);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // The topbar command button opens the palette through the shared event.
  useEffect(() => {
    function onOpen() {
      setCheatsheet(false);
      setOpen(true);
    }
    window.addEventListener(PALETTE_OPEN_EVENT, onOpen);
    return () => window.removeEventListener(PALETTE_OPEN_EVENT, onOpen);
  }, []);

  // Reset query + focus the input each time the palette opens.
  useEffect(() => {
    if (!open) return;
    setQ('');
    setSel(0);
    const id = window.setTimeout(() => inputRef.current?.focus(), 30);
    return () => window.clearTimeout(id);
  }, [open]);

  function close() {
    setOpen(false);
  }

  // The full, static command set. Suggested rows are always present (voice +
  // ask); "Go to" reuses the validated route set + plain labels from lib/vidya.
  const allItems = useMemo<PaletteItem[]>(() => {
    const suggested: PaletteItem[] = [
      {
        id: 'voice',
        section: 'suggested',
        label: 'Talk to Vidya',
        sub: 'voice',
        icon: 'spark',
        // No prompt → the orb opens voice-first and blooms (spec 17.2).
        run: () => openVidya(),
      },
      {
        id: 'ask',
        section: 'suggested',
        label: q.trim() ? `Ask Vidya: “${q.trim()}”` : 'Ask Vidya a question',
        sub: 'chat',
        icon: 'send',
        run: () => openVidya(q.trim() || undefined),
      },
    ];
    const go: PaletteItem[] = NAV_TARGETS.map((href) => ({
      id: `go:${href}`,
      section: 'go',
      label: NAV_LABELS[href as NavTarget],
      sub: href,
      icon: 'arrow-right',
      // Go to → route (the orb stays mounted as the dock across navigation).
      run: () => router.push(href),
    }));
    return [...suggested, ...go];
  }, [q, router]);

  // Live filter. The "Ask" row always survives (it carries the typed query); the
  // voice row and routes filter on label + route path.
  const filtered = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return allItems;
    return allItems.filter(
      (c) => c.id === 'ask' || c.label.toLowerCase().includes(t) || (c.sub ?? '').toLowerCase().includes(t),
    );
  }, [allItems, q]);

  // Keep the selection in range as the filtered set changes.
  useEffect(() => {
    setSel((s) => Math.min(s, Math.max(0, filtered.length - 1)));
  }, [filtered.length]);

  function runItem(item: PaletteItem | undefined) {
    if (!item) return;
    close();
    item.run();
  }

  function onKeyNav(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSel((s) => Math.min(s + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSel((s) => Math.max(s - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      runItem(filtered[sel]);
    } else if (e.key === 'Escape') {
      // The palette is the top-most overlay while open: claim Escape and stop it
      // bubbling so the orb's own Escape handler does not also fire (spec 17.4).
      e.preventDefault();
      e.stopPropagation();
      close();
    }
  }

  if (cheatsheet) {
    return (
      <>
        <div className="cmdk-scrim" onClick={() => setCheatsheet(false)} />
        <div className="cmdk cmdk-sheet" role="dialog" aria-label="Keyboard shortcuts">
          <div className="cmdk-head">
            <span className="overline" style={{ margin: 0 }}>
              Keyboard shortcuts
            </span>
            <button
              type="button"
              className="rail-btn"
              aria-label="Close shortcuts"
              onClick={() => setCheatsheet(false)}
            >
              <Icon name="close" size="sm" />
            </button>
          </div>
          <div className="cmdk-sheet-list">
            {SHORTCUTS.map((s) => (
              <div key={s.keys} className="cmdk-sheet-row">
                <span className="body-sm">{s.label}</span>
                <kbd className="cmdk-kbd">{s.keys}</kbd>
              </div>
            ))}
          </div>
        </div>
      </>
    );
  }

  if (!open) return null;

  // Index the first row of each section so we can print a section heading once.
  let lastSection: PaletteItem['section'] | null = null;

  return (
    <>
      <div className="cmdk-scrim" onClick={close} />
      <div className="cmdk" role="dialog" aria-label="Command palette" data-testid="command-palette">
        <div className="cmdk-head">
          <Icon name="search" size="sm" />
          <input
            ref={inputRef}
            className="cmdk-input"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setSel(0);
            }}
            onKeyDown={onKeyNav}
            placeholder="Search, jump to a page, or ask Vidya"
            aria-label="Command palette search"
            data-testid="command-palette-input"
          />
          <kbd className="cmdk-kbd">esc</kbd>
        </div>
        <div className="cmdk-list" role="listbox">
          {filtered.length === 0 ? (
            <p className="body-sm muted cmdk-empty">Nothing matches. Try “Ask Vidya”.</p>
          ) : (
            filtered.map((c, i) => {
              const heading =
                c.section !== lastSection ? (c.section === 'suggested' ? 'Suggested' : 'Go to') : null;
              lastSection = c.section;
              return (
                <div key={c.id}>
                  {heading ? <p className="overline cmdk-section">{heading}</p> : null}
                  <button
                    type="button"
                    role="option"
                    aria-selected={i === sel}
                    className={`cmdk-opt${i === sel ? ' is-sel' : ''}${c.id === 'voice' ? ' is-voice' : ''}`}
                    onMouseEnter={() => setSel(i)}
                    onClick={() => runItem(c)}
                  >
                    <span className="cmdk-icn">
                      <Icon name={c.icon} size="sm" />
                    </span>
                    <span className="cmdk-label">{c.label}</span>
                    {c.sub ? <span className="cmdk-sub">{c.sub}</span> : null}
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>
    </>
  );
}
