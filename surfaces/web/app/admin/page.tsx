import { AdminHome } from './AdminHome';

export const metadata = { title: 'Morning briefing — Classess School' };

/**
 * The admin morning briefing — manage by exception. The cold-start stitch lives
 * in AdminHome: an honest set-up path when the school is empty, the real created
 * school once it exists. Nothing acts on its own; every item routes a human to a
 * decision.
 */
export default function AdminBriefingPage() {
  return <AdminHome />;
}
