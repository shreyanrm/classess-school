import type { Metadata } from 'next';
import { StudentWork } from './StudentWork';

export const metadata: Metadata = {
  title: 'Your work · Classess',
  description:
    'Your assignment inbox and group projects — assigned checks, homework, and projects, with a permission-laddered submit.',
};

export default function StudentWorkPage() {
  return <StudentWork />;
}
