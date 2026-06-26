'use client';

import { Icon, Matrix, Tag } from '@classess/design-system';
import { StatCell } from './StatCell';
import { EvidenceDrawer } from './EvidenceDrawer';
import { SourceNote } from './SourceNote';
import type { ReadSource } from '@/lib/vizData';
import {
  STAFF_STATE_LABEL,
  STAFF_STATE_TONE,
  staffCounts,
  type StaffAttendance,
} from '@/lib/opsData';

/* ============================================================================
   StaffAttendanceTable — the v2 Staff Attendance screen, in the v3 grammar.

   A count-up matrix of today's states (present / on leave / late / covering /
   not marked), then a calm roster table grouped readable by department, each
   row carrying a plain reason + the cover arrangement. Never a ranking, never a
   judgement: a "not marked" row queues a quiet check-in, it does not name and
   shame. Plain counts only. Depth = hairline + tonal, NO shadow, reduced-motion
   safe. Pure + data-driven.
   ============================================================================ */

export interface StaffAttendanceTableProps {
  data: StaffAttendance;
  source?: ReadSource;
}

export function StaffAttendanceTable({ data, source = 'fallback' }: StaffAttendanceTableProps) {
  const c = staffCounts(data);
  const onSite = c.present + c.cover + c.late;

  return (
    <div className="stack" style={{ gap: 'var(--space-5)' }}>
      <Matrix columns={4}>
        <StatCell label="On site" value={onSite} delta={`of ${data.total} staff`} tone="up" />
        <StatCell label="On leave" value={c.leave} delta="cover arranged where needed" tone="flat" />
        <StatCell label="Covering" value={c.cover} delta="picked up a slot" tone="up" />
        <StatCell label="Not marked" value={c.absent} delta="a quiet check-in queued" tone={c.absent > 0 ? 'down' : 'flat'} />
      </Matrix>

      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Staff</th>
              <th>Department</th>
              <th>Today</th>
              <th>Note</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.id}>
                <td style={{ fontWeight: 'var(--fw-medium)' as React.CSSProperties['fontWeight'] }}>{r.label}</td>
                <td className="muted">{r.department}</td>
                <td>
                  <Tag tone={STAFF_STATE_TONE[r.state]} dot>{STAFF_STATE_LABEL[r.state]}</Tag>
                </td>
                <td className="muted" style={{ maxWidth: 360 }}>{r.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="row" style={{ gap: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap' }}>
        <EvidenceDrawer
          claim="How staff attendance is read"
          evidence={[
            'Read from the day’s timetable and check-ins — present, on leave, late, covering, or not yet marked.',
            'A “not marked” row queues a quiet check-in; it is an operational prompt to cover a slot, never a judgement.',
          ]}
          whySeeing="Staff attendance is shown so an open slot is covered early — it is a calm operational read, not a ranking of people."
        />
        <span className="caption quiet row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
          <Icon name="info" size="sm" /> Counts, not a score — a slot to cover, not a person to police.
        </span>
      </div>

      <SourceNote source={source} />
    </div>
  );
}
