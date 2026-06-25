'use client';

/* ============================================================================
   lib/useReaderText.ts — render engine-read content into the READER's language.

   The static chrome (labels, prompts) is translated by the i18n dictionary
   (lib/i18n). But the GENERATED / engine-read content a parent reads — the
   weekly briefings, strengths, support steps, learn-alongside activities,
   report feedback — is composed in English by the intelligence read. The
   multilingual-by-design law says the reader sees it IN THEIR LANGUAGE, not
   passthrough. This hook closes that gap by rendering those free-text fields
   through the EXISTING communication TRANSLATE capability (commData
   .translateForReader -> /api/comm -> the wall -> translation.render_for_reader),
   which preserves subject terminology and code-switch spans.

   It mirrors the proven pattern in app/messages/page.tsx (render-on-read,
   original stands until/unless a render lands), generalised so any parent /
   learner surface can drop in:

       const { tx, rendering, rendered } = useReaderText([b.title, b.why, ...]);
       <h3>{tx(b.title)}</h3>

   GUARANTEES (the law):
     - English readers skip the network entirely (en IS the source) — no
       wasteful calls, instant render.
     - Every call is best-effort and never throws; on any degrade the ORIGINAL
       text stands. Nothing ever blanks.
     - Subject terminology is preserved by the module, never by us.
   ============================================================================ */

import { useEffect, useMemo, useRef, useState } from 'react';
import { translateForReader } from './commData';
import { DEFAULT_LOCALE, useT } from './i18n';

interface ReaderText {
  /** Render one original string into the reader's language; falls back to it. */
  tx: (text: string) => string;
  /** True while at least one field is still rendering (for a calm indicator). */
  rendering: boolean;
  /** True once any field has been rendered into a non-English language. */
  rendered: boolean;
  /** The reader's active locale code (for a language indicator). */
  locale: string;
}

/**
 * Render a set of engine-read text fields into the reader's preferred language.
 * Pass the original strings (any falsy/blank entries are ignored). The returned
 * `tx(original)` yields the rendered text where one has landed, else the
 * original — so a surface can wrap every generated string and it simply reads
 * in-language once the renders resolve, and reads in English meanwhile.
 */
export function useReaderText(texts: ReadonlyArray<string | undefined | null>): ReaderText {
  const { locale } = useT();
  // original text -> rendered (reader-language) text. Keyed by the source string
  // so identical strings share one render and re-renders are cheap.
  const [map, setMap] = useState<Record<string, string>>({});
  const [rendering, setRendering] = useState(false);
  // Track in-flight / done keys per locale so a locale switch re-renders, and we
  // never fire the same (locale, text) twice.
  const doneRef = useRef<Set<string>>(new Set());

  // A de-duplicated list of non-blank whole source strings. Callers build a
  // fresh array each render (.flatMap); we key the memo on the JOINED content
  // (a newline no field contains) so `sources` keeps a stable reference while
  // the content is unchanged — the effect then re-runs only when the set of
  // strings (or the locale) actually changes, never on every render.
  const clean = texts.filter((s): s is string => !!s && s.trim().length > 0);
  const key = clean.join('\n');
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const sources = useMemo(() => Array.from(new Set(clean)), [key]);

  useEffect(() => {
    // English is the source language — there is nothing to render, and we must
    // not waste a network round-trip. Reset so a later switch back is clean.
    if (locale === DEFAULT_LOCALE) {
      doneRef.current = new Set();
      setMap({});
      setRendering(false);
      return;
    }

    let cancelled = false;
    const todo = sources.filter((s) => !doneRef.current.has(`${locale}::${s}`));
    if (todo.length === 0) return;

    setRendering(true);
    void Promise.all(
      todo.map(async (text) => {
        doneRef.current.add(`${locale}::${text}`);
        const res = await translateForReader({ text, preferredLang: locale });
        const rendered = res.ok ? res.data?.rendered_text : undefined;
        if (cancelled || !rendered || rendered === text) return;
        setMap((prev) => (prev[text] === rendered ? prev : { ...prev, [text]: rendered }));
      }),
    ).finally(() => {
      if (!cancelled) setRendering(false);
    });

    return () => {
      cancelled = true;
    };
  }, [sources, locale]);

  const tx = useMemo(() => (text: string) => map[text] ?? text, [map]);

  return {
    tx,
    rendering,
    rendered: locale !== DEFAULT_LOCALE && Object.keys(map).length > 0,
    locale,
  };
}
