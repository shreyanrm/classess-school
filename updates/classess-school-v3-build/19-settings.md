# 19 · Settings

A proper, structured settings area — not the single page v2 had. One shell, role-scoped
sections, reached from the rail foot (or Cmd-K → "settings"). Left sub-nav (sections),
right detail panel. v4.1, European-spacey, hairline dividers, no shadows. Every change is
explicit (no silent auto-apply on consequential settings) and audited where it touches
access or data.

## 19.1 Sections (all roles unless noted)

1. **Account & identity.** Name, photo, contact, linked sign-in methods (phone-OTP-first,
   Google/Apple/Microsoft, institutional SSO). Identity is the canonical KGtoPG identity —
   changes route through the identity service (`03`); no app-local account. Sign-out of
   this device / all devices.
2. **Profile & roles.** The roles this person holds (e.g. teacher + parent) and the active-
   role switcher; institution/class context. Read-mostly; role grants are managed by Admin.
3. **Notifications.** Per-channel (in-app, push, email, SMS/WhatsApp where enabled) and
   per-type (homework, results, attendance, meetings, proactive nudges) toggles; **quiet
   hours**. Calm by default — nothing screams.
4. **Language & region.** Interface language, content language, code-switching preference,
   region/calendar. Drives hyperlocalization (`08`) and translation (`13` b9). Subject
   terminology is always preserved.
5. **Appearance.** Theme (System / Light / Dark — flips `data-theme`, only the semantic
   layer changes), text size, reduced-motion (respects OS, overridable). Density stays
   European-spacey; no "compact mode" that violates the restraint principles.
6. **Voice & Vidya.** Voice on/off, push-to-talk key, the universal shortcut binding
   (Cmd-K default, rebindable), Vidya tone/verbosity, per-user memory controls (view, pause,
   clear — memory is PII-free and consent-gated, `11`), the assistance-ladder default
   (student).
7. **Privacy & consent.** The consent ledger — every consent (AI use, camera, mic,
   recording, data sharing) shown, scoped, **revocable**. Data **export**, **correction**,
   and **deletion / right-to-erasure** (deletion severs the PII link; aggregate behaviour is
   unlinkable, `12`). Source-lineage view ("what is this insight built from"). Age-tier
   status (DPDP — an open gating item, `02`).
8. **Devices & sessions.** Active sessions/devices, last access, revoke a device.
9. **Accessibility.** Reduced-motion, contrast, larger targets, screen-reader hints,
   captions for recorded sessions.
10. **Keyboard shortcuts.** The full cheatsheet (`17.4`), rebindable where safe.

### Role-specific

- **Teacher:** Teaching preferences (instructional model, project mentoring, consultation
  availability), grading defaults (rubric defaults, voice-entry), leave management.
- **Parent:** My children (link/switch/manage), the child-trigger setting for the shareable
  win, fee/payment contact (→ Feesable citizen).
- **Admin:** these personal settings **plus** the institution governance surfaces, which
  live under their own area (`08`: Policies, Roles & access, Consent & permissions,
  Hyperlocalization, AI control centre, Data governance, Integrations). Institution settings
  are governance, not personal preference, and carry audit + break-glass.

## 19.2 Behaviour rules

- Consequential settings (access, consent, data, account) confirm explicitly and write an
  audit event; never auto-apply silently.
- Consent is always visible and revocable; revoking recomputes affected insights (`12`).
- Deletion is honoured cleanly and lossless-for-aggregate (`12`); the user is told exactly
  what leaves and what (de-identified) remains.
- Secrets/keys never appear in any settings UI; integration credentials are placed in
  Infisical by an operator, surfaced here only as a connected/health status (`13`).
- Every section ships the five states (`05`); offline shows what is and isn't editable.
