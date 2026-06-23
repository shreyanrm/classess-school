'use client';

/* ============================================================================
   lib/useEmit.ts — the React binding for the live event seam (lib/events.ts).

   A page calls emit() on a real action (a loop attempt, an assignment created,
   an attendance confirmation). Emitting is best-effort and NEVER blocks the UI:

     - it resolves the canonical_uuid from the local account (the opaque demo id)
       so events are attributed without any PII;
     - it posts to /api/events through lib/events.ts;
     - on a persisted write it flips `saved` to 'saved' for a quiet affordance;
     - when there is no live database (the route answers { persisted:false }) it
       flips `saved` to 'local' so the surface can say it stayed on the local
       store — never an error.

   This hook holds NO secret and imports no database module; it is client-safe.
   ============================================================================ */

import { useCallback, useState } from 'react';
import { useStore } from './useStore';
import {
  emitEvent,
  type EmitEventInput,
  type EmitEventResult,
  type EventPurpose,
} from './events';

/** The quiet affordance state shown after an emit. */
export type SaveState = 'idle' | 'saving' | 'saved' | 'local';

export interface UseEmit {
  /** The current quiet affordance state. */
  saved: SaveState;
  /** A plain-language line for the affordance, or null when idle. */
  savedNote: string | null;
  /**
   * Emit an attributed event for the current account. `canonicalUuid` defaults
   * to the local account id; pass an explicit ref (e.g. a roster ref) to
   * attribute it elsewhere. Never throws; never blocks.
   */
  emit: (
    args: {
      type: string;
      purpose: EventPurpose;
      payload?: Record<string, unknown>;
      canonicalUuid?: string;
    },
  ) => Promise<EmitEventResult>;
  /** Reset the affordance back to idle. */
  reset: () => void;
}

const SAVED_NOTE: Record<SaveState, string | null> = {
  idle: null,
  saving: 'Saving…',
  saved: 'Saved to your record',
  local: 'Kept on this device',
};

export function useEmit(): UseEmit {
  const { account } = useStore();
  const [saved, setSaved] = useState<SaveState>('idle');

  const emit = useCallback<UseEmit['emit']>(
    async (args) => {
      const canonicalUuid = args.canonicalUuid ?? account?.id;
      if (!canonicalUuid) {
        // No account yet — nothing to attribute against. Stay local, never error.
        setSaved('local');
        return { persisted: false, reason: 'no-account' };
      }
      setSaved('saving');
      const input: EmitEventInput = {
        canonicalUuid,
        type: args.type,
        purpose: args.purpose,
        payload: args.payload,
      };
      const result = await emitEvent(input);
      setSaved(result.persisted ? 'saved' : 'local');
      return result;
    },
    [account?.id],
  );

  const reset = useCallback(() => setSaved('idle'), []);

  return { saved, savedNote: SAVED_NOTE[saved], emit, reset };
}
