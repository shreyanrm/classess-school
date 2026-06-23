import { chromium } from '@playwright/test';
const b=await chromium.launch(); const c=await b.newContext({reducedMotion:'reduce'}); const p=await c.newPage();
const errs=[]; p.on('pageerror',e=>errs.push('ERR:'+e.message.slice(0,120)));
await p.addInitScript(()=>localStorage.setItem('clss.web.store.v1',JSON.stringify({version:1,account:{id:'x',role:'teacher',method:'phone-otp',contactHint:'Demo',demo:true,createdAt:new Date().toISOString()}})));
await p.goto('http://localhost:3947/',{waitUntil:'domcontentloaded'}); await p.waitForTimeout(1500);
const orb=p.getByTestId('vidya-orb');
const t0=Date.now();
try { await orb.click({timeout:5000}); console.log('click OK in', Date.now()-t0,'ms'); }
catch(e){ console.log('click FAILED in', Date.now()-t0,'ms:', e.message.split('\n')[0]); }
await p.waitForTimeout(600);
console.log('panel visible:', await p.getByTestId('vidya-panel').isVisible().catch(()=>false));
console.log('open attr after JS click:', await p.evaluate(()=>{const o=document.querySelector('.vidya-orb');return o&&o.getAttribute('aria-expanded');}));
// try a direct DOM click as a control
await p.evaluate(()=>document.querySelector('[data-testid=\"vidya-orb\"]').click());
await p.waitForTimeout(500);
console.log('panel visible after DOM click:', await p.getByTestId('vidya-panel').isVisible().catch(()=>false));
console.log(errs.join(' | ')||'(no pageerror)');
await b.close();
