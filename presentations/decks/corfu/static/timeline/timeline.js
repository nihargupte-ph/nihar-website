(async function () {
  const root = document.getElementById('timeline'); const popup = document.getElementById('tl-popup');
  if (!root || !popup) return;
  const base = root.dataset.src.replace(/timeline\.json$/, '');
  const data = await (await fetch(root.dataset.src)).json();
  const touch = matchMedia('(hover: none)').matches;
  const PX_PER_DAY = 0.9, MIN_GAP = 40, TOP = 24, BOTTOM = 40;
  const day = (iso) => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10)) / 864e5;
  const entries = data.entries.slice().sort((a, b) => a.v1_date.localeCompare(b.v1_date));
  const years = entries.map((e) => +e.v1_date.slice(0, 4));
  const y0 = years.length ? Math.min(...years) : 2016, y1 = (years.length ? Math.max(...years) : 2016) + 1;
  const d0 = day(`${y0}-01-01`);
  const yFor = (iso) => TOP + (day(iso) - d0) * PX_PER_DAY;
  const height = yFor(`${y1}-01-01`) + BOTTOM;
  const el = (tag, attrs = {}, ...kids) => { const n = document.createElement(tag); for (const [k, v] of Object.entries(attrs)) { if (k === 'text') n.textContent = v; else if (k === 'html') n.innerHTML = v; else n.setAttribute(k, v); } n.append(...kids); return n; };
  const escapeHtml = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  root.innerHTML = '';
  root.append(el('div', { class: 'tl-head tl-head--axis', text: 'year' }));
  data.lanes.forEach((l) => root.append(el('div', { class: 'tl-head', text: l.title })));
  const axis = el('div', { class: 'tl-axis', style: `height:${height}px` });
  for (let y = y0; y <= y1; y++) axis.append(el('div', { class: 'tl-year', text: String(y), style: `top:${yFor(`${y}-01-01`)}px` }));
  root.append(axis);
  const byId = {};
  data.lanes.forEach((l) => {
    const lane = el('div', { class: 'tl-lane', 'data-lane': l.id, style: `height:${height}px` });
    let last = -Infinity;
    const mine = entries.filter((e) => e.lane === l.id);
    if (!mine.length) lane.append(el('div', { class: 'tl-empty', text: 'coming soon' }));
    mine.forEach((e) => {
      const top = Math.max(yFor(e.v1_date), last + MIN_GAP); last = top;
      const b = el('button', { class: 'tl-entry', type: 'button', 'data-id': e.id, style: `top:${top}px`, 'aria-haspopup': 'dialog' },
        el('span', { class: 'tl-dot' }), el('span', { class: 'tl-label', html: `${escapeHtml(e.first_author)}<small>${e.v1_date.slice(0, 4)}</small>` }));
      byId[e.id] = e; lane.append(b);
    });
    root.append(lane);
  });
  root.removeAttribute('aria-busy');

  let active = null, hideTimer = null;
  function show(btn) {
    const e = byId[btn.dataset.id]; if (!e) return; clearTimeout(hideTimer);
    if (active && active !== btn) active.classList.remove('active');
    active = btn; btn.classList.add('active');
    popup.innerHTML = '';
    popup.append(el('h2', { class: 'tl-popup__title', text: e.title }),
      el('p', { class: 'tl-popup__meta', html: `${escapeHtml(e.authors)} · ${e.v1_date}<a href="https://arxiv.org/abs/${escapeHtml(e.arxiv)}" target="_blank" rel="noopener">arXiv:${escapeHtml(e.arxiv)}</a>` }));
    if (e.figure) popup.append(el('img', { class: 'tl-popup__fig', src: base + e.figure, alt: e.caption || e.title }));
    else popup.append(el('div', { class: 'tl-popup__nofig', text: 'No figure chosen yet' }));
    if (e.caption) popup.append(el('p', { class: 'tl-popup__cap', text: e.caption }));
    popup.hidden = false;
  }
  function hide() { clearTimeout(hideTimer); popup.hidden = true; if (active) active.classList.remove('active'); active = null; }
  const hideSoon = () => { clearTimeout(hideTimer); hideTimer = setTimeout(hide, 180); };
  root.addEventListener('pointerenter', (ev) => { const b = ev.target.closest && ev.target.closest('.tl-entry'); if (b && !touch) show(b); }, true);
  root.addEventListener('pointerleave', (ev) => { const b = ev.target.closest && ev.target.closest('.tl-entry'); if (b && !touch) hideSoon(); }, true);
  root.addEventListener('focusin', (ev) => { const b = ev.target.closest('.tl-entry'); if (b) show(b); });
  root.addEventListener('click', (ev) => { const b = ev.target.closest('.tl-entry'); if (!b) return; ev.stopPropagation(); if (active === b && !popup.hidden) hide(); else show(b); });
  popup.addEventListener('pointerenter', () => clearTimeout(hideTimer));
  popup.addEventListener('pointerleave', () => { if (!touch) hideSoon(); });
  popup.addEventListener('click', (ev) => ev.stopPropagation());
  document.addEventListener('click', () => { if (!popup.hidden) hide(); });
  document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape' && !popup.hidden) { hide(); ev.stopPropagation(); } });
})();
