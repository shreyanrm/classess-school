/* ============================================================================
   lib/examsData.ts — single source for the admin exam-operations demo data.

   The OMR / scan-intake rows are genuinely-static demo data (there is no live
   scanner in the surface yet). Keeping them in lib/ rather than inline on the
   page means every surface and Vidya read ONE coherent layer. The live path is
   the gateway + scan pipeline (env vars in lib/runtime.ts); these rows are the
   graceful-degradation fallback until that path is wired.

   Scan intake is human-final: a low-quality scan is flagged for a person and is
   NEVER marked wrong — the student is never penalised for scan quality.
   ============================================================================ */

/** One scanned answer sheet in the intake queue. */
export interface ScanRow {
  id: string;
  label: string;
  quality: 'clean' | 'low';
  state: 'read' | 'needs-human';
}

export const SCAN_ROWS: ScanRow[] = [
  { id: 's1', label: 'Sheet A', quality: 'clean', state: 'read' },
  { id: 's2', label: 'Sheet B', quality: 'clean', state: 'read' },
  { id: 's3', label: 'Sheet C', quality: 'low', state: 'needs-human' },
  { id: 's4', label: 'Sheet D', quality: 'low', state: 'needs-human' },
];
