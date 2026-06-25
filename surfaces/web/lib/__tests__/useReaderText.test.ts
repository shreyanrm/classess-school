/* ============================================================================
   lib/__tests__/useReaderText.test.ts — engine-read content renders in the
   reader's language through the TRANSLATE capability, never passthrough.

   The hyperlocalised-delivery law (READINESS §7b): generated content a parent
   reads is rendered into THEIR language, subject terms preserved. This pins the
   hook that closes the gap:
     - English readers skip the network entirely (no wasteful calls).
     - A non-English reader's content is rendered through commData.translateForReader
       (the wall), and tx() returns the rendered text once it lands.
     - On a degrade the ORIGINAL text stands — nothing ever blanks.

   No JSX here (this is a lib/*.test.ts under the web project's glob): the
   LocaleProvider wrapper is built with React.createElement.
   ============================================================================ */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, waitFor, cleanup } from '@testing-library/react';
import { createElement, type ReactNode } from 'react';

// Control the wall seam: translateForReader is the ONLY network the hook makes.
const translateForReader = vi.fn();
vi.mock('../commData', () => ({
  translateForReader: (...args: unknown[]) => translateForReader(...args),
}));

import {
  setStoreAdapter,
  createMemoryAdapter,
  setLocale,
  type StoreAdapter,
} from '../store';
import { LocaleProvider } from '../i18n';
import { useReaderText } from '../useReaderText';

function wrapper({ children }: { children: ReactNode }) {
  return createElement(LocaleProvider, null, children);
}

let adapter: StoreAdapter;
beforeEach(() => {
  adapter = createMemoryAdapter();
  setStoreAdapter(adapter);
  translateForReader.mockReset();
});
afterEach(cleanup);

describe('useReaderText — engine content renders in the reader language', () => {
  it('skips the network entirely for an English reader', async () => {
    // No persisted locale -> default English. tx() returns the original.
    const { result } = renderHook(() => useReaderText(['You are on track']), { wrapper });
    await waitFor(() => expect(result.current.locale).toBe('en'));
    expect(translateForReader).not.toHaveBeenCalled();
    expect(result.current.rendered).toBe(false);
    expect(result.current.tx('You are on track')).toBe('You are on track');
  });

  it('renders generated text through the wall for a non-English reader', async () => {
    setLocale('hi');
    translateForReader.mockResolvedValue({
      ok: true,
      data: { rendered_text: 'आप ठीक कर रहे हैं', status: 'translated' },
      source: 'gateway',
    });

    const { result } = renderHook(() => useReaderText(['You are on track']), { wrapper });

    await waitFor(() => expect(translateForReader).toHaveBeenCalled());
    expect(translateForReader).toHaveBeenCalledWith(
      expect.objectContaining({ text: 'You are on track', preferredLang: 'hi' }),
    );
    await waitFor(() => expect(result.current.tx('You are on track')).toBe('आप ठीक कर रहे हैं'));
    expect(result.current.rendered).toBe(true);
  });

  it('keeps the ORIGINAL text on a degrade (never blanks)', async () => {
    setLocale('hi');
    translateForReader.mockResolvedValue({ ok: false, degraded: true, source: 'fallback' });

    const { result } = renderHook(() => useReaderText(['Practice word problems']), { wrapper });

    await waitFor(() => expect(translateForReader).toHaveBeenCalled());
    expect(result.current.tx('Practice word problems')).toBe('Practice word problems');
    expect(result.current.rendered).toBe(false);
  });

  it('ignores blank fields and de-duplicates repeats (one render per string)', async () => {
    setLocale('hi');
    translateForReader.mockResolvedValue({
      ok: true,
      data: { rendered_text: 'अनुवादित', status: 'translated' },
      source: 'gateway',
    });

    renderHook(() => useReaderText(['Same line', 'Same line', '', '   ', undefined]), { wrapper });

    await waitFor(() => expect(translateForReader).toHaveBeenCalled());
    // Only the one distinct non-blank string is sent.
    expect(translateForReader).toHaveBeenCalledTimes(1);
  });
});
