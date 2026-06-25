# 20 · Motion System

Motion is part of the brand. The vocabulary is the kit's `motion-lab.html`; this file
fixes **which motion goes where** so the app is expressive but coherent, never a
grab-bag. Everything is GPU-friendly (transform/opacity), eased with the kit curve
`cubic-bezier(0.2,0,0,1)`, frame-budgeted, and **gated by `prefers-reduced-motion`**.
The hard rule holds even here: **no drop shadows** — every "lift" is transform + hairline
+ tonal step.

## 20.1 Defaults (the chosen letters — fold these in)

| Element | Motion (motion-lab letter / class) | Where |
|---|---|---|
| Primary button | **Rise fill** (F · `v-rise`) — ultramarine floods up from baseline | the one forward/consequential action per surface |
| Secondary button | **Fill wipe** (A · `v-wipe`) — ultramarine wipes in from left | Open in <page>, Compare, Adjust, Regenerate |
| Hoverable card | **Spotlight** (C · `c-spot`) — faint signature light tracks the cursor | subject cards, list cards |
| Composing component | **Border draw** (E · `c-draw`) — the frame draws itself around the card | when Vidya composes a component into being (`16` Path 2) |
| Matrix cell hover | **Top-line wipe** (D · `c-line`) — signature line wipes across | the tight matrix |
| Entrance | **Fade-rise** + **stagger cascade** | lists, matrices, surface load |
| Stats | **Count-up** (and **odometer roll** for the rare hero number) | mastery summaries, dashboards |
| Progress | **Bar ease-out** (default), **bar spring** for a livelier moment; **ring draw** for a mastery ring | viz, readouts |
| Trend | **Sparkline draw** | trajectory, progress-over-time |
| Toggle / check / tab | **Switch glide · check draw · tab underline slide** | controls |
| Hero type (rare) | **Blur-in** / **mask slide** | a landing/section opener moment, sparingly |
| Mastery moment | **Crystallize** (`17.5`) — replaces the ignite ring | knowledge view, lessons, unlocks |

These are defaults, not a cage — any other motion-lab variant is available where it
genuinely earns its place. The test the kit states: if a variant feels too much, that is
the signal it is not for this brand.

## 20.2 The signature moment — Crystallize (see `17.5`)

Retire the ignite ring as the default. `CrystallizeNode` (`10`) with `variant`:
- **a · lattice lock-in** — default in the knowledge/progress view (resolve + glint +
  edges draw to neighbors).
- **b · facet bloom** — inline single-concept (rise-fill into the facet + glint).
- **c · constellation pulse** — the rare big unlock (snap + light runs along the wires).
Reference: `prototype/signature-and-motion.html`.

## 20.3 The alive layer (atmosphere, never loud)

- **The orb** — living molten→ultramarine gradient, drifting + breathing (`17.1`). CSS
  gradient keyframes; no canvas needed.
- **The voice bloom** — a flowing warm canvas field, blurred + additive, masked at the top
  (`17.2`). Canvas + rAF; must be buttery.
- **The home ambient bloom** — an extremely subtle living field behind the composer (`16`).
  Very low alpha; atmosphere only.
These make the product feel awake; they never compete with content and always fall back to
a static state under reduced-motion.

## 20.4 Performance & accessibility (non-negotiable)

- Animate only `transform` and `opacity` for anything interactive; use `will-change`
  sparingly on the rail width and the bloom canvas.
- Keep the rail expand and the palette open/close jank-free; no layout thrash, no spinners
  as the primary loading state where a skeleton fits.
- Canvas blooms: cap DPR work, keep blob counts low, blur via CSS filter; pause when
  hidden.
- **`prefers-reduced-motion: reduce`** disables all of the above and shows the resolved
  end-states (the crystallize end, the filled bar, the static bloom). Test this path.
- Every motion has a defined start and end state so an interrupted animation never leaves a
  component visually broken.

## 20.5 Durations & easing (from tokens)

`--ease: cubic-bezier(0.2,0,0,1)` · `--dur-fast 120ms` · `--dur 180ms` · `--dur-slow
260ms`. Spring (sparingly, for the resolve snap and the livelier bar):
`cubic-bezier(.34,1.4,.5,1)`. Never use a long bouncy ease on interface chrome — quick and
certain is the brand.
