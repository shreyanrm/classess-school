import { chromium } from '@playwright/test';

const ROUTES = process.argv.slice(2).length
  ? process.argv.slice(2).map((s) => {
      const [route, name] = s.split('::');
      return { route, name: name || route.replace(/\//g, '_') || 'home' };
    })
  : [
      { route: '/', name: 'home' },
      { route: '/teacher', name: 'teacher' },
      { route: '/teacher/plan', name: 'plan' },
      { route: '/teacher/assign', name: 'assign' },
      { route: '/teacher/evaluate', name: 'evaluate' },
      { route: '/teacher/students', name: 'students' },
      { route: '/teacher/students/a0000000-0000-4000-8000-00000000000a', name: 'student-detail' },
      { route: '/teacher/insights', name: 'insights' },
      { route: '/teacher/attendance', name: 'attendance' },
      { route: '/teacher/growth', name: 'growth' },
      { route: '/teacher/together', name: 'together' },
      { route: '/classroom', name: 'classroom' },
    ];

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
const p = await ctx.newPage();
await p.addInitScript(
  ([k, r, v, id]) => {
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
  },
  ['clss.web.store.v1', 'teacher', 1, 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'],
);

for (const { route, name } of ROUTES) {
  try {
    await p.goto('http://localhost:3210' + route, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await p.waitForTimeout(2800);
    await p.screenshot({ path: `/tmp/polish/teacher/${name}.png`, fullPage: true });
    console.log('shot', name);
  } catch (e) {
    console.log('FAIL', name, e.message);
  }
}
await b.close();
