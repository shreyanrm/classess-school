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

await p.goto('http://localhost:3210/settings', { waitUntil: 'domcontentloaded', timeout: 20000 });
await p.waitForTimeout(2200);

// theme picker: click Dark
const themeBefore = await p.evaluate(() => document.documentElement.getAttribute('data-theme'));
const darkBtn = p.getByTestId('theme-option').nth(1);
await darkBtn.click();
await p.waitForTimeout(500);
const themeAfter = await p.evaluate(() => document.documentElement.getAttribute('data-theme'));
console.log('THEME', themeBefore, '->', themeAfter);

// a11y: toggle larger text
const a11y = p.getByTestId('a11y-toggle').first();
await a11y.scrollIntoViewIfNeeded();
await a11y.click();
await p.waitForTimeout(400);
const large = await p.evaluate(() => document.documentElement.getAttribute('data-large-text') || document.documentElement.className);
console.log('A11Y-LARGE-ATTR', large);

// reset theme back to light for clean shots
await p.getByTestId('theme-option').nth(0).click();
await p.waitForTimeout(300);

// notifications + help open via dispatchEvent
await p.goto('http://localhost:3210/loop', { waitUntil: 'domcontentloaded', timeout: 20000 });
await p.waitForTimeout(2000);
await p.getByTestId('topbar-notifications').dispatchEvent('click');
await p.waitForTimeout(500);
const noteOpen = await p.locator('.ev-drawer-root').count();
console.log('NOTIFICATIONS-DRAWER', noteOpen > 0 ? 'open' : 'MISSING');
await p.keyboard.press('Escape');
await p.waitForTimeout(400);
await p.getByTestId('topbar-help').dispatchEvent('click');
await p.waitForTimeout(500);
const helpOpen = await p.locator('.faq-list').count();
console.log('HELP-DRAWER', helpOpen > 0 ? 'open' : 'MISSING');

await b.close();
console.log('done');
