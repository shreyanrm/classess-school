/* ============================================================================
   lib/i18n/index.ts — the i18n layer's public surface.

   A lightweight i18n layer for the multilingual-by-design law: a LocaleProvider
   + a t() dictionary, a persisted locale (captured in onboarding/personalise,
   changeable in settings), and the structure to add more languages. Subject
   terminology is never altered by translation.
   ============================================================================ */

export {
  DICTIONARIES,
  SOURCE_DICTIONARY,
  LOCALES,
  DEFAULT_LOCALE,
  asLocale,
  type Locale,
  type LocaleMeta,
  type Dictionary,
} from './dictionary';
export { t, makeTranslator } from './t';
export { LocaleProvider, useT } from './LocaleContext';
