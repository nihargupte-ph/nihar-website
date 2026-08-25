(function () {
  const P = (window.Presentations = window.Presentations || {});
  const W = 1920, H = 1080, NS = 'http://www.w3.org/2000/svg';
  const S = (P.stage = {});
  let idx = 0; const listeners = [];
  const slides = () => (P.data.slides || []);

  S.frac2stage = ([x, y, w, h]) => ({ x: x * W, y: y * H, w: w * W, h: h * H });
  S.px2frac = function (inner, clientX, clientY) {
    const r = inner.getBoundingClientRect();
    let cw = r.width, ch = r.width * H / W, ox = 0, oy = (r.height - ch) / 2;
    if (ch > r.height) { ch = r.height; cw = r.height * W / H; oy = 0; ox = (r.width - cw) / 2; }
    const fx = Math.min(1, Math.max(0, (clientX - r.left - ox) / cw));
    const fy = Math.min(1, Math.max(0, (clientY - r.top - oy) / ch));
    return [fx, fy];
  };
  S.rectEl = function (kind, rect, attrs) {
    const e = document.createElementNS(NS, 'rect'); const s = S.frac2stage(rect);
    e.setAttribute('x', s.x); e.setAttribute('y', s.y); e.setAttribute('width', s.w); e.setAttribute('height', s.h);
    e.setAttribute('rx', 10); e.setAttribute('class', kind);
    for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
    return e;
  };
  S.textEl = function (x, y, text, cls) {
    const e = document.createElementNS(NS, 'text'); e.setAttribute('x', x); e.setAttribute('y', y); e.setAttribute('class', cls); e.textContent = text; return e;
  };
  S.slideEl = (id) => document.querySelector(`.slide[data-slide-id="${CSS.escape(id)}"]`);
  S.overlay = (id) => { const s = S.slideEl(id); return s ? s.querySelector('.overlay') : null; };
  S.widgets = (id) => { const s = S.slideEl(id); return s ? s.querySelector('.stage__widgets') : null; };
  S.index = () => idx;
  S.current = () => (slides()[idx] || {}).id;
  S.onChange = (cb) => listeners.push(cb);
  S.go = function (target, opts) {
    const list = slides(); let n = typeof target === 'number' ? target : list.findIndex((s) => s.id === target);
    if (n < 0 || n >= list.length) return;
    idx = n;
    document.querySelectorAll('.slide').forEach((el) => { el.hidden = Number(el.dataset.index) !== n; });
    const num = document.querySelector('#slide-num'); if (num) num.textContent = String(n + 1);
    document.querySelectorAll('video').forEach((v) => { if (!v.closest('.slide') || v.closest('.slide').hidden) v.pause(); });
    listeners.forEach((cb) => cb(list[n].id, n, opts || {}));
  };
  S.next = (opts) => S.go(idx + 1, opts); S.prev = (opts) => S.go(idx - 1, opts);
  S.keys = function (onSpace) {
    document.addEventListener('keydown', (e) => {
      if (e.target.matches('input,textarea,select')) return;
      if (e.key === 'ArrowRight' || e.key === 'PageDown') { S.next({ user: true }); e.preventDefault(); }
      else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { S.prev({ user: true }); e.preventDefault(); }
      else if (e.key === ' ') { (onSpace || (() => S.next({ user: true })))(); e.preventDefault(); }
    });
  };
  S.swipe = function () {
    let x0 = null;
    document.addEventListener('touchstart', (e) => { x0 = e.touches[0].clientX; }, { passive: true });
    document.addEventListener('touchend', (e) => {
      if (x0 == null) return; const dx = e.changedTouches[0].clientX - x0; x0 = null;
      if (e.target.closest('canvas.draw,.comments-panel,.ask-panel')) return;
      if (dx < -60) S.next({ user: true }); else if (dx > 60) S.prev({ user: true });
    });
  };
  S.buttons = function () {
    const p = document.querySelector('#prev'), n = document.querySelector('#next');
    if (p) p.addEventListener('click', () => S.prev({ user: true }));
    if (n) n.addEventListener('click', () => S.next({ user: true }));
  };
})();
