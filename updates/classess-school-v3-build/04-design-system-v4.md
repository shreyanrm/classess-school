# 04 · Design System — v4.1 (the only brand)

The canonical kit is `classess-design-system/` (`tokens.json`, `tokens.css`,
components, styleguide, font docs) and its port at `packages/design-system/`. Consume
tokens; never hardcode hex. This file is the spine of the system and the **makeover
translation rules**; the kit is authoritative for the complete token set.

**Regenerate the brand skill from this v4.1 kit before building any UI. Never apply
the stale v3 (coral/cream/Fraunces) skill. Never use generic defaults or framework
base styles.**

## The nine laws

1. Monochrome warm-steel shell; colour appears only as meaning.
2. One vivid accent per surface — a card belongs to a single subject.
3. **Ultramarine `#1F35E0` is the signature** — brand mark + the mastery *ignite*.
   Never a subject.
4. **No drop shadows, ever.** Depth = hairlines (0.5px), tonal surface steps, frost on
   overlays only. A shadow anywhere is a defect.
5. Sharp corners (0–3px). No full-radius pills.
6. Whitespace is compositional and generous (European-spacey).
7. Lean on the two lightest whites — surface `#FCFBF9`, canvas `#F6F4F0`.
8. When cards group, stack them tight in a matrix sharing 1px hairlines, not floated
   with gaps.
9. One sans does the whole system — Google Sans Flex; weight (300–700) and size carry
   hierarchy. Serif, mono, script are on-demand only.

## Colour (the spine; kit is authoritative)

**Shell — warm whites:** `#FCFBF9` surface · `#F6F4F0` canvas · `#ECE8E1` sunken ·
`#DCD7CE` hairline · `#CFC9BE` hairline-strong.
**Ink — warm blacks:** `#0F0E0C` obsidian · `#171510` ink (primary text) · `#252119`
dark surface · `#332E25` dark hairline · `#56514A` secondary · `#78726A` quiet ·
`#8B857A` tertiary/disabled.
**Signature:** ultramarine `#1F35E0` (ink `#0A1574`, tint `#E0E4FB`) — brand mark and
mastery ignite only.
**Subject palette (one accent per surface; ultramarine never a subject):** Mathematics
violet `#7A2FF2` · Physics cyan `#00B5D8` · Chemistry magenta `#DD1E9A` · Biology
emerald `#10A37A` · Computer science acid `#C2F000` · English rose `#F4356E` · Social
science amber `#FFB020` · Second language tangerine `#FF8A00`. Extend with cobalt,
tiffany, hotRed, molten, grape, indigo for the full 16-subject set; never two subjects
sharing a hue together.
**Semantic states (system only, never subject):** success `#10936A` · danger `#EC1C2D`
· warning `#FFB020` · info `#1F35E0` (shares the signature hue).
**Theme tokens flip with `data-theme`** — only the semantic layer changes; raw palette
and component code stay identical. (Dark: canvas `#0F0E0C`, surface `#252119`, text
`#F6F4F0`.)

## Type — one sans

- **Google Sans Flex** (roundness axis `ROND ~12`, `opsz 18` — crisp, not bubbly) does
  display, UI, body, everything. Poppins is the drop-in alternate.
- **Google Sans Code** — mono (data, code, timestamps, tabular numerals, the overline).
- **Caveat** — script, the rare human annotation, sparingly.
- **DM Serif Display** — opt-in editorial only; never a default.
- Scale (px / weight): displayLg 64/300 · display 48/300 · displaySm 36/400 · h1 32/600
  · h2 26/600 · h3 21/500 · h4 18/500 · h5 16/500 · h6 14/500 · bodyLg 18/400 · body
  16/400 · bodySm 14/400 · caption 13 · overline 11 mono uppercase 0.12em · data 13 mono
  tabular · statValue 30/500 tabular.
- **Bundle fonts locally via Fontsource. No CDN dependency in production.** Reject the
  v3 stack (Fraunces, Inter, JetBrains Mono) entirely.

## Space / radius / border / depth

- Space scale (px): 0 4 8 12 16 24 32 48 64 96 128. Prefer 24/32/48 for section rhythm.
- Radius: default sm 3px; xs 2; md 6. No pills.
- Border: hairline 0.5px · strong 1px · focus ring 2px.
- Depth: frost bg `rgba(246,244,240,0.72)` · frost blur `blur(14px)` · scrim
  `rgba(15,14,12,0.42)`. No shadows.

## Motion — quick and certain, never bouncy (gated by `prefers-reduced-motion`)

Easing `cubic-bezier(0.2,0,0,1)` · fast 120ms · base 180ms · slow 260ms. Patterns:
`reveal` (entrance fade + 10px rise, staggered) · `fillbar` (progress fills from 0) ·
**`ignite`** (the signature — an ultramarine ring expands and fades around the mastery
dot on genuine comprehension) · `countUp` · `matrixHover` (signature top-line wipe on a
cell). **Animate meaning, never chrome:** a misconception shattering, scaffolding
fading, a derivation self-assembling, the knowledge view igniting a region on mastery.

## Layout

container 1200 · containerNarrow 760 · sidenav 248 (the rail is slimmer — icon-rail
~64, expandable) · topbar 60.

## Components (framework-agnostic CSS → React 1:1)

`.btn` → `<Button>`, `.card` → `<Card>`, `.matrix` → grid wrapper, `.subject-card`
(set `--subject` + `--subject-ink`), `.confidence-band`, `.ignite`/`IgniteDot`,
`.progress.animate` with `--val`, `.spotlight-card`, `.suggestion-chip`, `.stat`
(tabular). Full vocabulary and the makeover-specific components in `10`.

## The tight matrix (a core part of the look)

Grouped cards stack close, sharing 1px hairlines: grid with `gap = border-width` and
`background = border colour`; cells get `bg = surface`; wrap in a container with outer
border + radius 6px + `overflow:hidden`. Hover wipes a signature ultramarine top-line
across a cell — no shadow. Markup contract: `.matrix > .cell`. This replaces v2's
floated, shadowed card grids everywhere.

## The makeover translation (v3 surfaces inherit these defaults)

- v2 coral `#D97757` → **steel ink + ultramarine signature.** Coral is never used.
- v2 cream `#F8F5EE` backgrounds → **canvas `#F6F4F0` / surface `#FCFBF9`.**
- v2 Fraunces display → **Google Sans Flex** weight-300/400 large editorial headings.
- v2 shadowed floated cards → **hairline tight matrix.**
- v2 donut-as-default → a chart only where a human reads the shape; else a briefing /
  recommendation primitive.
- v2 pills/rounded chips → sharp 2–3px chips.
- v2 modal flows → inline disclosure (small) or a docked-Vidya page (large).
- The **logo**: molten wordmark with the ultramarine spark in the C; use the provided
  asset, never recolour to coral.

## Do / don't

- **Do** use one subject accent per surface; **don't** paint a screen in multiple vivids.
- **Do** reserve ultramarine for brand + mastery ignite; **don't** use it as a subject
  or a generic action colour.
- **Do** separate surfaces with hairlines and tonal steps; **don't** add a shadow,
  ever.
- **Do** show large light-weight editorial headings with generous whitespace;
  **don't** build a kitchen-sink dense catalog.
- **Do** keep product copy calm — no emoji, no exclamation marks, sentence case,
  tabular numerics in mono; **don't** use real pricing (use `₹X,XXX`).
