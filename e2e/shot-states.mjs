import { chromium } from '@playwright/test';

const mode = process.argv[2] ?? 'consent'; // consent | offline
const name = process.argv[3] ?? mode;

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
const p = await ctx.newPage();
await p.addInitScript(
  (args) => {
    const k = args[0], r = args[1], v = args[2], id = args[3];
    try { Object.defineProperty(navigator, 'mediaDevices', { value: undefined, configurable: true }); } catch (e) {}
    const a = { id, role: r, method: 'phone-otp', contactHint: 'Demo', demo: true, createdAt: new Date().toISOString() };
    const raw = localStorage.getItem(k);
    const s = raw ? JSON.parse(raw) : {};
    s.version = v; s.account = a; s.onboarding = { completed: true, step: 'welcome', choices: {} };
    localStorage.setItem(k, JSON.stringify(s));
  },
  ['clss.web.store.v1', 'parent', 1, 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'],
);

await p.goto('http://localhost:3210/parent', { waitUntil: 'domcontentloaded', timeout: 25000 });
await p.waitForTimeout(2500);

if (mode === 'offline') {
  // go offline, then re-navigate so the surface reads the offline state
  await ctx.setOffline(true);
  await p.evaluate(() => window.dispatchEvent(new Event('offline')));
  await p.waitForTimeout(1500);
}

if (mode === 'consent') {
  // click the third (locked) child chip — child-c is not consented. Force past
  // any floating orb/capsule that may overlay the click point.
  await p.evaluate(() => {
    const chips = document.querySelectorAll('.child-chip');
    const locked = chips[2];
    if (locked) (locked).click();
  });
  await p.waitForTimeout(1800);
}

await p.screenshot({ path: `/tmp/revamp/${name}.png`, fullPage: true });
console.log('state shot', name);
await b.close();
