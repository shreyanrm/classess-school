'use client';

import { useRef, useState } from 'react';
import { Button, Icon, Input, Matrix, SpotlightCard, Tag } from '@classess/design-system';
import { StatCell } from './StatCell';
import { EvidenceDrawer } from './EvidenceDrawer';
import { SourceNote } from './SourceNote';
import type { ReadSource } from '@/lib/vizData';
import type { AdminConfigValue } from '@/lib/adminConfig';

/* ============================================================================
   KnowledgeBase — institutional document upload for AI reference, in v3.

   The v2 "Documents & Knowledge Base" screen, recomposed. The school adds its
   own reference documents (a handbook, a syllabus, a marking policy as PDF /
   DOC / TXT) so Vidya can ground its answers in the institution's own material
   instead of generic text. Two laws govern it:

     · GOVERNANCE GATE — the documents are used as AI reference ONLY when the
       admin turns the gate on. Until then they are stored as references but the
       intelligence never reads them. The gate persists through the wall.
     · PERMISSION LADDER — a freshly added document is PREPARED, not live. It
       waits at the gate until the admin makes it available to the assistant.
       Nothing an agent can read is enabled automatically.

   PII-FREE: only a document's TITLE, FORMAT, and SIZE are kept here — never the
   file's contents, never anything personal. A real ingest would extract text on
   the server behind the wall; this surface manages the reference list and the
   gate. Ultramarine signature, hairline + tonal depth, NO shadow, reduced-motion
   safe. The host owns the gate persistence; the doc list is local + PII-free.
   ============================================================================ */

type DocFormat = 'pdf' | 'doc' | 'txt';

const FORMAT_LABEL: Record<DocFormat, string> = { pdf: 'PDF', doc: 'DOC', txt: 'TXT' };

function formatFor(name: string): DocFormat {
  const ext = name.toLowerCase().split('.').pop() ?? '';
  if (ext === 'pdf') return 'pdf';
  if (ext === 'txt' || ext === 'md') return 'txt';
  return 'doc';
}

function prettySize(bytes: number): string {
  if (!bytes) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface KbDoc {
  id: string;
  /** A generic, institution-owned title — never a person. */
  title: string;
  format: DocFormat;
  size: string;
  /** Prepared (added, not yet readable) vs available (admin made it AI-readable). */
  available: boolean;
}

const SEED_DOCS: KbDoc[] = [
  { id: 'kb-1', title: 'Academic handbook 2025–26', format: 'pdf', size: '1.2 MB', available: true },
  { id: 'kb-2', title: 'Assessment & marking policy', format: 'doc', size: '340 KB', available: true },
  { id: 'kb-3', title: 'Lab safety guidelines', format: 'txt', size: '18 KB', available: false },
];

export interface KnowledgeBaseProps {
  /** The persisted config (merged over the seed) from the admin-config seam. */
  config: Record<string, AdminConfigValue>;
  source?: ReadSource;
  /** Persist one config set through the wall — host owns the round-trip. */
  onSet: (key: string, value: AdminConfigValue) => Promise<{ persisted: boolean }>;
}

export function KnowledgeBase({ config, source = 'fallback', onSet }: KnowledgeBaseProps) {
  // The governance gate is the one persisted scalar — whether the intelligence
  // may read these references at all. The list itself is PII-free + local.
  const gateOn = config.kbConsent === true;
  const [docs, setDocs] = useState<KbDoc[]>(SEED_DOCS);

  const [adding, setAdding] = useState(false);
  const [title, setTitle] = useState('');
  const [pickedFormat, setPickedFormat] = useState<DocFormat>('pdf');
  const [pickedSize, setPickedSize] = useState<string>('—');
  const fileRef = useRef<HTMLInputElement | null>(null);

  const available = docs.filter((d) => d.available).length;
  const prepared = docs.length - available;

  function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    // PII-free: we read only the file's NAME, FORMAT, and SIZE — never its bytes.
    if (!title.trim()) setTitle(file.name.replace(/\.[^.]+$/, ''));
    setPickedFormat(formatFor(file.name));
    setPickedSize(prettySize(file.size));
    e.target.value = '';
  }

  function addDoc() {
    const t = title.trim();
    if (!t) return;
    const doc: KbDoc = {
      id: `kb-${Date.now()}`,
      title: t,
      format: pickedFormat,
      size: pickedSize,
      available: false, // prepared, not live — waits at the gate
    };
    setDocs((d) => [doc, ...d]);
    void onSet('kbCount', docs.length + 1);
    setAdding(false);
    setTitle('');
    setPickedSize('—');
    setPickedFormat('pdf');
  }

  function toggleAvailable(id: string) {
    setDocs((d) => d.map((doc) => (doc.id === id ? { ...doc, available: !doc.available } : doc)));
  }

  function removeDoc(id: string) {
    setDocs((d) => {
      const next = d.filter((doc) => doc.id !== id);
      void onSet('kbCount', next.length);
      return next;
    });
  }

  return (
    <div className="stack" style={{ gap: 'var(--space-5)' }}>
      <Matrix columns={4}>
        <StatCell label="Reference documents" value={docs.length} delta="institution-owned" tone="flat" />
        <StatCell label="Available to Vidya" value={available} delta="readable as reference" tone={available > 0 ? 'up' : 'flat'} />
        <StatCell label="Prepared" value={prepared} delta="held at the gate" tone={prepared > 0 ? 'down' : 'flat'} />
        <StatCell
          label="Reference gate"
          value={gateOn ? 1 : 0}
          unit={gateOn ? ' on' : ' off'}
          delta={gateOn ? 'Vidya may ground in them' : 'never read until you turn it on'}
          tone={gateOn ? 'up' : 'flat'}
        />
      </Matrix>

      {/* The governance gate — the documents are read by the intelligence ONLY
          when the admin turns this on. Persisted through the wall. */}
      <SpotlightCard padLg>
        <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-4)' }}>
          <div>
            <h3 className="body-lg" style={{ margin: 0 }}>
              Use these documents as AI reference
            </h3>
            <p className="body-sm muted" style={{ marginTop: 'var(--space-2)', maxWidth: 560 }}>
              When this is on, Vidya may ground its answers in the documents you have made available —
              your handbook, your policies, your syllabus — instead of generic text. When it is off,
              the references are stored but never read. You hold this gate.
            </p>
          </div>
          <Button
            variant={gateOn ? 'primary' : 'secondary'}
            size="sm"
            aria-pressed={gateOn}
            onClick={() => onSet('kbConsent', !gateOn)}
          >
            {gateOn ? 'Reference on' : 'Reference off'}
          </Button>
        </div>

        <EvidenceDrawer
          claim="How the knowledge base is used"
          evidence={[
            'Only a document’s title, format, and size are kept on this surface — never the file’s contents, and nothing personal.',
            'A newly added document is prepared, not live. It is read by the assistant only after you make it available and the reference gate is on.',
            'When the gate is off, the references are stored but the intelligence never reads them.',
          ]}
          whySeeing="Grounding the assistant in the school’s own documents is powerful, so it is governed: explicit, PII-free, and off until you turn it on."
        />
      </SpotlightCard>

      {/* Add a document — generic title + format; the file's bytes are never read. */}
      <section>
        <div className="sec-head">
          <h3 className="h3" style={{ margin: 0 }}>Reference documents</h3>
          <span className="overline">PDF · DOC · TXT</span>
        </div>
        <p className="caption quiet" style={{ marginTop: 'calc(var(--space-4) * -1)', marginBottom: 'var(--space-4)' }}>
          Add your institution’s own documents for the assistant to reference. A new document is
          prepared and waits at the gate — you make it available when you are ready. Only the title,
          format, and size are kept; the file’s contents are never stored on this surface.
        </p>

        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.doc,.docx,.txt,.md"
          onChange={onPickFile}
          style={{ display: 'none' }}
          aria-hidden="true"
          tabIndex={-1}
          data-testid="kb-file-input"
        />

        {adding ? (
          <SpotlightCard>
            <div className="stack" style={{ gap: 'var(--space-3)' }}>
              <Input
                label="Document title"
                hint="A generic, institution-owned title — never a person’s name."
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Academic handbook 2025–26"
              />
              <div className="row" style={{ gap: 'var(--space-3)', alignItems: 'flex-end', flexWrap: 'wrap' }}>
                <div>
                  <p className="overline" style={{ margin: '0 0 var(--space-2)' }}>Format</p>
                  <div className="segmented" role="group" aria-label="Document format">
                    {(['pdf', 'doc', 'txt'] as DocFormat[]).map((f) => (
                      <button
                        key={f}
                        type="button"
                        className={pickedFormat === f ? 'active' : ''}
                        aria-pressed={pickedFormat === f}
                        onClick={() => setPickedFormat(f)}
                      >
                        {FORMAT_LABEL[f]}
                      </button>
                    ))}
                  </div>
                </div>
                <Button variant="secondary" size="sm" onClick={() => fileRef.current?.click()} data-testid="kb-pick-file">
                  <Icon name="upload" size="sm" />
                  Choose a file
                </Button>
                {pickedSize !== '—' ? <Tag tone="neutral">{pickedSize}</Tag> : null}
              </div>
              <p className="caption quiet" style={{ margin: 0 }}>
                Choosing a file reads only its name, format, and size — never its contents.
              </p>
              <div className="rec-actions">
                <Button variant="accent" size="sm" disabled={!title.trim()} onClick={addDoc} data-testid="kb-add-confirm">
                  Add as a reference
                </Button>
                <Button variant="ghost" size="sm" onClick={() => { setAdding(false); setTitle(''); setPickedSize('—'); }}>
                  Cancel
                </Button>
              </div>
            </div>
          </SpotlightCard>
        ) : (
          <div className="rec-actions" style={{ marginBottom: 'var(--space-4)' }}>
            <Button variant="secondary" size="sm" onClick={() => setAdding(true)} data-testid="kb-add-open">
              <Icon name="plus" size="sm" />
              Add a document
            </Button>
          </div>
        )}

        {docs.length === 0 ? (
          <SpotlightCard>
            <div className="empty">
              <Icon name="file" size="lg" className="glyph" />
              <h4 className="body">No reference documents yet</h4>
              <p>Add your handbook, policies, or syllabus so Vidya can ground its answers in your own material.</p>
            </div>
          </SpotlightCard>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Format</th>
                  <th>Size</th>
                  <th>Reference state</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {docs.map((d) => (
                  <tr key={d.id}>
                    <td style={{ fontWeight: 'var(--fw-medium)' as React.CSSProperties['fontWeight'] }}>
                      <span className="row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
                        <Icon name="file" size="sm" />
                        {d.title}
                      </span>
                    </td>
                    <td className="muted">{FORMAT_LABEL[d.format]}</td>
                    <td className="muted">{d.size}</td>
                    <td>
                      {d.available ? (
                        <Tag tone={gateOn ? 'success' : 'neutral'} dot>
                          {gateOn ? 'Available to Vidya' : 'Available — gate off'}
                        </Tag>
                      ) : (
                        <Tag tone="info" dot>Prepared — held at the gate</Tag>
                      )}
                    </td>
                    <td>
                      <div className="row" style={{ gap: 'var(--space-2)', justifyContent: 'flex-end' }}>
                        <Button variant="ghost" size="sm" onClick={() => toggleAvailable(d.id)}>
                          {d.available ? 'Hold back' : 'Make available'}
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => removeDoc(d.id)} aria-label={`Remove ${d.title}`}>
                          <Icon name="trash" size="sm" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className="row" style={{ gap: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap' }}>
        <span className="caption quiet row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
          <Icon name="info" size="sm" /> Titles, formats, and sizes only — never the file’s contents, never anything personal.
        </span>
      </div>

      <SourceNote source={source} />
    </div>
  );
}
