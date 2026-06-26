import { chromium } from '@playwright/test';

const ROUTE = process.argv[2] || '/admin';
const NAME = process.argv[3] || 'admin-empty';

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
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
    // No confirmed school — the cold-start path.
    delete s.school;
    localStorage.setItem(k, JSON.stringify(s));
  },
  ['clss.web.store.v1', 'admin', 1, 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'],
);
await p.goto('http://localhost:3210' + ROUTE, { waitUntil: 'domcontentloaded', timeout: 30000 });
await p.waitForTimeout(2500);
await p.screenshot({ path: `/tmp/revamp/${NAME}.png`, fullPage: true });
await b.close();
console.log('shot', NAME, ROUTE);
