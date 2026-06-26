import { chromium } from '@playwright/test';

const routes = [
  ['/parent', 'parent-week'],
  ['/parent/child', 'parent-child'],
  ['/parent/reports', 'parent-reports'],
  ['/parent/together', 'parent-together'],
];

const tag = process.argv[2] ?? 'now';
const theme = process.argv[3] ?? 'light';

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
const p = await ctx.newPage();

await p.addInitScript(
  ([k, r, v, id, th]) => {
    try {
      Object.defineProperty(navigator, 'mediaDevices', { value: undefined, configurable: true });
    } catch {}
    const a = {
      id,
      role: r,
      method: 'phone-otp',
      contactHint: 'Demo',
      demo: true,
      createdAt: new Date().toISOString(),
    };
    const raw = localStorage.getItem(k);
    const s = raw ? JSON.parse(raw) : {};
    s.version = v;
    s.account = a;
    s.onboarding = { completed: true, step: 'welcome', choices: {} };
    localStorage.setItem(k, JSON.stringify(s));
    try {
      document.documentElement.setAttribute('data-theme', th);
    } catch {}
  },
  ['clss.web.store.v1', 'parent', 1, 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', theme],
);

for (const [route, name] of routes) {
  await p.goto('http://localhost:3210' + route, { waitUntil: 'domcontentloaded', timeout: 25000 });
  await p.waitForTimeout(2800);
  await p.screenshot({ path: `/tmp/revamp/${name}-${tag}-${theme}.png`, fullPage: true });
  console.log('shot', name, tag, theme);
}

await b.close();
