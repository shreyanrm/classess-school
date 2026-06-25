'use client';

/* ============================================================================
   app/_components/LanguageBadge.tsx — the reader's language / region indicator.

   Hyperlocalised delivery (READINESS §7b): a calm, designed indicator that tells
   the reader what language this surface is rendered in, and — when the engine
   content has been rendered into a non-English language through the TRANSLATE
   capability — that it is in THEIR language with subject terms preserved. It
   links to Settings so the choice is always one tap away.

   Premium bar: a hairline-bordered, frosted pill (NO shadow), tone + a quiet
   pulsing dot only while a render is in flight. Reduced-motion is honoured by
   the .dot-live keyframe guard in globals.css.
   ============================================================================ */

import Link from 'next/link';
import { LOCALES, type Locale } from '@/lib/i18n';

interface LanguageBadgeProps {
  /** The reader's active locale code. */
  locale: string;
  /** True while engine content is being rendered into the reader's language. */
  rendering?: boolean;
  /** True once engine content has been rendered into a non-English language. */
  rendered?: boolean;
  /** A short region/board label, when the surface carries one (optional). */
  region?: string;
}

/** The human label for a locale, in its own script (falls back to the code). */
function localeLabel(code: string): string {
  return LOCALES.find((l: { code: Locale }) => l.code === code)?.label ?? code.toUpperCase();
}

export function LanguageBadge({ locale, rendering, rendered, region }: LanguageBadgeProps) {
  const label = localeLabel(locale);
  const isEnglish = locale === 'en';
  // The state line: rendering -> rendered (in your language) -> reading-in.
  const state = rendering
    ? 'Translating for you'
    : rendered
      ? 'In your language · subject terms kept'
      : isEnglish
        ? 'Reading in English'
        : `Reading in ${label}`;

  return (
    <Link
      href="/settings"
      className="lang-badge"
      data-rendering={rendering ? 'true' : undefined}
      aria-label={`Language: ${label}. ${state}. Change in settings.`}
      title={`${state}. Change your language in Settings.`}
    >
      <span className={`lang-badge-dot${rendering ? ' dot-live' : ''}`} aria-hidden />
      <span className="lang-badge-lang">{label}</span>
      {region ? <span className="lang-badge-region">· {region}</span> : null}
      <span className="lang-badge-state caption">{state}</span>
    </Link>
  );
}
