import { chromium } from '@playwright/test';
const OUT = '/private/tmp/claude-501/-Users-depl-Documents-classess-school/1083c844-c375-4211-b53a-039be29b8cb8/scratchpad';
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1440, height: 1600 } });
const p = await ctx.newPage();
await p.addInitScript(([k, r, v, id]) => {
  try { Object.defineProperty(navigator, 'mediaDevices', { value: undefined, configurable: true }); } catch {}
  const a = { id, role: r, method: 'phone-otp', contactHint: 'Demo', demo: true, createdAt: new Date().toISOString() };
  const raw = localStorage.getItem(k); const s = raw ? JSON.parse(raw) : {};
  s.version = v; s.account = a; s.onboarding = { completed: true, step: 'welcome', choices: {} };
  localStorage.setItem(k, JSON.stringify(s));
}, ['clss.web.store.v1', 'parent', 1, 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa']);
await p.goto('http://localhost:3210/parent/reports', { waitUntil: 'domcontentloaded', timeout: 30000 });
await p.waitForTimeout(3000);
// 1) default = holistic (plain language) card present, formal NOT present
const holisticDefault = await p.getByTestId('holistic-progress-card').count();
const formalDefault = await p.getByTestId('formal-report-card').count();
console.log('DEFAULT holistic present:', holisticDefault, ' formal present:', formalDefault);
// 2) capture toggle ladder region
const ladder = p.locator('.ladder', { has: p.getByRole('button', { name: 'Formal report card' }) }).first();
if (await ladder.count()) { await ladder.scrollIntoViewIfNeeded(); await ladder.screenshot({ path: `${OUT}/formal_toggle.png` }); console.log('toggle ladder: shot'); }
// 3) switch to formal then emulate print
await p.getByRole('button', { name: 'Formal report card' }).first().dispatchEvent('click');
await p.waitForTimeout(1000);
await p.emulateMedia({ media: 'print' });
await p.waitForTimeout(500);
const card = p.getByTestId('formal-report-card').first();
await card.scrollIntoViewIfNeeded();
await card.screenshot({ path: `${OUT}/formal_print.png` });
console.log('print-media card: shot');
await b.close();
console.log('done');
