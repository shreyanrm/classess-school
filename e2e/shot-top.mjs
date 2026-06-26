import { chromium } from '@playwright/test';

const ROUTE = process.argv[2] || '/teacher';
const NAME = process.argv[3] || 'teacher-top';
const ROLE = process.argv[4] || 'teacher';

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1440, height: 820 }, deviceScaleFactor: 2 });
const p = await ctx.newPage();
await p.addInitScript(
  ([k, r, v, id]) => {
    try {
      Object.defineProperty(navigator, 'mediaDevices', { value: undefined, configurable: true });
    } catch {}
    const a = { id, role: r, method: 'phone-otp', contactHint: 'Demo', demo: true, createdAt: new Date().toISOString() };
    const raw = localStorage.getItem(k);
    const s = raw ? JSON.parse(raw) : {};
    s.version = v;
    s.account = a;
    s.onboarding = { completed: true, step: 'welcome', choices: {} };
    localStorage.setItem(k, JSON.stringify(s));
  },
  ['clss.web.store.v1', ROLE, 1, 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'],
);
await p.goto('http://localhost:3210' + ROUTE, { waitUntil: 'domcontentloaded', timeout: 30000 });
await p.waitForTimeout(2800);
await p.screenshot({ path: `/tmp/revamp/${NAME}.png` });
await b.close();
console.log('shot-top', NAME, ROUTE);
