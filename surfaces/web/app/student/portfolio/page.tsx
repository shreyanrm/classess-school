import type { Metadata } from 'next';
import { StudentPortfolio } from './StudentPortfolio';

export const metadata: Metadata = {
  title: 'Portfolio and credentials · Classess',
  description:
    'Your record of mastered topics with evidence, and verifiable credentials you control. Plain language, never a raw score.',
};

export default function StudentPortfolioPage() {
  return <StudentPortfolio />;
}
