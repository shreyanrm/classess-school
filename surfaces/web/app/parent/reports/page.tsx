'use client';

import { useEffect, useState } from 'react';
import { Button, Icon, Input, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ChildSwitcher } from '../../_components/ChildSwitcher';
import { ConsentGated } from '../../_components/ConsentGated';
import { ReadStates } from '../../_components/ReadStates';
import { useParentRead } from '@/lib/useParentRead';
import { useEmit } from '@/lib/useEmit';
import { EVENT_PURPOSE } from '@/lib/events';
import {
  DEFAULT_CHILD_ID,
  findChild,
  type ParentReport,
} from '@/lib/parentData';
import { sendEmail } from '@/lib/emailClient';
import { useT } from '@/lib/i18n';

/**
 * Assignments, exams and reports — with parent-specific feedback, celebration
 * points and next steps. Everything is written in the parent's language, never
 * a raw mark or formula. Reports are published by a human (consequential actions
 * never auto-fire); the parent reads what the school has chosen to share.
 */
export default function ParentReportsPage() {
  const [childId, setChildId] = useState(DEFAULT_CHILD_ID);
  const child = findChild(childId);
  // Gateway-first governed read; the mock bundle answers on degrade. Reports are
  // released by a human (never auto-fired); five designed states via the hook.
  const { phase, data, source } = useParentRead(childId);
  const { emit } = useEmit();
  const { t } = useT();

  useEffect(() => {
    if (phase === 'ready') {
      emit({
        type: 'surface.viewed',
        purpose: EVENT_PURPOSE.learning,
        payload: { surface: 'parent.reports', child: childId, source },
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, childId]);

  return (
    <SurfaceShell
      eyebrow={child ? child.section : t('parent.reports.eyebrow')}
      title={child ? `${child.label}'s reports and feedback` : 'Reports and feedback'}
      dockIntro="Ask what a report means in plain language, or how to act on a next step at home."
      dockChips={['What does this mean', 'What should we do next', 'Show the celebration points']}
    >
      <section className="stack">
        <p className="overline">{t('parent.reports.whose')}</p>
        <ChildSwitcher selectedId={childId} onSelect={setChildId} />
      </section>

      {phase === 'permission-denied' ? (
        <ConsentGated label={child?.label} />
      ) : phase !== 'ready' ? (
        <ReadStates phase={phase} />
      ) : !child || !data ? (
        <ConsentGated label={child?.label} />
      ) : data.reports.length === 0 ? (
        <section className="stack">
          <div className="empty">
            <Icon name="book" size="lg" className="glyph" />
            <h4 className="body">{t('parent.reports.noneTitle')}</h4>
            <p>
              When the school shares an assignment, exam or report for {child.label}, it will appear
              here with feedback you can act on.
            </p>
          </div>
        </section>
      ) : (
        <>
          <section className="stack">
            <p className="overline">{t('parent.reports.sharedWithYou')}</p>
            <p className="caption quiet">
              {t('parent.reports.plainNote')}
            </p>
            {data.reports.map((r) => (
              <ReportCard key={r.id} report={r} childLabel={child.label} />
            ))}
          </section>

          <p className="caption quiet row" style={{ gap: 'var(--space-2)' }}>
            <Icon name="info" size="sm" />
            {t('parent.reports.releasedNote')}
          </p>
        </>
      )}
    </SurfaceShell>
  );
}

function ReportCard({ report, childLabel }: { report: ParentReport; childLabel: string }) {
  const { t } = useT();
  // "Email this report" — a real end-to-end trigger over /api/email. The browser
  // posts the typed { kind:'weekly-briefing', data } and the server route renders
  // the branded HTML and (when the Resend key is present) sends it. With no key
  // it resolves { sent:false } and we show a calm "saved, not sent" state.
  const [emailing, setEmailing] = useState(false);
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  async function sendReport() {
    if (!EMAIL_RE.test(email.trim())) {
      setStatus('Enter a valid email address to send this report.');
      return;
    }
    setBusy(true);
    setStatus(null);
    const result = await sendEmail({
      to: email.trim(),
      email: {
        kind: 'weekly-briefing',
        data: {
          childLabel,
          highlights: [
            { title: 'How it is going.', detail: report.feedback },
            { title: 'To celebrate.', detail: report.celebration },
            { title: 'One next step.', detail: report.nextStep },
          ],
          reportUrl:
            typeof window !== 'undefined' ? `${window.location.origin}/parent/reports` : '/parent/reports',
        },
      },
      // The parent reading their own child's shared report has consent by design.
      flags: { consent: true },
    });
    setBusy(false);
    setStatus(
      result.sent
        ? 'Sent. Check the inbox in a moment.'
        : 'Saved. Sending is not switched on here yet, so nothing was emailed.',
    );
  }

  return (
    <SpotlightCard padLg>
      <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-4)' }}>
        <h3 className="body-lg" style={{ margin: 0 }}>
          {report.title}
        </h3>
        <span className="caption muted">{report.shared}</span>
      </div>

      <p className="body-sm" style={{ marginTop: 'var(--space-3)' }}>
        {report.feedback}
      </p>

      <div className="parent-report-points">
        <div className="parent-report-point">
          <Tag tone="success">{t('parent.reports.celebrate')}</Tag>
          <p className="body-sm" style={{ margin: 0 }}>
            {report.celebration}
          </p>
        </div>
        <div className="parent-report-point">
          <Tag tone="info">{t('parent.reports.nextStep')}</Tag>
          <p className="body-sm" style={{ margin: 0 }}>
            {report.nextStep}
          </p>
        </div>
      </div>

      <p className="caption muted" style={{ marginTop: 'var(--space-4)' }}>
        {t('parent.reports.sharedBy')} {report.publishedBy}
      </p>

      <div className="divider" />
      {emailing ? (
        <div className="stack" style={{ gap: 'var(--space-3)' }}>
          <Input
            label="Send to"
            type="email"
            inputMode="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
          />
          <div className="rec-actions">
            <Button variant="accent" size="sm" disabled={busy} onClick={sendReport} data-testid="report-email-send">
              {busy ? 'Sending' : t('parent.reports.send')}
            </Button>
            <Button variant="ghost" size="sm" disabled={busy} onClick={() => { setEmailing(false); setStatus(null); }}>
              Not now
            </Button>
          </div>
          {status ? (
            <p className="caption muted" role="status" aria-live="polite">
              {status}
            </p>
          ) : null}
        </div>
      ) : (
        <div className="rec-actions">
          <Button variant="secondary" size="sm" onClick={() => setEmailing(true)} data-testid="report-email-open">
            <Icon name="send" size="sm" />
            {t('parent.reports.email')}
          </Button>
          <span className="caption muted">{t('parent.reports.emailHint')}</span>
        </div>
      )}
    </SpotlightCard>
  );
}
