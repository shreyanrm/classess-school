'use client';

import Link from 'next/link';
import { ConfidenceBand, Icon, SpotlightCard, Tag } from '@classess/design-system';
import type { Confidence } from '@classess/design-system';

export interface InlineResultData {
  /** Short title of the generated artifact. */
  title: string;
  /** A line or two summarising what was produced. */
  body: string;
  /** Plain-language bullet points making up the artifact. */
  items?: string[];
  /** The verification confidence on the generated content. */
  confidence?: Confidence;
  /** Where the full version lives, if this warrants a real page. */
  openHref?: string;
  /** Label for the open control. */
  openLabel?: string;
}

export interface InlineResultProps {
  data: InlineResultData;
}

/**
 * A self-contained, ephemeral result rendered inline in the thread as a
 * generative component (the signature SpotlightCard), carrying an "open in its
 * page" control. Small task stays inline; the control routes to the dedicated
 * page when the user wants the full workspace.
 */
export function InlineResult({ data }: InlineResultProps) {
  return (
    <SpotlightCard padLg>
      <div className="inline-result-head">
        <div>
          <span className="overline">
            <Icon name="spark" size="sm" /> Generated for you
          </span>
          <h3 className="body-lg" style={{ margin: '6px 0 0' }}>
            {data.title}
          </h3>
        </div>
        {data.confidence ? <ConfidenceBand level={data.confidence} /> : null}
      </div>

      <p className="body-sm muted">{data.body}</p>

      {data.items && data.items.length > 0 ? (
        <ul className="stack" style={{ margin: 'var(--space-4) 0 0', paddingLeft: '1.1rem' }}>
          {data.items.map((it, i) => (
            <li key={i} className="body-sm">
              {it}
            </li>
          ))}
        </ul>
      ) : null}

      <div className="divider" />

      <div className="rec-actions">
        {data.openHref ? (
          <Link
            href={data.openHref}
            className="btn btn-secondary btn-sm row"
            style={{ gap: 'var(--space-2)' }}
          >
            {data.openLabel ?? 'Open in its page'}
            <Icon name="arrow-up-right" size="sm" />
          </Link>
        ) : (
          <Tag tone="neutral">Ephemeral — lives in this thread</Tag>
        )}
      </div>
    </SpotlightCard>
  );
}
