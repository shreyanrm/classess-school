'use client';

import { Button, ConfidenceBand, Icon, SpotlightCard, Tag } from '@classess/design-system';
import {
  RESOURCE_TYPE_LABEL,
  SOURCE_LABEL,
  VERIFICATION_LABEL,
  type ResourceView,
} from '@/lib/contentData';
import { EvidenceDrawer } from './EvidenceDrawer';

const VERIFICATION_TONE = {
  verified: 'success',
  'needs-review': 'warning',
  generated: 'neutral',
} as const;

export interface LibraryItemProps {
  resource: ResourceView;
  /** Open the human verification surface for a not-yet-verified resource. */
  onReview?: (resource: ResourceView) => void;
}

/**
 * One content-library resource. Mapped to an ontology topic, with its
 * generate-and-verify state shown as a ConfidenceBand, its provenance behind the
 * evidence drawer, and a clear servable / held-back read. Only VERIFIED content
 * is servable (INVARIANT 7); a not-yet-verified item offers a human review act,
 * never an auto-publish.
 */
export function LibraryItem({ resource, onReview }: LibraryItemProps) {
  return (
    <SpotlightCard padLg data-subject={resource.accent}>
      <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-3)' }}>
        <div>
          <h3 className="body-lg" style={{ margin: 0 }}>
            {resource.title}
          </h3>
          <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
            {resource.subjectName} · {resource.topicName} · {RESOURCE_TYPE_LABEL[resource.type]}
          </p>
        </div>
        <Tag tone={VERIFICATION_TONE[resource.verification]}>
          {VERIFICATION_LABEL[resource.verification]}
        </Tag>
      </div>

      <p className="body-sm muted" style={{ marginTop: 'var(--space-3)' }}>
        {resource.summary}
      </p>

      <div className="row" style={{ gap: 'var(--space-3)', marginTop: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap' }}>
        <ConfidenceBand level={resource.confidence} />
        <Tag tone="neutral">{SOURCE_LABEL[resource.source]}</Tag>
        {resource.servable ? (
          <span className="row caption" style={{ gap: 'var(--space-2)', color: 'var(--text-secondary)' }}>
            <Icon name="check" size="sm" />
            Servable to learners
          </span>
        ) : (
          <span className="row caption" style={{ gap: 'var(--space-2)', color: 'var(--text-secondary)' }}>
            <Icon name="search" size="sm" />
            Held back until verified
          </span>
        )}
      </div>

      <div style={{ marginTop: 'var(--space-3)' }}>
        <EvidenceDrawer
          evidence={[resource.provenance, `Rights: ${resource.licence}`, resource.updated]}
          whySeeing={
            resource.servable
              ? 'This passed the verification gate and a human approved it, so it can be served to learners.'
              : 'Generated and ingested content is never auto-served. It waits for an explicit human review before it can reach a learner.'
          }
        />
      </div>

      {!resource.servable ? (
        <>
          <div className="divider" />
          <div className="rec-actions">
            <Button variant="primary" size="sm" onClick={() => onReview?.(resource)}>
              Open the review
              <Icon name="arrow-right" size="sm" />
            </Button>
            <span className="caption muted">Approval is a human decision — nothing publishes on its own.</span>
          </div>
        </>
      ) : null}
    </SpotlightCard>
  );
}
