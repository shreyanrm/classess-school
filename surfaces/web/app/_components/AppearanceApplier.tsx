'use client';

/* ============================================================================
   AppearanceApplier — applies the persisted Appearance to <html>.

   The user's chosen theme palette + subject-accent tint + visual-accessibility
   mode live in the store (lib/store: Appearance). This tiny client component
   reads them and stamps the matching attributes onto the document root so the
   whole surface re-skins from one place:

     • data-theme   — light / dark (the existing token flip in tokens.css).
     • data-accent  — an optional chosen cool subject hue. globals.css maps it to
                      --accent so the WHOLE surface reads in the chosen hue,
                      overriding the per-surface data-surface default. Brand law:
                      the cool subject palette only — never coral, never warm.
     • data-large-text / data-high-contrast / data-reduce-motion — the
                      visual-accessibility mode toggles, each a globals.css hook.

   It renders nothing. SSR-safe: the DOM write happens in an effect, so the
   server paint and first client paint agree (the default 'light' theme) and the
   persisted look is applied right after mount. Reduced-motion is additive — the
   OS @media query still wins; this only lets a user opt IN to reduced motion.
   ============================================================================ */

import { useEffect } from 'react';
import { useStore } from '@/lib/useStore';
import { defaultAppearance } from '@/lib/store';

export function AppearanceApplier() {
  const { appearance } = useStore();

  useEffect(() => {
    if (typeof document === 'undefined') return;
    const root = document.documentElement;
    const a = { ...defaultAppearance(), ...appearance };

    // Theme palette — authoritative for the persisted choice. (ThemeProvider
    // also writes data-theme; this reflects the user's saved preference.)
    root.setAttribute('data-theme', a.theme);

    // Optional chosen accent — when set, the whole surface reads in this hue.
    if (a.accent) root.setAttribute('data-accent', a.accent);
    else root.removeAttribute('data-accent');

    // Visual-accessibility mode — additive globals.css hooks.
    root.toggleAttribute('data-large-text', a.largeText);
    root.toggleAttribute('data-high-contrast', a.highContrast);
    root.toggleAttribute('data-reduce-motion', a.reduceMotion);
  }, [appearance]);

  return null;
}
