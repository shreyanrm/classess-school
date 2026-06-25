import { ProactiveFeed } from './ProactiveFeed';

export const metadata = { title: 'Approval queue — Classess School' };

/**
 * The approval queue — the one manage-by-exception surface for everything Vidya
 * has prepared and is waiting on a human decision. The live feed + the five
 * designed states live in the client ProactiveFeed (wired to the proactive loop
 * recommend/approve/execute endpoints, gateway-first with the local fallback).
 * The Today briefings on the home and role pages are not repeated here.
 */
export default function ProactivePage() {
  return <ProactiveFeed />;
}
