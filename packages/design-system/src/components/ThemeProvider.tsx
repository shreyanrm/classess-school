"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import type { Theme } from '../types';

interface ThemeContextValue {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export interface ThemeProviderProps {
  children: ReactNode;
  /** Initial theme. Default 'light'. */
  defaultTheme?: Theme;
  /**
   * The element to stamp data-theme onto. Defaults to document.documentElement
   * (<html>), matching the canonical playground behavior.
   */
  target?: HTMLElement;
}

/**
 * Owns the active theme and writes data-theme onto <html> (or a supplied
 * target). Only the semantic token layer flips between themes — the raw
 * palette never changes. SSR-safe: the DOM write happens in an effect.
 */
export function ThemeProvider({ children, defaultTheme = 'light', target }: ThemeProviderProps) {
  const [theme, setThemeState] = useState<Theme>(defaultTheme);

  useEffect(() => {
    const el = target ?? (typeof document !== 'undefined' ? document.documentElement : null);
    if (el) el.setAttribute('data-theme', theme);
  }, [theme, target]);

  const setTheme = useCallback((next: Theme) => setThemeState(next), []);
  const toggleTheme = useCallback(
    () => setThemeState((t) => (t === 'dark' ? 'light' : 'dark')),
    [],
  );

  const value = useMemo<ThemeContextValue>(
    () => ({ theme, setTheme, toggleTheme }),
    [theme, setTheme, toggleTheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

/** Read and control the active theme. Throws if used outside a ThemeProvider. */
export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within a ThemeProvider');
  return ctx;
}