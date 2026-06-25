'use client';

/* ============================================================================
   app/_components/VidyaDock.tsx — Vidya, DOCKED on a deep page (spec 16.4 / 17).

   The dock is NOT a second Vidya. It is the SAME presence — the same
   `useVidya` orchestrator, the same thread, the same composer + voice path, the
   same permission ladder — presented as a collapsible RIGHT-EDGE panel that
   DRIVES the current page instead of floating over it. A Path-4 route lands the
   user on a workspace; Vidya docks there, pre-filled with the conversation
   context, and keeps driving (spec 16.2 Path 4).

   THE LAZIEST THING THAT WORKS (ponytail): rather than rebuild 400 LOC of orb
   logic in a parallel component — which would be a second source of truth for
   Vidya's behaviour, drifting from the orb — the dock IS the orb. `VidyaOrb`
   detects a deep page (`isDeepPage`) and renders itself in the docked treatment
   (the `data-docked` root + dock CSS in globals.css). One component, one mount
   in the root layout, one behaviour; the page decides float-vs-dock by route.

   This module exists so the shell + the spec have the named `VidyaDock` and the
   `isDeepPage` contract to build to. It re-exports the single Vidya presence; do
   not mount it alongside `<VidyaOrb />` (that would double-mount Vidya).
   ============================================================================ */

export { VidyaOrb as VidyaDock, isDeepPage } from './VidyaOrb';
