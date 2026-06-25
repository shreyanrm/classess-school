'use client';

/**
 * A quiet, one-line note of WHICH source answered a governed read — the live
 * SPINE behind the gateway ('gateway'), or the on-device engine port when the
 * wall was unreachable / declined ('fallback', the degrade path). The
 * user-visible reading is identical either way; this only makes the seam
 * honest. v4.1 tokens only; no shadow. Reused across the teacher loop surfaces.
 */
export function SourceNote({ source }: { source: 'gateway' | 'fallback' }) {
  return (
    <p className="caption quiet" role="status">
      {source === 'gateway'
        ? 'Read live from the intelligence spine through the gateway.'
        : 'On the last-known on-device read — the gateway was unreachable, so nothing here is stale or lost. It refreshes the moment the spine is reachable again.'}
    </p>
  );
}
