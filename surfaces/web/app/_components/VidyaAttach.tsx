'use client';

/* ============================================================================
   app/_components/VidyaAttach.tsx — calm multimodal intake for the orb.

   Two quiet affordances beneath the composer: attach an image/document, and
   (where supported) share the screen. Both are read at the BOUNDARY into the
   bounded VidyaAttachment shape (base64, validated mime) and handed to the
   orchestrator on the next send. Nothing uploads on its own; the human attaches,
   then sends. It DEGRADES gracefully: with no file API or no getDisplayMedia,
   the affordance is simply absent — typing and voice still work.

   v4 brand: calm, no shadows, sharp corners, plain language, no emoji. The
   attached items show as small removable chips; the screen share takes a single
   still frame (a calm capture, not a live feed) so it is one bounded attachment.

   data-testids: vidya-attach, vidya-attach-file, vidya-attach-screen,
   vidya-attach-chip.
   ============================================================================ */

import { useRef, useState } from 'react';
import { Icon } from '@classess/design-system';
import {
  isValidAttachment,
  ATTACHMENT_MIME_PREFIXES,
  MAX_ATTACH_BYTES,
  type VidyaAttachment,
} from '@/lib/vidya';

/**
 * A practical raw-bytes ceiling on a picked file, before reading it. base64
 * inflates bytes by ~4/3, so we cap the raw file at 3/4 of the base64 budget so
 * the encoded payload still lands under MAX_ATTACH_BYTES. This stops a huge file
 * from being read fully into memory only to be rejected afterwards.
 */
export const MAX_FILE_BYTES = Math.floor((MAX_ATTACH_BYTES * 3) / 4);

/** Longest edge (px) a captured screen still is clamped to, to bound the PNG. */
const MAX_CAPTURE_EDGE = 1600;

/** Strip the `data:<mime>;base64,` prefix a FileReader/dataURL carries. */
export function stripDataUrlPrefix(dataUrl: string): string {
  const comma = dataUrl.indexOf(',');
  return comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
}

/** Classify a mime type into the attachment kind the orchestrator frames on. */
export function kindForMime(mime: string): VidyaAttachment['kind'] {
  return mime.startsWith('image/') ? 'image' : 'document';
}

/** Read a File into a bounded, validated VidyaAttachment (null if unusable). */
export async function fileToAttachment(file: File): Promise<VidyaAttachment | null> {
  const mime = file.type || 'application/octet-stream';
  if (!ATTACHMENT_MIME_PREFIXES.some((p) => mime.startsWith(p))) return null;
  // Guard the raw size BEFORE reading, so a huge file is never read fully into
  // memory only to be rejected by the base64 cap afterwards.
  if (typeof file.size === 'number' && file.size > MAX_FILE_BYTES) return null;
  const dataUrl = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ''));
    reader.onerror = () => reject(reader.error ?? new Error('read failed'));
    reader.readAsDataURL(file);
  });
  const attachment: VidyaAttachment = {
    kind: kindForMime(mime),
    mimeType: mime,
    dataBase64: stripDataUrlPrefix(dataUrl),
    name: file.name || undefined,
  };
  return isValidAttachment(attachment) ? attachment : null;
}

/** Whether screen share is available in this environment (degrade if not). */
export function screenShareSupported(): boolean {
  return (
    typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices &&
    typeof navigator.mediaDevices.getDisplayMedia === 'function'
  );
}

/** A small accept hint for the picker, derived from the accepted prefixes. */
const ACCEPT = 'image/*,application/pdf,text/plain';

function PaperclipGlyph() {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 9.5 12.5 18a4 4 0 0 1-5.7-5.7l8-8a2.5 2.5 0 0 1 3.5 3.5l-8 8a1 1 0 0 1-1.4-1.4l7.3-7.3" />
    </svg>
  );
}

function ScreenGlyph() {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="4" width="18" height="12" rx="1" />
      <path d="M8 20h8M12 16v4" />
    </svg>
  );
}

export interface VidyaAttachProps {
  /** The current staged attachments (lifted to the orb so send() can read them). */
  attachments: VidyaAttachment[];
  /** Replace the staged attachments. */
  onChange: (next: VidyaAttachment[]) => void;
  /** Bounded count — keep the turn small and the route happy. */
  max?: number;
}

/**
 * The calm intake row. Picks a file (image/doc) or captures one screen still,
 * reads it into the bounded attachment shape, and stages it as a removable chip.
 * Degrades by hiding any affordance the environment cannot support.
 */
export function VidyaAttach({ attachments, onChange, max = 4 }: VidyaAttachProps) {
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string>('');
  const canScreen = screenShareSupported();
  const full = attachments.length >= max;

  async function onFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setBusy(true);
    setNote('');
    const next = [...attachments];
    for (const file of Array.from(files)) {
      if (next.length >= max) break;
      // Distinguish "too large" from "unsupported" so the note is honest.
      if (typeof file.size === 'number' && file.size > MAX_FILE_BYTES) {
        setNote('That file is too large to attach. Try one under about 3 MB.');
        continue;
      }
      const att = await fileToAttachment(file).catch(() => null);
      if (att) next.push(att);
      else setNote('That file type is not supported. Try an image, a PDF, or text.');
    }
    setBusy(false);
    onChange(next);
  }

  // A single still frame of the shared screen — one bounded attachment, not a
  // live feed. We draw the first frame to a canvas, then stop the track at once.
  async function shareScreen() {
    if (!canScreen || full) return;
    setBusy(true);
    setNote('');
    let stream: MediaStream | null = null;
    try {
      stream = await navigator.mediaDevices.getDisplayMedia({ video: true });
      const track = stream.getVideoTracks()[0];
      const dataUrl = await captureStillFromStream(stream);
      track?.stop();
      const base64 = stripDataUrlPrefix(dataUrl);
      const att: VidyaAttachment = {
        kind: 'screen',
        mimeType: 'image/png',
        dataBase64: base64,
        name: 'screen.png',
      };
      if (isValidAttachment(att)) onChange([...attachments, att]);
      else setNote('That screen capture was too large to attach.');
    } catch {
      // Cancelled or unsupported — stay calm, no error theatre.
      setNote('Screen share was not started.');
    } finally {
      stream?.getTracks().forEach((t) => t.stop());
      setBusy(false);
    }
  }

  function remove(i: number) {
    onChange(attachments.filter((_, n) => n !== i));
  }

  return (
    <div className="vidya-attach" data-testid="vidya-attach">
      <div className="vidya-attach-controls">
        <input
          ref={fileRef}
          type="file"
          accept={ACCEPT}
          multiple
          hidden
          data-testid="vidya-attach-input"
          onChange={(e) => {
            void onFiles(e.target.files);
            e.target.value = ''; // allow re-picking the same file
          }}
        />
        <button
          type="button"
          className="vidya-attach-btn"
          data-testid="vidya-attach-file"
          aria-label="Attach an image or document"
          title="Attach an image or document"
          disabled={busy || full}
          onClick={() => fileRef.current?.click()}
        >
          <PaperclipGlyph />
        </button>
        {canScreen ? (
          <button
            type="button"
            className="vidya-attach-btn"
            data-testid="vidya-attach-screen"
            aria-label="Share a screen capture"
            title="Share a screen capture"
            disabled={busy || full}
            onClick={() => void shareScreen()}
          >
            <ScreenGlyph />
          </button>
        ) : null}
      </div>

      {attachments.length > 0 ? (
        <ul className="vidya-attach-chips" aria-label="Attached">
          {attachments.map((a, i) => (
            <li key={i} className="vidya-attach-chip" data-testid="vidya-attach-chip">
              <span className="body-sm">
                {a.kind === 'image' ? 'Image' : a.kind === 'screen' ? 'Screen' : 'Document'}
                {a.name ? ` — ${a.name}` : ''}
              </span>
              <button
                type="button"
                className="vidya-attach-remove"
                aria-label="Remove attachment"
                onClick={() => remove(i)}
              >
                <Icon name="close" size="sm" />
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      {note ? (
        <p className="body-sm muted" role="status" style={{ margin: 0 }}>
          {note}
        </p>
      ) : null}
    </div>
  );
}

/** Draw the first available frame of a display stream to a PNG data URL. */
async function captureStillFromStream(stream: MediaStream): Promise<string> {
  const video = document.createElement('video');
  video.srcObject = stream;
  video.muted = true;
  await video.play().catch(() => undefined);
  // Wait one frame so dimensions are known.
  await new Promise<void>((resolve) => {
    if (video.videoWidth > 0) return resolve();
    video.onloadedmetadata = () => resolve();
    // Safety: resolve after a short tick even if metadata never fires.
    window.setTimeout(() => resolve(), 300);
  });
  const srcW = video.videoWidth || 1280;
  const srcH = video.videoHeight || 720;
  // Clamp the longest edge so a 4K capture does not produce a multi-MB PNG that
  // would balloon the request body. We scale down proportionally; never up.
  const scale = Math.min(1, MAX_CAPTURE_EDGE / Math.max(srcW, srcH));
  const w = Math.max(1, Math.round(srcW * scale));
  const h = Math.max(1, Math.round(srcH * scale));
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  ctx?.drawImage(video, 0, 0, w, h);
  return canvas.toDataURL('image/png');
}
