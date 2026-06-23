import { chromium } from '@playwright/test';
const b=await chromium.launch(); const p=await b.newPage();
await p.addInitScript(()=>{try{Object.defineProperty(navigator,'mediaDevices',{value:undefined,configurable:true})}catch{}});
const email='e2e'+Date.now()+'@gmail.com';
await p.goto('http://localhost:3947/sign-up',{waitUntil:'commit',timeout:15000}).catch(()=>{});
await p.waitForSelector('.auth-role-row',{timeout:8000}).catch(()=>{});
await p.locator('.auth-role-row').first().click().catch(()=>{}); await p.waitForTimeout(400);
await p.getByLabel('Email').fill(email).catch(()=>{}); await p.getByTestId('auth-continue').click().catch(()=>{}); await p.waitForTimeout(500);
await p.getByLabel('Password',{exact:true}).fill('Testpw12345').catch(()=>{}); await p.getByTestId('auth-continue').click().catch(()=>{}); await p.waitForTimeout(4500);
console.log('after signup URL:', p.url());
console.log('signup error:', await p.evaluate(()=>document.querySelector('.auth-error')?.textContent||'(none)'));
console.log('session:', await p.evaluate(()=>Object.keys(localStorage).some(k=>k.includes('auth-token'))));
if (p.url().includes('personalise')) {
  const chips=p.locator('button[aria-pressed]'); const n=await chips.count(); console.log('chips:',n);
  for(let i=0;i<n;i++){await chips.nth(i).click().catch(()=>{});await p.waitForTimeout(120);}
  const fin=p.getByRole('button',{name:/continue|finish|done|start|begin|enter|let|go/i}).first();
  console.log('finish visible:', await fin.isVisible().catch(()=>false), '| enabled:', await fin.isEnabled().catch(()=>false));
  await fin.click().catch(()=>{}); await p.waitForTimeout(3000);
  console.log('FINAL URL:', p.url());
  console.log('home head:', JSON.stringify(await p.evaluate(()=>document.body?.innerText?.slice(0,80)||'')));
}
await b.close(); process.exit(0);
