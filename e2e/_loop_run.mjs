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
await p.waitForTimeout(2500);

async function clickByText(text) {
  const el = p.getByRole('button', { name: text });
  await el.first().dispatchEvent('click');
  await p.waitForTimeout(900);
}

// drive: assign -> set independent -> record -> probe -> approve -> continue -> reassess transfer
await clickByText('Assign the check');
await p.getByRole('button', { name: 'Independent' }).first().dispatchEvent('click');
await p.waitForTimeout(400);
await clickByText('Record two attempts');
await clickByText('Try one unaided');
await clickByText('Approve');
await clickByText('Continue to reassessment');
await clickByText('It transferred');
await p.waitForTimeout(1200);

await p.screenshot({ path: '/tmp/polish/teacher/loop_run.png', fullPage: true });
await b.close();
console.log('done');
