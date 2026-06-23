/* ============================================================================
   app/_components/Logo.tsx — the Classess wordmark, used everywhere it appears.

   ONE place the brand logo lives so every surface (auth card, forgot/reset,
   personalise, the rail mark) renders the SAME asset. It is the black wordmark
   PNG (500x200) served from /brand; height is auto so it never distorts. The
   ORANGE variant is used only on a dark/inverted surface (pass inverted).

   The tiny floating orb keeps its compact SVG "C" mark instead — a 500x200 PNG
   would not stay crisp at orb size — so this component is for the wordmark spots.

   Alt text is always "Classess School".
   ============================================================================ */

interface LogoProps {
  /** Rendered width in px; height stays auto so the wordmark never distorts. */
  width?: number;
  /** Use the orange variant — ONLY on a dark/inverted surface. */
  inverted?: boolean;
  className?: string;
}

export function Logo({ width = 110, inverted = false, className }: LogoProps) {
  const src = inverted ? '/brand/classess-logo-orange.png' : '/brand/classess-logo-black.png';
  return (
    // A plain <img> (not next/image) keeps it dependency-free and crisp at the
    // wordmark sizes used here; height auto preserves the 500x200 ratio.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt="Classess School"
      width={width}
      height={Math.round((width * 200) / 500)}
      style={{ width, height: 'auto', display: 'block' }}
      className={className}
    />
  );
}
