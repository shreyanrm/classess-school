import { chromium } from '@playwright/test';

const OUT = '/tmp/polish/student';
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
const p = await ctx.newPage();
await p.addInitScript(
  ([k, r, v, id]) => {
    try {
      Object.defineProperty(navigator, 'mediaDevices', { value: undefined, configurable: true });
    } catch {}
    const a = { id, role: r, method: 'phone-otp', contactHint: 'Demo', demo: true, createdAt: new Date().toISOString() };
    const raw = localStorage.getItem(k);
    const s = raw ? JSON.parse(raw) : {};
    s.version = v;
    s.account = a;
    s.onboarding = { completed: true, step: 'welcome', choices: {} };
    localStorage.setItem(k, JSON.stringify(s));
  },
  ['clss.web.store.v1', 'student', 1, 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'],
);

await p.goto('http://localhost:3210/student/mocks', { waitUntil: 'domcontentloaded', timeout: 20000 });
await p.waitForTimeout(2500);
// Click the first "Begin the mock" button to enter the sitting view.
const begin = p.getByRole('button', { name: /Begin the mock/i }).first();
await begin.scrollIntoViewIfNeeded();
await begin.dispatchEvent('click');
await p.waitForTimeout(1500);
await p.screenshot({ path: `${OUT}/mock-session.png`, fullPage: true });
console.log('shot mock-session');

// Submit the paper -> result view (sectioned review).
// Jump to last question via navigator then submit, else just submit if present.
const nav = await p.$$('.mock-nav-cell');
if (nav.length) {
  await nav[nav.length - 1].dispatchEvent('click');
  await p.waitForTimeout(400);
}
const submit = await p.$('button:has-text("Submit the paper")');
if (submit) {
  await submit.dispatchEvent('click');
  await p.waitForTimeout(1200);
  await p.screenshot({ path: `${OUT}/mock-result.png`, fullPage: true });
  console.log('shot mock-result');
} else {
  console.log('no submit button visible');
}

await b.close();
