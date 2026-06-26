import { chromium } from '@playwright/test';

const OUT = '/private/tmp/claude-501/-Users-depl-Documents-classess-school/1083c844-c375-4211-b53a-039be29b8cb8/scratchpad';

async function seed(p, role) {
  await p.addInitScript(([k, r, v, id]) => {
    try { Object.defineProperty(navigator, 'mediaDevices', { value: undefined, configurable: true }); } catch {}
    const a = { id, role: r, method: 'phone-otp', contactHint: 'Demo', demo: true, createdAt: new Date().toISOString() };
    const raw = localStorage.getItem(k); const s = raw ? JSON.parse(raw) : {};
    s.version = v; s.account = a; s.onboarding = { completed: true, step: 'welcome', choices: {} };
    localStorage.setItem(k, JSON.stringify(s));
  }, ['clss.web.store.v1', role, 1, 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa']);
}

const b = await chromium.launch();

// ---- TEACHER builder (Student A detail) ----
{
  const ctx = await b.newContext({ viewport: { width: 1440, height: 1600 } });
  const p = await ctx.newPage();
  await seed(p, 'teacher');
  await p.goto('http://localhost:3210/teacher/students/a0000000-0000-4000-8000-00000000000a', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await p.waitForTimeout(3000);
  // toggle to the formal report card inside the builder
  const formalBtn = p.getByRole('button', { name: 'Formal report card' }).first();
  if (await formalBtn.count()) {
    await formalBtn.scrollIntoViewIfNeeded();
    await formalBtn.dispatchEvent('click');
    await p.waitForTimeout(1200);
  }
  const card = p.getByTestId('formal-report-card').first();
  if (await card.count()) {
    await card.scrollIntoViewIfNeeded();
    await p.waitForTimeout(800);
    await card.screenshot({ path: `${OUT}/formal_teacher.png` });
    console.log('TEACHER formal card: shot');
  } else {
    console.log('TEACHER formal card: MISSING');
  }
  await ctx.close();
}

// ---- STUDENT progress (Analytics tab) ----
{
  const ctx = await b.newContext({ viewport: { width: 1440, height: 1600 } });
  const p = await ctx.newPage();
  await seed(p, 'student');
  await p.goto('http://localhost:3210/student/progress', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await p.waitForTimeout(3000);
  const analytics = p.getByRole('tab', { name: 'Analytics' }).first();
  if (await analytics.count()) { await analytics.dispatchEvent('click'); await p.waitForTimeout(1800); }
  const formalBtn = p.getByRole('button', { name: 'Formal report card' }).first();
  if (await formalBtn.count()) {
    await formalBtn.scrollIntoViewIfNeeded();
    await formalBtn.dispatchEvent('click');
    await p.waitForTimeout(1200);
  }
  const card = p.getByTestId('formal-report-card').first();
  if (await card.count()) {
    await card.scrollIntoViewIfNeeded();
    await p.waitForTimeout(800);
    await card.screenshot({ path: `${OUT}/formal_student.png` });
    console.log('STUDENT formal card: shot');
  } else {
    console.log('STUDENT formal card: MISSING');
  }
  await ctx.close();
}

// ---- PARENT reports ----
{
  const ctx = await b.newContext({ viewport: { width: 1440, height: 1600 } });
  const p = await ctx.newPage();
  await seed(p, 'parent');
  await p.goto('http://localhost:3210/parent/reports', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await p.waitForTimeout(3000);
  const formalBtn = p.getByRole('button', { name: 'Formal report card' }).first();
  if (await formalBtn.count()) {
    await formalBtn.scrollIntoViewIfNeeded();
    await formalBtn.dispatchEvent('click');
    await p.waitForTimeout(1200);
  }
  const card = p.getByTestId('formal-report-card').first();
  if (await card.count()) {
    await card.scrollIntoViewIfNeeded();
    await p.waitForTimeout(800);
    await card.screenshot({ path: `${OUT}/formal_parent.png` });
    console.log('PARENT formal card: shot');
  } else {
    console.log('PARENT formal card: MISSING');
  }
  await ctx.close();
}

await b.close();
console.log('done');
