# 17 · The Vidya Orb, Voice Mode, Command, and the Signature Moment

Reference implementations: `prototype/vidya-experience.html` (orb, voice bloom, Cmd-K)
and `prototype/signature-and-motion.html` (the signature options). The current repo's
orb/Vidya visual is replaced wholesale by this.

## 17.1 The floating orb — the living Vidya presence

A small (~52px) circle, fixed bottom-right, present on every surface. It is **alive**, not
a static icon:

- **The core** is a layered radial gradient — molten at the top-left, ultramarine and
  violet through the body — that **drifts** (the gradient positions move on a slow ~7s
  loop) and **breathes** (a subtle ~1.05 scale on a ~3.6s loop). A faint glass highlight
  sits top-left; a hairline ring defines the edge. The signature spark mark sits centered,
  low-opacity.
- **Idle:** breathing + drifting, calm. **Hover:** scales to ~1.06, shows a tooltip
  ("Talk to Vidya · Space"). **Press:** scales to ~0.96. No shadow — depth is the ring +
  the living gradient.
- **It is the same Vidya** as the home composer and the dock — one identity, three
  placements. On deep pages the orb is the collapsed VidyaDock.
- **Reduced-motion:** the gradient holds a static, still-beautiful position; no breathing.

Build it GPU-cheap: CSS gradient + `background-position`/`transform` keyframes (no canvas
needed for the idle orb). The reference uses exactly this.

## 17.2 Voice mode — the Siri-like bloom (alive, buttery)

Activated by **clicking the orb**, **clicking the composer mic**, **press-and-hold Space**
(when not typing), or the **command palette → Talk to Vidya**. On activation:

- **The bloom.** The bottom ~62vh of the screen fills with a **living, flowing warm
  field** — layered molten / tangerine / ultramarine / violet radial blobs drifting and
  morphing on a canvas, heavily blurred and additively blended, masked to fade out toward
  the top. This is the v4.1 translation of the Claude voice bloom: warm and organic, on
  our palette, frosted, **no hard edges, no shadow**. It must feel *alive and buttery* —
  continuous rAF motion, long eased drifts, GPU-friendly.
- **The panel.** Centered above the bloom: the animated signature spark (pulsing with a
  gentle ~2.2s breath), the label "Listening — press `esc` to stop" (sentence case, **no
  exclamation**), and a live transcript line as the user speaks.
- **The flow.** Idle bloom while listening → as Vidya interprets, the bloom calms → the
  response composes in the thread above (a Path-1..5 result, `16`) and the bloom recedes.
- **Dismiss:** `esc`, release Space, or click out. The bloom fades and recedes smoothly
  back toward the orb; never a hard cut.
- **Reduced-motion:** a static frosted warm field, the label, and the transcript — no
  flow animation.
- **Real audio (production):** wire to the STT path in the AI fabric (`11`); the prototype
  simulates the transcript. The mic is consent-gated (`02`).

Implementation contract (from the reference): a fixed full-screen layer, a `<canvas>`
bloom with ~5 drifting colored radial blobs (`globalCompositeOperation='lighter'`, CSS
`filter: blur(26px) saturate(1.12)`), a top mask gradient, and a frosted panel. Open/close
animate opacity + a small translateY on the panel.

## 17.3 The command palette (Cmd/Ctrl-K, universal)

A fast launcher available **everywhere**, opened by **Cmd-K / Ctrl-K** or the topbar
command button:

- **The panel.** Centered near the top, frosted (`--frost-bg` + `--frost-blur`), hairline
  border, radius-md, **no shadow**. A scrim dims the app behind it.
- **The input.** "Search, jump to a page, or ask Vidya." Typing filters live.
- **The sections.** *Suggested* (Talk to Vidya · voice; Ask Vidya a question), then *Go
  to* (jump to any surface), then results as the user types (pages, people, actions,
  recent threads). The first option is pre-selected.
- **Keyboard.** Up/Down to move, Enter to run, Esc to close. Mouse hover selects.
- **The actions.** Voice → opens the bloom. Ask → opens a thread with the query. Go to →
  routes (and docks Vidya). Any action → prepared through the permission ladder if
  consequential.
- **Universal.** The shortcut works on every surface, including inside deep pages; it is
  the keyboard twin of the orb.

Build it as a single global component mounted at the app root, listening for the shortcut
and exposing a registry of commands (routes + actions + a Vidya fallback).

## 17.4 Keyboard shortcuts (universal set)

- **Cmd/Ctrl-K** — command palette.
- **Hold Space** — talk to Vidya (when focus is not in a text field).
- **Esc** — close the top-most overlay (palette → voice → drawer → modal), in that order.
- **Cmd/Ctrl-/** — shortcut cheatsheet (lists these).
- Per-surface shortcuts are registered with the palette so they are discoverable. Document
  every shortcut in the cheatsheet; never ship a hidden one.

## 17.5 The signature moment — "Crystallize" (replaces the ignite ring)

The kit's ignite (an ultramarine ring expanding around a dot) is retired as the default.
The replacement means what it shows — a concept **resolving** from fuzzy to crisp and
**locking into** the structure of what a learner knows. Three forms (see
`prototype/signature-and-motion.html`):

- **A · Crystallize / lattice lock-in (the default, knowledge view).** The mastered node
  sits soft, grainy, low-opacity (unresolved). On genuine independent mastery: a refraction
  glint sweeps across the facet, the fill resolves to crisp ultramarine and the grain
  clears (a scale "resolve" snap), then **hairline edges draw outward** to the 1–3
  prerequisite/dependent nodes it now connects — the concept visibly locking into the
  lattice. Then it settles to a calm steady state. No expanding rings, no glow, no shadow.
  Reuses the motions already loved: border-draw (the edges) and the rise/resolve snap.
- **B · Facet bloom (inline single concept).** For a lesson or practice card with no
  neighbors to light: ultramarine floods up into the facet (the rise-fill), the grain
  clears, one specular glint. Self-contained.
- **C · Constellation pulse (the rare big unlock).** For a synthesis/"boss" moment: the
  node snaps crisp, then a light runs outward along each existing wire to its neighbors —
  the new connection energizing the lattice. The most dynamic, still restrained.

**Usage:** A is the default mastery moment in the knowledge view and the progress surface;
B is the inline moment in lessons/practice; C is reserved for genuine synthesis unlocks.
All three are ultramarine-signature, sharp, hairline, shadow-free, and honour
reduced-motion (which shows the resolved end-state with no animation). The `IgniteDot`
component in `10` is renamed/replaced by **`CrystallizeNode`** with a `variant` prop
(`a` | `b` | `c`); update the component library and every reference.

**The aha is multisensory (optional, consented):** pair A/B with a single sub-second
signature sound + a light haptic on supported devices, firing only on genuine
comprehension — scarcity keeps it precious. Never on routine completion.
