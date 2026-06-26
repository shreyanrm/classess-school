'use client';

import Link from 'next/link';
import { Icon, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ReadStates } from '../../_components/ReadStates';
import { LeaveBoard } from '../../_components/LeaveBoard';
import { StaffAttendanceTable } from '../../_components/StaffAttendanceTable';
import { SupportLog } from '../../_components/SupportLog';
import { AccessControlConfig } from '../../_components/AccessControlConfig';
import { useAdminConfig } from '@/lib/adminConfig';
import { useRole } from '@/lib/RoleContext';
import { useStore } from '@/lib/useStore';
import {
  LEAVE_FALLBACK,
  STAFF_ATTENDANCE_FALLBACK,
  SUPPORT_LOG_FALLBACK,
  leaveCounts,
  mergeSubmittedLeave,
  staffCounts,
  supportCounts,
} from '@/lib/opsData';

/**
 * Operations (admin) — the v2 operational workflows, recomposed to the
 * sample-page bar in the v3 grammar. Three tabs ride a tab strip:
 *
 *   · Leave approval — counts + a request list + a detail drawer (BottomSheet)
 *     with approve / reject gated by the PERMISSION LADDER (coordinator vs
 *     principal). Nothing auto-approves.
 *   · Staff attendance — today's plain-count states + a roster with cover. A
 *     calm operational read, never a ranking.
 *   · Support log — the discipline log, NON-PUNITIVE: patterns to notice with a
 *     prepared restorative step that waits for approval.
 *
 * The active lens persists through the wall (admin config); the surface degrades
 * to the PII-free seed with an observable SourceNote on each board.
 */
type Lens = 'leave' | 'staff' | 'support' | 'access';

export default function AdminOperationsPage() {
  const surface = useAdminConfig('operations');
  const { role } = useRole();
  // Pull in any leave a teacher/student SUBMITTED locally so the requester ->
  // approver circuit is real: a submitted application appears in this queue as a
  // fresh pending request. Merged onto the PII-free seed, newest first.
  const { leaveApplications } = useStore();
  const leaveBoard = mergeSubmittedLeave(LEAVE_FALLBACK, leaveApplications ?? []);
  const savedLens = surface.config.lens;
  const lens: Lens =
    savedLens === 'staff' || savedLens === 'support' || savedLens === 'access' || savedLens === 'leave'
      ? (savedLens as Lens)
      : 'leave';
  const setLens = (l: Lens) => {
    void surface.set('lens', l);
  };
  const accessOn = surface.config.acEnabled === true;

  // Source per board — gateway-first config rehydrate drives the SourceNote.
  const source = surface.source;
  const leave = leaveCounts(leaveBoard);
  const staff = staffCounts(STAFF_ATTENDANCE_FALLBACK);
  const support = supportCounts(SUPPORT_LOG_FALLBACK);

  const dock: Record<Lens, { intro: string; chips: string[] }> = {
    leave: {
      intro:
        'I gather every leave request and hold it at the approval gate. A coordinator can clear a short leave; an overlapping or long one is held for the principal. I never approve anything on my own.',
      chips: ['Which requests need me today', 'Why is this one flagged', 'Who can approve a five-day leave'],
    },
    staff: {
      intro:
        'I read today’s staff attendance from the timetable and check-ins — present, on leave, late, covering, not yet marked. It is a calm operational read so an open slot is covered early, never a ranking.',
      chips: ['Which slots still need cover', 'Who is not marked yet', 'Arrange cover for 10-B period 3'],
    },
    support: {
      intro:
        'I keep a calm, non-punitive support log: patterns to notice, each with a prepared restorative step that waits for a human. Nothing is a punishment, nothing is applied automatically.',
      chips: ['What needs a look this week', 'Prepare a check-in for 9-A', 'Which patterns have repeated'],
    },
    access: {
      intro:
        'I hold the attendance access rule — where a mark is valid (a campus geofence) and when (a daily window). It is campus geometry, never a tracker of a person. You set it; nothing applies until you save, and a mark outside the rule is held for a human, never rejected.',
      chips: ['Set the campus geofence', 'What does the time window do', 'Is any location stored about a student'],
    },
  };

  return (
    <SurfaceShell
      eyebrow="Operations"
      title="Daily operations"
      breadcrumb={[{ label: 'School', href: '/' }, { label: 'Operations' }]}
      meta={[
        { value: leave.pending + leave.flagged, label: 'leave awaiting you' },
        { value: staff.absent, label: 'staff not marked' },
        { value: support.needsLook, label: 'support items to look at' },
        { label: 'nothing acts on its own' },
      ]}
      tabs={[
        { label: 'Leave approval', active: lens === 'leave', onClick: () => setLens('leave') },
        { label: 'Staff attendance', active: lens === 'staff', onClick: () => setLens('staff') },
        { label: 'Support log', active: lens === 'support', onClick: () => setLens('support') },
        { label: 'Access control', active: lens === 'access', onClick: () => setLens('access') },
      ]}
      actions={
        <Link href="/admin/calendar" className="btn btn-secondary row" style={{ gap: 'var(--space-2)' }}>
          <Icon name="calendar" size="sm" />
          Calendar
        </Link>
      }
      dockIntro={dock[lens].intro}
      dockChips={dock[lens].chips}
      aside={
        surface.phase !== 'ready' ? null : (
          <>
            <div className="ignite-card reveal reveal-2">
              <div className="row-between" style={{ marginBottom: 14 }}>
                <span className="overline">Yours to decide</span>
                <Icon name="flame" size="md" style={{ color: 'var(--accent)' }} />
              </div>
              <div className="who">
                {lens === 'leave'
                  ? `${leave.pending + leave.flagged} leave requests at the gate`
                  : lens === 'staff'
                    ? `${staff.cover} slots already picked up`
                    : lens === 'access'
                      ? accessOn
                        ? 'the access rule is on'
                        : 'the access rule is advisory'
                      : `${support.needsLook} patterns to look at, calmly`}
              </div>
              <p className="body-sm" style={{ opacity: 0.8, marginTop: 8 }}>
                {lens === 'leave'
                  ? 'Each request waits for a human; the ladder names who may decide each one.'
                  : lens === 'staff'
                    ? 'Cover is arranged where staff are on leave. A not-marked row queues a quiet check-in, never a flag against the person.'
                    : lens === 'access'
                      ? 'The geofence and window are campus geometry — a mark outside the rule is held for a person, never rejected, and no individual location is stored.'
                      : 'Behaviour is read to understand and support early — every step is restorative and waits for you.'}
              </p>
            </div>

            <div className="panel">
              <div className="sec-head" style={{ marginBottom: 8 }}>
                <h4 className="h4" style={{ margin: 0 }}>The permission ladder</h4>
                <Tag tone="info" dot>prepare → approve</Tag>
              </div>
              <p className="caption" style={{ marginBottom: 12 }}>
                Every operational action is prepared and held. A human approves; nothing auto-fires.
              </p>
              {[
                { t: 'Coordinator', note: 'Clears short leave, arranges cover, opens a check-in.' },
                { t: 'Principal', note: 'Holds long or overlapping leave, signs off restorative steps.' },
              ].map((s) => (
                <div className="sched" key={s.t}>
                  <span className="t">{s.t}</span>
                  <div>
                    <p className="caption">{s.note}</p>
                  </div>
                </div>
              ))}
            </div>

            <div className="panel" style={{ padding: '18px 20px' }}>
              <p className="handnote" style={{ fontSize: 22 }}>
                {lens === 'support'
                  ? 'a log to understand, never a record of punishments'
                  : lens === 'access'
                    ? 'a rule about a mark, never a tracker of a person'
                    : 'you hold the decision — the platform only prepares it'}
              </p>
            </div>
          </>
        )
      }
    >
      {surface.phase !== 'ready' ? (
        <ReadStates phase={surface.phase} onRetry={surface.refresh} />
      ) : (
        <>
          <p className="caption quiet" style={{ margin: 0 }}>
            {source === 'gateway'
              ? 'Your last lens is read back from the event store, so you return to the workflow you left.'
              : 'Your lens records to the event store when it is reachable; the boards are showing the last-known read.'}
          </p>

          {lens === 'leave' ? (
            <section>
              <div className="sec-head">
                <h3 className="h3" style={{ margin: 0 }}>Leave approval</h3>
                <span className="overline">{leaveBoard.scopeLabel}</span>
              </div>
              <LeaveBoard data={leaveBoard} source={source} role={role} />
            </section>
          ) : lens === 'staff' ? (
            <section>
              <div className="sec-head">
                <h3 className="h3" style={{ margin: 0 }}>Staff attendance</h3>
                <span className="overline">today</span>
              </div>
              <StaffAttendanceTable data={STAFF_ATTENDANCE_FALLBACK} source={source} />
            </section>
          ) : lens === 'support' ? (
            <section>
              <div className="sec-head">
                <h3 className="h3" style={{ margin: 0 }}>Support log</h3>
                <span className="overline">calm and non-punitive</span>
              </div>
              <SupportLog data={SUPPORT_LOG_FALLBACK} source={source} />
            </section>
          ) : (
            <section>
              <div className="sec-head">
                <h3 className="h3" style={{ margin: 0 }}>Attendance access control</h3>
                <span className="overline">geofence · time window</span>
              </div>
              <AccessControlConfig config={surface.config} source={source} onSet={surface.set} />
            </section>
          )}
        </>
      )}
    </SurfaceShell>
  );
}
