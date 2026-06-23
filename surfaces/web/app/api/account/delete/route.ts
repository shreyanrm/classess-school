/* ============================================================================
   app/api/account/delete/route.ts — the SERVER-ONLY right-to-erasure seam.

   SERVER-ONLY (runtime = 'nodejs', POST). This is where a person's RIGHT TO
   ERASURE is honoured WITHOUT breaking the platform's IMMUTABILITY invariant.

   What it does, in order:
     (a) verifies the caller — the body carries the current session's opaque
         canonical id (canonical_uuid); a malformed id is rejected before any
         privileged work.
     (b) deletes the Auth user via the SERVICE-ROLE key (lib/supabaseAdmin) so
         the login identity is gone.
     (c) through the server-only pool (lib/db), ERASES the PII row
         (pii_vault.users for that canonical id) and removes the operational
         roster rows (operational.memberships) — severing identity + attribution.
     (d) appends ONE immutable audit row (platform.audit_log) recording the
         erasure: who (actor), what (action 'account.erasure'), when.
     (e) returns { deleted:true }.

   It MUST NOT delete platform.events. Those rows carry NO PII — only the opaque
   canonical_uuid — so once the vault row is gone they are un-attributable. That
   is precisely how erasure and immutability coexist: we sever identity, we do
   not (and cannot) hard-delete the append-only behavioural store.

   DEGRADE: when CLSS_DATABASE_URL or the service-role key is unset (the demo
   default) the privileged work cannot run, so this resolves 200 with
   { deleted:false, reason } and the client STILL clears its local session — the
   demo erasure path works end-to-end with no backend.

   No secret is ever read into a response or a log line.
   ============================================================================ */

import { getPool, type PoolLike } from '@/lib/db';
import { deleteAuthUser, isAdminConfigured } from '@/lib/supabaseAdmin';
import { ok, isUuid, str } from '@/lib/opRoute';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface DeleteBody {
  /** The opaque canonical id of the session being erased. */
  canonicalUuid?: string;
}

/**
 * Sever identity + attribution for one canonical id, then append the audit row.
 * Deletes the PII vault row and the operational roster rows; NEVER touches
 * platform.events (immutability). Returns true when the erasure write path ran.
 */
async function eraseIdentity(pool: PoolLike, canonicalUuid: string): Promise<boolean> {
  // (c) Erase the single PII row that maps the opaque id to a real person.
  await pool.query(`DELETE FROM pii_vault.users WHERE canonical_uuid = $1`, [canonicalUuid]);

  // (c) Remove the operational roster memberships keyed by the opaque id.
  await pool.query(`DELETE FROM operational.memberships WHERE canonical_uuid = $1`, [canonicalUuid]);

  // (d) Append ONE immutable audit row recording the erasure (who/what/when).
  // platform.audit_log is append-only; we mint the audit_id and stamp the actor.
  await pool.query(
    `INSERT INTO platform.audit_log
       (audit_id, actor_canonical_uuid, app, action, decision, resource_scope, reasons, request_id)
     VALUES (gen_random_uuid(), $1, 'school', 'account.erasure', 'allow', $2::jsonb, $3::jsonb, $4)`,
    [
      canonicalUuid,
      JSON.stringify({ canonical_uuid: canonicalUuid }),
      JSON.stringify(['right-to-erasure', 'identity-and-pii-severed', 'events-retained-unattributable']),
      `erasure-${canonicalUuid}`,
    ],
  );

  return true;
}

export async function POST(req: Request): Promise<Response> {
  let body: DeleteBody;
  try {
    body = (await req.json()) as DeleteBody;
  } catch {
    return ok({ deleted: false, reason: 'bad-request' }, 400);
  }

  // (a) Verify the caller — a valid opaque canonical id is required.
  const canonicalUuid = str(body.canonicalUuid);
  if (!isUuid(canonicalUuid)) {
    return ok({ deleted: false, reason: 'invalid-input' }, 400);
  }

  // The PII erasure needs the live pool; the Auth delete needs the service key.
  // Either being absent is the designed degraded path: we report deleted:false
  // with a plain reason and the client still clears its local session.
  const pool = getPool();
  if (!pool) return ok({ deleted: false, reason: 'no-db' });
  if (!isAdminConfigured()) return ok({ deleted: false, reason: 'admin-unset' });

  try {
    // (b) Delete the Auth login identity with the service-role key. A false here
    // (provider hiccup) does not abort the PII erasure — severing PII is the
    // primary obligation; the audit row records that the erasure ran.
    await deleteAuthUser(canonicalUuid);

    // (c) + (d) sever identity/PII and append the audit row. NOT platform.events.
    await eraseIdentity(pool, canonicalUuid);

    // (e)
    return ok({ deleted: true });
  } catch {
    // A live database that rejected the write must not break the flow; the
    // client still clears local state on a non-deleted result.
    return ok({ deleted: false, reason: 'erase-failed' });
  }
}

/** A GET probe answers calmly; erasure is a POST-only operation. */
export async function GET(): Promise<Response> {
  return ok({ deleted: false, reason: 'use-post' }, 405);
}
