'use client';

import { useEffect, useState } from 'react';

/**
 * Tracks the browser online state so offline can be a designed, first-class
 * state for the core flows rather than a failure screen. SSR-safe: starts
 * optimistic (online) and corrects on mount.
 */
export function useOnline(): boolean {
  const [online, setOnline] = useState(true);

  useEffect(() => {
    const sync = () => setOnline(navigator.onLine);
    sync();
    window.addEventListener('online', sync);
    window.addEventListener('offline', sync);
    return () => {
      window.removeEventListener('online', sync);
      window.removeEventListener('offline', sync);
    };
  }, []);

  return online;
}
