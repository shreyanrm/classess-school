/** Join class name fragments, dropping falsy values. Tiny, no dependency. */
export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ');
}
