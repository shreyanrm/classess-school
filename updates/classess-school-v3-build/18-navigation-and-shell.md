# 18 · Navigation and the App Shell

Reference: the rail in `prototype/vidya-experience.html`. The shell is identical across
roles; only the rail's feature entries change.

## 18.1 The thin expanding rail

- **Collapsed** to `--rail-collapsed` (64px): the brand mark at top, a column of icon-only
  nav items, and a foot cluster (pin · settings · avatar). This is the resting state.
- **Expands** to `--rail-expanded` (248px) on **hover** (or stays expanded when **pinned**).
  The width animates on `--dur-slow` (260ms) with the `--ease` curve; labels fade and slide
  in (opacity + a 6px translateX). **Butter-smooth: animate `width` with `will-change:width`
  and animate only transform/opacity on the labels — never layout-thrash, never a spinner,
  never lag.** The reference does exactly this; match it.
- **Slide in / slide out** is the hover behaviour; **pin** (the foot control) locks it open
  so it does not collapse on mouse-leave. Pin state persists per user.
- **Active item:** a 2px signature bar on the left edge + signature text colour. Hover:
  sunken background + primary text.
- **Order (top→bottom):** brand mark · New conversation (home) · the role's primary feature
  groups in journey order · a hairline separator · Proactive feed · Search & history · then
  the foot: Pin · Settings · Avatar/name. History is tucked behind Search, not listed — the
  user returns to a thread only when they need one.
- **No labels-always rail.** The collapsed icon rail is the default so the home stays calm
  and spacious; labels are on demand. This is deliberate (the Gemini shape).
- **Reduced-motion:** width snaps without animating; labels appear without sliding.

Per-role rail entries are the surface groups in `06`–`09`. Every entry routes to a real
page (no orphan pages, no dead links — a quality gate, `15`).

## 18.2 The shell regions

- **Rail (left).** As above.
- **Topbar.** The mono role/context line (left), the command button + theme toggle (right).
  No page title on the home; deep pages show a minimal breadcrumb + the page's one primary
  action.
- **Main.** Either the conversation-first home (`16`) or a routed page with the VidyaDock
  (`17`). Pages use `--container` (1200) / `--container-narrow` (760) widths and the
  European-spacey rhythm.
- **Floating orb (fixed).** `17`. Present over every region.
- **Command palette + voice bloom + drawers (overlays).** Mounted at the app root, above
  the shell.

## 18.3 Routing & state

- Client routing maps each rail entry and each Path-4 promote to a surface route (`06`–`09`).
- Vidya context carries into a routed page (the dock is pre-filled from the conversation).
- Back always returns cleanly; a routed page is never a dead end (the dock + the next best
  action are always present).
- Deep-linkable: every surface has a stable route so the palette, notifications, and shared
  links land precisely.

## 18.4 Responsive

- **Desktop:** rail + main as described.
- **Tablet:** rail stays collapsed; expand on tap; main reflows to a single column.
- **Mobile / native (Expo, Wave 3):** the rail becomes a bottom tab + a slide-in drawer;
  the orb stays fixed; the composer is the home; voice is a full-screen bloom. The
  conversation-first model carries over unchanged; only the chrome adapts.
