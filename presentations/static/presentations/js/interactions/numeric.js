Presentations.registerInteraction('numeric', {
  input(el, config, submit, prior) {
    const P = Presentations;
    const v = P.el('input', { class: 'num', type: 'number', step: 'any', placeholder: config.unit ? `value (${config.unit})` : 'value', value: prior ? prior.value : '' });
    const e = P.el('input', { class: 'num', type: 'number', step: 'any', min: '0', placeholder: '± uncertainty (optional)', value: prior && prior.err != null ? prior.err : '', style: 'margin-top:.4rem' });
    const b = P.el('button', { class: 'btn btn--primary', text: 'Submit', style: 'margin-top:.5rem', onclick: () => submit({ value: v.value, err: e.value }) });
    el.append(v, e, b);
  },
  aggregate(el, config, agg, ctx) {
    const P = Presentations; const W = 600, H = 140, pad = 40;
    const vals = agg.values; if (!vals.length) { el.append(P.el('div', { class: 'too-small', text: 'no responses' })); return; }
    const all = vals.concat(config.truth != null && ctx.revealed ? [config.truth] : []);
    const f = config.log ? Math.log10 : (x) => x, g = config.log ? (x) => Math.pow(10, x) : (x) => x;
    let lo = Math.min(...all.map(f)), hi = Math.max(...all.map(f)); if (hi === lo) { lo -= 1; hi += 1; }
    const X = (x) => pad + (f(x) - lo) / (hi - lo) * (W - 2 * pad);
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.style.width = '100%';
    const add = (tag, a) => { const n = document.createElementNS('http://www.w3.org/2000/svg', tag); for (const [k, v] of Object.entries(a)) n.setAttribute(k, v); svg.append(n); return n; };
    add('line', { x1: pad, x2: W - pad, y1: H - 30, y2: H - 30, stroke: 'currentColor', 'stroke-opacity': .4 });
    [lo, (lo + hi) / 2, hi].forEach((t) => { const tx = add('text', { x: X(g(t)), y: H - 10, 'text-anchor': 'middle', 'font-size': 12, fill: 'currentColor' }); tx.textContent = Number(g(t).toPrecision(3)); });
    vals.forEach((v, i) => { const err = agg.errs[i]; if (err) add('line', { x1: X(Math.max(v - err, config.log ? v / 10 : v - err)), x2: X(v + err), y1: 50 + (i % 5) * 10, y2: 50 + (i % 5) * 10, stroke: 'var(--accent)', 'stroke-opacity': .35 }); add('circle', { cx: X(v), cy: 50 + (i % 5) * 10, r: 5, fill: 'var(--accent)', 'fill-opacity': .7 }); });
    if (agg.median != null) { add('line', { x1: X(agg.median), x2: X(agg.median), y1: 20, y2: H - 30, stroke: 'var(--fg)', 'stroke-dasharray': '4 3' }); const t = add('text', { x: X(agg.median), y: 14, 'text-anchor': 'middle', 'font-size': 12, fill: 'currentColor' }); t.textContent = 'median ' + Number(agg.median.toPrecision(3)); }
    if (ctx.revealed && config.truth != null) { add('line', { x1: X(config.truth), x2: X(config.truth), y1: 20, y2: H - 30, stroke: 'var(--accent-2, #e9c46a)', 'stroke-width': 3 }); const t = add('text', { x: X(config.truth), y: H - 34, 'text-anchor': 'middle', 'font-size': 12, fill: 'var(--accent-2, #e9c46a)' }); t.textContent = 'true ' + config.truth; }
    el.append(svg);
  },
});
