(async function () {
  const root = document.getElementById('ch-root'); const popup = document.getElementById('ch-popup');
  if (!root || !popup) return;
  const base = root.dataset.src.replace(/channels\.json$/, '');
  const [data, graphs] = await Promise.all([fetch(root.dataset.src).then((r) => r.json()), fetch(base + 'graph.json').then((r) => r.json())]);
  const SVG = 'http://www.w3.org/2000/svg';
  const el = (tag, attrs = {}, ...kids) => { const n = document.createElement(tag); for (const [k, v] of Object.entries(attrs)) { if (k === 'text') n.textContent = v; else if (k === 'html') n.innerHTML = v; else n.setAttribute(k, v); } n.append(...kids); return n; };
  const svg = (tag, attrs = {}, ...kids) => { const n = document.createElementNS(SVG, tag); for (const [k, v] of Object.entries(attrs)) { if (k === 'text') n.textContent = v; else n.setAttribute(k, v); } n.append(...kids); return n; };
  const escapeHtml = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  // ---- the stage: one thick line, media cards around it, leaders to each channel's region -------
  const W = 1800, H = 880, LINE_Y = 425, LINE_H = 18, PAD_L = 120, PAD_R = 60;
  const group = (c) => c.id === 'agn' ? 'agn' : (c.id === 'triples' || c.id === 'zkl-smbh') ? 'zkl' : c.group;
  const GAP = 20, EDGE = 40, LABEL_H = 26, FAM_PAD = 12;        // card spacing, stage margin, row-label band, family box padding
  const { log_min: L0, log_max: L1 } = data.axis;
  const x = (log) => PAD_L + (log - L0) / (L1 - L0) * (W - PAD_L - PAD_R);
  const FAMS = data.families || {}, ROWS = data.rows || {};
  const famPeak = {};   // families are laid out as one block at their mean peak so the box can enclose them
  for (const c of data.channels) if (c.family) (famPeak[c.family] = famPeak[c.family] || []).push(c.peak);
  const orderKey = (c) => c.family ? famPeak[c.family].reduce((a, b) => a + b) / famPeak[c.family].length + c.peak * 1e-3 : c.peak;
  const rows = data.channels.slice().sort((p, q) => orderKey(p) - orderKey(q));
  const stage = el('div', { class: 'ch-stage', style: `width:${W}px;height:${H}px` });
  const s = svg('svg', { class: 'ch-stage__svg', viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: 'img', 'aria-label': 'Formation channels placed by their predicted eccentricity at 10 Hz' });
  const cardsLayer = el('div', { class: 'ch-cards' });
  // axis: decade ticks + labels under the thick line
  for (let d = L0; d <= L1; d++) {
    s.append(svg('line', { class: 'ch-tick', x1: x(d), x2: x(d), y1: LINE_Y + LINE_H / 2 + 52, y2: LINE_Y + LINE_H / 2 + 62 }));
    const t = svg('text', { class: 'ch-ticklabel', x: x(d), y: LINE_Y + LINE_H / 2 + 88, 'text-anchor': 'middle' });
    if (d === 0) t.textContent = '1'; else { t.append('10'); t.append(svg('tspan', { class: 'sup', dy: -10, text: String(d) })); }
    s.append(t);
  }
  s.append(svg('text', { class: 'ch-axis-title', x: x(L1) + 4, y: LINE_Y + LINE_H / 2 + 118, 'text-anchor': 'end', text: 'Eccentricity at 10 Hz' }));
  // the thick line
  s.append(svg('rect', { class: 'ch-thick', x: x(L0) - 6, y: LINE_Y - LINE_H / 2, width: x(L1) - x(L0) + 12, height: LINE_H, rx: LINE_H / 2 }));
  // leaders + bands go in their own groups so bands sit on top of the line and leaders below the cards
  const leaders = svg('g', { class: 'ch-leaders' }), bands = svg('g', { class: 'ch-bands' });
  s.append(leaders, bands);
  const rowEls = {}; let active = null;
  // rows by outcome: eccentric channels above the line, quasi-circular ones below; cards fill the row width,
  // shrinking (and keeping the 16:9 media) when a row has many of them
  const above = rows.filter((c) => c.row === 'eccentric'), below = rows.filter((c) => c.row !== 'eccentric');
  const cardW = (n) => Math.min(380, Math.floor((W - 2 * EDGE - GAP * (n - 1)) / n));
  const CW = cardW(Math.max(above.length, below.length));   // both rows share one card size (the fuller row sets it)
  const cardH = (w) => Math.round((w - 20) * 9 / 16 + 98);
  const place = (list, top) => {
    const cw = CW, ch = cardH(cw), total = list.length * cw + (list.length - 1) * GAP, x0 = (W - total) / 2;
    const y = top ? LABEL_H + FAM_PAD : H - LABEL_H - FAM_PAD - ch;
    list.forEach((c, i) => { const cx = x0 + i * (cw + GAP) + cw / 2; c._card = { x: cx - cw / 2, y, w: cw, h: ch, cx, ay: top ? y + ch : y }; });
    // row caption
    s.append(svg('text', { class: 'ch-rowlabel', x: EDGE, y: top ? LABEL_H - 8 : H - 8, text: (ROWS[top ? 'eccentric' : 'circular'] || '').toUpperCase() }));
  };
  place(above, true); place(below, false);
  // family boxes (e.g. the three isolated-binary channels) drawn around their contiguous cards
  for (const [fid, f] of Object.entries(FAMS)) {
    const members = rows.filter((c) => c.family === fid); if (!members.length) continue;
    const xs = members.map((c) => c._card.x), xe = members.map((c) => c._card.x + c._card.w), p0 = members[0]._card;
    const box = el('div', { class: 'ch-family', 'data-group': group(members[0]), style: `left:${Math.min(...xs) - FAM_PAD}px;top:${p0.y - FAM_PAD}px;width:${Math.max(...xe) - Math.min(...xs) + 2 * FAM_PAD}px;height:${p0.h + 2 * FAM_PAD}px` },
      el('span', { class: 'ch-family__label', text: f.label }));
    cardsLayer.append(box);
  }
  const playable = (c) => { const m = c.media || {}; return m.type === 'youtube' || ((m.type === 'gif' || m.type === 'video') && !!m.still); };
  const thumb = (c) => {
    const m = c.media || {};
    // a line-art icon as the face (tools/iconpicker.py sets c.icon); hovering still swaps the video in
    if (c.icon) return el('div', { class: 'ch-card__media ch-card__media--icon' }, el('img', { src: base + c.icon, alt: '', loading: 'lazy' }), playable(c) ? el('span', { class: 'ch-card__play', text: '▶' }) : '');
    if (m.type === 'youtube') return el('div', { class: 'ch-card__media' }, el('img', { src: `https://i.ytimg.com/vi/${m.id}/hqdefault.jpg`, alt: '', loading: 'lazy' }), el('span', { class: 'ch-card__play', text: '▶' }));
    if (m.type === 'gif' || m.type === 'video') return el('div', { class: 'ch-card__media' }, el('img', { src: base + (m.still || m.src), alt: '', loading: 'lazy' }), m.still ? el('span', { class: 'ch-card__play', text: '▶' }) : '');
    if (c.figure) return el('div', { class: 'ch-card__media ch-card__media--fig' }, el('img', { src: base + c.figure.src, alt: '', loading: 'lazy' }), el('span', { class: 'ch-card__nomedia', text: 'no video yet' }));
    return el('div', { class: 'ch-card__media ch-card__media--none', text: 'no media yet' });
  };
  const hi = (c) => (c.tail ? c.tail[1] : c.band[1]);               // a channel's line runs solid over band ∪ tail
  const range = (c) => { const f = (v) => v >= 0 ? '1' : `10^${v}`; return `${f(c.band[0])} – ${f(hi(c))}`; };
  const BR_H = 9, BR_GAP = 5;
  // one bracket lane per channel (a family shares a single lane) so regions never overlap
  const laneKey = (c) => c.family || c.id, laneIdx = {};
  [above, below].forEach((list) => { let i = 0; list.forEach((c) => { const k = laneKey(c); if (!(k in laneIdx)) laneIdx[k] = i++; }); });
  const famBand = {};
  rows.forEach((c) => {
    const g = group(c), p = c._card, up = p.ay < LINE_Y;
    const lane = laneIdx[laneKey(c)];
    const by = up ? LINE_Y - LINE_H / 2 - BR_GAP - (lane + 1) * (BR_H + BR_GAP) + BR_GAP : LINE_Y + LINE_H / 2 + BR_GAP + lane * (BR_H + BR_GAP);
    let bg = c.family && famBand[c.family];
    if (!bg) {
      bg = svg('g', { class: 'ch-row', 'data-id': c.id, 'data-group': g });
      bg.append(svg('rect', { class: 'ch-band', x: x(c.band[0]), y: by, width: x(hi(c)) - x(c.band[0]), height: BR_H, rx: BR_H / 2 }));
      bg.append(svg('circle', { class: 'ch-peak', cx: x(c.peak), cy: by + BR_H / 2, r: 7 }));
      bands.append(bg); if (c.family) famBand[c.family] = bg;
    }
    // leader: card anchor → the peak on the bracket
    const px = x(c.peak), py = up ? by : by + BR_H;
    const midY = (p.ay + py) / 2;
    const leader = svg('path', { class: 'ch-leader', 'data-id': c.id, 'data-group': g, d: `M${p.cx} ${p.ay} C${p.cx} ${midY} ${px} ${midY} ${px} ${py}` });
    leaders.append(leader);
    const card = el('button', { class: 'ch-card', type: 'button', 'data-id': c.id, 'data-group': g, style: `left:${p.x}px;top:${p.y}px;width:${p.w}px;height:${p.h}px`, 'aria-haspopup': 'dialog' },
      thumb(c), el('div', { class: 'ch-card__name', text: c.name }), el('div', { class: 'ch-card__range', html: `e<sub>10 Hz</sub> ≈ ${escapeHtml(range(c)).replace(/10\^(-?[\d.]+)/g, '10<sup>$1</sup>')}` }));
    cardsLayer.append(card);
    rowEls[c.id] = { band: bg, card, leader };
  });
  stage.append(s, cardsLayer);
  root.innerHTML = ''; root.append(stage);
  root.removeAttribute('aria-busy');
  // scale the fixed-size stage to the available width
  // scale to fill the width, but never taller than what is left below the heading (footer is 2rem)
  // (the archive shows one slide at a time, so this also has to run when the slide becomes visible — hence the ResizeObserver)
  const fit = () => {
    if (!root.clientWidth) return;                                  // hidden slide: nothing to fit against yet
    const avail = innerHeight - root.getBoundingClientRect().top - 40;
    const sc = Math.max(0.4, Math.min(1, root.clientWidth / W, avail / H));
    stage.style.transform = `scale(${sc})`; stage.style.marginLeft = `${(root.clientWidth - W * sc) / 2}px`; root.style.height = `${H * sc}px`;
  };
  fit(); addEventListener('resize', fit); new ResizeObserver(fit).observe(root);
  const setHot = (id, on) => { const r = rowEls[id]; if (!r) return; [r.band, r.card, r.leader].forEach((n) => n.classList.toggle('hot', on)); };
  root.addEventListener('pointerover', (ev) => { const n = ev.target.closest && ev.target.closest('[data-id]'); if (n) setHot(n.dataset.id, true); });
  root.addEventListener('pointerout', (ev) => { const n = ev.target.closest && ev.target.closest('[data-id]'); if (n && n.dataset.id !== active) setHot(n.dataset.id, false); });
  // hover a card → its YouTube video plays inline (muted, looping); leave → back to the thumbnail
  if (!matchMedia('(hover: none)').matches) {
    rows.forEach((c) => {
      const m = c.media || {}; if (!playable(c)) return;
      const box = rowEls[c.id].card.querySelector('.ch-card__media'); const still = box.innerHTML;
      let timer = null, vid = null;
      if (m.type === 'video') {                                   // Manim clip: one persistent <video> behind the still, play/pause only
        vid = el('video', { class: 'ch-card__video', src: base + m.src, muted: '', loop: '', playsinline: '', preload: 'metadata', tabindex: '-1' });
        vid.muted = true; box.append(vid);
      }
      const play = () => {
        if (vid) { vid.currentTime = 0; box.classList.add('ch-card__media--playing'); vid.play().catch(() => {}); return; }
        box.innerHTML = ''; box.classList.remove('ch-card__media--icon');   // the video fills the box even when the face is an icon
        if (m.type === 'youtube') box.append(el('iframe', { src: `https://www.youtube.com/embed/${m.id}?autoplay=1&mute=1&controls=0&rel=0&loop=1&playlist=${m.id}&modestbranding=1`, title: c.name, allow: 'autoplay; encrypted-media', referrerpolicy: 'strict-origin-when-cross-origin', tabindex: '-1' }));
        else box.append(el('img', { src: base + m.src + '?t=' + Date.now(), alt: '' }));   // cache-bust so the gif restarts from frame 0
      };
      const stop = () => {
        clearTimeout(timer);
        if (vid) { vid.pause(); box.classList.remove('ch-card__media--playing'); return; }
        box.innerHTML = still; box.classList.toggle('ch-card__media--icon', !!c.icon);
      };
      rowEls[c.id].card.addEventListener('pointerenter', () => { clearTimeout(timer); timer = setTimeout(play, 250); });
      rowEls[c.id].card.addEventListener('pointerleave', stop);
    });
  }

  // ---- reference list (from graph.json's refs table, built by tools/channelgraph.py) ---------------
  const REFS = graphs.refs || {};
  function refList(c) {
    const items = (c.papers || []).map((k) => REFS[k]).filter(Boolean).map((r) => ({ ...r }));
    const seen = new Set(items.map((r) => r.arxiv).filter(Boolean));
    for (const src of c.sources || []) {                     // sources that are not among the cited papers join the list
      if (src.arxiv && seen.has(src.arxiv)) continue;
      const [label, title] = src.label.split(' — ');
      const m = label.match(/^(.*?)\s+(\d{4})$/);
      items.push({ label: m ? m[1] : label, year: m ? +m[2] : undefined, title: title || '', arxiv: src.arxiv, url: src.url });
      if (src.arxiv) seen.add(src.arxiv);
    }
    items.sort((p, q) => (p.year || 0) - (q.year || 0));
    if (!items.length) return null;
    const ul = el('ol', { class: 'ch-refs' });
    for (const r of items) {
      const lk = r.arxiv ? `<a href="https://arxiv.org/abs/${escapeHtml(r.arxiv)}" target="_blank" rel="noopener">arXiv:${escapeHtml(r.arxiv)}</a>` : r.doi ? `<a href="https://doi.org/${escapeHtml(r.doi.replace(/^https?:\/\/doi\.org\//, ''))}" target="_blank" rel="noopener">doi</a>` : r.url ? `<a href="${escapeHtml(r.url)}" target="_blank" rel="noopener">link</a>` : '';
      ul.append(el('li', { html: `${escapeHtml(r.label)} ${r.year || ''} ${lk}` }));
    }
    return ul;
  }

  // ---- popup -----------------------------------------------------------------
  const byId = Object.fromEntries(rows.map((c) => [c.id, c]));
  function media(c) {
    const m = c.media || { type: 'none' };
    if (m.type === 'youtube') return el('div', { class: 'ch-media' }, el('iframe', { src: `https://www.youtube.com/embed/${m.id}?rel=0`, title: c.name, allow: 'accelerometer; autoplay; encrypted-media; picture-in-picture', allowfullscreen: '', referrerpolicy: 'strict-origin-when-cross-origin' }));
    if (m.type === 'gif' || m.type === 'video') return el('div', { class: 'ch-media' }, m.type === 'gif' ? el('img', { src: base + m.src, alt: m.caption || c.name }) : el('video', { src: base + m.src, controls: '', autoplay: '', loop: '', muted: '', playsinline: '' }));
    return el('div', { class: 'ch-media ch-media--none', text: m.note || 'No video found yet.' });
  }
  function show(id) {
    const c = byId[id]; if (!c) return;
    if (active) setHot(active, false); active = id; setHot(id, true);
    popup.innerHTML = ''; popup.style.setProperty('--lane', getComputedStyle(rowEls[id].band).getPropertyValue('--lane'));
    popup.append(el('button', { class: 'ch-popup__close', type: 'button', 'aria-label': 'close', text: '×' }));
    popup.append(el('h2', { class: 'ch-popup__title', text: c.name }), el('p', { class: 'ch-popup__sub', text: c.sub }));
    const left = el('div'), right = el('div');
    left.append(el('h4', { text: 'How it evolves' }), media(c));
    if (c.media && c.media.caption) left.append(el('p', { class: 'ch-explain', text: c.media.caption }));   // what the clip shows, beat by beat
    right.append(el('h4', { text: 'Where it lands on the line' }));
    if (c.figure) right.append(el('img', { class: 'ch-fig', src: base + c.figure.src, alt: c.figure.caption }), el('p', { class: 'ch-explain', text: c.figure.caption }));
    popup.append(el('div', { class: 'ch-popup__grid' }, left, right));
    const refs = refList(c);                                        // citations run full-width under both columns
    if (refs) popup.append(el('div', { class: 'ch-popup__refs' }, el('h4', { text: 'References' }), refs));
    popup.hidden = false; popup.scrollTop = 0;
  }
  function hide() { popup.hidden = true; popup.innerHTML = ''; if (active) setHot(active, false); active = null; }
  root.addEventListener('click', (ev) => { const g = ev.target.closest && ev.target.closest('[data-id]'); if (!g) return; ev.stopPropagation(); if (active === g.dataset.id && !popup.hidden) hide(); else show(g.dataset.id); });
  popup.addEventListener('click', (ev) => { ev.stopPropagation(); if (ev.target.closest('.ch-popup__close')) hide(); });
  document.addEventListener('click', () => { if (!popup.hidden) hide(); });
  document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape' && !popup.hidden) { hide(); ev.stopPropagation(); } });
  const c0 = new URLSearchParams(location.search).get('ch'); if (c0 && byId[c0]) show(c0);   // ?ch=agn opens a card's popup directly
})();
