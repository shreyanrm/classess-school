/* ============================================================================
   lib/emailTemplate.ts — the branded, email-safe HTML builder.

   One reusable, table-layout, inline-style-only builder that renders every
   Classess transactional email in the SAME v4 frame as our auth emails:

     - a light steel background (#F4F5F7)
     - a 560px centred white card with sharp corners (no rounding, no shadow)
     - a 3px ultramarine (#1F35FF) top rule
     - the Classess logo (the black wordmark image, matching the auth emails)
     - an ink (#16181D) heading, muted (#5B6470) body
     - a dark ink button (sharp corners)
     - a hairline footer
     - a system font stack

   It is PURE and node-testable: no network, no secret, no DOM. The server route
   (app/api/email/route.ts) chooses a typed builder by "kind" and posts the
   rendered HTML to Resend. Every caller-supplied value is HTML-escaped, so a
   name or message body can never inject markup. Plain language throughout — no
   emoji, no exclamation marks.
   ============================================================================ */

/* ----------------------------------------------------------------------------
   Brand tokens — mirrored as literal hex here because email clients cannot read
   CSS custom properties; these are the inline values of our v4 tokens.
   ---------------------------------------------------------------------------- */

const BRAND = {
  bg: '#F4F5F7', // steel page background
  card: '#FFFFFF', // white card
  accent: '#1F35FF', // restrained ultramarine — the one accent
  ink: '#16181D', // heading + button fill
  muted: '#5B6470', // body copy
  hairline: '#E2E5EA', // hairline rules + footer divider
  buttonText: '#FFFFFF',
} as const;

const FONT =
  "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";

/* ----------------------------------------------------------------------------
   HTML escaping — every interpolated, caller-supplied value passes through this
   so untrusted input (a name, a message, a school label) cannot inject markup.
   ---------------------------------------------------------------------------- */

/** Escape the five HTML-significant characters. Safe for text and attributes. */
export function escapeHtml(value: string): string {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/* ----------------------------------------------------------------------------
   The frame — the shared branded shell every email renders into.
   ---------------------------------------------------------------------------- */

/** A single call-to-action: visible label + the URL it opens. */
export interface EmailAction {
  label: string;
  url: string;
}

/** The pieces a builder hands the frame. All text is escaped by the builder. */
export interface EmailContent {
  /** A short preheader (the preview line); kept out of the visible card. */
  preheader: string;
  /** The ink heading. */
  heading: string;
  /** One or more muted body paragraphs, in order. */
  paragraphs: string[];
  /** An optional dark ink button. */
  action?: EmailAction;
  /** An optional small note under the body (e.g. a "why you are seeing this"). */
  footnote?: string;
}

/** What a built email carries: a plain-language subject + the full HTML body. */
export interface BuiltEmail {
  subject: string;
  html: string;
}

/** Render the shared branded shell. Caller-supplied text MUST be pre-escaped. */
function renderFrame(content: EmailContent): string {
  const paragraphs = content.paragraphs
    .map(
      (p) =>
        `<p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:${BRAND.muted};">${p}</p>`,
    )
    .join('');

  const button = content.action
    ? `<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:8px 0 4px;">
         <tr><td style="background-color:${BRAND.ink};">
           <a href="${content.action.url}" target="_blank" rel="noopener noreferrer"
              style="display:inline-block;padding:12px 22px;font-family:${FONT};font-size:14px;font-weight:600;color:${BRAND.buttonText};text-decoration:none;">${content.action.label}</a>
         </td></tr>
       </table>`
    : '';

  const footnote = content.footnote
    ? `<p style="margin:20px 0 0;font-size:13px;line-height:1.5;color:${BRAND.muted};">${content.footnote}</p>`
    : '';

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="color-scheme" content="light only" />
</head>
<body style="margin:0;padding:0;background-color:${BRAND.bg};font-family:${FONT};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">${content.preheader}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:${BRAND.bg};">
  <tr>
    <td align="center" style="padding:32px 16px;">
      <table role="presentation" width="560" cellpadding="0" cellspacing="0" border="0" style="width:560px;max-width:100%;background-color:${BRAND.card};">
        <tr><td style="height:3px;line-height:3px;font-size:3px;background-color:${BRAND.accent};">&nbsp;</td></tr>
        <tr>
          <td style="padding:32px 36px 0;">
            <img src="https://3.classess.com/brand/classess-logo-black.png" alt="Classess School" width="120" height="48" style="display:block;border:0;width:120px;height:48px" />
          </td>
        </tr>
        <tr>
          <td style="padding:24px 36px 36px;">
            <h1 style="margin:0 0 16px;font-size:22px;line-height:1.3;font-weight:600;color:${BRAND.ink};">${content.heading}</h1>
            ${paragraphs}
            ${button}
            ${footnote}
          </td>
        </tr>
        <tr><td style="border-top:1px solid ${BRAND.hairline};padding:20px 36px 28px;">
          <p style="margin:0;font-size:12px;line-height:1.5;color:${BRAND.muted};">Classess School. You receive this because your school keeps you in the loop. This is sent in plain language, with consent and quiet hours respected.</p>
        </td></tr>
      </table>
    </td>
  </tr>
</table>
</body>
</html>`;
}

/* ----------------------------------------------------------------------------
   Typed builders — one per kind. Each escapes its inputs and hands the frame a
   plain-language, calm message. The discriminated union "kind" is what the
   server route validates against.
   ---------------------------------------------------------------------------- */

/** The discriminator the route + builders share. */
export type EmailKind =
  | 'weekly-briefing'
  | 'attendance-risk'
  | 'new-message'
  | 'credential-issued'
  | 'roster-invite';

/** A small briefing item, in the parent's language. */
export interface BriefingLine {
  title: string;
  detail: string;
}

export interface WeeklyBriefingData {
  /** The parent's display name or a generic greeting fallback. */
  parentName?: string;
  /** A generic child label — never a real name in the demo. */
  childLabel: string;
  /** Two or three plain-language lines for the week. */
  highlights: BriefingLine[];
  /** Where "Open the full report" goes. */
  reportUrl: string;
}

export interface AttendanceRiskData {
  parentName?: string;
  childLabel: string;
  /** Plain-language description of what was noticed — never a raw count alone. */
  summary: string;
  /** The one supportive next step. */
  nextStep: string;
  detailUrl: string;
}

export interface NewMessageData {
  recipientName?: string;
  /** Who it is from — a role or generic label, never raw PII in the demo. */
  fromLabel: string;
  /** A short preview of the message body (escaped, bounded by the caller). */
  preview: string;
  threadUrl: string;
}

export interface CredentialIssuedData {
  learnerName?: string;
  /** The credential title. */
  credentialTitle: string;
  /** What it attests, in plain language. */
  claim: string;
  viewUrl: string;
}

export interface RosterInviteData {
  /** Who is being invited — a generic label or email head. */
  inviteeLabel?: string;
  /** The school / campus name. */
  schoolName: string;
  /** The role they are invited as, e.g. "teacher". */
  roleLabel: string;
  /** The accept-invite link. */
  inviteUrl: string;
}

/** The full input union the route accepts: a kind plus its matching data. */
export type EmailInput =
  | { kind: 'weekly-briefing'; data: WeeklyBriefingData }
  | { kind: 'attendance-risk'; data: AttendanceRiskData }
  | { kind: 'new-message'; data: NewMessageData }
  | { kind: 'credential-issued'; data: CredentialIssuedData }
  | { kind: 'roster-invite'; data: RosterInviteData };

/** A calm greeting line — escaped name, or a generic fallback. */
function greeting(name: string | undefined): string {
  const trimmed = (name ?? '').trim();
  return trimmed ? `Hello ${escapeHtml(trimmed)},` : 'Hello,';
}

export function buildWeeklyBriefing(data: WeeklyBriefingData): BuiltEmail {
  const child = escapeHtml(data.childLabel);
  const lines = data.highlights
    .map(
      (h) =>
        `<strong style="color:${BRAND.ink};font-weight:600;">${escapeHtml(h.title)}</strong> ${escapeHtml(h.detail)}`,
    );
  const html = renderFrame({
    preheader: `This week with ${child}`,
    heading: `This week with ${child}`,
    paragraphs: [
      greeting(data.parentName),
      `Here is a calm summary of how ${child} is getting on. No raw marks — just what is going well and where a little home time helps most.`,
      ...lines,
    ],
    action: { label: 'Open the full report', url: data.reportUrl },
    footnote:
      'You see only what the school has chosen to share. You can change how often these arrive in your settings.',
  });
  return { subject: `This week with ${data.childLabel}`, html };
}

export function buildAttendanceRisk(data: AttendanceRiskData): BuiltEmail {
  const child = escapeHtml(data.childLabel);
  const html = renderFrame({
    preheader: `A gentle heads-up about ${child}`,
    heading: `A gentle heads-up about ${child}`,
    paragraphs: [
      greeting(data.parentName),
      escapeHtml(data.summary),
      `A small step that helps: ${escapeHtml(data.nextStep)}`,
    ],
    action: { label: 'See the details', url: data.detailUrl },
    footnote:
      'This is a supportive nudge, not a mark against anyone. If something at home is making attendance hard, your school is here to help.',
  });
  return { subject: `A gentle heads-up about ${data.childLabel}`, html };
}

export function buildNewMessage(data: NewMessageData): BuiltEmail {
  const from = escapeHtml(data.fromLabel);
  const html = renderFrame({
    preheader: `New message from ${from}`,
    heading: `New message from ${from}`,
    paragraphs: [
      greeting(data.recipientName),
      `You have a new message: ${escapeHtml(data.preview)}`,
      'Open the thread to read it in full and reply.',
    ],
    action: { label: 'Open the message', url: data.threadUrl },
    footnote:
      'Messages on Classess are kept in a monitored, safe channel. There is no unmonitored back-channel.',
  });
  return { subject: `New message from ${data.fromLabel}`, html };
}

export function buildCredentialIssued(data: CredentialIssuedData): BuiltEmail {
  const title = escapeHtml(data.credentialTitle);
  const html = renderFrame({
    preheader: `A credential was issued: ${title}`,
    heading: `Your credential is ready: ${title}`,
    paragraphs: [
      greeting(data.learnerName),
      `A new credential has been issued to you: ${escapeHtml(data.claim)}`,
      'It is signed and tamper-evident, so anyone you share it with can verify it independently.',
    ],
    action: { label: 'View the credential', url: data.viewUrl },
    footnote:
      'A credential is only verifiable once it is signed. This one is — a signature is never faked.',
  });
  return { subject: `Your credential is ready: ${data.credentialTitle}`, html };
}

export function buildRosterInvite(data: RosterInviteData): BuiltEmail {
  const school = escapeHtml(data.schoolName);
  const role = escapeHtml(data.roleLabel);
  const html = renderFrame({
    preheader: `You are invited to join ${school} on Classess`,
    heading: `You are invited to join ${school}`,
    paragraphs: [
      greeting(data.inviteeLabel),
      `${school} has invited you to join Classess as a ${role}.`,
      'Accepting sets up your account and lands you on your own surface. You can change your details any time.',
    ],
    action: { label: 'Accept the invite', url: data.inviteUrl },
    footnote:
      'If you were not expecting this invite, you can safely ignore this email — nothing happens until you accept.',
  });
  return { subject: `You are invited to join ${data.schoolName} on Classess`, html };
}

/* ----------------------------------------------------------------------------
   The dispatcher — choose a builder by "kind". Returns null on an unknown kind
   so the route can answer a clean 400 rather than throw.
   ---------------------------------------------------------------------------- */

export function buildEmail(input: EmailInput): BuiltEmail | null {
  switch (input.kind) {
    case 'weekly-briefing':
      return buildWeeklyBriefing(input.data);
    case 'attendance-risk':
      return buildAttendanceRisk(input.data);
    case 'new-message':
      return buildNewMessage(input.data);
    case 'credential-issued':
      return buildCredentialIssued(input.data);
    case 'roster-invite':
      return buildRosterInvite(input.data);
    default:
      return null;
  }
}

/** The set of valid kinds, for input validation in the route. */
export const EMAIL_KINDS: readonly EmailKind[] = [
  'weekly-briefing',
  'attendance-risk',
  'new-message',
  'credential-issued',
  'roster-invite',
];
