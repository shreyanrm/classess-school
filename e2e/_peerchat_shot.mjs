import { chromium } from '@playwright/test';

const OUT = '/private/tmp/claude-501/-Users-depl-Documents-classess-school/1083c844-c375-4211-b53a-039be29b8cb8/scratchpad';

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
const p = await ctx.newPage();

await p.addInitScript(() => {
  try {
    Object.defineProperty(navigator, 'mediaDevices', { value: undefined, configurable: true });
  } catch {}
  const store = {
    version: 1,
    account: {
      id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      role: 'student',
      method: 'phone-otp',
      demo: true,
      createdAt: new Date().toISOString(),
    },
    onboarding: { completed: true, step: 'welcome', choices: {} },
  };
  localStorage.setItem('clss.web.store.v1', JSON.stringify(store));
});

await p.goto('http://localhost:3210/messages', { waitUntil: 'domcontentloaded', timeout: 20000 });
await p.waitForTimeout(2500);
await p.screenshot({ path: `${OUT}/peerchat-1-list.png`, fullPage: true });
console.log('shot list');

// Open a peer DM (Study partner — Maths) via dispatchEvent to avoid overlays.
const peer = p.locator('.msg-chan', { hasText: 'Study partner' }).first();
await peer.dispatchEvent('click');
await p.waitForTimeout(900);
await p.screenshot({ path: `${OUT}/peerchat-2-thread.png`, fullPage: true });
console.log('shot thread');

// Zoomed crop of the thread pane BEFORE reporting — bubble + report button.
await p.locator('.msg-pane').first().screenshot({ path: `${OUT}/peerchat-4-pane.png` });
console.log('shot pane');

// Report the incoming message.
const report = p.locator('[data-testid="report-message"]').first();
if (await report.count()) {
  await report.dispatchEvent('click');
  await p.waitForTimeout(700);
  await p.screenshot({ path: `${OUT}/peerchat-3-reported.png`, fullPage: true });
  console.log('shot reported');
} else {
  console.log('NO report affordance found');
}

await b.close();
