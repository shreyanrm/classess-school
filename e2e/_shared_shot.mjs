import { chromium } from '@playwright/test';

const routes = [
  ['/loop', 'loop'],
  ['/insights', 'insights'],
  ['/content', 'content'],
  ['/messages', 'messages'],
  ['/proactive', 'proactive'],
  ['/profile', 'profile'],
  ['/settings', 'settings'],
];

const only = process.argv[2];
const list = only ? routes.filter(([r, n]) => n === only || r === only) : routes;

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

for (const [route, name] of list) {
  try {
    await p.goto('http://localhost:3210' + route, { waitUntil: 'domcontentloaded', timeout: 20000 });
    await p.waitForTimeout(2800);
    await p.screenshot({ path: `/tmp/polish/teacher/${name}.png`, fullPage: true });
    console.log('shot', name);
  } catch (e) {
    console.log('FAIL', name, e.message);
  }
}
await b.close();
