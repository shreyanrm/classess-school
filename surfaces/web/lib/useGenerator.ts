'use client';

/* ============================================================================
   lib/useGenerator.ts — the React binding for the teacher's governed GENERATE-
   AND-VERIFY capabilities (gateway-first, ontology fallback).

   The teacher/content surfaces are client components; the wall lives
   server-side. This hook is the client end of the /api/generate hop: it asks
   the SPINE to verify a board-agnostic artifact (gateway-first), and the route
   answers with the locally-composed verified-shaped artifact on degrade. The
   hook never throws.

   Generation is ON DEMAND (a consequential prepare step), so this hook is lazy:
   nothing fires until `run()` is called. It surfaces the designed states:
     - idle     : nothing generated yet (the designed pre-generate state)
     - loading  : a generate request is in flight
     - error    : the route itself failed
     - ready    : an artifact is available

   `source` is 'gateway' when the spine verified it, 'fallback' on the degrade
   path — surfaced so the surface can show the OBSERVABLE SourceNote marker.
   ============================================================================ */

import { useCallback, useState } from 'react';
import { useStore } from './useStore';
import type { Confidence } from './generate';

export type GeneratorOp = 'worksheet' | 'lesson-plan' | 'session-plan' | 'course-outline';
export type GeneratorPhase = 'idle' | 'loading' | 'error' | 'ready';

export interface GeneratorState<T> {
  phase: GeneratorPhase;
  artifact: T | null;
  confidence: Confidence;
  source: 'gateway' | 'fallback';
  /** Trigger a generate-and-verify for the given target. */
  run: (args: { topic?: string; subject?: string; count?: number }) => void;
  /** Drop back to the designed idle state. */
  reset: () => void;
}

interface ApiBody<T> {
  artifact: T;
  confidence: Confidence;
  source: 'gateway' | 'fallback';
}

export function useGenerator<T>(op: GeneratorOp): GeneratorState<T> {
  const { account } = useStore();
  const [state, setState] = useState<Omit<GeneratorState<T>, 'run' | 'reset'>>({
    phase: 'idle',
    artifact: null,
    confidence: 'high',
    source: 'fallback',
  });

  const reset = useCallback(
    () => setState({ phase: 'idle', artifact: null, confidence: 'high', source: 'fallback' }),
    [],
  );

  const run = useCallback(
    (args: { topic?: string; subject?: string; count?: number }) => {
      setState((prev) => ({ ...prev, phase: 'loading' }));

      const headers: Record<string, string> = {};
      if (account?.id) headers['x-caller-uuid'] = account.id;
      headers['x-caller-role'] = account?.role ?? 'teacher';

      const qs = new URLSearchParams({ op });
      if (args.topic) qs.set('topic', args.topic);
      if (args.subject) qs.set('subject', args.subject);
      if (args.count) qs.set('count', String(args.count));

      fetch(`/api/generate?${qs.toString()}`, { headers })
        .then(async (res) => {
          if (!res.ok) throw new Error(`http-${res.status}`);
          return (await res.json()) as ApiBody<T>;
        })
        .then((body) => {
          setState({
            phase: 'ready',
            artifact: body.artifact ?? null,
            confidence: body.confidence ?? 'high',
            source: body.source ?? 'fallback',
          });
        })
        .catch(() => setState((prev) => ({ ...prev, phase: 'error' })));
    },
    [op, account?.id, account?.role],
  );

  return { ...state, run, reset };
}
