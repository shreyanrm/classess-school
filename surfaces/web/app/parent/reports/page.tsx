'use client';

import { useEffect, useMemo, useState } from 'react';
import { Button, Icon, Input, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ChildSwitcher } from '../../_components/ChildSwitcher';
import { ConsentGated } from '../../_components/ConsentGated';
import { ReadStates } from '../../_components/ReadStates';
import { SourceNote } from '../../_components/SourceNote';
import { LanguageBadge } from '../../_components/LanguageBadge';
import { useParentRead } from '@/lib/useParentRead';
import { useReaderText } from '@/lib/useReaderText';
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
 * Reports and feedback — recomposed to the sample-page bar. A stat matrix of
 * plain-language counts (reports shared, celebration points, next steps,
 * subjects covered), then a .cols layout:
 *   · main — each shared report as a designed card, with a real end-to-end
 *     "email this report" trigger over /api/email.
 *   · aside — a "what to ask" panel that turns next steps into questions, and a
 *     Caveat handnote. Reports are released by a human, never auto-fired.
 *
 * Gateway-first read; mock bundle on degrade; SourceNote degrades honestly.
 * Generated feedback renders into the parent's language through tx(). Never a
 * raw mark or formula. All five designed states ship.
 */
export default function ParentReportsPage() {
  const [childId, setChildId] = useState(DEFAULT_CHILD_ID);
  const child = findChild(childId);
  const { phase, data, source } = useParentRead(childId);
  const { emit } = useEmit();
  const { t } = useT();

  const reports = useMemo(() => data?.reports ?? [], [data]);
  const { tx, rendering, rendered, locale } = useReaderText(
    reports.flatMap((r) => [r.feedback, r.celebration, r.nextStep]),
  );

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

  const counts = useMemo(() => {
    if (!data) return { reports: 0, celebrations: 0, nextSteps: 0, subjects: 0 };
    const subjects = new Set(data.reports.map((r) => r.subject)).size;
    return {
      reports: data.reports.length,
      celebrations: data.reports.filter((r) => r.celebration).length,
      nextSteps: data.reports.filter((r) => r.nextStep).length,
      subjects,
    };
  }, [data]);

  const hasReports = phase === 'ready' && child && data && data.reports.length > 0;

  return (
    <SurfaceShell
      eyebrow={child ? child.section : t('parent.reports.eyebrow')}
      title={child ? `${child.label}'s reports and feedback` : 'Reports and feedback'}
      breadcrumb={[
        { label: 'Family', href: '/parent' },
        { label: t('parent.reports.eyebrow') },
      ]}
      meta={[
        { value: counts.reports || '—', label: 'shared with you' },
        { value: counts.subjects || '—', label: 'subjects covered' },
        { label: 'released by a teacher, never automatically' },
      ]}
      tabs={[
        { label: 'This week', href: '/parent' },
        { label: 'The child', href: '/parent/child' },
        { label: 'Reports', active: true },
        { label: 'Together', href: '/parent/together' },
      ]}
      dockIntro="Ask what a report means in plain language, or how to act on a next step at home."
      dockChips={['What does this mean', 'What should we do next', 'Show the celebration points']}
      aside={
        !hasReports ? null : (
          <>
            <div className="panel reveal reveal-2">
              <div className="sec-head" style={{ marginBottom: 8 }}>
                <h4 className="h4" style={{ margin: 0 }}>
                  What to ask
                </h4>
                <Tag tone="info">{counts.nextSteps}</Tag>
              </div>
              <p className="caption" style={{ marginBottom: 12 }}>
                Each next step, turned into one calm question for the teacher.
              </p>
              {data!.reports.map((r) => (
                <div className="flag" key={r.id}>
                  <div className="flag-ic">
                    <Icon name="target" size="sm" />
                  </div>
                  <div>
                    <div className="body-sm" style={{ fontWeight: 500 }}>
                      {r.title}
                    </div>
                    <p className="caption">{tx(r.nextStep)}</p>
                  </div>
                </div>
              ))}
            </div>

            <div className="panel reveal reveal-4" style={{ padding: '18px 20px' }}>
              <p className="handnote" style={{ fontSize: 22 }}>
                read the celebration first — it is true, and it is theirs
              </p>
            </div>
          </>
        )
      }
    >
      <section className="stack">
        <div
          className="row-between"
          style={{ alignItems: 'flex-end', gap: 'var(--space-3)', flexWrap: 'wrap' }}
        >
          <p className="overline" style={{ margin: 0 }}>
            {t('parent.reports.whose')}
          </p>
          <LanguageBadge locale={locale} rendering={rendering} rendered={rendered} />
        </div>
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
          <ReportsMatrix counts={counts} />

          <section className="stack">
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                {t('parent.reports.sharedWithYou')}
              </h3>
              <span className="overline">plain language, never a raw mark</span>
            </div>
            <p className="caption quiet">{t('parent.reports.plainNote')}</p>
            {data.reports.map((r) => (
              <ReportCard key={r.id} report={r} childLabel={child.label} tx={tx} />
            ))}
          </section>

          <p className="caption quiet row" style={{ gap: 'var(--space-2)' }}>
            <Icon name="info" size="sm" />
            {t('parent.reports.releasedNote')}
          </p>

          <SourceNote source={source} />
        </>
      )}
    </SurfaceShell>
  );
}

/** The plain-language count matrix for reports. Counts, never marks. */
function ReportsMatrix({
  counts,
}: {
  counts: { reports: number; celebrations: number; nextSteps: number; subjects: number };
}) {
  const cells: Array<{ label: string; value: number; delta: string; tone: 'up' | 'flat' }> = [
    { label: 'Shared with you', value: counts.reports, delta: 'by a teacher, deliberately', tone: 'flat' },
    { label: 'Celebration points', value: counts.celebrations, delta: 'true, and theirs', tone: 'up' },
    { label: 'Next steps', value: counts.nextSteps, delta: 'concrete and supportive', tone: 'flat' },
    { label: 'Subjects covered', value: counts.subjects, delta: 'across this term', tone: 'flat' },
  ];
  return (
    <div className="matrix reveal reveal-1" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
      {cells.map((c) => (
        <div className="cell" key={c.label}>
          <div className="cell-label">{c.label}</div>
          <div className="cell-value">
            <span>{c.value}</span>
          </div>
          <div className={`cell-delta ${c.tone}`}>{c.delta}</div>
        </div>
      ))}
    </div>
  );
}

function ReportCard({
  report,
  childLabel,
  tx,
}: {
  report: ParentReport;
  childLabel: string;
  /** Render generated text into the reader's language (falls back to original). */
  tx: (text: string) => string;
}) {
  const { t } = useT();
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
            typeof window !== 'undefined'
              ? `${window.location.origin}/parent/reports`
              : '/parent/reports',
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
    <SpotlightCard padLg data-subject={report.subject}>
      <div
        className="row"
        style={{ gap: 'var(--space-3)', alignItems: 'center', marginBottom: 'var(--space-3)' }}
      >
        <span
          className="report-subject-chip"
          style={
            {
              '--subject': `var(--${report.subject})`,
              '--subject-ink': `var(--${report.subject}-ink)`,
            } as React.CSSProperties
          }
        >
          {report.subject.slice(0, 3).toUpperCase()}
        </span>
        <div className="row-between" style={{ flex: 1, alignItems: 'flex-start', gap: 'var(--space-4)' }}>
          <h3 className="body-lg" style={{ margin: 0 }}>
            {report.title}
          </h3>
          <span className="caption muted">{report.shared}</span>
        </div>
      </div>

      <p className="body-sm" style={{ marginTop: 'var(--space-2)' }}>
        {tx(report.feedback)}
      </p>

      <div className="parent-report-points">
        <div className="parent-report-point">
          <Tag tone="success">{t('parent.reports.celebrate')}</Tag>
          <p className="body-sm" style={{ margin: 0 }}>
            {tx(report.celebration)}
          </p>
        </div>
        <div className="parent-report-point">
          <Tag tone="info">{t('parent.reports.nextStep')}</Tag>
          <p className="body-sm" style={{ margin: 0 }}>
            {tx(report.nextStep)}
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
            <Button
              variant="accent"
              size="sm"
              disabled={busy}
              onClick={sendReport}
              data-testid="report-email-send"
            >
              {busy ? 'Sending' : t('parent.reports.send')}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={busy}
              onClick={() => {
                setEmailing(false);
                setStatus(null);
              }}
            >
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
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setEmailing(true)}
            data-testid="report-email-open"
          >
            <Icon name="send" size="sm" />
            {t('parent.reports.email')}
          </Button>
          <span className="caption muted">{t('parent.reports.emailHint')}</span>
        </div>
      )}
    </SpotlightCard>
  );
}
