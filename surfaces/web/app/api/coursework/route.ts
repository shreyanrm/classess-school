/* ============================================================================
   app/api/coursework/route.ts — the LIVE coursework seam over operational.*

   SERVER-ONLY (runtime = 'nodejs'). Persists teacher-created assignments and
   learner submissions into operational.assignments / operational.submissions
   through the server-only pool (lib/db.ts).

     POST  { ... }                creates an assignment, returns its live id.
     POST  { submission: {...} }  records a learner submission for an assignment.
     GET   ?institution_id=...    reads assignments back (with a submission count).

   DEGRADE: no CLSS_DATABASE_URL -> 200 { persisted:false } so the surface stays
   on its engine/mock layer. created_by / submitted_by are opaque refs, never
   PII; no secret is returned.
   ============================================================================ */

import { getPool, type PoolLike } from '@/lib/db';
import { ok, degraded, isUuid, str, label } from '@/lib/opRoute';
import { authorizeWrite, denied } from '@/lib/opGate';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const KINDS = new Set(['quick_check', 'assignment', 'project']);
const MODES = new Set(['independent', 'supported']);

interface Body {
  institutionId?: string;
  createdBy?: string;
  kind?: string;
  title?: string;
  instructions?: string;
  dueAt?: string;
  submission?: {
    assignmentId?: string;
    submittedBy?: string;
    producedMode?: string;
  };
}

async function createAssignment(pool: PoolLike, body: Body): Promise<string | null> {
  const kind = KINDS.has(str(body.kind)) ? str(body.kind) : 'assignment';
  const res = await pool.query<{ assignment_id: string }>(
    `INSERT INTO operational.assignments
       (institution_id, created_by, kind, title, instructions, due_at)
     VALUES ($1, $2, $3, $4, $5, $6)
     RETURNING assignment_id`,
    [
      body.institutionId,
      body.createdBy,
      kind,
      label(body.title, 200) || 'Untitled',
      body.instructions ? label(body.instructions, 2000) : null,
      str(body.dueAt) || null,
    ],
  );
  return res.rows[0]?.assignment_id ?? null;
}

async function recordSubmission(pool: PoolLike, body: Body): Promise<string | null> {
  const sub = body.submission!;
  const mode = MODES.has(str(sub.producedMode)) ? str(sub.producedMode) : 'independent';
  const res = await pool.query<{ submission_id: string }>(
    `INSERT INTO operational.submissions
       (institution_id, assignment_id, submitted_by, produced_mode)
     VALUES ($1, $2, $3, $4)
     RETURNING submission_id`,
    [body.institutionId, sub.assignmentId, sub.submittedBy, mode],
  );
  return res.rows[0]?.submission_id ?? null;
}

export async function POST(req: Request): Promise<Response> {
  let body: Body;
  try {
    body = (await req.json()) as Body;
  } catch {
    return ok({ persisted: false, reason: 'bad-request' }, 400);
  }
  if (!isUuid(body.institutionId)) {
    return ok({ persisted: false, reason: 'invalid-input' }, 400);
  }

  // Submission branch.
  if (body.submission) {
    if (!isUuid(body.submission.assignmentId) || !isUuid(body.submission.submittedBy)) {
      return ok({ persisted: false, reason: 'invalid-input' }, 400);
    }
    // The wall authorizes the submit FIRST (the permission ladder gates submit).
    const gate = await authorizeWrite(req, 'coursework', 'submit', {
      payload: { institution_id: body.institutionId, assignment_id: body.submission.assignmentId },
    });
    if (!gate.proceed) return denied(gate.detail);
    const pool = getPool();
    if (!pool) return degraded();
    try {
      const id = await recordSubmission(pool, body);
      return ok({ persisted: Boolean(id), id: id ?? undefined });
    } catch {
      return ok({ persisted: false, reason: 'write-failed' });
    }
  }

  // Assignment branch.
  if (!isUuid(body.createdBy) || !str(body.title)) {
    return ok({ persisted: false, reason: 'invalid-input' }, 400);
  }
  // The wall authorizes the create FIRST (RBAC: only a teacher/coordinator).
  const gate = await authorizeWrite(req, 'coursework', 'create', {
    payload: { institution_id: body.institutionId },
  });
  if (!gate.proceed) return denied(gate.detail);
  const pool = getPool();
  if (!pool) return degraded();
  try {
    const id = await createAssignment(pool, body);
    return ok({ persisted: Boolean(id), id: id ?? undefined });
  } catch {
    return ok({ persisted: false, reason: 'write-failed' });
  }
}

export async function GET(req: Request): Promise<Response> {
  const url = new URL(req.url);
  const institutionId = str(url.searchParams.get('institution_id'));
  if (!isUuid(institutionId)) {
    return ok({ persisted: false, rows: [], reason: 'invalid-input' }, 400);
  }

  const pool = getPool();
  if (!pool) return degraded();

  try {
    const res = await pool.query(
      `SELECT a.assignment_id, a.kind, a.title, a.instructions, a.due_at, a.created_at,
              COUNT(s.submission_id)::int AS submission_count
         FROM operational.assignments a
         LEFT JOIN operational.submissions s ON s.assignment_id = a.assignment_id
        WHERE a.institution_id = $1
        GROUP BY a.assignment_id
        ORDER BY a.created_at DESC`,
      [institutionId],
    );
    return ok({ persisted: true, rows: res.rows });
  } catch {
    return ok({ persisted: false, rows: [], reason: 'read-failed' });
  }
}
