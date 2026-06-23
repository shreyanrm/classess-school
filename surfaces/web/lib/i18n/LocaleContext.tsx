'use client';

/* ============================================================================
   lib/i18n/LocaleContext.tsx — the persisted locale provider + the useT() hook.

   Multilingual-by-design law: the chosen locale is held here, mirrored to the
   persisted store (lib/store, key `locale`) so it survives reload, and applied
   to the high-traffic surfaces through useT(). Captured implicitly in
   onboarding/personalise and changeable in settings via a calm switcher.

   SSR-safe: it hydrates the persisted locale after mount (like RoleContext) to
   avoid server/client drift, defaulting to English. Used outside the provider
   (an isolated story/test), useT() still works — it falls back to English.
   ============================================================================ */

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { readStore, setLocale as persistLocale } from '@/lib/store';
import { asLocale, DEFAULT_LOCALE, type Locale } from './dictionary';
import { makeTranslator } from './t';

interface LocaleContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  /** The bound translator for the active locale. */
  t: (key: string, vars?: Record<string, string | number>) => string;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  // Hydrate the persisted locale after mount (avoids SSR drift).
  useEffect(() => {
    try {
      const stored = readStore().locale;
      if (stored) setLocaleState(asLocale(stored));
    } catch {
      // Non-fatal: stay on the default.
    }
  }, []);

  const setLocale = useCallback((next: Locale) => {
    const loc = asLocale(next);
    setLocaleState(loc);
    try {
      persistLocale(loc);
    } catch {
      // Non-fatal: the locale still applies in memory for this session.
    }
  }, []);

  const value: LocaleContextValue = {
    locale,
    setLocale,
    t: makeTranslator(locale),
  };

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

/** Read the active locale + translator. Falls back to English outside a provider. */
export function useT(): LocaleContextValue {
  const ctx = useContext(LocaleContext);
  if (ctx) return ctx;
  return {
    locale: DEFAULT_LOCALE,
    setLocale: () => undefined,
    t: makeTranslator(DEFAULT_LOCALE),
  };
}
