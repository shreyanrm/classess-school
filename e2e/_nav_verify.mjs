import { chromium } from '@playwright/test';
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
const p = await ctx.newPage();
await p.addInitScript(([k, r, v, id]) => {
  try { Object.defineProperty(navigator, 'mediaDevices', { value: undefined, configurable: true }); } catch {}
  const a = { id, role: r, method: 'phone-otp', contactHint: 'Demo', demo: true, createdAt: new Date().toISOString() };
  const raw = localStorage.getItem(k); const s = raw ? JSON.parse(raw) : {};
  s.version = v; s.account = a; s.onboarding = { completed: true, step: 'welcome', choices: {} };
  localStorage.setItem(k, JSON.stringify(s));
}, ['clss.web.store.v1', 'teacher', 1, 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa']);

await p.goto('http://localhost:3210/loop', { waitUntil: 'domcontentloaded', timeout: 20000 });
await p.waitForTimeout(2200);
await p.getByTestId('topbar-notifications').dispatchEvent('click');
await p.waitForTimeout(700);
// trusted mouse click at the note row center
const box = await p.locator('.note-row').first().boundingBox();
await p.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
try { await p.waitForURL('**/teacher/insights', { timeout: 6000 }); console.log('NOTE NAV OK ->', p.url()); }
catch { console.log('NOTE NAV FAIL url=', p.url()); }

await p.goto('http://localhost:3210/loop', { waitUntil: 'domcontentloaded', timeout: 20000 });
await p.waitForTimeout(1500);
await p.getByTestId('topbar-help').dispatchEvent('click');
await p.waitForTimeout(700);
const box2 = await p.locator('.help-links a').nth(1).boundingBox();
await p.mouse.click(box2.x + box2.width / 2, box2.y + box2.height / 2);
try { await p.waitForURL('**/teacher/insights', { timeout: 6000 }); console.log('HELP NAV OK ->', p.url()); }
catch { console.log('HELP NAV FAIL url=', p.url()); }

await b.close();
