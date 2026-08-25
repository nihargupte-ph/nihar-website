(function () {
  const P = (window.Presentations = window.Presentations || {});
  const Hs = (P.hotspots = {});
  const card = () => P.$('#hotspot-card');
  let pinned = null;
  const touch = matchMedia('(hover: none)').matches;

  function place(x, y) {
    const c = card(); const pad = 14; const r = c.getBoundingClientRect();
    let left = x + pad, top = y + pad;
    if (left + r.width > innerWidth - 8) left = Math.max(8, x - r.width - pad);
    if (top + r.height > innerHeight - 8) top = Math.max(48, y - r.height - pad);
    c.style.left = left + 'px'; c.style.top = top + 'px';
  }
  function show(h, x, y, pin) {
    const c = card(); if (!c) return;
    P.$('.hotspot-card__title', c).textContent = h.title;
    P.$('.hotspot-card__body', c).innerHTML = h.body_html || '';
    const links = P.$('.hotspot-card__links', c); links.innerHTML = '';
    (h.links || []).forEach((l) => links.append(P.el('a', { href: l.url, target: '_blank', rel: 'noopener', text: l.label || l.url })));
    c.hidden = false; c.classList.toggle('hotspot-card--pinned', !!pin); place(x, y);
  }
  function hide(force) { if (pinned && !force) return; pinned = null; const c = card(); if (c) { c.hidden = true; c.classList.remove('hotspot-card--pinned'); } document.querySelectorAll('.hotspot.active,[data-hotspot].active').forEach((e) => e.classList.remove('active')); }

  function wireRect(el, h) {
    el.addEventListener('pointerenter', (e) => { if (!touch && !pinned) show(h, e.clientX, e.clientY, false); });
    el.addEventListener('pointermove', (e) => { if (!touch && !pinned) place(e.clientX, e.clientY); });
    el.addEventListener('pointerleave', () => { if (!touch) hide(false); });
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      if (pinned === el) { hide(true); return; }
      hide(true); pinned = el; el.classList.add('active'); show(h, e.clientX, e.clientY, true);
    });
  }

  Hs.mount = function () {
    for (const s of P.data.slides || []) {
      const ov = P.stage.overlay(s.id);
      if (ov) for (const h of s.hotspots || []) {
        const r = P.stage.rectEl('hotspot', h.rect); ov.append(r);
        const st = P.stage.frac2stage(h.rect);
        const mark = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        mark.setAttribute('cx', st.x + st.w - 14); mark.setAttribute('cy', st.y + 14); mark.setAttribute('r', 8); mark.setAttribute('class', 'hotspot-mark');
        ov.append(mark); wireRect(r, h);
      }
    }
    P.$$('[data-hotspot]').forEach((el) => {
      const h = { title: el.dataset.hotspot, body_html: el.dataset.body ? P.escape(el.dataset.body).replace(/\n/g, '<br>') : '', links: el.dataset.link ? [{ url: el.dataset.link, label: el.dataset.linkLabel || el.dataset.link }] : [] };
      wireRect(el, h);
    });
    document.addEventListener('click', (e) => { if (!e.target.closest('#hotspot-card')) hide(true); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hide(true); });
    P.stage.onChange(() => hide(true));
  };
})();
