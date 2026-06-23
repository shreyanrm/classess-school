import { chromium } from '@playwright/test';
const b=await chromium.launch({args:['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});
const c=await b.newContext({reducedMotion:'reduce',permissions:['microphone']}); const p=await c.newPage();
await p.addInitScript(()=>localStorage.setItem('clss.web.store.v1',JSON.stringify({version:1,account:{id:'x',role:'teacher',method:'phone-otp',contactHint:'Demo',demo:true,createdAt:new Date().toISOString()}})));
await p.goto('http://localhost:3947/',{waitUntil:'commit',timeout:15000}).catch(()=>{});
await p.waitForSelector('[data-testid="vidya-orb"]',{timeout:8000}).catch(()=>{});
await p.getByTestId('vidya-orb').dispatchEvent('click');
await p.getByTestId('vidya-panel').waitFor({state:'visible',timeout:5000}).catch(e=>console.log('panel wait:',e.message.slice(0,40)));
let t=Date.now();
await p.keyboard.press('Escape',{timeout:5000}).then(()=>console.log('keyboard.press OK in',Date.now()-t,'ms')).catch(e=>console.log('keyboard.press FAILED in',Date.now()-t,'ms:',e.message.split('\n')[0]));
await p.waitForTimeout(400);
console.log('panel count after Escape:', await p.getByTestId('vidya-panel').count());
// try clicking type-instead
t=Date.now();
await p.getByTestId('vidya-orb').dispatchEvent('click'); await p.waitForTimeout(300);
await p.getByTestId('vidya-type-instead').click({timeout:5000}).then(()=>console.log('type-instead click OK in',Date.now()-t,'ms')).catch(e=>console.log('type-instead click FAILED in',Date.now()-t,'ms:',e.message.split('\n')[0]));
await b.close(); process.exit(0);
