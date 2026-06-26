import { chromium } from '@playwright/test';

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
const p = await ctx.newPage();
await p.addInitScript(([k, r, v, id]) => {
  try { Object.defineProperty(navigator, 'mediaDevices', { value: undefined, configurable: true }); } catch {}
  const a = { id, role: r, method: 'phone-otp', contactHint: 'Demo', demo: true, createdAt: new Date().toISOString() };
  const raw = localStorage.getItem(k); const s = raw ? JSON.parse(raw) : {};
  s.version = v; s.account = a; s.onboarding = { completed: true, step: 'welcome', choices: {} };
  localStorage.setItem(k, JSON.stringify(s));
}, ['clss.web.store.v1', 'teacher', 1, 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa']);

await p.goto('http://localhost:3210/loop', { waitUntil: 'domcontentloaded', timeout: 20000 });
await p.waitForTimeout(2500);

// topbar crop
await p.screenshot({ path: '/tmp/polish/teacher/_topbar.png', clip: { x: 900, y: 0, width: 540, height: 64 } });

// open notifications
await p.getByTestId('topbar-notifications').dispatchEvent('click');
await p.waitForTimeout(900);
await p.screenshot({ path: '/tmp/polish/teacher/_notifications.png', clip: { x: 1010, y: 0, width: 430, height: 900 } });
await p.keyboard.press('Escape');
await p.waitForTimeout(400);

// open help
await p.getByTestId('topbar-help').dispatchEvent('click');
await p.waitForTimeout(900);
await p.screenshot({ path: '/tmp/polish/teacher/_help.png', clip: { x: 1010, y: 0, width: 430, height: 900 } });

await b.close();
console.log('done');
