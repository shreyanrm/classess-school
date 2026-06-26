import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const ROUTES = [
  ['home', '/'],
  ['admin', '/admin'],
  ['setup', '/admin/setup'],
  ['curriculum', '/admin/curriculum'],
  ['calendar', '/admin/calendar'],
  ['operations', '/admin/operations'],
  ['exams', '/admin/exams'],
  ['intelligence', '/admin/intelligence'],
  ['network', '/admin/network'],
  ['integrations', '/admin/integrations'],
  ['control-centre', '/admin/control-centre'],
  ['governance', '/admin/governance'],
  ['section', '/admin/section/10-b'],
];

const only = process.argv[2]; // optional name filter
const dir = '/tmp/polish/admin';
mkdirSync(dir, { recursive: true });

const b = await chromium.launch();
for (const [name, route] of ROUTES) {
  if (only && name !== only) continue;
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  await p.addInitScript(([k, r, v, id]) => {
    try { Object.defineProperty(navigator, 'mediaDevices', { value: undefined, configurable: true }); } catch {}
    const a = { id, role: r, method: 'phone-otp', contactHint: 'Demo', demo: true, createdAt: new Date().toISOString() };
    const raw = localStorage.getItem(k);
    const s = raw ? JSON.parse(raw) : {};
    s.version = v;
    s.account = a;
    s.onboarding = { completed: true, step: 'welcome', choices: {} };
    localStorage.setItem(k, JSON.stringify(s));
  }, ['clss.web.store.v1', 'admin', 1, 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa']);
  try {
    await p.goto('http://localhost:3210' + route, { waitUntil: 'domcontentloaded', timeout: 20000 });
    await p.waitForTimeout(2800);
    await p.screenshot({ path: `${dir}/${name}.png`, fullPage: true });
    console.log('shot', name);
  } catch (e) {
    console.log('FAIL', name, e.message);
  }
  await ctx.close();
}
await b.close();
