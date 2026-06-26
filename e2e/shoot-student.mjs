import { chromium } from '@playwright/test';

const OUT = '/tmp/polish/student';

const STATIC_ROUTES = [
  { route: '/', name: 'home' },
  { route: '/student', name: 'student' },
  { route: '/student/learn', name: 'learn' },
  { route: '/student/practice', name: 'practice' },
  { route: '/student/work', name: 'work' },
  { route: '/student/mocks', name: 'mocks' },
  { route: '/student/timetable', name: 'timetable' },
  { route: '/student/progress', name: 'progress' },
  { route: '/student/portfolio', name: 'portfolio' },
];

const filter = process.argv.slice(2);
const routes = filter.length
  ? STATIC_ROUTES.filter((r) => filter.includes(r.name))
  : STATIC_ROUTES;

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
  ['clss.web.store.v1', 'student', 1, 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'],
);

for (const { route, name } of routes) {
  await p.goto('http://localhost:3210' + route, { waitUntil: 'domcontentloaded', timeout: 20000 });
  await p.waitForTimeout(2500);
  await p.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  console.log('shot', name);
}

// Topic detail — discover a real seeded id from the progress page DOM.
if (!filter.length || filter.includes('topic')) {
  await p.goto('http://localhost:3210/student/progress', {
    waitUntil: 'domcontentloaded',
    timeout: 20000,
  });
  await p.waitForTimeout(2500);
  const href = await p.evaluate(() => {
    const a = Array.from(document.querySelectorAll('a[href^="/student/topic/"]'))[0];
    return a ? a.getAttribute('href') : null;
  });
  if (href) {
    await p.goto('http://localhost:3210' + href, {
      waitUntil: 'domcontentloaded',
      timeout: 20000,
    });
    await p.waitForTimeout(2500);
    await p.screenshot({ path: `${OUT}/topic.png`, fullPage: true });
    console.log('shot topic', href);
  } else {
    console.log('NO topic href found');
  }
}

await b.close();
