import { describe, it, expect } from 'vitest';
import {
  stripDataUrlPrefix,
  kindForMime,
  fileToAttachment,
} from '@/app/_components/VidyaAttach';
import { isValidAttachment, MAX_ATTACH_BYTES } from '../vidya';

/* ============================================================================
   Multimodal intake helpers — the BOUNDARY that reads a picked file into the
   bounded VidyaAttachment shape (base64 with no data: prefix, validated mime),
   classifies the kind, and rejects an unsupported type. The orchestrator only
   ever sees a sanitised attachment.
   ============================================================================ */

describe('stripDataUrlPrefix', () => {
  it('removes the data: prefix and keeps just the base64 payload', () => {
    expect(stripDataUrlPrefix('data:image/png;base64,AAAB')).toBe('AAAB');
    // Already-bare base64 is returned untouched.
    expect(stripDataUrlPrefix('AAAB')).toBe('AAAB');
  });
});

describe('kindForMime', () => {
  it('classifies images vs documents', () => {
    expect(kindForMime('image/png')).toBe('image');
    expect(kindForMime('image/jpeg')).toBe('image');
    expect(kindForMime('application/pdf')).toBe('document');
    expect(kindForMime('text/plain')).toBe('document');
  });
});

describe('fileToAttachment', () => {
  it('reads a supported image into a valid, prefix-free attachment', async () => {
    const file = new File(['hello'], 'photo.png', { type: 'image/png' });
    const att = await fileToAttachment(file);
    expect(att).not.toBeNull();
    expect(att?.kind).toBe('image');
    expect(att?.mimeType).toBe('image/png');
    expect(att?.name).toBe('photo.png');
    // No data: prefix leaked through.
    expect(att?.dataBase64.startsWith('data:')).toBe(false);
    expect(att?.dataBase64.length).toBeGreaterThan(0);
    expect(isValidAttachment(att)).toBe(true);
  });

  it('reads a PDF as a document attachment', async () => {
    const file = new File(['%PDF-1.4'], 'report.pdf', { type: 'application/pdf' });
    const att = await fileToAttachment(file);
    expect(att?.kind).toBe('document');
    expect(isValidAttachment(att)).toBe(true);
  });

  it('rejects an unsupported file type (degrades gracefully -> null)', async () => {
    const file = new File(['MZ'], 'app.exe', { type: 'application/x-msdownload' });
    const att = await fileToAttachment(file);
    expect(att).toBeNull();
  });
});

describe('isValidAttachment — bounds the inline payload', () => {
  const ok = {
    kind: 'image' as const,
    mimeType: 'image/png',
    dataBase64: 'AAAB',
  };

  it('accepts a small, well-formed attachment', () => {
    expect(isValidAttachment(ok)).toBe(true);
  });

  it('rejects an oversized base64 payload (would balloon the request body)', () => {
    const huge = { ...ok, dataBase64: 'A'.repeat(MAX_ATTACH_BYTES + 1) };
    expect(isValidAttachment(huge)).toBe(false);
    // Exactly at the cap is still allowed.
    const atCap = { ...ok, dataBase64: 'A'.repeat(MAX_ATTACH_BYTES) };
    expect(isValidAttachment(atCap)).toBe(true);
  });
});
