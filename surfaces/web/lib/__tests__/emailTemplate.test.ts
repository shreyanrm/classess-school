/* ============================================================================
   lib/__tests__/emailTemplate.test.ts — the branded email builder.

   Every kind renders valid, branded, email-safe HTML (table layout, the v4
   tokens inline, the 3px ultramarine rule, the wordmark, a dark ink button), and
   caller-supplied input is HTML-escaped so a name or message can never inject
   markup. Plain language: no emoji, no exclamation marks.
   ============================================================================ */

import { describe, it, expect } from 'vitest';
import {
  buildEmail,
  escapeHtml,
  EMAIL_KINDS,
  type EmailInput,
} from '../emailTemplate';

/** A representative, valid input for each kind. */
const SAMPLES: EmailInput[] = [
  {
    kind: 'weekly-briefing',
    data: {
      parentName: 'A Parent',
      childLabel: 'Child A',
      highlights: [{ title: 'Going well.', detail: 'Linear equations on their own.' }],
      reportUrl: 'https://classess.test/parent/reports',
    },
  },
  {
    kind: 'attendance-risk',
    data: {
      childLabel: 'Child B',
      summary: 'A few mornings were missed this fortnight.',
      nextStep: 'A short check-in about mornings would help.',
      detailUrl: 'https://classess.test/parent/child',
    },
  },
  {
    kind: 'new-message',
    data: {
      fromLabel: 'Section 10-B teacher',
      preview: 'A quick note about this week.',
      threadUrl: 'https://classess.test/messages',
    },
  },
  {
    kind: 'credential-issued',
    data: {
      credentialTitle: 'Algebra, independent',
      claim: 'Can solve linear equations without help.',
      viewUrl: 'https://classess.test/portfolio',
    },
  },
  {
    kind: 'roster-invite',
    data: {
      schoolName: 'Campus North',
      roleLabel: 'teacher',
      inviteUrl: 'https://classess.test/sign-up',
    },
  },
];

describe('escapeHtml', () => {
  it('escapes the five HTML-significant characters', () => {
    expect(escapeHtml(`<script>"&'`)).toBe('&lt;script&gt;&quot;&amp;&#39;');
  });
});

describe('buildEmail — branded, valid HTML for each kind', () => {
  it('covers every declared kind', () => {
    expect(SAMPLES.map((s) => s.kind).sort()).toEqual([...EMAIL_KINDS].sort());
  });

  for (const sample of SAMPLES) {
    it(`renders branded, email-safe HTML for "${sample.kind}"`, () => {
      const built = buildEmail(sample);
      expect(built).not.toBeNull();
      const html = built!.html;

      // A real, plain-language subject.
      expect(built!.subject.length).toBeGreaterThan(0);

      // Email-safe frame: a document with a table layout and inline styles.
      expect(html).toContain('<!DOCTYPE html>');
      expect(html).toContain('role="presentation"');
      expect(html).toContain('style=');

      // The v4 brand, inline (tokens rendered as their literal hex for email):
      expect(html).toContain('#1F35FF'); // the 3px ultramarine top rule
      expect(html).toContain('#16181D'); // ink heading + button fill
      expect(html).toContain('#5B6470'); // muted body
      expect(html).toContain('#F4F5F7'); // steel page background
      expect(html).toContain('width="560"'); // the centred 560px card
      expect(html).toContain('Classess'); // the wordmark (alt text)

      // The header carries the BRAND LOGO image (matching the auth emails), not a
      // text wordmark — the absolute URL + the "Classess School" alt must be present.
      expect(html).toContain('https://3.classess.com/brand/classess-logo-black.png');
      expect(html).toContain('alt="Classess School"');

      // A dark ink button that opens a real URL.
      expect(html).toContain('<a href=');

      // Sharp corners + no shadow: never a border-radius or a box-shadow.
      expect(html).not.toContain('border-radius');
      expect(html).not.toContain('box-shadow');

      // Plain language: no emoji, no exclamation marks in the rendered COPY.
      // Strip tags first so the legitimate <!DOCTYPE ...> never trips the check.
      const copy = html.replace(/<[^>]*>/g, ' ');
      expect(copy).not.toContain('!');
      // A coarse emoji guard (no characters above the BMP astral plane).
      expect(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}]/u.test(copy)).toBe(false);
    });
  }
});

describe('buildEmail — escapes untrusted input', () => {
  it('escapes a malicious child label so markup cannot be injected', () => {
    const built = buildEmail({
      kind: 'weekly-briefing',
      data: {
        childLabel: '<img src=x onerror=alert(1)>',
        highlights: [{ title: 'Hi', detail: 'Note' }],
        reportUrl: 'https://classess.test/parent/reports',
      },
    });
    const html = built!.html;
    expect(html).not.toContain('<img src=x');
    expect(html).toContain('&lt;img src=x onerror=alert(1)&gt;');
  });

  it('escapes a message preview body', () => {
    const built = buildEmail({
      kind: 'new-message',
      data: {
        fromLabel: 'Teacher',
        preview: '<b>bold</b> & "quotes"',
        threadUrl: 'https://classess.test/messages',
      },
    });
    const html = built!.html;
    expect(html).not.toContain('<b>bold</b>');
    expect(html).toContain('&lt;b&gt;bold&lt;/b&gt;');
  });

  it('returns null for an unknown kind', () => {
    // Cast through unknown — the route relies on this null to answer a clean 400.
    expect(buildEmail({ kind: 'nope', data: {} } as unknown as EmailInput)).toBeNull();
  });
});
