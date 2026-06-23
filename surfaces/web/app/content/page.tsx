import type { Metadata } from 'next';
import { ContentLibrary } from './ContentLibrary';

export const metadata: Metadata = {
  title: 'Resource library · Classess',
  description:
    'Browse and search content mapped to the curriculum, with its generate-and-verify state. Only verified content is servable.',
};

export default function ContentPage() {
  return <ContentLibrary />;
}
