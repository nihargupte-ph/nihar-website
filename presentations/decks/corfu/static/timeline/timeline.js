(async function () {
  const root = document.getElementById('tl-root'); const popup = document.getElementById('tl-popup');
  if (!root || !popup) return;
  const base = root.dataset.src.replace(/timeline\.json$/, '');
  const data = await (await fetch(root.dataset.src)).json();
  const touch = matchMedia('(hover: none)').matches;
  const PX_PER_DAY = 1.3, MIN_GAP = 34, TOP = 24, BOTTOM = 40;
  const day = (iso) => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10)) / 864e5;
  const entries = data.entries.slice().sort((a, b) => a.v1_date.localeCompare(b.v1_date));
  const years = entries.map((e) => +e.v1_date.slice(0, 4));
  const y0 = years.length ? Math.min(...years) : 2016, y1 = (years.length ? Math.max(...years) : 2016) + 1;
  const d0 = day(`${y0}-01-01`);
  // Years before the first real-data paper (the waveform models' run-up) are drawn compressed so 2014 doesn't push 2026 off the page.
  const yBreak = entries.filter((e) => e.lane === 'real-data').map((e) => +e.v1_date.slice(0, 4)).reduce((a, b) => Math.min(a, b), y1);
  const dBreak = day(`${yBreak}-01-01`), SLOW = 0.22;
  const yFor = (iso) => { const dd = day(iso); return TOP + (Math.min(dd, dBreak) - d0) * PX_PER_DAY * SLOW + Math.max(0, dd - dBreak) * PX_PER_DAY; };
  const height = yFor(`${y1}-01-01`) + BOTTOM;
  const el = (tag, attrs = {}, ...kids) => { const n = document.createElement(tag); for (const [k, v] of Object.entries(attrs)) { if (k === 'text') n.textContent = v; else if (k === 'html') n.innerHTML = v; else n.setAttribute(k, v); } n.append(...kids); return n; };
  const escapeHtml = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  // "Gupte+" for 3+ authors, "Fei & Yang" for exactly two, bare name for one author or a collaboration.
  const label = (e) => {
    const names = (e.authors || '').split(', ');
    if (/Collaboration/.test(e.authors || '') || names.length <= 1) return e.first_author;
    if (names.length === 2 && !/et al\.$/.test(e.authors)) return `${names[0]} & ${names[1]}`;
    return `${e.first_author}+`;
  };

  // Keep entries at their date, but at least MIN_GAP apart: push down, then shift each
  // touching cluster back up by half its mean displacement so it straddles the true dates.
  function layout(want) {
    const pos = want.slice();
    for (let i = 1; i < pos.length; i++) pos[i] = Math.max(pos[i], pos[i - 1] + MIN_GAP);
    for (let i = 0; i < pos.length;) {
      let j = i; while (j + 1 < pos.length && pos[j + 1] - pos[j] <= MIN_GAP + 0.01) j++;
      if (j > i) {
        let shift = 0; for (let k = i; k <= j; k++) shift += pos[k] - want[k]; shift /= (j - i + 1);
        const room = i > 0 ? pos[i] - pos[i - 1] - MIN_GAP : pos[i] - TOP;
        const up = Math.max(0, Math.min(shift / 2, room));
        for (let k = i; k <= j; k++) pos[k] -= up;
      }
      i = j + 1;
    }
    return pos;
  }

  // One column: real-data papers as circles on a vertical line, waveform models as short horizontal
  // rules across the lane. Both are laid out together so rules never land on a circle's label.
  root.innerHTML = '';
  root.append(el('div', { class: 'tl-head tl-head--axis', text: 'year' }));
  const laneTitle = (data.lanes[0] && data.lanes[0].title) || 'Real-data analyses';
  root.append(el('div', { class: 'tl-head', text: laneTitle }));
  const axis = el('div', { class: 'tl-axis', style: `height:${height}px` });
  for (let y = y0; y <= y1; y++) axis.append(el('div', { class: 'tl-year', text: String(y), style: `top:${yFor(`${y}-01-01`)}px` }));
  root.append(axis);
  const byId = {};
  const lane = el('div', { class: 'tl-lane', 'data-lane': 'real-data', style: `height:${height}px` });
  if (!entries.length) lane.append(el('div', { class: 'tl-empty', text: 'coming soon' }));
  const tops = layout(entries.map((e) => yFor(e.v1_date)));
  const papers = entries.map((e, i) => [e, tops[i]]).filter(([e]) => e.lane === 'real-data');
  if (papers.length) lane.append(el('div', { class: 'tl-line', style: `top:${papers[0][1]}px;height:${papers[papers.length - 1][1] - papers[0][1]}px` }));
  entries.forEach((e, i) => {
    const top = tops[i], year = e.v1_date.slice(0, 4);
    const b = e.lane === 'model'
      ? el('button', { class: 'tl-entry tl-rule', type: 'button', 'data-id': e.id, style: `top:${top}px`, 'aria-haspopup': 'dialog', title: e.title },
        el('span', { class: 'tl-rule__line' }), el('span', { class: 'tl-rule__label', html: `${escapeHtml(e.model || label(e))}<small>${year}</small>` }))
      : el('button', { class: 'tl-entry', type: 'button', 'data-id': e.id, style: `top:${top}px`, 'aria-haspopup': 'dialog' },
        el('span', { class: 'tl-dot' }), el('span', { class: 'tl-label', html: `${escapeHtml(label(e))}<small>${year}</small>` }));
    byId[e.id] = e; lane.append(b);
  });
  root.append(lane);
  root.removeAttribute('aria-busy');

  const link = (e) => e.arxiv ? `<a href="https://arxiv.org/abs/${escapeHtml(e.arxiv)}" target="_blank" rel="noopener">arXiv:${escapeHtml(e.arxiv)}</a>`
    : e.url ? `<a href="${escapeHtml(e.url)}" target="_blank" rel="noopener">${escapeHtml(e.link_label || 'paper')}</a>` : '';
  let active = null, hideTimer = null, lastHide = null, ptr = { x: -1, y: -1 };
  // The timeline lives in the left ~40vw at all times (CSS); the popup docks in the right ~58vw on desktop
  // and is centred on phones (CSS media queries), so opening it never moves the timeline.
  function show(btn) {
    const e = byId[btn.dataset.id]; if (!e) return; clearTimeout(hideTimer);
    if (active && active !== btn) active.classList.remove('active');
    active = btn; btn.classList.add('active');
    popup.innerHTML = '';
    popup.append(el('h2', { class: 'tl-popup__title', text: e.title }),
      el('p', { class: 'tl-popup__meta', html: `${e.model ? `<b class="tl-popup__model">${escapeHtml(e.model)}</b> · ` : ''}${escapeHtml(e.authors)} · ${e.v1_date}${link(e)}${e.note ? `<br>${escapeHtml(e.note)}` : ''}` }));
    if (e.figure) popup.append(el('img', { class: 'tl-popup__fig', src: base + e.figure, alt: e.caption || e.title }));
    else if (e.lane !== 'model') popup.append(el('div', { class: 'tl-popup__nofig', text: 'No figure chosen yet' }));
    if (e.caption) popup.append(el('p', { class: 'tl-popup__cap', text: e.caption }));
    popup.hidden = false;
  }
  function hide() {
    clearTimeout(hideTimer); popup.hidden = true; if (active) active.classList.remove('active'); active = null;
    lastHide = { x: ptr.x, y: ptr.y, t: performance.now() };
  }
  const hideSoon = () => { clearTimeout(hideTimer); hideTimer = setTimeout(hide, 250); };
  // Right after a hide Chrome can synthesise a hover on whatever sits under a still cursor —
  // ignore that so the popup does not immediately reopen; a real pointer movement re-arms it.
  const stale = () => lastHide && performance.now() - lastHide.t < 700 && Math.hypot(ptr.x - lastHide.x, ptr.y - lastHide.y) < 10;
  root.addEventListener('pointerenter', (ev) => {
    const b = ev.target.closest && ev.target.closest('.tl-entry'); if (!b || touch) return;
    ptr = { x: ev.clientX, y: ev.clientY }; if (!stale()) show(b);
  }, true);
  root.addEventListener('focusin', (ev) => { const b = ev.target.closest('.tl-entry'); if (b) show(b); });
  root.addEventListener('click', (ev) => { const b = ev.target.closest('.tl-entry'); if (!b) return; ev.stopPropagation(); if (active === b && !popup.hidden) hide(); else show(b); });
  // Leaving the timeline column (or the popup) for anywhere but the other one closes it.
  const inside = (t) => t && t.closest && t.closest('#tl-root, #tl-popup');
  root.addEventListener('pointerleave', (ev) => { if (!popup.hidden && !touch && !inside(ev.relatedTarget)) hideSoon(); });
  popup.addEventListener('pointerleave', (ev) => { if (!popup.hidden && !touch && !inside(ev.relatedTarget)) hideSoon(); });
  document.addEventListener('pointermove', (ev) => {
    ptr = { x: ev.clientX, y: ev.clientY };
    if (popup.hidden || touch) return;
    if (inside(ev.target)) clearTimeout(hideTimer); else hideSoon();
  });
  addEventListener('resize', () => { if (!popup.hidden) hide(); });
  popup.addEventListener('click', (ev) => ev.stopPropagation());
  document.addEventListener('click', () => { if (!popup.hidden) hide(); });
  document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape' && !popup.hidden) { hide(); ev.stopPropagation(); } });
})();
