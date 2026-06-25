# Fonts — sourcing, licensing, install

The system runs on **one sans**. Weight and size carry the whole hierarchy. Mono and script appear only on demand; serif is opt-in for a rare moment that genuinely needs it. All families are **free for commercial use** under the SIL Open Font License (OFL) — no fees, no attribution required, usable in apps, web, logos, and products you sell.

| Role | Family | Use | License | Source |
|------|--------|-----|---------|--------|
| **System** | **Google Sans Flex** | display, UI, body — everything | OFL | fonts.google.com/specimen/Google+Sans+Flex |
| **Alternate** | **Poppins** | drop-in replacement if the Google font is ever swapped | OFL | fonts.google.com/specimen/Poppins |
| Proof (on demand) | **Google Sans Code** | data, code, timestamps | OFL | fonts.google.com/specimen/Google+Sans+Code |
| Human (on demand) | **Caveat** | margin notes, sparingly | OFL | fonts.google.com/specimen/Caveat |
| Opt-in only | **DM Serif Display** | a single editorial moment, never a default | OFL | fonts.google.com/specimen/DM+Serif+Display |

## One sans, weight does the work

There is no serif in the system. Hierarchy comes from weight (300–700) and size on the one grotesque:

- **Light 300 at large sizes** is the editorial voice — hero lines, subject titles.
- **400 / 500 / 600** run the interface — body, labels, headings.
- 700 is available for rare emphasis.

This is the European single-grotesque approach (COS / Jil Sander / Braun). The personality lives in the weight contrast, the one vivid, the tight matrix, and the motion — not in a second typeface.

## On Google Sans

Use **Google Sans Flex** specifically — the variable, open-sourced rebuild released under OFL in November 2025. Do **not** use the legacy static "Google Sans" / "Product Sans"; that one remains proprietary and Google-only, and is a trademark risk for a third-party product.

Google Sans Flex is variable with six axes (weight, width, optical size, slant, grade, **roundness**). Our "rounded but sharp" lives on the roundness axis:

```css
/* set in tokens.css as --sans-axes */
font-variation-settings: "ROND" 12, "opsz" 18;   /* low roundness = crisp, not bubbly */
```

Tune `ROND` between ~0 and ~20 to taste; we sit at 12.

## Poppins — the alternate

Poppins is the designated fallback if Google Sans Flex is ever unavailable or undesirable. It is geometric, slightly rounded, fully open (OFL), and renders everywhere. It already sits second in the `--font-sans` stack, so any environment that can't load Google Sans Flex degrades to Poppins before touching system fonts. To make Poppins the primary, just swap the order in `--font-sans` — nothing else in the system changes.

## Preview vs. production

- **This kit** (`brand-kit.html`, `sample-page.html`) loads fonts from the **Google Fonts CDN** so it renders immediately on open. This is for review only.
- **Production** must **self-host / bundle** the fonts — no CDN dependency in shipped artifacts.

**Route A — npm (Fontsource), recommended for the React/Expo apps**
```bash
npm i @fontsource/poppins @fontsource-variable/google-sans-code @fontsource/caveat
# Google Sans Flex: download the variable woff2 from Google Fonts (or the googlefonts
# GitHub repo) and self-host via @font-face — see Route B. DM Serif only if you use it.
```

**Route B — direct woff2 + @font-face (self-host)**
1. Download the latest variable woff2 for each family from Google Fonts ("Get font" → download) or the `googlefonts/*` GitHub releases.
2. Place under `/assets/fonts/`.
3. Declare:
```css
@font-face {
  font-family: 'Google Sans Flex';
  src: url('/assets/fonts/GoogleSansFlex.woff2') format('woff2-variations');
  font-weight: 300 700; font-display: swap;
}
@font-face {
  font-family: 'Poppins';
  src: url('/assets/fonts/Poppins-Variable.woff2') format('woff2-variations');
  font-weight: 300 700; font-display: swap;
}
@font-face {
  font-family: 'Google Sans Code';
  src: url('/assets/fonts/GoogleSansCode.woff2') format('woff2-variations');
  font-weight: 400 500; font-display: swap;
}
@font-face {
  font-family: 'Caveat';
  src: url('/assets/fonts/Caveat.woff2') format('woff2-variations');
  font-weight: 400 700; font-display: swap;
}
/* DM Serif Display only if a moment uses the opt-in serif */
```

After self-hosting, delete the two `<link href="https://fonts.googleapis.com...">` tags from the HTML and rely on the bundled `@font-face` block.

## Fallback stacks (in tokens.css)

If a face fails to load, the stack degrades sensibly so layout never breaks:
- sans → Poppins → `system-ui` / Roboto / Segoe UI
- mono → `ui-monospace` / SF Mono
- script → cursive
- serif → Georgia
