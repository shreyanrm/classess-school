'use client';

import { useState } from 'react';
import { Button, Icon, SpotlightCard, Tag } from '@classess/design-system';
import { useEmit } from '@/lib/useEmit';
import { EVENT_PURPOSE } from '@/lib/events';
import {
  applyTransition,
  canSubmit,
  type AssignmentView,
  type WorkStatus,
} from '@/lib/workData';

const STATUS_TONE: Record<WorkStatus, 'neutral' | 'info' | 'success' | 'warning'> = {
  todo: 'neutral',
  'in-progress': 'info',
  submitted: 'success',
  returned: 'warning',
};

export interface InboxItemProps {
  item: AssignmentView;
}

/**
 * One assignment in the learner's inbox. The status moves along an explicit
 * ladder (to do -> in progress -> submitted -> returned). SUBMISSION IS
 * CONSEQUENTIAL: it is never auto-fired — the learner starts it, then explicitly
 * confirms, and can step back before confirming. Plain language throughout.
 */
export function InboxItem({ item }: InboxItemProps) {
  const [status, setStatus] = useState<WorkStatus>(item.status);
  const [confirming, setConfirming] = useState(false);
  const { emit } = useEmit();

  function start() {
    setStatus((s) => applyTransition(s, 'in-progress'));
  }

  // Submit is the consequential action — it fires ONLY after the explicit
  // confirm (the human-approval rung), and emits an attributed, consent-stamped
  // event the record can audit. Never auto-fired.
  function confirmSubmit() {
    setStatus((s) => applyTransition(s, 'submitted'));
    setConfirming(false);
    emit({
      type: 'submission.created',
      purpose: EVENT_PURPOSE.learning,
      payload: { assignment_id: item.id, kind: item.kindLabel, approved: true },
    });
  }

  return (
    <SpotlightCard padLg>
      <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-3)' }}>
        <div>
          <h3 className="body-lg" style={{ margin: 0 }}>
            {item.title}
          </h3>
          <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
            {item.subjectName} · {item.topicName} · {item.kindLabel}
          </p>
        </div>
        <Tag tone={STATUS_TONE[status]}>{statusLabel(status)}</Tag>
      </div>

      <p className="body-sm muted" style={{ marginTop: 'var(--space-3)' }}>
        {item.brief}
      </p>
      <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
        {item.due}
        {item.itemCount ? ` · ${item.itemCount} items` : ''}
      </p>

      {status === 'returned' && item.feedback ? (
        <p className="body-sm" style={{ marginTop: 'var(--space-3)' }}>
          <span className="quiet">Feedback. </span>
          {item.feedback}
        </p>
      ) : null}

      <div className="divider" />

      {status === 'todo' ? (
        <div className="rec-actions">
          <Button variant="primary" size="sm" onClick={start}>
            Start
            <Icon name="arrow-right" size="sm" />
          </Button>
          <span className="caption muted">Starting does not submit anything.</span>
        </div>
      ) : status === 'in-progress' ? (
        confirming ? (
          <div className="rec-actions">
            <Button variant="accent" size="sm" onClick={confirmSubmit}>
              Yes, submit it
            </Button>
            <Button variant="secondary" size="sm" onClick={() => setConfirming(false)}>
              Not yet
            </Button>
            <span className="caption muted">
              Once you submit, it goes to your teacher. You decide when it is ready.
            </span>
          </div>
        ) : (
          <div className="rec-actions">
            <Button variant="primary" size="sm" disabled={!canSubmit(status)} onClick={() => setConfirming(true)}>
              Submit
            </Button>
            <span className="caption muted">You will be asked to confirm — nothing submits on its own.</span>
          </div>
        )
      ) : status === 'submitted' ? (
        <div className="rec-actions">
          <span className="row body-sm" style={{ gap: 'var(--space-2)', color: 'var(--text-secondary)' }}>
            <Icon name="check" size="sm" />
            Submitted. Your teacher will return it with feedback.
          </span>
        </div>
      ) : (
        <div className="rec-actions">
          <span className="body-sm">Returned with feedback. Have a look above.</span>
        </div>
      )}
    </SpotlightCard>
  );
}

function statusLabel(status: WorkStatus): string {
  const map: Record<WorkStatus, string> = {
    todo: 'To do',
    'in-progress': 'In progress',
    submitted: 'Submitted',
    returned: 'Returned',
  };
  return map[status];
}
