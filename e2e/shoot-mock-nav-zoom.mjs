import { chromium } from '@playwright/test';

const OUT = '/tmp/polish/student';
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
const p = await ctx.newPage();
await p.addInitScript(
  ([k, r, v, id]) => {
    try { Object.defineProperty(navigator, 'mediaDevices', { value: undefined, configurable: true }); } catch {}
    const a = { id, role: r, method: 'phone-otp', contactHint: 'Demo', demo: true, createdAt: new Date().toISOString() };
    const raw = localStorage.getItem(k);
    const s = raw ? JSON.parse(raw) : {};
    s.version = v; s.account = a; s.onboarding = { completed: true, step: 'welcome', choices: {} };
    localStorage.setItem(k, JSON.stringify(s));
  },
  ['clss.web.store.v1', 'student', 1, 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'],
);
await p.goto('http://localhost:3210/student/mocks', { waitUntil: 'domcontentloaded', timeout: 20000 });
await p.waitForTimeout(2200);
const begin = p.getByRole('button', { name: /Begin the mock/i }).first();
await begin.dispatchEvent('click');
await p.waitForTimeout(1400);
const nav = await p.$('.mock-nav');
if (nav) { await nav.screenshot({ path: `${OUT}/mock-nav-zoom.png` }); console.log('shot mock-nav-zoom'); }
else console.log('no .mock-nav');
await b.close();
