'use client';

import { useEffect, useRef, useState } from 'react';
import { Button, Icon, Input, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { SETUP_STEPS } from '@/lib/mock';
import { useStore } from '@/lib/useStore';
import { saveSchool, clearSchool, setSchoolLiveId, type GroupNode, type RosterMember } from '@/lib/store';
import { draftStructure, draftRoster, countStructure, assembleSchool } from '@/lib/setupDraft';
import { saveSchoolLive, loadSchoolLive } from '@/lib/opData';
import { sendEmail } from '@/lib/emailClient';

/**
 * The blueprint wizard — a calm, multi-step flow that PERSISTS to lib/store.
 * Vidya assists: it can suggest a structure and draft a starter roster, both
 * board-agnostic and with generic labels. Nothing is committed automatically —
 * the human approves the drafts and confirms the blueprint (the permission
 * ladder: prepare, then execute only on a human's explicit approval).
 */
export default function AdminSetupPage() {
  const { school } = useStore();

  const [index, setIndex] = useState(0);
  const [name, setName] = useState(school?.institution.name ?? '');
  const [board, setBoard] = useState(school?.institution.board ?? 'Example State Board');
  const [pacing, setPacing] = useState(school?.institution.pacing ?? 'Standard, by section');
  const [structure, setStructure] = useState<GroupNode[]>(school?.structure ?? []);
  const [roster, setRoster] = useState<RosterMember[]>(school?.roster ?? []);

  // GAP#6 — rehydrate the institution config from the DB on mount (a real
  // round-trip, not just localStorage). When a live institution_id exists we
  // reload the persisted row and reconcile the institution-level config (name /
  // board / pacing) from what the operational plane returns, so the blueprint
  // survives a reload because the DB is the source of truth, not the browser.
  // Best-effort: an unconfigured / unreachable DB resolves { persisted:false }
  // and the local store stands, so the surface never breaks or blanks.
  const liveId = school?.institution.liveId;
  const rehydrated = useRef(false);
  useEffect(() => {
    if (!liveId || rehydrated.current) return;
    rehydrated.current = true;
    void loadSchoolLive(liveId).then((res) => {
      const row = res.persisted ? res.rows?.[0] : undefined;
      if (!row) return;
      const dbName = typeof row.label === 'string' ? row.label : undefined;
      const attrs = (row.attributes ?? {}) as { board?: unknown; pacing?: unknown };
      const dbBoard = typeof attrs.board === 'string' ? attrs.board : undefined;
      const dbPacing = typeof attrs.pacing === 'string' ? attrs.pacing : undefined;
      if (dbName) setName(dbName);
      if (dbBoard) setBoard(dbBoard);
      if (dbPacing) setPacing(dbPacing);
      // Re-persist the reconciled institution config to the local store so the
      // rehydrated values survive the next reload too.
      saveSchool(
        assembleSchool({
          name: dbName ?? name,
          board: dbBoard ?? board,
          pacing: dbPacing ?? pacing,
          structure,
          roster,
        }),
      );
      setSchoolLiveId(liveId);
    });
    // Only rehydrate once per live id, on mount; the form drives later edits.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveId]);

  // Teacher/roster invite — a real end-to-end trigger over /api/email. The route
  // renders the branded invite and (when the Resend key is present) sends it;
  // with no key it resolves { sent:false } and we show a calm "not sent" note.
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviting, setInviting] = useState(false);
  const [inviteStatus, setInviteStatus] = useState<string | null>(null);

  async function sendInvite() {
    const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!EMAIL_RE.test(inviteEmail.trim())) {
      setInviteStatus('Enter a valid email address to invite a teacher.');
      return;
    }
    setInviting(true);
    setInviteStatus(null);
    const result = await sendEmail({
      to: inviteEmail.trim(),
      email: {
        kind: 'roster-invite',
        data: {
          schoolName: name || 'Campus North',
          roleLabel: 'teacher',
          inviteUrl:
            typeof window !== 'undefined' ? `${window.location.origin}/sign-up` : '/sign-up',
        },
      },
      // An admin inviting a colleague into their own school has consent by design.
      flags: { consent: true },
    });
    setInviting(false);
    setInviteStatus(
      result.sent
        ? 'Invite sent. They will get a branded email with an accept link.'
        : 'Saved. Sending is not switched on here yet, so no email went out.',
    );
  }

  const step = SETUP_STEPS[index]!;
  const isLast = index === SETUP_STEPS.length - 1;
  const counts = countStructure(structure);

  function suggestStructure() {
    const s = draftStructure();
    setStructure(s);
    // Re-draft the roster against the new structure so they stay consistent.
    setRoster(draftRoster(s));
  }

  function draftRosterOnly() {
    setRoster(draftRoster(structure.length ? structure : draftStructure()));
  }

  function confirm() {
    const blueprint = assembleSchool({ name: name || 'Campus North', board, pacing, structure, roster });
    saveSchool(blueprint);
    setIndex(SETUP_STEPS.length - 1);
    // Persist live to Supabase (best-effort). When a live database is wired the
    // returned institution_id is stamped onto the blueprint so it reloads from
    // the operational plane and survives a refresh; when unwired this resolves
    // to { persisted:false } and the blueprint simply stays on the local store.
    void saveSchoolLive({
      institutionId: blueprint.institution.liveId,
      name: blueprint.institution.name,
      board: blueprint.institution.board,
      pacing: blueprint.institution.pacing,
      structure: blueprint.structure,
      roster: blueprint.roster,
    }).then((res) => {
      if (res.persisted && res.id) setSchoolLiveId(res.id);
    });
  }

  function startOver() {
    clearSchool();
    setName('');
    setStructure([]);
    setRoster([]);
    setIndex(0);
  }

  return (
    <SurfaceShell
      eyebrow="Setup and hierarchy"
      title="Build your school blueprint"
      dockIntro="I can suggest a structure and draft a starter roster for you to approve. Nothing is created until you confirm — I only prepare, you decide."
      dockChips={['Suggest a structure', 'Draft a starter roster', 'What does each role see']}
    >
      <ol className="loop-steps" aria-label="Setup steps">
        {SETUP_STEPS.map((s, i) => (
          <li key={s.id} className={`loop-step${i === index ? ' active' : ''}${i < index ? ' done' : ''}`}>
            <span className="num">{i < index ? <Icon name="check" size="sm" /> : i + 1}</span>
            {s.title}
          </li>
        ))}
      </ol>

      {school?.confirmed && isLast ? (
        <SpotlightCard padLg>
          <div className="row" style={{ gap: 'var(--space-3)' }}>
            <Icon name="success" size="lg" />
            <div>
              <h3 className="body-lg" style={{ margin: 0 }}>
                Blueprint confirmed and saved
              </h3>
              <p className="body-sm muted" style={{ marginTop: 'var(--space-2)' }}>
                {school.institution.name} is set up with {counts.groups} campus, {counts.grades} grades,
                and {counts.sections} sections. {roster.length} people are on the starter roster. This
                persists across reloads. Your morning briefing now reflects the real school.
              </p>
            </div>
          </div>
          <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
            <Button variant="secondary" size="sm" onClick={() => setIndex(0)}>
              Review again
            </Button>
            <Button variant="ghost" size="sm" onClick={startOver}>
              Start over
            </Button>
          </div>
        </SpotlightCard>
      ) : (
        <SpotlightCard padLg>
          <p className="overline">
            Step {index + 1} of {SETUP_STEPS.length}
          </p>
          <h3 className="display-sm" style={{ margin: 'var(--space-2) 0 0' }}>
            {step.title}
          </h3>
          <p className="body" style={{ marginTop: 'var(--space-3)', color: 'var(--text-secondary)' }}>
            {step.summary}
          </p>

          {/* Step 1 — Structure */}
          {index === 0 ? (
            <div className="stack" style={{ marginTop: 'var(--space-4)' }}>
              <Input label="Institution name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Campus North" />
              <Input label="Board" hint="A field, never a lock-in." value={board} onChange={(e) => setBoard(e.target.value)} />
              <div className="divider" />
              <div className="row-between" style={{ gap: 'var(--space-3)' }}>
                <p className="caption quiet" style={{ margin: 0 }}>
                  Vidya can suggest a starting structure for you to adjust. It commits nothing.
                </p>
                <Button variant="secondary" size="sm" onClick={suggestStructure}>
                  <Icon name="spark" size="sm" />
                  Suggest a structure
                </Button>
              </div>
              {structure.length > 0 ? (
                <div className="stack">
                  <Tag tone="info" dot>
                    Drafted by Vidya — yours to approve
                  </Tag>
                  {structure.map((g) => (
                    <div key={g.id} className="admin-list-row" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 'var(--space-2)' }}>
                      <strong className="body-sm">{g.name}</strong>
                      {g.grades.map((gr) => (
                        <span key={gr.id} className="caption muted">
                          {gr.name}: {gr.sections.map((s) => s.name).join(', ')}
                        </span>
                      ))}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}

          {/* Step 2 — Roles / roster */}
          {index === 1 ? (
            <div className="stack" style={{ marginTop: 'var(--space-4)' }}>
              <div className="row-between" style={{ gap: 'var(--space-3)' }}>
                <p className="caption quiet" style={{ margin: 0 }}>
                  Vidya can draft a starter roster of generic teachers and students for you to approve.
                </p>
                <Button variant="secondary" size="sm" onClick={draftRosterOnly}>
                  <Icon name="spark" size="sm" />
                  Draft a starter roster
                </Button>
              </div>
              {roster.length > 0 ? (
                <div className="stack">
                  <Tag tone="info" dot>
                    Drafted by Vidya — yours to approve
                  </Tag>
                  <p className="caption muted">
                    {roster.filter((m) => m.kind === 'teacher').length} teachers and{' '}
                    {roster.filter((m) => m.kind === 'student').length} students across{' '}
                    {counts.sections} sections. Generic labels only — no personal names.
                  </p>
                </div>
              ) : (
                <p className="caption quiet">No roster drafted yet.</p>
              )}

              <div className="divider" />
              <p className="caption quiet" style={{ margin: 0 }}>
                Invite a teacher by email. They receive a branded invite with an accept link.
                Nothing is created until they accept.
              </p>
              {inviteOpen ? (
                <div className="stack" style={{ gap: 'var(--space-3)' }}>
                  <Input
                    label="Teacher email"
                    type="email"
                    inputMode="email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="teacher@example.com"
                  />
                  <div className="rec-actions">
                    <Button variant="accent" size="sm" disabled={inviting} onClick={sendInvite} data-testid="roster-invite-send">
                      {inviting ? 'Sending' : 'Send invite'}
                    </Button>
                  </div>
                  {inviteStatus ? (
                    <p className="caption muted" role="status" aria-live="polite">
                      {inviteStatus}
                    </p>
                  ) : null}
                </div>
              ) : (
                <div className="rec-actions">
                  <Button variant="secondary" size="sm" onClick={() => setInviteOpen(true)} data-testid="roster-invite-open">
                    <Icon name="send" size="sm" />
                    Invite a teacher by email
                  </Button>
                </div>
              )}
            </div>
          ) : null}

          {/* Step 3 — Policies */}
          {index === 2 ? (
            <div className="stack" style={{ marginTop: 'var(--space-4)' }}>
              <Input label="Pacing approach" value={pacing} onChange={(e) => setPacing(e.target.value)} />
              <ul className="stack" style={{ paddingLeft: '1.1rem' }}>
                {step.fields.map((f) => (
                  <li key={f} className="body-sm">
                    {f}
                  </li>
                ))}
              </ul>
              <p className="caption quiet">
                Consequential actions stay behind explicit approval. Nothing auto-fires.
              </p>
            </div>
          ) : null}

          {/* Step 4 — Review */}
          {index === 3 ? (
            <div className="stack" style={{ marginTop: 'var(--space-4)' }}>
              <p className="body-sm">
                <strong>{name || 'Campus North'}</strong> · {board} · {pacing}
              </p>
              <p className="caption muted">
                {counts.groups} campus, {counts.grades} grades, {counts.sections} sections,{' '}
                {roster.length} on the roster.
              </p>
              <p className="caption quiet">
                Confirming saves this blueprint to your school. It persists across reloads, and you
                can adjust it any time. Nothing is created until you confirm.
              </p>
            </div>
          ) : null}

          <div className="divider" />

          <div className="rec-actions">
            <Button variant="ghost" size="sm" disabled={index === 0} onClick={() => setIndex((i) => Math.max(0, i - 1))}>
              Back
            </Button>
            {isLast ? (
              <Button variant="accent" size="sm" onClick={confirm}>
                Confirm the blueprint
              </Button>
            ) : (
              <Button
                variant="primary"
                size="sm"
                disabled={index === 0 && structure.length === 0}
                onClick={() => setIndex((i) => i + 1)}
              >
                Continue
                <Icon name="arrow-right" size="sm" />
              </Button>
            )}
          </div>
          {index === 0 && structure.length === 0 ? (
            <p className="caption quiet" style={{ marginTop: 'var(--space-3)' }}>
              Suggest or define a structure to continue.
            </p>
          ) : null}
        </SpotlightCard>
      )}
    </SurfaceShell>
  );
}
