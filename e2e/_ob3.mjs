import { chromium } from '@playwright/test';
const b=await chromium.launch(); const p=await b.newPage();
const email='e2e'+Date.now()+'@gmail.com';
await p.goto('http://localhost:3947/sign-up',{waitUntil:'networkidle',timeout:30000}).catch(()=>{});
await p.waitForTimeout(700);
await p.locator('.auth-role-row').first().click().catch(()=>{}); await p.waitForTimeout(400);
await p.getByLabel('Email').fill(email).catch(()=>{}); await p.getByTestId('auth-continue').click().catch(()=>{}); await p.waitForTimeout(500);
await p.getByLabel('Password',{exact:true}).fill('Testpw12345').catch(()=>{}); await p.getByTestId('auth-continue').click().catch(()=>{}); await p.waitForTimeout(4000);
console.log('after signup URL:', p.url());
console.log('signup error:', await p.evaluate(()=>document.querySelector('.auth-error')?.textContent||'(none)'));
const hasSession = await p.evaluate(()=>Object.keys(localStorage).some(k=>k.includes('auth-token')));
console.log('supabase session created:', hasSession);
if (p.url().includes('personalise')) {
  const chips=p.locator('button[aria-pressed]'); const n=await chips.count();
  for(let i=0;i<n;i++){await chips.nth(i).click().catch(()=>{});await p.waitForTimeout(120);}
  await p.getByRole('button',{name:/continue|finish|done|start|begin|enter|go/i}).first().click().catch(()=>{});
  await p.waitForTimeout(3000);
  console.log('after personalise URL:', p.url());
  console.log('home body head:', JSON.stringify(await p.evaluate(()=>document.body?.innerText?.slice(0,90)||'')));
}
await b.close(); process.exit(0);
