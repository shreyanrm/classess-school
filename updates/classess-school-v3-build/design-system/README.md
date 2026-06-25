# Classess · Design System v4.1

**Steel + one hit of pigment.** The visual system for the Classess ecosystem — built European-minimal: structural, confident, restrained. A monochrome warm-steel shell carries the entire interface; vivid colour appears only as *meaning*, in the smallest possible portion, where it hits hardest.

This kit supersedes v3 (Fraunces / Inter / coral / cream). It is the new source of truth for every Classess surface — School, Learner, and every other app in the ecosystem.

---

## What's in here

| File | What it is |
|------|-----------|
| `brand-kit.html` | **The living styleguide.** Every foundation and component, rendered live, with a light/dark toggle and the tight-matrix motion demo. Open this first. |
| `sample-page.html` | A real **Class 10-B teacher dashboard** built entirely from the system — tight matrices, animated stats, the ignite moment. |
| `tokens.css` | **Single source of truth.** All primitives as CSS custom properties (light + dark). App code references these, never raw hex. |
| `tokens.json` | The same tokens, machine-readable, for programmatic consumption / tooling. |
| `components.css` | The component library — buttons, cards, inputs, tables, nav, badges, alerts, modal, the tight matrix, and the motion layer. Built only on tokens. |
| `FONTS.md` | Font families, licensing (all OFL / free commercial), Poppins alternate, and production self-hosting. |
| `README.md` | This file. |

Open `brand-kit.html` and `sample-page.html` directly in a browser. Toggle the theme top-right. Animations run on load.

---

## The system in one screen

**Colour.** Warm-neutral whites (read as white, never grey or cream) and warm graphite blacks (depth, never pure #000) build the whole shell. Backgrounds lean on the two lightest whites — `#FCFBF9` (surface) and `#F6F4F0` (canvas); the darker steps are for borders and the occasional well. On top sits the accent family — **15 vivid pigments**, knocked back from neon. **Ultramarine (`#1F35E0`)** is the signature: the brand mark and the mastery *ignite*. The other fourteen — molten among them — are subject identity, one hue per surface. A separate semantic set (success / danger / warning / info) handles system states only.

**Type — one sans.** No serif in the system. A single grotesque — **Google Sans Flex** (roundness axis tuned low for "rounded but sharp") — carries everything, with **weight (300–700) and size** doing the hierarchy: light at large sizes for the editorial voice, medium and semibold for the interface. **Poppins** is the designated alternate if the Google font is ever swapped. Mono (**Google Sans Code**) and script (**Caveat**) appear only on demand; serif (DM Serif Display) is opt-in for a rare moment.

**Space, shape, depth.** European-spacey: whitespace is compositional and generous. Corners are sharp (0–3px; no full-radius pills). **No drop shadows anywhere** — depth comes from hairlines (0.5px), tonal surface steps, and frost on overlays only.

**Tight matrices.** When cards group, they stack *close* — a grid sharing 1px hairlines instead of floating with gaps. The signature line wipes across a cell on hover. This dense, structural module is a core part of the look.

**Motion.** Restrained and certain, never bouncy: staggered entrance reveals, progress bars filling from zero, stat numerals counting up, and the ignite — an ultramarine ring expanding around the mastery dot. Everything is gated by `prefers-reduced-motion`.

**Icons.** One outline set, 1.5px stroke, round caps, currentColor. Production library is Lucide, bundled and matched to the spec; the house style is shown in the kit.

---

## The laws (non-negotiable)

1. Monochrome steel shell; colour only ever carries meaning.
2. **One vivid per surface** — a card belongs to a single subject. Two competing vivids is the rainbow trap.
3. Ultramarine is reserved for the brand mark and the mastery ignite — not a subject, not decoration.
4. No drop shadows. Separate surfaces with hairlines and tonal steps.
5. Backgrounds lean on `#FCFBF9` and `#F6F4F0`; use the darker steel sparingly.
6. When cards group, stack them tight in a matrix sharing hairlines — don't float them with gaps.
7. One sans; weight and size do the hierarchy. Serif, mono, script are on-demand only.
8. Sharp corners. Sentence case. Tabular numerics set in mono.
9. No emoji or exclamation marks in product copy. No real pricing in tech-facing mockups (use `₹X,XXX`).

---

## Handoff to Claude Code

- **Consume tokens, never hardcode.** Import `tokens.css` once at the app root; every colour/size/space/radius is a `var(--token)`. For RN/Expo or tooling, read `tokens.json`.
- **Components** in `components.css` are framework-agnostic CSS classes — port them to React components 1:1 (`.btn` → `<Button>`, `.card` → `<Card>`, `.matrix` → a grid wrapper, etc.), keeping the class contracts.
- **Theming** is one attribute: set `data-theme="dark"` on the root to flip the semantic layer. Wire it to OS preference or a user setting. Only the semantic layer changes; raw palette and component code stay identical.
- **Subjects:** set `--subject` + `--subject-ink` on a `.subject-card` (see `tokens.json → subjectMap`). App logic must guarantee no two subjects shown together share a hue. Ultramarine is never a subject.
- **Tight matrices:** wrap grouped cards in `.matrix` and make each child a `.cell` (or a `.subject-card`); the 1px gap renders as shared hairlines. See the demo in `brand-kit.html` and both card groups in `sample-page.html`.
- **Motion:** apply `.reveal` (+ `.reveal-1..8` for stagger) for entrance, `.progress.animate` with `--val` for bars, `.ignite` for the mastery moment, and the `.count` + small JS pattern for count-ups. All honor reduced-motion.
- **Fonts:** self-host for production per `FONTS.md`; strip the CDN `<link>` tags. Poppins is the drop-in alternate. All families are OFL.
- **Extending:** add new components in `components.css` using existing tokens only. If a primitive is missing, add it to `tokens.css` **and** `tokens.json` together, then build on it.

## Note on the brand skill

The `classess-v3-brand` skill is superseded by this v4.1 kit and should be regenerated from these files (same structure: colours, type, surfaces, subject palette, voice, layout patterns, do/don't). Carry forward the v3 voice rules that still hold — no emoji in body copy, no exclamation marks in product copy, dummy `₹X,XXX` pricing for tech-facing mockups, Caveat used sparingly. Replace everything visual.
