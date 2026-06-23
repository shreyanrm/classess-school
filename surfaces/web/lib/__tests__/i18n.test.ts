/* ============================================================================
   lib/__tests__/i18n.test.ts — the translation lookup.

   t() returns the chosen-locale string when present, FALLS BACK TO ENGLISH for a
   key the locale has not translated, and never alters subject terminology (subject
   names are simply not in the dictionary, so they pass through verbatim).
   ============================================================================ */

import { describe, it, expect } from 'vitest';
import { t } from '../i18n/t';
import { DICTIONARIES, SOURCE_DICTIONARY, LOCALES } from '../i18n/dictionary';

describe('t — locale lookup with English fallback', () => {
  it('returns the Hindi string when the key is translated', () => {
    expect(t('hi', 'common.continue')).toBe('जारी रखें');
    expect(t('hi', 'common.continue')).not.toBe(t('en', 'common.continue'));
  });

  it('falls back to English for a key Hindi has not translated', () => {
    // A key present in English but deliberately not in the Hindi map.
    const enOnlyKey = Object.keys(SOURCE_DICTIONARY).find((k) => !(k in DICTIONARIES.hi));
    // The dictionary is large enough that some English-only key always exists,
    // but if Hindi ever covers everything, assert the fallback path directly.
    if (enOnlyKey) {
      expect(t('hi', enOnlyKey)).toBe(SOURCE_DICTIONARY[enOnlyKey]);
    }
    // And an entirely unknown key falls back to English source, else the key.
    expect(t('hi', 'definitely.not.a.real.key')).toBe('definitely.not.a.real.key');
  });

  it('returns the English source for the default locale', () => {
    expect(t('en', 'settings.title')).toBe(SOURCE_DICTIONARY['settings.title']);
  });

  it('treats an unknown locale as English', () => {
    expect(t('xx', 'common.signIn')).toBe(t('en', 'common.signIn'));
  });

  it('returns a missing key verbatim (loud, never blank)', () => {
    expect(t('en', 'definitely.not.a.real.key')).toBe('definitely.not.a.real.key');
  });

  it('exposes at least English + Hindi', () => {
    const codes = LOCALES.map((l) => l.code);
    expect(codes).toContain('en');
    expect(codes).toContain('hi');
  });

  it('never translates a subject name (subjects are not in the dictionary)', () => {
    // Subject terminology must pass through verbatim in every locale.
    expect(t('hi', 'Mathematics')).toBe('Mathematics');
    expect(t('hi', 'Trigonometric Ratios')).toBe('Trigonometric Ratios');
  });
});
