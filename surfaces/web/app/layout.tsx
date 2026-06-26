import type { Metadata, Viewport } from 'next';
import { ThemeProvider } from '@classess/design-system';
import { RoleProvider } from '@/lib/RoleContext';
import { LocaleProvider } from '@/lib/i18n';
import { AuthGate } from './_components/AuthGate';
import { VidyaOrb } from './_components/VidyaOrb';
import { CommandPalette } from './_components/CommandPalette';
import { EvidenceDrawerHost } from './_components/EvidenceDrawer';
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
          <LocaleProvider>
            <RoleProvider>
              {/* The shared right-slide EvidenceDrawer host — any "Why this"
                  across any stage can open the lineage panel imperatively. */}
              <EvidenceDrawerHost>
                <AuthGate>{children}</AuthGate>
              </EvidenceDrawerHost>
              {/* Vidya floats on every route, persisting across navigation. */}
              <VidyaOrb />
              {/* The universal Cmd/Ctrl-K command palette — the keyboard twin of
                  the orb, available on every surface (spec 17.3-17.4). */}
              <CommandPalette />
            </RoleProvider>
          </LocaleProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
