# @classess/design-system

The Classess v4.1 design system, as a consumable React package. "Steel + one hit of pigment." European-minimal.

The laws are not negotiable:

- No drop shadows, ever. Depth comes from hairlines, tonal surface steps, and frost on overlays only. A drop shadow anywhere is a defect.
- Sharp corners. The radius ceiling is 6px; the default is 3px. No full-radius pills.
- One sans. Google Sans Flex carries display, UI, and body. Weight and size do the work.
- One vivid accent per surface, and colour carries meaning, never decoration.
- The ultramarine signature is reserved for the brand mark and the mastery ignite. It is never a subject colour.
- Token-driven. Every value resolves to a CSS custom property. No hardcoded hex.

## Install and import

This package ships source. The styles are a single side-effect stylesheet; import it once at your app root, then use components anywhere.

```ts
// app entry (once)
import '@classess/design-system/styles.css';
```

```tsx
import { ThemeProvider, SpotlightCard, Button, IgniteDot } from '@classess/design-system';

export function App() {
  return (
    <ThemeProvider defaultTheme="light">
      <SpotlightCard padLg>
        <h3>Mastery check</h3>
        <p className="muted">Move your pointer across this card.</p>
        <Button variant="accent">Continue</Button>
      </SpotlightCard>
    </ThemeProvider>
  );
}
```

`ThemeProvider` writes `data-theme` (`light` or `dark`) onto `<html>`. Only the semantic token layer flips between themes; the raw palette never changes. Read or toggle the theme with `useTheme()`.

## Fonts

Fonts are self-hosted via Fontsource — no CDN dependency in production. Poppins (the designated fallback), Google Sans Code (mono), and Caveat (script) are bundled by `styles.css`.

Google Sans Flex is the system face but is not yet on Fontsource. To self-host it, download the variable woff2 from Google Fonts, place it in your app (for example `/public/assets/fonts/GoogleSansFlex.woff2`), and add the `@font-face` block documented in `src/styles/fonts.css`. Until then, the `--font-sans` stack degrades to Poppins, then to system fonts, so layout never breaks. See the repository `FONTS.md` for the full sourcing and licensing notes.

## The subject-color rule

A surface wears at most one vivid accent at a time, and that accent carries meaning. Subject identity is expressed through the `SubjectCard` colour band:

```tsx
<SubjectCard name="Mathematics" code="MATH" accent="tiffany">
  <p>Quadratic equations, revision due.</p>
</SubjectCard>
```

The `accent` prop accepts a `SubjectAccent` — every vivid in the palette **except** ultramarine. Ultramarine is the signature, reserved for the brand mark and the ignite, so the type system makes it impossible to pass `"ultramarine"` as a subject. The band paints `var(--<accent>)` with the matching `var(--<accent>-ink)` text; the body stays on the calm surface.

## The spotlight (the hero)

`SpotlightCard` is the signature hover. An ultramarine radial wash at 10% alpha follows the pointer across the surface — a 180px circle anchored to the `--mx` / `--my` CSS variables, fading to transparent at 60%. The hairline strengthens on hover. Corners stay sharp; the glow is clipped by `overflow: hidden`, so it never bleeds into a drop shadow.

```tsx
import { SpotlightCard } from '@classess/design-system';

<SpotlightCard padLg>
  <h3>Where you left off</h3>
  <p className="muted">Integers, part two.</p>
</SpotlightCard>;
```

It honors `prefers-reduced-motion`: when reduced, the pointer handlers no-op and the glow stays centred and static.

### Build your own spotlight surface

If you need the effect on a custom element, use the hook directly. It returns a ref plus pointer handlers that write `--mx` / `--my` (as percentages of the element box). Pair it with the `.c-spot` class.

```tsx
import { useSpotlight } from '@classess/design-system';

function Panel() {
  const spot = useSpotlight<HTMLDivElement>();
  return <section className="card c-spot" ref={spot.ref} onPointerMove={spot.onPointerMove} onPointerLeave={spot.onPointerLeave} />;
}
```

### SpotlightCard API

| Prop       | Type      | Default | Notes                                              |
| ---------- | --------- | ------- | -------------------------------------------------- |
| `padLg`    | `boolean` | `false` | Larger padding (space-6 instead of space-5).       |
| `children` | `ReactNode` | —     | Card content.                                      |
| ...rest    | `div` props | —     | `className`, `style`, handlers, etc. all pass through. |

## Hooks

- `useSpotlight()` — pointer-tracked `--mx` / `--my` for the spotlight effect.
- `useTilt({ max })` — restrained 3D tilt toward the pointer (`.c-tilt`).
- `useMagnetic({ strengthX, strengthY })` — magnetic pull for buttons and small targets.
- `useCountUp(to, { duration, onView })` — eased count-up, gated on scroll into view.
- `useReducedMotion()` — live `prefers-reduced-motion` state; every motion hook honors it.

## Components

`ThemeProvider`, `Icon`, `Button`, `Card` / `CardHeader`, `SpotlightCard`, `TiltCard`, `Matrix` / `Cell`, `SubjectCard`, `Stat`, `Tag`, `Badge`, `ProgressBar`, `IgniteDot`, `ConfidenceBand`, `Avatar`, `Input`, `Textarea`, `Composer`, `SuggestionChip`.

Icons are Lucide-backed at the house 1.5px stroke. Use house names: `home`, `grid`, `search`, `spark`, `flame`, `target`, `book`, `chart`, and more (see `iconNames`).
