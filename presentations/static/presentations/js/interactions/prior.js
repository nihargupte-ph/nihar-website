// `prior`: the audience draws a probability curve on a log10(e) grid, with who-drew-it metadata.
// Phone: freehand stroke on a canvas + name / institute / expertise, resubmit allowed.
// Screen: every curve as a thin grey line (hover → who), the unweighted mixture, an expertise
// filter row, and — once the poll is closed — two reference priors on the same grid.
Presentations.registerInteraction('prior', {
  slicer: false,        // the plot carries its own expertise filter; skip the generic join-tag row
  // Mirrors EXPERTISE in presentations/interactions/prior.py (the server validates).
  EXPERTISE: ['data analysis', 'waveform model', 'theoretical modelling', 'numerical relativity', 'astrophysics', 'instrumentation', 'other'],
  LABELS: { 'theoretical modelling': 'theoretical modelling (PN, PM, self-force, …)' },

  input(el, config, submit, prior) {
    const P = Presentations; const ax = config.axis; const bins = ax.bins;
    const w = prior ? prior.weights.slice() : new Array(bins).fill(0);
    const me = (P.data.participant && P.data.participant.name) || '';
    const c = P.el('canvas', { class: 'draw draw--prior' }); el.append(c);
    el.append(P.el('div', { class: 'n', text: `drag left → right to draw p(${ax.label || 'x'}) · ${ax.min} → ${ax.max}` }));
    const row = P.el('div', { class: 'prior-row' }); el.append(row);
    row.append(P.el('button', { class: 'btn', text: 'Clear', onclick: () => { w.fill(0); draw(); } }));
    const f = P.el('div', { class: 'prior-form' }); el.append(f);
    const name = P.el('input', { class: 'txt', maxlength: 60, placeholder: 'anonymous', value: prior ? prior.name : me });
    const inst = P.el('input', { class: 'txt', maxlength: 80, placeholder: 'Institute', value: prior ? prior.institute : '' });
    f.append(P.el('label', { text: 'Name' }), name, P.el('label', { text: 'Institute' }), inst, P.el('label', { text: 'Expertise (tick all that apply)' }));
    const boxes = {}; const grid = P.el('div', { class: 'prior-tags' }); f.append(grid);
    const other = P.el('input', { class: 'txt', maxlength: 60, placeholder: 'other: what?', value: prior ? prior.other : '' });
    other.hidden = !(prior && prior.expertise.includes('other'));
    for (const t of this.EXPERTISE) {
      const cb = P.el('input', { type: 'checkbox' }); cb.checked = !!(prior && prior.expertise.includes(t)); boxes[t] = cb;
      if (t === 'other') cb.addEventListener('change', () => { other.hidden = !cb.checked; if (cb.checked) other.focus(); });
      grid.append(P.el('label', {}, [cb, P.el('span', { text: this.LABELS[t] || t })]));
    }
    f.append(other);
    const msg = P.el('div', { class: 'n' }); el.append(msg);
    el.append(P.el('button', { class: 'btn btn--primary', text: 'Submit my prior', style: 'margin-top:.4rem;width:100%', onclick: () => {
      if (!w.some((v) => v > 0)) { msg.textContent = 'draw a curve first'; return; }
      const expertise = this.EXPERTISE.filter((t) => boxes[t].checked);
      submit({ weights: w, name: name.value.trim(), institute: inst.value.trim(), expertise,
               other: expertise.includes('other') ? other.value.trim() : '' });
    } }));
    const ctx = c.getContext('2d');
    const draw = () => {
      c.width = c.clientWidth * devicePixelRatio; c.height = c.clientHeight * devicePixelRatio; ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
      const cw = c.clientWidth, ch = c.clientHeight, pad = 18, max = Math.max(1e-9, ...w);
      const fg = getComputedStyle(c).color || '#888';
      ctx.clearRect(0, 0, cw, ch);
      ctx.strokeStyle = fg; ctx.globalAlpha = .25; ctx.lineWidth = 1; ctx.font = '11px sans-serif'; ctx.fillStyle = fg; ctx.textAlign = 'center';
      for (let t = Math.ceil(ax.min); t <= ax.max; t++) {
        const x = (t - ax.min) / (ax.max - ax.min) * cw;
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, ch - pad); ctx.stroke();
        ctx.globalAlpha = .7; ctx.fillText(String(t), Math.min(cw - 10, Math.max(10, x)), ch - 5); ctx.globalAlpha = .25;
      }
      ctx.globalAlpha = 1;
      if (!w.some((v) => v > 0)) return;
      const accent = getComputedStyle(c).getPropertyValue('--accent') || '#37b49f';
      ctx.beginPath();
      w.forEach((v, i) => { const x = (i + .5) / bins * cw, y = (ch - pad) - v / max * (ch - pad - 8); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
      ctx.strokeStyle = accent; ctx.lineWidth = 3; ctx.lineJoin = 'round'; ctx.stroke();
      ctx.lineTo(cw, ch - pad); ctx.lineTo(0, ch - pad); ctx.closePath(); ctx.fillStyle = accent; ctx.globalAlpha = .18; ctx.fill(); ctx.globalAlpha = 1;
    };
    let down = false, lastBin = null, lastVal = 0;
    const paint = (e) => {
      const r = c.getBoundingClientRect(), pad = 18;
      const i = Math.min(bins - 1, Math.max(0, Math.floor((e.clientX - r.left) / r.width * bins)));
      const v = Math.max(0, Math.min(1, 1 - (e.clientY - r.top) / (r.height - pad)));
      if (lastBin != null && Math.abs(i - lastBin) > 1) {   // fast drags skip bins: interpolate them
        const step = i > lastBin ? 1 : -1;
        for (let k = lastBin + step; k !== i; k += step) w[k] = lastVal + (v - lastVal) * ((k - lastBin) / (i - lastBin));
      }
      w[i] = v; lastBin = i; lastVal = v; draw();
    };
    c.addEventListener('pointerdown', (e) => { down = true; lastBin = null; c.setPointerCapture(e.pointerId); paint(e); });
    c.addEventListener('pointermove', (e) => { if (down) paint(e); });
    c.addEventListener('pointerup', () => { down = false; lastBin = null; }); c.addEventListener('pointercancel', () => { down = false; lastBin = null; });
    requestAnimationFrame(draw); addEventListener('resize', draw);
  },

  aggregate(el, config, agg, ctx) {
    const P = Presentations; const self = this;
    const st = { agg, filter: 'all', hover: null, config };
    el._prior = st;
    const wrap = P.el('div', { class: 'prior-agg' }); el.append(wrap);
    const clock = P.el('div', { class: 'prior-clock' }); wrap.append(clock);
    const tick = () => {
      const until = P.pollDeadline && P.pollDeadline(el.closest('[data-iid]') ? el.closest('[data-iid]').dataset.iid : '');
      if (!until || st.agg.state !== 'open') { clock.textContent = ''; clock.classList.remove('prior-clock--low'); return; }
      const left = Math.max(0, Math.round((until - Date.now()) / 1000));
      clock.textContent = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}`;
      clock.classList.toggle('prior-clock--low', left <= 15);
    };
    tick(); const clockTimer = setInterval(tick, 250);
    st.stopClock = () => clearInterval(clockTimer);
    const slice = P.el('div', { class: 'slice prior-filter' }); wrap.append(slice);
    const rebuildFilter = () => {
      slice.innerHTML = '';
      for (const t of ['all', ...self.EXPERTISE]) {
        const n = t === 'all' ? st.agg.curves.length : st.agg.curves.filter((c) => c.expertise.includes(t)).length;
        slice.append(P.el('button', { class: 'btn' + (t === st.filter ? ' on' : ''), text: `${t} (${n})`, onclick: () => { st.filter = t; st.hover = null; redraw(); } }));
      }
    };
    const W = 1000, H = 440, L = 56, R = 20, T = 16, B = 44;
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.classList.add('prior-plot'); wrap.append(svg);
    const tip = P.el('div', { class: 'prior-tip' }); tip.hidden = true; wrap.append(tip);
    const legend = P.el('div', { class: 'prior-legend' }); wrap.append(legend);
    const ns = (tag, a, parent) => { const n = document.createElementNS('http://www.w3.org/2000/svg', tag); for (const [k, v] of Object.entries(a)) n.setAttribute(k, v); (parent || svg).append(n); return n; };
    const redraw = () => {
      const a = st.agg, ax = st.config.axis, bins = ax.bins;
      const shown = a.curves.map((c, i) => ({ c, i })).filter(({ c }) => st.filter === 'all' || c.expertise.includes(st.filter));
      const mean = shown.length ? Array.from({ length: bins }, (_, k) => shown.reduce((s, { c }) => s + c.weights[k], 0) / shown.length) : null;
      const closed = a.state === 'closed' || a.state === 'revealed';
      const cmp = closed ? a.comparisons : null;
      const ymax = Math.max(1e-9, ...shown.flatMap(({ c }) => c.weights), ...(mean || []), ...(cmp ? cmp.log_uniform : []));
      const clipped = cmp && Math.max(...cmp.uniform) > ymax * 1.02;
      const X = (k) => L + (k + .5) / bins * (W - L - R);
      const Y = (v) => T + (H - T - B) * (1 - Math.min(v, ymax) / ymax);
      const path = (ws) => ws.map((v, k) => `${k ? 'L' : 'M'}${X(k).toFixed(1)},${Y(v).toFixed(1)}`).join(' ');
      svg.innerHTML = '';
      if (st.hover == null || !shown.some(({ i }) => i === st.hover)) { st.hover = null; tip.hidden = true; }   // rebuilding the paths swallows pointerleave
      // axes
      ns('line', { x1: L, x2: W - R, y1: H - B, y2: H - B, stroke: 'currentColor', 'stroke-opacity': .5 });
      ns('line', { x1: L, x2: L, y1: T, y2: H - B, stroke: 'currentColor', 'stroke-opacity': .5 });
      for (let t = Math.ceil(ax.min); t <= ax.max; t++) {
        const x = L + (t - ax.min) / (ax.max - ax.min) * (W - L - R);
        ns('line', { x1: x, x2: x, y1: T, y2: H - B, stroke: 'currentColor', 'stroke-opacity': .1 });
        const tx = ns('text', { x, y: H - B + 20, 'text-anchor': 'middle', 'font-size': 15, fill: 'currentColor' }); tx.textContent = t;
      }
      const xl = ns('text', { x: (L + W - R) / 2, y: H - 6, 'text-anchor': 'middle', 'font-size': 15, fill: 'currentColor' }); xl.textContent = ax.label || '';
      const yl = ns('text', { x: 16, y: (T + H - B) / 2, 'text-anchor': 'middle', 'font-size': 15, fill: 'currentColor', transform: `rotate(-90 16 ${(T + H - B) / 2})` }); yl.textContent = 'p(' + (ax.label || 'x') + ')';
      if (cmp) {
        ns('path', { d: path(cmp.log_uniform), fill: 'none', stroke: 'currentColor', 'stroke-opacity': .8, 'stroke-width': 2.5, 'stroke-dasharray': '10 6' });
        ns('path', { d: path(cmp.uniform), fill: 'none', stroke: 'currentColor', 'stroke-opacity': .8, 'stroke-width': 2.5, 'stroke-dasharray': '3 5' });
      }
      // audience curves: thin grey lines + a fat invisible hit target each
      for (const { c, i } of shown) {
        const on = st.hover === i;
        ns('path', { d: path(c.weights), fill: 'none', stroke: on ? 'var(--accent)' : 'currentColor', 'stroke-opacity': on ? 1 : .35, 'stroke-width': on ? 4 : 1.5, 'data-i': i });
      }
      if (mean) ns('path', { d: path(mean), fill: 'none', stroke: 'var(--accent-2, #e9c46a)', 'stroke-width': 5, 'stroke-linejoin': 'round' });
      for (const { c, i } of shown) {
        const hit = ns('path', { d: path(c.weights), fill: 'none', stroke: 'transparent', 'stroke-width': 14, class: 'prior-hit', 'data-i': i });
        hit.addEventListener('pointerenter', (e) => { st.hover = i; showTip(e, c); redraw(); });
        hit.addEventListener('pointermove', (e) => showTip(e, c));
        hit.addEventListener('pointerleave', () => { st.hover = null; tip.hidden = true; redraw(); });
      }
      if (!shown.length) { const t = ns('text', { x: (L + W - R) / 2, y: (T + H - B) / 2, 'text-anchor': 'middle', 'font-size': 20, fill: 'currentColor', 'fill-opacity': .6 }); t.textContent = a.curves.length ? 'nobody in this group yet' : 'waiting for the first curve…'; }
      legend.innerHTML = '';
      const item = (cls, text) => legend.append(P.el('span', { class: 'prior-legend__item' }, [P.el('i', { class: cls }), P.el('span', { text })]));
      item('curve', `one participant (${shown.length}${st.filter === 'all' ? '' : ' of ' + a.curves.length})`);
      item('mean', 'mixture (unweighted mean)');
      if (cmp) { item('logu', 'log-uniform, e ≥ 10⁻⁴'); item('uni', 'uniform in e on [0, 1]' + (clipped ? ' (clipped at top)' : '')); }
      rebuildFilter();
    };
    const showTip = (e, c) => {
      const who = [c.name || 'anonymous', c.institute].filter(Boolean).join(' · ');   // blank name reads as anonymous
      const tags = c.expertise.map((t) => (t === 'other' && c.other ? `other: ${c.other}` : t)).join(', ');
      tip.innerHTML = `<b>${P.escape(who)}</b><br>${P.escape(tags || 'no expertise given')}`;
      tip.hidden = false;
      const r = wrap.getBoundingClientRect();
      tip.style.left = Math.min(r.width - 260, e.clientX - r.left + 14) + 'px'; tip.style.top = (e.clientY - r.top + 14) + 'px';
    };
    st.redraw = redraw;
    redraw();
  },

  // Called by widgets.js on each re-poll instead of rebuilding: keeps the filter and the hover.
  update(el, config, agg) {
    const st = el._prior; if (!st) return false;
    if (!el.isConnected) { st.stopClock(); return false; }
    st.agg = agg; st.config = config; st.redraw(); return true;
  },
});
