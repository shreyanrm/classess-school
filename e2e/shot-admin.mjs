import { chromium } from '@playwright/test';

const ROUTE = process.argv[2] || '/admin';
const NAME = process.argv[3] || 'admin';
const THEME = process.argv[4] || 'light';

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
const p = await ctx.newPage();
await p.addInitScript(
  ([k, r, v, id, theme]) => {
    try {
      Object.defineProperty(navigator, 'mediaDevices', { value: undefined, configurable: true });
    } catch {}
    const a = {
      id,
      role: r,
      method: 'phone-otp',
      contactHint: 'Demo',
      demo: true,
      createdAt: new Date().toISOString(),
    };
    const raw = localStorage.getItem(k);
    const s = raw ? JSON.parse(raw) : {};
    s.version = v;
    s.account = a;
    s.onboarding = { completed: true, step: 'welcome', choices: {} };
    // A confirmed school so /admin renders the real briefing, not the cold-start.
    s.school = {
      confirmed: true,
      institution: { name: 'Campus North', board: 'Example State Board', pacing: 'Standard, by section' },
      structure: [
        {
          id: 'g1',
          name: 'Campus North',
          grades: [
            { id: 'gr10', name: 'Grade 10', sections: [{ id: 's10b', name: '10-B' }, { id: 's10a', name: '10-A' }] },
            { id: 'gr9', name: 'Grade 9', sections: [{ id: 's9a', name: '9-A' }] },
          ],
        },
      ],
      roster: [
        { id: 't1', kind: 'teacher', label: 'Teacher A' },
        { id: 't2', kind: 'teacher', label: 'Teacher B' },
        { id: 'st1', kind: 'student', label: 'Student A' },
        { id: 'st2', kind: 'student', label: 'Student B' },
        { id: 'st3', kind: 'student', label: 'Student C' },
      ],
    };
    localStorage.setItem(k, JSON.stringify(s));
    try {
      document.documentElement.setAttribute('data-theme', theme);
      localStorage.setItem('clss.theme', theme);
    } catch {}
  },
  ['clss.web.store.v1', 'admin', 1, 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', THEME],
);
await p.goto('http://localhost:3210' + ROUTE, { waitUntil: 'domcontentloaded', timeout: 30000 });
await p.waitForTimeout(2800);
await p.screenshot({ path: `/tmp/revamp/${NAME}.png`, fullPage: true });
await b.close();
console.log('shot', NAME, ROUTE);
