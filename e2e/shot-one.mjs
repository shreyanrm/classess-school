import { chromium } from '@playwright/test';

const route = process.argv[2] ?? '/parent';
const name = process.argv[3] ?? 'one';
const theme = process.argv[4] ?? 'light';

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
const p = await ctx.newPage();

await p.addInitScript(
  ([k, r, v, id, th]) => {
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
    try { document.documentElement.setAttribute('data-theme', th); } catch {}
  },
  ['clss.web.store.v1', 'parent', 1, 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', theme],
);

await p.goto('http://localhost:3210' + route, { waitUntil: 'domcontentloaded', timeout: 25000 });
await p.waitForTimeout(3000);
await p.screenshot({ path: `/tmp/revamp/${name}.png`, fullPage: true });
const errs = await p.evaluate(() => (window.__errs__ || []));
console.log('shot', name, errs.length ? errs : 'ok');
await b.close();
