import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

// Zoomed clips of specific regions, to inspect fidelity the full-page view hides.
const dir = '/tmp/polish/parent';
mkdirSync(dir, { recursive: true });

const b = await chromium.launch();

async function open(route) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 2 });
  const p = await ctx.newPage();
  await p.addInitScript(([k, r, v, id]) => {
    try { Object.defineProperty(navigator, 'mediaDevices', { value: undefined, configurable: true }); } catch {}
    const a = { id, role: r, method: 'phone-otp', contactHint: 'Demo', demo: true, createdAt: new Date().toISOString() };
    const raw = localStorage.getItem(k);
    const s = raw ? JSON.parse(raw) : {};
    s.version = v; s.account = a; s.onboarding = { completed: true, step: 'welcome', choices: {} };
    localStorage.setItem(k, JSON.stringify(s));
  }, ['clss.web.store.v1', 'parent', 1, 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa']);
  await p.goto('http://localhost:3210' + route, { waitUntil: 'domcontentloaded', timeout: 20000 });
  await p.waitForTimeout(2800);
  return { ctx, p };
}

// parent hero + matrix + aside ignite
{
  const { ctx, p } = await open('/parent');
  await p.screenshot({ path: `${dir}/z-parent-top.png`, clip: { x: 0, y: 80, width: 1440, height: 720 } });
  await ctx.close();
}
// reports holistic donut detail — find it and clip
{
  const { ctx, p } = await open('/parent/reports');
  const el = await p.$('.viz-card');
  if (el) await el.screenshot({ path: `${dir}/z-reports-holistic.png` });
  await ctx.close();
}
// child analytics lens — click "The deeper read"
{
  const { ctx, p } = await open('/parent/child');
  await p.evaluate(() => {
    const rung = Array.from(document.querySelectorAll('.ladder-rung'))
      .find((el) => el.textContent.trim() === 'The deeper read');
    if (rung) rung.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  });
  await p.waitForTimeout(2000);
  await p.screenshot({ path: `${dir}/z-child-analytics.png`, fullPage: true });
  await ctx.close();
}
await b.close();
console.log('done');
