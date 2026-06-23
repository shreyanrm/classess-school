import type { Metadata, Viewport } from 'next';
import { ThemeProvider } from '@classess/design-system';
import { RoleProvider } from '@/lib/RoleContext';
import { AuthGate } from './_components/AuthGate';
import { VidyaOrb } from './_components/VidyaOrb';
import '@classess/design-system/styles.css';
import './globals.css';

export const metadata: Metadata = {
  title: 'Classess School',
  description:
    'Classess School — a calm, conversation-first academic intelligence surface. Vidya, the front door.',
};

export const viewport: Viewport = {
  themeColor: '#F6F4F0',
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="light">
      <body>
        <ThemeProvider defaultTheme="light">
          <RoleProvider>
            <AuthGate>{children}</AuthGate>
            {/* Vidya floats on every route, persisting across navigation. */}
            <VidyaOrb />
          </RoleProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
