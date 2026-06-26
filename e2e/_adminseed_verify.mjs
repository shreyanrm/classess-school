import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const DIR = '/tmp/adminseed';
mkdirSync(DIR, { recursive: true });

const b = await chromium.launch();

// CASE 1: fresh DEMO admin — account.demo + onboarding done, NO school injected.
// The app's own ensureDemoSchool must populate the briefing.
{
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  await p.addInitScript(([k, v, id]) => {
    try { Object.defineProperty(navigator, 'mediaDevices', { value: undefined, configurable: true }); } catch {}
    const s = {
      version: v,
      account: { id, role: 'admin', method: 'phone-otp', demo: true },
      onboarding: { completed: true },
    };
    localStorage.setItem(k, JSON.stringify(s));
  }, ['clss.web.store.v1', 1, 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa']);
  await p.goto('http://localhost:3210/admin', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await p.waitForTimeout(2500);
  await p.screenshot({ path: `${DIR}/demo-populated.png`, fullPage: true });
  const title = await p.title();
  const headText = await p.evaluate(() => document.body.innerText.slice(0, 400));
  const stored = await p.evaluate(() => JSON.parse(localStorage.getItem('clss.web.store.v1')));
  console.log('CASE1 title:', title);
  console.log('CASE1 school confirmed:', stored?.school?.confirmed, 'sections:',
    stored?.school?.structure?.flatMap(g => g.grades).flatMap(gr => gr.sections).map(x => x.name));
  console.log('CASE1 head:', headText.replace(/\n/g, ' | '));
  await ctx.close();
}

// CASE 2: real brand-new admin — NO demo flag. Cold-start must stay intact.
{
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  await p.addInitScript(([k, v, id]) => {
    try { Object.defineProperty(navigator, 'mediaDevices', { value: undefined, configurable: true }); } catch {}
    const s = {
      version: v,
      account: { id, role: 'admin', method: 'phone-otp' },
      onboarding: { completed: true },
    };
    localStorage.setItem(k, JSON.stringify(s));
  }, ['clss.web.store.v1', 1, 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb']);
  await p.goto('http://localhost:3210/admin', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await p.waitForTimeout(2500);
  await p.screenshot({ path: `${DIR}/real-coldstart.png`, fullPage: true });
  const stored = await p.evaluate(() => JSON.parse(localStorage.getItem('clss.web.store.v1')));
  const headText = await p.evaluate(() => document.body.innerText.slice(0, 300));
  console.log('CASE2 school (should be null/absent):', stored?.school ?? null);
  console.log('CASE2 head:', headText.replace(/\n/g, ' | '));
  await ctx.close();
}

await b.close();
console.log('done');
