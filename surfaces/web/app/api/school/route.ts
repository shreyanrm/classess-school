/* ============================================================================
   app/api/school/route.ts — the LIVE school-setup seam over operational.*

   SERVER-ONLY (runtime = 'nodejs'). Persists the cold-start blueprint the admin
   confirms in app/admin/setup (and the welcome onboarding for an admin) into the
   operational plane through the server-only pool (lib/db.ts):

     POST  upserts operational.institutions, writes the structure_nodes tree
           (group -> grade -> section) and the starter memberships (roster), then
           returns the live institution_id so the client can reload from it.

     GET   ?institution_id=...  reads the institution + its structure tree +
           roster back, scoped to that opaque id, so a refresh survives.

   DEGRADE: when CLSS_DATABASE_URL is unset (getPool() === null) both verbs
   answer 200 with { persisted:false } / { rows:[] } so the app keeps working on
   its local store. No secret is ever returned, logged, or exposed.

   No PII is ever stored: institution + node labels are generic data, roster
   members are generic labels mapped to opaque canonical_uuid refs.
   ============================================================================ */

import { getPool, type PoolLike } from '@/lib/db';
import { ok, degraded, isUuid, str, label } from '@/lib/opRoute';
import { authorizeWrite, denied } from '@/lib/opGate';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface SectionWire { id: string; name: string; teacherLabel?: string }
interface GradeWire { id: string; name: string; sections: SectionWire[] }
interface GroupWire { id: string; name: string; grades: GradeWire[] }
interface RosterWire { id: string; label: string; kind: 'student' | 'teacher'; sectionId: string }

interface SchoolBody {
  institutionId?: string;
  name?: string;
  board?: string;
  pacing?: string;
  structure?: GroupWire[];
  roster?: RosterWire[];
}

async function persistSchool(pool: PoolLike, body: SchoolBody): Promise<string | null> {
  const name = label(body.name) || 'Campus';
  const attributes = JSON.stringify({
    board: label(body.board, 120),
    pacing: label(body.pacing, 120),
  });

  // Upsert the institution. When a live id is supplied we update in place so a
  // re-confirm does not create a duplicate tenant; otherwise mint a new one.
  let institutionId = isUuid(body.institutionId) ? body.institutionId : null;
  if (institutionId) {
    await pool.query(
      `UPDATE operational.institutions
          SET label = $2, attributes = $3::jsonb
        WHERE institution_id = $1`,
      [institutionId, name, attributes],
    );
  } else {
    const created = await pool.query<{ institution_id: string }>(
      `INSERT INTO operational.institutions (label, attributes)
         VALUES ($1, $2::jsonb)
       RETURNING institution_id`,
      [name, attributes],
    );
    institutionId = created.rows[0]?.institution_id ?? null;
  }
  if (!institutionId) return null;

  // Rewrite the structure tree + roster for a clean, idempotent re-confirm.
  // memberships first (they reference nodes via ON DELETE SET NULL), then nodes.
  await pool.query(`DELETE FROM operational.memberships WHERE institution_id = $1`, [institutionId]);
  await pool.query(`DELETE FROM operational.structure_nodes WHERE institution_id = $1`, [institutionId]);

  // Map a section's local id to its freshly-minted node_id so the roster lands
  // in the right section. Labels are generic data; refs are opaque.
  const sectionNode = new Map<string, string>();

  for (const group of body.structure ?? []) {
    const groupRow = await pool.query<{ node_id: string }>(
      `INSERT INTO operational.structure_nodes (institution_id, kind, label)
         VALUES ($1, 'group', $2) RETURNING node_id`,
      [institutionId, label(group.name) || 'Campus'],
    );
    const groupId = groupRow.rows[0]?.node_id;
    for (const grade of group.grades ?? []) {
      const gradeRow = await pool.query<{ node_id: string }>(
        `INSERT INTO operational.structure_nodes (institution_id, kind, label, parent_id)
           VALUES ($1, 'grade', $2, $3) RETURNING node_id`,
        [institutionId, label(grade.name) || 'Grade', groupId ?? null],
      );
      const gradeId = gradeRow.rows[0]?.node_id;
      for (const section of grade.sections ?? []) {
        const sectionRow = await pool.query<{ node_id: string }>(
          `INSERT INTO operational.structure_nodes (institution_id, kind, label, parent_id, attributes)
             VALUES ($1, 'section', $2, $3, $4::jsonb) RETURNING node_id`,
          [
            institutionId,
            label(section.name) || 'Section',
            gradeId ?? null,
            JSON.stringify(section.teacherLabel ? { teacherLabel: label(section.teacherLabel, 80) } : {}),
          ],
        );
        const sid = sectionRow.rows[0]?.node_id;
        if (sid) sectionNode.set(section.id, sid);
      }
    }
  }

  for (const member of body.roster ?? []) {
    const nodeId = sectionNode.get(member.sectionId) ?? null;
    const role = member.kind === 'teacher' ? 'teacher' : 'student';
    // Each roster member needs an opaque canonical_uuid; mint one server-side.
    await pool.query(
      `INSERT INTO operational.memberships (institution_id, canonical_uuid, node_id, role, attributes)
         VALUES ($1, gen_random_uuid(), $2, $3, $4::jsonb)`,
      [institutionId, nodeId, role, JSON.stringify({ label: label(member.label, 80) })],
    );
  }

  return institutionId;
}

export async function POST(req: Request): Promise<Response> {
  let body: SchoolBody;
  try {
    body = (await req.json()) as SchoolBody;
  } catch {
    return ok({ persisted: false, reason: 'bad-request' }, 400);
  }
  if (!str(body.name)) return ok({ persisted: false, reason: 'invalid-input' }, 400);

  // The wall authorizes the institution write FIRST (only an admin may publish a
  // school structure). A denied caller is refused; an unreachable wall degrades.
  const gate = await authorizeWrite(req, 'school', 'publish', {
    payload: { institution_id: body.institutionId },
  });
  if (!gate.proceed) return denied(gate.detail);

  const pool = getPool();
  if (!pool) return degraded();

  try {
    const institutionId = await persistSchool(pool, body);
    return ok({ persisted: Boolean(institutionId), id: institutionId ?? undefined });
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
    const inst = await pool.query(
      `SELECT institution_id, label, attributes
         FROM operational.institutions WHERE institution_id = $1`,
      [institutionId],
    );
    if (inst.rowCount === 0) return ok({ persisted: true, rows: [] });

    const nodes = await pool.query(
      `SELECT node_id, kind, label, parent_id, attributes
         FROM operational.structure_nodes
        WHERE institution_id = $1
        ORDER BY created_at`,
      [institutionId],
    );
    const roster = await pool.query(
      `SELECT membership_id, canonical_uuid, node_id, role, attributes
         FROM operational.memberships
        WHERE institution_id = $1 AND valid_to IS NULL
        ORDER BY created_at`,
      [institutionId],
    );
    return ok({
      persisted: true,
      rows: inst.rows,
      nodes: nodes.rows,
      roster: roster.rows,
    });
  } catch {
    return ok({ persisted: false, rows: [], reason: 'read-failed' });
  }
}
