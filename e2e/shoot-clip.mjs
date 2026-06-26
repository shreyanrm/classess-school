import { chromium } from '@playwright/test';
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 760 }, deviceScaleFactor: 2 });
const p = await ctx.newPage();
await p.addInitScript(
  ([k, r, v, id]) => {
    try { Object.defineProperty(navigator, 'mediaDevices', { value: undefined, configurable: true }); } catch {}
    const a = { id, role: r, method: 'phone-otp', contactHint: 'Demo', demo: true, createdAt: new Date().toISOString() };
    const raw = localStorage.getItem(k); const s = raw ? JSON.parse(raw) : {};
    s.version = v; s.account = a; s.onboarding = { completed: true, step: 'welcome', choices: {} };
    localStorage.setItem(k, JSON.stringify(s));
  },
  ['clss.web.store.v1', 'teacher', 1, 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'],
);
await p.goto('http://localhost:3210/teacher/insights', { waitUntil: 'domcontentloaded', timeout: 30000 });
await p.waitForTimeout(3500);
// Open the band with the most learners so the spotlight + start-set CTA shows.
await p.evaluate(() => {
  const bands = [...document.querySelectorAll('.quadrant-band')];
  let best = null; let max = -1;
  for (const el of bands) {
    const n = parseInt(el.querySelector('.quadrant-count')?.textContent || '0', 10);
    if (n > max) { max = n; best = el; }
  }
  best?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
});
await p.waitForTimeout(700);
// Scroll so the "Group by independence" heading sits near the top of the viewport.
await p.evaluate(() => {
  const el = document.querySelector('.quadrant');
  if (el) window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - 90 });
});
await p.waitForTimeout(500);
await p.screenshot({ path: '/tmp/polish/teacher/insights-quadrant.png' });
console.log('done');
await b.close();
