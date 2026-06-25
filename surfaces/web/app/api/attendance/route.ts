/* ============================================================================
   app/api/attendance/route.ts — the LIVE attendance seam over operational.*

   SERVER-ONLY (runtime = 'nodejs'). Persists human-confirmed attendance marks
   into operational.attendance_records through the server-only pool (lib/db.ts).

     POST  upserts one confirmed mark per learner for a session (the human
           confirm — method 'manual', confirmed_by/confirmed_at stamped). A
           re-roll for the same (session, learner) updates in place.

     GET   ?session_id=...&institution_id=...  reads the confirmed roll back.

   DEGRADE: no CLSS_DATABASE_URL -> 200 { persisted:false } so the surface stays
   on its local/mock roll. No PII is stored (opaque canonical_uuid only); no
   secret is returned.
   ============================================================================ */

import { getPool, type PoolLike } from '@/lib/db';
import { ok, degraded, isUuid, str } from '@/lib/opRoute';
import { authorizeWrite, denied } from '@/lib/opGate';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const STATUSES = new Set(['present', 'absent', 'late', 'excused', 'unknown']);

interface MarkBody { canonicalUuid?: string; status?: string }
interface Body {
  institutionId?: string;
  sessionId?: string;
  nodeId?: string;
  confirmedBy?: string;
  marks?: MarkBody[];
}

async function persistRoll(pool: PoolLike, body: Body): Promise<number> {
  const institutionId = body.institutionId!;
  const sessionId = body.sessionId!;
  const nodeId = isUuid(body.nodeId) ? body.nodeId : null;
  const confirmedBy = isUuid(body.confirmedBy) ? body.confirmedBy : null;
  let written = 0;

  for (const mark of body.marks ?? []) {
    const learner = str(mark.canonicalUuid);
    const status = str(mark.status);
    if (!isUuid(learner) || !STATUSES.has(status)) continue;
    await pool.query(
      `INSERT INTO operational.attendance_records
         (institution_id, session_id, node_id, canonical_uuid, status, method,
          confirmed_by, confirmed_at)
       VALUES ($1, $2, $3, $4, $5, 'manual', $6, now())
       ON CONFLICT (session_id, canonical_uuid)
       DO UPDATE SET status = EXCLUDED.status,
                     confirmed_by = EXCLUDED.confirmed_by,
                     confirmed_at = now()`,
      [institutionId, sessionId, nodeId, learner, status, confirmedBy],
    );
    written += 1;
  }
  return written;
}

export async function POST(req: Request): Promise<Response> {
  let body: Body;
  try {
    body = (await req.json()) as Body;
  } catch {
    return ok({ persisted: false, reason: 'bad-request' }, 400);
  }
  if (!isUuid(body.institutionId) || !isUuid(body.sessionId) || !Array.isArray(body.marks)) {
    return ok({ persisted: false, reason: 'invalid-input' }, 400);
  }

  // The wall authorizes this consequential write FIRST (RBAC/ABAC/audit). A
  // caller without the right role/scope is denied; an unreachable wall degrades.
  const gate = await authorizeWrite(req, 'attendance', 'confirm', {
    payload: { institution_id: body.institutionId, session_id: body.sessionId },
  });
  if (!gate.proceed) return denied(gate.detail);

  const pool = getPool();
  if (!pool) return degraded();

  try {
    const written = await persistRoll(pool, body);
    return ok({ persisted: written > 0, written });
  } catch {
    return ok({ persisted: false, reason: 'write-failed' });
  }
}

export async function GET(req: Request): Promise<Response> {
  const url = new URL(req.url);
  const sessionId = str(url.searchParams.get('session_id'));
  const institutionId = str(url.searchParams.get('institution_id'));
  if (!isUuid(sessionId) || !isUuid(institutionId)) {
    return ok({ persisted: false, rows: [], reason: 'invalid-input' }, 400);
  }

  const pool = getPool();
  if (!pool) return degraded();

  try {
    const res = await pool.query(
      `SELECT record_id, canonical_uuid, node_id, status, confirmed_at, occurred_on
         FROM operational.attendance_records
        WHERE institution_id = $1 AND session_id = $2
        ORDER BY created_at`,
      [institutionId, sessionId],
    );
    return ok({ persisted: true, rows: res.rows });
  } catch {
    return ok({ persisted: false, rows: [], reason: 'read-failed' });
  }
}
