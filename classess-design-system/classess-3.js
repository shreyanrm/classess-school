/* ============================================================================
   CLASSESS 3.0 — behavior supplement (loads after playground.js, which already
   wires cursor, tilt, spotlight, magnetic, ripple, count-ups, and every
   component). This adds the editorial-nav scrollspy and the motion replays.
   ============================================================================ */
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---- editorial nav: smooth scroll + scrollspy ---- */
  $$('.cs-nav a').forEach(a => a.addEventListener('click', e => {
    e.preventDefault(); const t = $(a.getAttribute('href'));
    if (t) t.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
  }));
  const spy = new IntersectionObserver(es => es.forEach(en => {
    if (en.isIntersecting) $$('.cs-nav a').forEach(a => a.classList.toggle('on', a.getAttribute('href') === '#' + en.target.id));
  }), { rootMargin: '-15% 0px -75% 0px' });
  $$('.cs-sec').forEach(s => spy.observe(s));

  /* ---- motion replays: toggle .run on a wrapper ---- */
  function rerun(el) { if (!el) return; el.classList.remove('run'); void el.offsetWidth; el.classList.add('run'); }
  $$('[data-run3]').forEach(b => b.addEventListener('click', () => rerun($(b.dataset.run3))));

  /* ---- odometer ---- */
  function runOdo(o) { const to = (o.dataset.to || '0').padStart(2, '0'); $$('.col .strip', o).forEach((c, i) => { c.style.transform = `translateY(-${+to[i]}em)`; }); }
  $$('.odo').forEach(o => { o.querySelectorAll('.strip').forEach(s => s.style.transform = 'translateY(0)'); requestAnimationFrame(() => runOdo(o)); });
  $$('[data-odo]').forEach(b => b.addEventListener('click', () => { const o = $(b.dataset.odo); o.querySelectorAll('.strip').forEach(s => s.style.transform = 'translateY(0)'); setTimeout(() => runOdo(o), 60); }));

  /* ---- check draw ---- */
  function checkDraw() { $$('.js-checkdraw path').forEach(p => { const len = p.getTotalLength(); p.style.transition = 'none'; p.style.strokeDasharray = len; p.style.strokeDashoffset = len; void p.getBoundingClientRect(); p.style.transition = 'stroke-dashoffset .5s cubic-bezier(.2,0,0,1)'; p.style.strokeDashoffset = '0'; }); }
  checkDraw();
  $$('[data-checkdraw]').forEach(b => b.addEventListener('click', checkDraw));

  /* ---- tag pop ---- */
  const popKf = document.createElement('style'); popKf.textContent = '@keyframes tagpop{0%{transform:scale(.4);opacity:0}60%{transform:scale(1.12)}100%{transform:scale(1);opacity:1}}'; document.head.appendChild(popKf);
  $$('[data-pop]').forEach(b => b.addEventListener('click', () => { const t = $(b.dataset.pop); t.style.animation = 'none'; void t.offsetWidth; t.style.animation = 'tagpop .45s cubic-bezier(.34,1.56,.64,1)'; }));

  /* ---- ensure motion sections animate on first view ---- */
  const io = new IntersectionObserver(es => es.forEach(en => { if (en.isIntersecting) { en.target.classList.add('run'); io.unobserve(en.target); } }), { threshold: .3 });
  $$('.auto-run').forEach(el => io.observe(el));
})();
