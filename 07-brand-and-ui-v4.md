# Brand and UI — v4 (the only brand)

The v4 design system is the single source of truth for every surface. The delivered v4 kit — `tokens.json`, components, styleguide, font docs, README — is canonical. Consume it directly. **Regenerate the brand skill from the v4 kit before building any UI. Never apply the stale v3 skill. Never use generic defaults or framework base styles.** The values below are the spine of the system; the kit is authoritative for the complete token set.

## Palette

- Canvas `#F6F4F0` · Surface `#FCFBF9` · Ink `#171510` · Obsidian `#0F0E0C`.
- Eight vivid accents led by **Molten `#FF4D1A`**.
- **Color is semantic, never decorative.** One vivid accent per surface, carrying meaning only. A surface does not wear more than one vivid accent at a time.

## Depth

- **No shadows, ever.** Depth comes from hairlines, tonal steps between canvas and surface, and frost on overlays only. A drop shadow anywhere is a defect.

## Typography

- **Google Sans Flex** (roundness axis ~12) — primary.
- **Google Sans Code** — mono.
- **DM Serif Display** — editorial display (Bodoni Moda as the editorial alternate).
- **Caveat** — script, for the rare human annotation.
- Bundle fonts locally via Fontsource. **No CDN dependencies in production.** Google Sans Flex and Google Sans Code are open-sourced under SIL OFL.
- Rejected and not to be used: Fraunces, Inter, JetBrains Mono (the v3 stack).

## Voice and restraint

- Restraint is the positioning made visual — calm, spacious, certain — while the whole category is red-urgency noise. European, not Korean, minimalism. Calm is a status signal and the antidote an anxious student is starving for.
- No emoji. No exclamation marks in titles or body. Clean, professional prose everywhere a string appears.

## UX laws

- **One screen, one intention, one next action.** The home is never a wall of charts; it answers what needs attention, what to do next, how long it takes, why it is recommended, and what progress it creates.
- **Progressive disclosure.** Show the simple thing first; advanced configuration and deep analytics appear only when asked for.
- **Explainable intelligence in the UI.** Every recommendation surfaces evidence, confidence, owner, due date, and a "why am I seeing this." Nothing is a black box.
- **Plain language for learners.** Students never see the mastery formula or raw scores — they see "you understand this with guidance," "you can solve this independently," "revision is now due."
- **Animate meaning, not chrome.** A misconception shattering, scaffolding fading, a derivation self-assembling — motion that carries meaning, never decoration.
- Tokens as code. The v4 kit drives every color, type ramp, space, and radius. Hardcoded values and base-stylesheet classes are defects.
