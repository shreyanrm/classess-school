/* ============================================================================
   lib/i18n/t.ts — the pure translation lookup with English fallback.

   t(locale, key) resolves a key in the chosen locale and FALLS BACK TO ENGLISH
   for any key the locale has not translated (so a half-translated language never
   shows a blank or the raw key). If a key exists in no dictionary at all it
   returns the key itself as a last resort, which is loud enough to spot.

   Optional {placeholder} interpolation is supported for the few dynamic strings.
   SUBJECT TERMINOLOGY is never passed through here — subject names render verbatim
   from the engine, so translation can never alter them.
   ============================================================================ */

import {
  DICTIONARIES,
  SOURCE_DICTIONARY,
  DEFAULT_LOCALE,
  asLocale,
  type Locale,
} from './dictionary';

/** Substitute {name} placeholders from a vars map. */
function interpolate(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_, k: string) =>
    k in vars ? String(vars[k]) : `{${k}}`,
  );
}

/**
 * Resolve a translation key. Order: chosen locale -> English source -> the key.
 * The English fallback is the guarantee the law needs: a parent who chose Hindi
 * never sees a blank where a string has not been translated yet.
 */
export function t(
  locale: Locale | string | undefined,
  key: string,
  vars?: Record<string, string | number>,
): string {
  const loc = asLocale(typeof locale === 'string' ? locale : DEFAULT_LOCALE);
  const fromLocale = DICTIONARIES[loc]?.[key];
  if (typeof fromLocale === 'string') return interpolate(fromLocale, vars);
  const fromSource = SOURCE_DICTIONARY[key];
  if (typeof fromSource === 'string') return interpolate(fromSource, vars);
  return key; // last resort — a missing key is visible, not blank
}

/** Build a bound translator for a fixed locale (the hook returns this). */
export function makeTranslator(locale: Locale | string | undefined) {
  return (key: string, vars?: Record<string, string | number>) => t(locale, key, vars);
}
