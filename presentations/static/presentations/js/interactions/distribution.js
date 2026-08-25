Presentations.registerInteraction('distribution', {
  input(el, config, submit, prior) {
    const P = Presentations; const bins = config.axis.bins; const w = prior ? prior.weights.slice() : new Array(bins).fill(0);
    const c = P.el('canvas', { class: 'draw' }); el.append(c);
    const lab = P.el('div', { class: 'n', text: `drag to draw your ${config.axis.label || 'x'} distribution · ${config.axis.min} → ${config.axis.max}` }); el.append(lab);
    const b = P.el('button', { class: 'btn btn--primary', text: 'Submit', style: 'margin-top:.4rem', onclick: () => submit({ weights: w }) }); el.append(b);
    const ctx = c.getContext('2d');
    function draw() {
      c.width = c.clientWidth * devicePixelRatio; c.height = c.clientHeight * devicePixelRatio; ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
      const cw = c.clientWidth, ch = c.clientHeight, bw = cw / bins, max = Math.max(1e-9, ...w);
      ctx.clearRect(0, 0, cw, ch); ctx.fillStyle = getComputedStyle(c).getPropertyValue('--accent') || '#37b49f';
      w.forEach((v, i) => { const h = v / max * (ch - 8); ctx.fillRect(i * bw + 1, ch - h, bw - 2, h); });
    }
    let down = false, lastBin = null, lastVal = 0;
    const paint = (e) => {
      const r = c.getBoundingClientRect();
      const i = Math.min(bins - 1, Math.max(0, Math.floor((e.clientX - r.left) / r.width * bins)));
      const v = Math.max(0, 1 - (e.clientY - r.top) / r.height);
      // a fast drag only fires a handful of pointer events: fill the bins it skipped over
      if (lastBin != null && Math.abs(i - lastBin) > 1) {
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
    const P = Presentations; const W = 600, H = 220, pad = 30, bins = config.axis.bins;
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.style.width = '100%';
    const add = (tag, a) => { const n = document.createElementNS('http://www.w3.org/2000/svg', tag); for (const [k, v] of Object.entries(a)) n.setAttribute(k, v); svg.append(n); return n; };
    const max = Math.max(1e-9, ...agg.curves.flat(), ...agg.mean);
    const path = (ws) => ws.map((v, i) => `${i ? 'L' : 'M'}${pad + (i + .5) / bins * (W - 2 * pad)},${H - pad - v / max * (H - 2 * pad)}`).join(' ');
    agg.curves.forEach((ws) => add('path', { d: path(ws), fill: 'none', stroke: 'var(--accent)', 'stroke-opacity': .15, 'stroke-width': 2 }));
    if (agg.n) add('path', { d: path(agg.mean), fill: 'none', stroke: 'var(--accent-2, #e9c46a)', 'stroke-width': 4 });
    add('line', { x1: pad, x2: W - pad, y1: H - pad, y2: H - pad, stroke: 'currentColor', 'stroke-opacity': .4 });
    [agg.edges[0], agg.edges[bins]].forEach((v, k) => { const t = add('text', { x: k ? W - pad : pad, y: H - 8, 'text-anchor': 'middle', 'font-size': 12, fill: 'currentColor' }); t.textContent = v; });
    const lab = add('text', { x: W / 2, y: H - 8, 'text-anchor': 'middle', 'font-size': 12, fill: 'currentColor' }); lab.textContent = config.axis.label || '';
    el.append(svg);
  },
});
