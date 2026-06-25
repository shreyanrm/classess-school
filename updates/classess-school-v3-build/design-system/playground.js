/* ============================================================================
   CLASSESS PLAYGROUND — behavior
   ============================================================================ */
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const root = document.documentElement;

  /* ---- theme ---- */
  const tb = $('#themeBtn');
  if (tb) tb.addEventListener('click', () => {
    const d = root.getAttribute('data-theme') === 'dark';
    root.setAttribute('data-theme', d ? 'light' : 'dark');
    const l = $('#themeLbl'); if (l) l.textContent = d ? 'Dark' : 'Light';
  });

  /* ---- CURSOR SYSTEM ---- */
  const dot = $('#cursorDot'), ring = $('#cursorRing'), spot = $('#spotlight');
  let mx = innerWidth / 2, my = innerHeight / 2, rx = mx, ry = my;
  if (dot && !reduce) {
    addEventListener('mousemove', e => {
      mx = e.clientX; my = e.clientY;
      dot.style.transform = `translate(${mx}px,${my}px)`;
      if (spot) { spot.style.setProperty('--cx', mx + 'px'); spot.style.setProperty('--cy', my + 'px'); }
    });
    (function loop() {
      rx += (mx - rx) * 0.18; ry += (my - ry) * 0.18;
      ring.style.transform = `translate(${rx}px,${ry}px)`;
      requestAnimationFrame(loop);
    })();
    document.addEventListener('mouseover', e => {
      if (e.target.closest('button, a, input, .menu-item, [data-magnetic], .cal .d, .star, .pilltab, .vtab, .acc-head'))
        ring.classList.add('hot'); else ring.classList.remove('hot');
    });
  }
  $$('.cursor-bar button').forEach(b => b.addEventListener('click', () => {
    $$('.cursor-bar button').forEach(x => x.classList.remove('on'));
    b.classList.add('on');
    document.body.setAttribute('data-cursor', b.dataset.cursor);
  }));

  /* ---- section scrollspy + smooth scroll ---- */
  $$('.pg-nav a').forEach(a => a.addEventListener('click', e => {
    e.preventDefault(); const t = $(a.getAttribute('href'));
    if (t) t.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
  }));
  const secs = $$('.pg-sec');
  const spy = new IntersectionObserver(es => es.forEach(en => {
    if (en.isIntersecting) {
      $$('.pg-nav a').forEach(a => a.classList.toggle('on', a.getAttribute('href') === '#' + en.target.id));
    }
  }), { rootMargin: '-20% 0px -70% 0px' });
  secs.forEach(s => spy.observe(s));

  /* ---- magnetic buttons ---- */
  $$('.js-magnet').forEach(el => {
    el.addEventListener('mousemove', e => { const r = el.getBoundingClientRect(); el.style.transform = `translate(${(e.clientX - r.left - r.width / 2) * .3}px,${(e.clientY - r.top - r.height / 2) * .4}px)`; });
    el.addEventListener('mouseleave', () => el.style.transform = '');
  });
  /* ---- ripple ---- */
  $$('.js-ripple').forEach(el => el.addEventListener('click', e => {
    const r = el.getBoundingClientRect(), s = document.createElement('span'), d = Math.max(r.width, r.height);
    s.className = 'rip'; s.style.width = s.style.height = d + 'px'; s.style.left = (e.clientX - r.left - d / 2) + 'px'; s.style.top = (e.clientY - r.top - d / 2) + 'px';
    el.appendChild(s); setTimeout(() => s.remove(), 650);
  }));
  /* ---- loading button demo ---- */
  $$('.js-load').forEach(b => b.addEventListener('click', () => { b.classList.add('btn-loading'); setTimeout(() => b.classList.remove('btn-loading'), 1800); }));

  /* ---- generic toggles ---- */
  $$('.js-toggle').forEach(b => b.addEventListener('click', () => b.classList.toggle('on')));
  $$('.theme-pill').forEach(g => $$('button', g).forEach(b => b.addEventListener('click', () => { $$('button', g).forEach(x => x.classList.remove('on')); b.classList.add('on'); })));
  $$('.tristate').forEach(g => $$('button', g).forEach(b => b.addEventListener('click', () => { $$('button', g).forEach(x => x.classList.remove('on')); b.classList.add('on'); })));
  $$('.btn-group').forEach(g => $$('.btn', g).forEach(b => b.addEventListener('click', () => { $$('.btn', g).forEach(x => x.classList.remove('on')); b.classList.add('on'); })));

  /* ---- number stepper ---- */
  $$('.stepper').forEach(s => {
    const inp = $('input', s), [minus, plus] = [$('.minus', s), $('.plus', s)];
    minus && minus.addEventListener('click', () => inp.value = Math.max(0, (+inp.value || 0) - 1));
    plus && plus.addEventListener('click', () => inp.value = (+inp.value || 0) + 1);
  });
  /* ---- OTP ---- */
  $$('.otp').forEach(o => { const ins = $$('input', o); ins.forEach((inp, i) => { inp.addEventListener('input', () => { if (inp.value && ins[i + 1]) ins[i + 1].focus(); }); inp.addEventListener('keydown', e => { if (e.key === 'Backspace' && !inp.value && ins[i - 1]) ins[i - 1].focus(); }); }); });
  /* ---- tags input ---- */
  $$('.tagsin').forEach(t => { const inp = $('input', t); inp.addEventListener('keydown', e => {
    if (e.key === 'Enter' && inp.value.trim()) { e.preventDefault(); const c = document.createElement('span'); c.className = 'chip'; c.innerHTML = inp.value.trim() + ' <button>&times;</button>'; c.querySelector('button').onclick = () => c.remove(); t.insertBefore(c, inp); inp.value = ''; }
  }); $$('.chip button', t).forEach(b => b.onclick = () => b.closest('.chip').remove()); });
  /* ---- password reveal ---- */
  $$('.pw-wrap .toggle').forEach(b => b.addEventListener('click', () => { const i = $('input', b.parentElement); i.type = i.type === 'password' ? 'text' : 'password'; }));

  /* ---- single range fill + bubble ---- */
  $$('.js-range').forEach(r => { const bub = r.parentElement.querySelector('.bubble');
    const upd = () => { const p = (r.value - r.min) / (r.max - r.min) * 100; r.style.setProperty('--fill', p + '%'); if (bub) { bub.textContent = r.value; bub.style.left = p + '%'; } };
    r.classList.add('filled'); r.addEventListener('input', upd); upd();
  });
  /* ---- dual range ---- */
  $$('.dual').forEach(d => { const [a, b] = $$('input', d), fill = $('.fill', d);
    const upd = () => { let lo = Math.min(+a.value, +b.value), hi = Math.max(+a.value, +b.value); const min = +a.min, max = +a.max;
      fill.style.left = (lo - min) / (max - min) * 100 + '%'; fill.style.width = (hi - lo) / (max - min) * 100 + '%'; };
    a.addEventListener('input', upd); b.addEventListener('input', upd); upd();
  });

  /* ---- dropdowns ---- */
  $$('.dd > .js-dd').forEach(t => t.addEventListener('click', e => { e.stopPropagation(); const dd = t.closest('.dd'); $$('.dd.open').forEach(o => o !== dd && o.classList.remove('open')); dd.classList.toggle('open'); }));
  document.addEventListener('click', () => $$('.dd.open').forEach(o => o.classList.remove('open')));
  $$('.multi-opt').forEach(o => o.addEventListener('click', e => { e.stopPropagation(); o.classList.toggle('sel'); const lbl = o.closest('.dd').querySelector('.ms-count'); if (lbl) lbl.textContent = o.closest('.menu').querySelectorAll('.sel').length + ' selected'; }));

  /* ---- command palette ---- */
  const cmdk = $('#cmdk');
  function openCmdk(o) { if (!cmdk) return; cmdk.classList.toggle('open', o); if (o) { const i = $('input', cmdk); i.value = ''; i.focus(); filterCmdk(''); } }
  function filterCmdk(q) { $$('#cmdk .cmdk-row').forEach(r => r.style.display = r.textContent.toLowerCase().includes(q.toLowerCase()) ? '' : 'none'); }
  $$('[data-cmdk]').forEach(b => b.addEventListener('click', () => openCmdk(true)));
  if (cmdk) { $('input', cmdk).addEventListener('input', e => filterCmdk(e.target.value)); cmdk.addEventListener('click', e => { if (e.target === cmdk) openCmdk(false); }); }
  addEventListener('keydown', e => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); openCmdk(!cmdk.classList.contains('open')); } if (e.key === 'Escape') { openCmdk(false); closeAll(); } });

  /* ---- context menu ---- */
  const ctx = $('#ctxMenu'), ctxZone = $('#ctxZone');
  if (ctx && ctxZone) {
    ctxZone.addEventListener('contextmenu', e => { e.preventDefault(); ctx.style.left = e.clientX + 'px'; ctx.style.top = e.clientY + 'px'; ctx.classList.add('open'); });
    document.addEventListener('click', () => ctx.classList.remove('open'));
  }

  /* ---- accordions ---- */
  $$('.acc-head').forEach(h => h.addEventListener('click', () => { const it = h.closest('.acc-item'), multi = it.closest('.acc').dataset.multi; if (!multi) it.closest('.acc').querySelectorAll('.acc-item.open').forEach(o => o !== it && o.classList.remove('open')); it.classList.toggle('open'); }));

  /* ---- pill tabs (sliding indicator) ---- */
  $$('.pilltabs').forEach(g => { const ind = $('.pill-ind', g); const tabs = $$('.pilltab', g);
    const move = t => { ind.style.left = t.offsetLeft + 'px'; ind.style.width = t.offsetWidth + 'px'; };
    tabs.forEach(t => t.addEventListener('click', () => { tabs.forEach(x => x.classList.remove('on')); t.classList.add('on'); move(t); }));
    const on = $('.pilltab.on', g) || tabs[0]; if (on) { on.classList.add('on'); requestAnimationFrame(() => move(on)); }
  });
  /* ---- vertical tabs ---- */
  $$('.vtabs').forEach(g => { const tabs = $$('.vtab', g), panes = $$('.vpane', g);
    tabs.forEach((t, i) => t.addEventListener('click', () => { tabs.forEach(x => x.classList.remove('on')); panes.forEach(p => p.style.display = 'none'); t.classList.add('on'); if (panes[i]) panes[i].style.display = ''; }));
    panes.forEach((p, i) => p.style.display = i === 0 ? '' : 'none');
  });
  /* ---- underline tabs (components.css .tabs) ---- */
  $$('.tabs').forEach(g => $$('.tab', g).forEach(t => t.addEventListener('click', () => { $$('.tab', g).forEach(x => x.classList.remove('active')); t.classList.add('active'); })));

  /* ---- table: sort, select, expand, paginate ---- */
  $$('table.js-sort').forEach(tb => { const tbody = $('tbody', tb);
    $$('th.sortable', tb).forEach((th, idx) => th.addEventListener('click', () => {
      const asc = !th.classList.contains('asc');
      $$('th', tb).forEach(h => h.classList.remove('asc', 'desc'));
      th.classList.add(asc ? 'asc' : 'desc');
      const rows = $$('tr', tbody).filter(r => !r.classList.contains('row-expand'));
      rows.sort((a, b) => { const x = a.children[idx].innerText, y = b.children[idx].innerText; const nx = parseFloat(x), ny = parseFloat(y); const r = (!isNaN(nx) && !isNaN(ny)) ? nx - ny : x.localeCompare(y); return asc ? r : -r; });
      rows.forEach(r => tbody.appendChild(r));
    }));
  });
  $$('.js-selectall').forEach(c => c.addEventListener('change', () => { $$('tbody .rowsel', c.closest('table')).forEach(b => { b.checked = c.checked; b.closest('tr').classList.toggle('sel', c.checked); }); }));
  $$('.rowsel').forEach(b => b.addEventListener('change', () => b.closest('tr').classList.toggle('sel', b.checked)));
  $$('.js-expand').forEach(b => b.addEventListener('click', () => { const tr = b.closest('tr'), ex = tr.nextElementSibling; if (ex && ex.classList.contains('row-expand')) { ex.classList.toggle('open'); b.classList.toggle('open'); } }));
  $$('.pagination').forEach(p => $$('button', p).forEach(b => b.addEventListener('click', () => { $$('button', p).forEach(x => x.classList.remove('on')); b.classList.add('on'); })));

  /* ---- OVERLAYS: drawers / sheets / modal ---- */
  const ovScrim = $('#ovScrim');
  function closeAll() { $$('.drawer.open, .sheet.open, .modal-ov.open').forEach(o => o.classList.remove('open')); if (ovScrim) ovScrim.classList.remove('open'); }
  $$('[data-open]').forEach(b => b.addEventListener('click', () => { const t = $(b.dataset.open); if (!t) return; t.classList.add('open'); if (ovScrim) ovScrim.classList.add('open'); }));
  $$('[data-close]').forEach(b => b.addEventListener('click', closeAll));
  if (ovScrim) ovScrim.addEventListener('click', closeAll);

  /* ---- chat ---- */
  const chat = $('#chat');
  if (chat) {
    const body = $('.chat-body', chat), inp = $('.chat-in input', chat), send = $('.chat-in .js-send', chat);
    const add = (txt, who) => { const b = document.createElement('div'); b.className = 'bubble ' + who; b.textContent = txt; body.appendChild(b); body.scrollTop = body.scrollHeight; return b; };
    const reply = () => { const t = document.createElement('div'); t.className = 'typing'; t.innerHTML = '<span></span><span></span><span></span>'; body.appendChild(t); body.scrollTop = body.scrollHeight;
      setTimeout(() => { t.remove(); add('Good question — let me show you where that idea breaks, then you try the next step.', 'them'); }, 1400); };
    const go = () => { const v = inp.value.trim(); if (!v) return; add(v, 'me'); inp.value = ''; setTimeout(reply, 350); };
    send.addEventListener('click', go); inp.addEventListener('keydown', e => { if (e.key === 'Enter') go(); });
  }

  /* ---- mic ---- */
  $$('.js-mic').forEach(m => { const stateEl = m.parentElement.querySelector('.mic-state'), wave = m.parentElement.querySelector('.wave');
    let on = false; m.addEventListener('click', () => { on = !on; m.classList.toggle('live', on); if (wave) wave.style.visibility = on ? 'visible' : 'hidden'; if (stateEl) stateEl.textContent = on ? 'listening…' : 'tap to speak'; });
    if (wave) wave.style.visibility = 'hidden';
  });

  /* ---- dropzone ---- */
  $$('.dropzone').forEach(dz => { const list = dz.parentElement.querySelector('.file-list'); const input = dz.querySelector('input[type=file]');
    ['dragenter', 'dragover'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add('drag'); }));
    ['dragleave', 'drop'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove('drag'); }));
    dz.addEventListener('drop', e => addFiles(e.dataTransfer.files));
    dz.addEventListener('click', () => input && input.click());
    input && input.addEventListener('change', () => addFiles(input.files));
    function addFiles(files) { Array.from(files).slice(0, 4).forEach(f => { const row = document.createElement('div'); row.className = 'filerow';
      row.innerHTML = '<div class="thumb">▣</div><div class="meta"><div class="nm">' + f.name + '</div><div class="pbar"><span></span></div></div>';
      list.appendChild(row); let p = 0; const bar = row.querySelector('span'); const t = setInterval(() => { p += Math.random() * 22; if (p >= 100) { p = 100; clearInterval(t); } bar.style.width = p + '%'; }, 160); });
    }
    if (!list) return;
  });

  /* ---- toasts ---- */
  const stack = $('#toastStack');
  window.fireToast = function (kind) {
    if (!stack) return;
    const map = { success: ['alert-success', '✓', 'Saved. Weekly summary queued for 36 families.'], info: ['alert-info', 'i', 'Vidya flagged a prerequisite gap in integers.'], warning: ['alert-warning', '!', 'Two assignments are due tomorrow.'], danger: ['alert-danger', '×', 'Sync with the school system failed.'] };
    const [cls, ico, msg] = map[kind] || map.info;
    const t = document.createElement('div'); t.className = 'toast'; t.innerHTML = '<svg class="icon"><use href="#i-spark"/></svg><div>' + msg + '</div>';
    stack.appendChild(t); requestAnimationFrame(() => t.classList.add('in'));
    setTimeout(() => { t.classList.remove('in'); setTimeout(() => t.remove(), 400); }, 3200);
  };
  $$('[data-toast]').forEach(b => b.addEventListener('click', () => window.fireToast(b.dataset.toast)));

  /* ---- stepper / wizard ---- */
  $$('.js-wizard').forEach(w => { let i = 0; const steps = $$('.step', w), lines = $$('.line', w), next = $('.js-next', w.parentElement), back = $('.js-back', w.parentElement);
    const render = () => steps.forEach((s, n) => { s.classList.toggle('done', n < i); s.classList.toggle('active', n === i); if (lines[n]) lines[n].classList.toggle('fill', n < i); });
    next && next.addEventListener('click', () => { if (i < steps.length - 1) { i++; render(); } });
    back && back.addEventListener('click', () => { if (i > 0) { i--; render(); } });
    render();
  });

  /* ---- rating ---- */
  $$('.rating').forEach(r => { const stars = $$('.star', r); let val = +r.dataset.val || 0;
    const paint = n => stars.forEach((s, i) => s.classList.toggle('on', i < n));
    stars.forEach((s, i) => { s.addEventListener('mouseenter', () => paint(i + 1)); s.addEventListener('click', () => { val = i + 1; paint(val); }); });
    r.addEventListener('mouseleave', () => paint(val)); paint(val);
  });

  /* ---- calendar ---- */
  $$('.cal').forEach(c => $$('.d:not(.dim)', c).forEach(d => d.addEventListener('click', () => { $$('.d', c).forEach(x => x.classList.remove('on')); d.classList.add('on'); })));

  /* ---- count-ups ---- */
  function countUp(el) { const to = +el.getAttribute('data-to'); if (reduce) { el.textContent = to; return; } let s = null; function step(t) { if (!s) s = t; const k = Math.min((t - s) / 1100, 1); el.textContent = Math.round(k * to); if (k < 1) requestAnimationFrame(step); } requestAnimationFrame(step); }
  const cuObs = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { countUp(e.target); cuObs.unobserve(e.target); } }));
  $$('.count').forEach(el => cuObs.observe(el));

  /* ---- replay any [data-run] container ---- */
  $$('[data-run]').forEach(b => b.addEventListener('click', () => { const t = $(b.dataset.run); if (!t) return; t.querySelectorAll('.replayable, .bars .b, .linechart path.line, .donut .seg, .gauge path.g-fill, .heat .cell').forEach(el => { const a = el.style.animation; el.style.animation = 'none'; void el.offsetWidth; el.style.animation = ''; }); }));

  /* ---- heatmap random fill ---- */
  $$('.heat').forEach(h => $$('.cell', h).forEach((c, i) => { c.style.animationDelay = (i * 0.012) + 's'; const lv = Math.random(); if (lv > 0.82) c.style.background = 'var(--signature)'; else if (lv > 0.6) c.style.background = 'color-mix(in srgb, var(--signature) 55%, transparent)'; else if (lv > 0.4) c.style.background = 'color-mix(in srgb, var(--signature) 28%, transparent)'; }));

})();
