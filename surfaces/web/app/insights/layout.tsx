import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = { title: 'Subject and cohort rollup — Classess School' };

export default function InsightsLayout({ children }: { children: ReactNode }) {
  return children;
}
