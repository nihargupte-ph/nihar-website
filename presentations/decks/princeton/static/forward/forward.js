// Forward-model pipeline (16-forward.html). The template is on the page eight times (fwd-1..8, the
// reveal steps), and on the archive page all copies are in the DOM at once, so one shared state
// drives every copy: the current draw (a host and a row of that host's precomputed pool). Nothing
// here is physics -- forward.json holds every sample and curve (tools/forwardmodel.py); this file
// only picks samples and draws them.
(function () {
  const roots = [...document.querySelectorAll('.fwd:not([data-done])')];
  if (!roots.length) return;
  roots.forEach((r) => { r.dataset.done = '1'; });

  // seeded so that every viewer (and every reload) starts on the same draw
  let seed = 20261020;
  const rand = () => { seed |= 0; seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };

  const S = { beta: 0.16, cur: null, d: null };   // beta: the paper's posterior median, 0.16 (+0.31 / -0.16)
  const NS = 'http://www.w3.org/2000/svg';
  const minus = (s) => String(s).replace(/-/g, '−');
  const kms = (v) => (v >= 100 ? v.toFixed(0) : v.toFixed(1));
  const loge = (e) => minus(Math.log10(Math.max(e, 1e-30)).toFixed(2));   // the talk quotes eccentricities as log10 e

  function drawOne() {
    const host = rand() < S.beta ? 'nsc' : 'gc';
    const pool = S.d.pool[host];
    const [sigma, m1, m2, e, vinf, , rp] = pool[Math.floor(rand() * pool.length)];
    return { host, sigma, m1, m2, e, vinf, rp };
  }

  // --- tiny svg helpers -------------------------------------------------------------------
  const el = (tag, attrs = {}, text) => { const n = document.createElementNS(NS, tag); for (const k in attrs) n.setAttribute(k, attrs[k]); if (text != null) rich(n, text); return n; };
  // svg text with subscripts: "e_{10 Hz}" -> e + a lowered, smaller tspan (dy, since Firefox ignores baseline-shift)
  function rich(n, text) {
    String(text).split(/(_\{[^}]*\})/).forEach((part) => {
      if (!part) return;
      const m = part.match(/^_\{(.*)\}$/);
      if (!m) { n.append(part); return; }
      const t = document.createElementNS(NS, 'tspan'); t.setAttribute('dy', '0.4em'); t.setAttribute('font-size', '75%'); t.textContent = m[1];
      const back = document.createElementNS(NS, 'tspan'); back.setAttribute('dy', '-0.3em'); back.textContent = '\u200b';
      n.append(t, back);
    });
  }
  function axes(svg, { W, H, L = 46, R = 10, T = 12, B = 36, x0, x1, y0, y1, xticks, yticks, xlab, ylab, ylog = false, tickDy = 15 }) {
    svg.replaceChildren();
    const px = (x) => L + (x - x0) / (x1 - x0) * (W - L - R);
    const yv = (y) => (ylog ? Math.log10(Math.max(y, 1e-30)) : y);
    const py = (y) => H - B - (yv(y) - yv(y0)) / (yv(y1) - yv(y0)) * (H - B - T);
    svg.append(el('path', { class: 'ax', d: `M${L} ${T}V${H - B}H${W - R}` }));
    for (const t of xticks || []) {
      svg.append(el('path', { class: 'ax', d: `M${px(t)} ${H - B}v4` }));
      svg.append(el('text', { class: 'tick', x: px(t), y: H - B + tickDy, 'text-anchor': 'middle' }, minus(t)));
    }
    for (const [t, lab] of yticks || []) {
      svg.append(el('path', { class: 'ax', d: `M${L} ${py(t)}h-4` }));
      svg.append(el('text', { class: 'tick', x: L - 6, y: py(t) + 4, 'text-anchor': 'end' }, lab));
    }
    if (xlab) svg.append(el('text', { class: 'lbl', x: (L + W - R) / 2, y: H - 5, 'text-anchor': 'middle' }, xlab));
    if (ylab) svg.append(el('text', { class: 'lbl', x: 12, y: (T + H - B) / 2, 'text-anchor': 'middle', transform: `rotate(-90 12 ${(T + H - B) / 2})` }, ylab));
    return { px, py, L, R, T, B, W, H };
  }
  const line = (xs, ys, px, py) => xs.map((x, i) => `${i ? 'L' : 'M'}${px(x).toFixed(1)} ${py(ys[i]).toFixed(1)}`).join('');
  const stepPath = (edges, vals, px, py, base) => {
    let d = `M${px(edges[0]).toFixed(1)} ${py(base).toFixed(1)}`;
    vals.forEach((v, i) => { d += `V${py(v).toFixed(1)}H${px(edges[i + 1]).toFixed(1)}`; });
    return d + `V${py(base).toFixed(1)}`;
  };
  const clampX = (x, a, b) => Math.min(b, Math.max(a, x));

  // --- card 1: host --------------------------------------------------------------------------
  function renderHost(root) {
    root.querySelectorAll('.fwd__hosts figure').forEach((f) => f.classList.toggle('is-drawn', f.dataset.host === S.cur.host));
    root.querySelectorAll('[data-ctl="beta"]').forEach((i) => { i.value = S.beta; });
    root.querySelectorAll('[data-out="beta"]').forEach((o) => { o.textContent = S.beta.toFixed(2); });
    root.querySelector('[data-split="gc"]').style.flexGrow = 1 - S.beta;
    root.querySelector('[data-split="nsc"]').style.flexGrow = S.beta;
  }

  // --- card 2: the two log-normal fits and the drawn sigma ------------------------------------
  function renderSigma(root) {
    const svg = root.querySelector('[data-plot="sigma"]'), H = S.d.hosts;
    const x0 = -0.5, x1 = 2.75, gauss = (x, { mu, std }) => Math.exp(-0.5 * ((x - mu) / std) ** 2) / (std * Math.sqrt(2 * Math.PI));
    const peak = Math.max(gauss(H.gc.mu, H.gc), gauss(H.nsc.mu, H.nsc));
    const a = axes(svg, { W: 400, H: 320, x0, x1, y0: 0, y1: peak * 1.12, xticks: [0, 1, 2], xlab: 'log₁₀ σ / (km s⁻¹)', ylab: 'p(log₁₀ σ)' });
    const xs = Array.from({ length: 200 }, (_, i) => x0 + (x1 - x0) * i / 199);
    for (const h of ['gc', 'nsc']) {
      const ys = xs.map((x) => gauss(x, H[h]));
      svg.append(el('path', { class: `fit--${h}`, d: `${line(xs, ys, a.px, a.py)}L${a.px(x1)} ${a.py(0)}L${a.px(x0)} ${a.py(0)}Z` }));
    }
    svg.append(el('text', { class: 'lbl lbl--gc', x: a.px(H.gc.mu), y: a.py(gauss(H.gc.mu, H.gc)) - 8, 'text-anchor': 'middle' }, `GC  ${H.gc.n} (Gaia)`));
    svg.append(el('text', { class: 'lbl lbl--nsc', x: a.px(H.nsc.mu), y: a.py(gauss(H.nsc.mu, H.nsc)) - 8, 'text-anchor': 'middle' }, `NSC  ${H.nsc.n} (HST)`));
    const xd = clampX(Math.log10(S.cur.sigma), x0, x1);
    svg.append(el('path', { class: 'marker', d: `M${a.px(xd)} ${a.py(0)}V${a.py(0.82 * peak)}` }));
    const right = xd > 1.2;                                  // label on the side away from the peaks' labels
    svg.append(el('rect', { x: a.px(xd) + (right ? -104 : 4), y: a.py(0.5 * peak) - 13, width: 100, height: 18, fill: '#f1efe9', opacity: 0.85 }));
    svg.append(el('text', { class: 'lbl lbl--teal', x: a.px(xd) + (right ? -6 : 6), y: a.py(0.5 * peak), 'text-anchor': right ? 'end' : 'start' }, `σ = ${kms(S.cur.sigma)} km/s`));
  }

  // card 2 visual: stars jiggling at a speed set by the drawn sigma (only visible copies animate)
  const swarms = [];
  function initSwarm(root) {
    const svg = root.querySelector('.fwd__swarm');
    svg.replaceChildren(el('circle', { class: 'bg', cx: 150, cy: 150, r: 146 }));
    const stars = [];
    for (let i = 0; i < 110; i++) {
      const r = 128 * Math.sqrt(Math.random()), t = 2 * Math.PI * Math.random();
      const c = el('circle', { class: 'star', r: (0.8 + 1.6 * Math.random()).toFixed(2), opacity: (0.45 + 0.55 * Math.random()).toFixed(2) });
      svg.append(c);
      stars.push({ c, x: 150 + r * Math.cos(t), y: 150 + r * Math.sin(t), a: 2 * Math.PI * Math.random() });
    }
    const label = el('text', { x: 150, y: 262, 'text-anchor': 'middle' });
    svg.append(label);
    swarms.push({ svg, stars, label });
  }
  function tick() {
    const speed = 0.12 * Math.sqrt(S.cur ? S.cur.sigma : 5);       // px/frame; sqrt keeps 1 and 300 km/s both visible
    for (const sw of swarms) {
      if (sw.svg.getBoundingClientRect().width === 0) continue;
      for (const s of sw.stars) {
        s.a += (Math.random() - 0.5) * 0.6;
        s.x += speed * Math.cos(s.a); s.y += speed * Math.sin(s.a);
        const dx = s.x - 150, dy = s.y - 150, r = Math.hypot(dx, dy);
        if (r > 132) { s.a = Math.atan2(-dy, -dx) + (Math.random() - 0.5); s.x = 150 + dx * 131 / r; s.y = 150 + dy * 131 / r; }
        s.c.setAttribute('cx', s.x.toFixed(1)); s.c.setAttribute('cy', s.y.toFixed(1));
      }
      sw.label.textContent = `σ = ${kms(S.cur.sigma)} km/s`;
    }
    requestAnimationFrame(tick);
  }

  // --- card 3: the capture, equation by equation -----------------------------------------------
  function renderBinary(root) {
    const c = S.cur, set = (k, html) => { root.querySelector(`[data-val="${k}"]`).innerHTML = html; };
    set('m', `m₁ = ${c.m1.toFixed(0)}, m₂ = ${c.m2.toFixed(0)} M☉`);
    set('v', `v<sub>∞</sub> = ${kms(c.vinf)} km/s`);
    // r_p comes in GM/c^2 of the drawn binary; GM_sun/c^2 = 1.4766 km
    const km = c.rp * (c.m1 + c.m2) * 1.4766, k = Math.floor(Math.log10(km)), sup = (n) => String(n).replace(/\d/g, (d) => '⁰¹²³⁴⁵⁶⁷⁸⁹'[d]);
    set('rp', `r<sub>p</sub> = ${km < 1e4 ? Math.round(km).toLocaleString('en') : (km / 10 ** k).toFixed(1) + ' × 10' + sup(k)} km`);
    set('e', `log<sub>10</sub> e = ${loge(c.e)}`);
  }
  function renderMass(root) {
    const svg = root.querySelector('[data-plot="mass"]'), m = S.d.mass;
    const a = axes(svg, { W: 300, H: 400, L: 56, B: 40, x0: 0, x1: 100, y0: 1e-4, y1: 0.3, ylog: true, xticks: [0, 50, 100], yticks: [[1e-4, '10⁻⁴'], [1e-2, '10⁻²']], xlab: 'mass / M☉', ylab: 'p(m₁)' });
    svg.append(el('path', { class: 'curve', d: line(m.m, m.p.map((p) => Math.max(p, 1e-4)), a.px, a.py) }));
    svg.append(el('path', { class: 'marker', d: `M${a.px(S.cur.m1)} ${a.py(1e-4)}V${a.T + 6}` }));
    svg.append(el('path', { class: 'marker--dash', d: `M${a.px(S.cur.m2)} ${a.py(1e-4)}V${a.T + 6}` }));
    svg.append(el('text', { class: 'lbl lbl--teal', x: a.W - 12, y: a.T + 16, 'text-anchor': 'end' }, `m₁ ${S.cur.m1.toFixed(0)}`));
    svg.append(el('text', { class: 'lbl lbl--teal', x: a.W - 12, y: a.T + 32, 'text-anchor': 'end' }, `m₂ ${S.cur.m2.toFixed(0)} (dashed)`));
  }
  function renderEcc(root) {
    const svg = root.querySelector('[data-plot="ecc"]'), L = S.d.loge;
    let best = S.d.curves[0];
    for (const c of S.d.curves) if (Math.abs(Math.log(c.sigma / S.cur.sigma)) < Math.abs(Math.log(best.sigma / S.cur.sigma))) best = c;
    const ymax = Math.max(...best.p) * 1.18 || 1;
    const a = axes(svg, { W: 300, H: 400, L: 34, B: 40, x0: L.min, x1: L.max, y0: 0, y1: ymax, xticks: [-4, -3, -2, -1, 0], xlab: 'log₁₀ e_{10 Hz}', ylab: 'p(log₁₀ e | σ)' });
    svg.append(el('path', { class: 'curve--fill', d: stepPath(L.edges, best.p, a.px, a.py, 0) }));
    const le = Math.log10(Math.max(S.cur.e, 1e-30));
    if (le >= L.min) {
      svg.append(el('path', { class: 'marker', d: `M${a.px(le)} ${a.py(0)}V${a.T + 18}` }));
      svg.append(el('text', { class: 'lbl lbl--teal', x: le > -1.6 ? a.px(le) - 5 : a.px(le) + 5, y: a.T + 12, 'text-anchor': le > -1.6 ? 'end' : 'start' }, `log₁₀ e = ${loge(S.cur.e)}`));
    } else {
      svg.append(el('text', { class: 'lbl lbl--teal', x: a.px(L.min) + 4, y: a.T + 12 }, `← log₁₀ e = ${loge(S.cur.e)}`));
    }
  }

  // --- card 4: the eccentric signal, and a quasi-circular bank scanned template by template -----
  // forward.json `bank` holds, per template, its match against this signal and the template already
  // shifted and phase-rotated onto it (tools/forwardmodel.py); the scan below only replays those.
  const SCAN_MS = 420, SCAN_DELAY = 900;               // per template; the delay lets the card slide in
  const BANK = { L: 70, T: 60, W: 252, H: 360 };      // the bank's box inside its 330 x 500 viewBox
  function renderWave(root) {
    const svg = root.querySelector('[data-plot="wave"]'), w = S.d.waveforms;
    const a = axes(svg, { W: 520, H: 500, L: 14, R: 14, B: 56, x0: -1.2, x1: 0.05, y0: -1.15, y1: 1.15, xticks: [-1, -0.5, 0], tickDy: 20, xlab: 'time to merger [s]' });
    const qc = el('path', { class: 'wave--qc' });
    svg.append(qc, el('path', { class: 'wave--ecc', d: line(w.eccentric.t, w.eccentric.h, a.px, a.py) }));
    svg.append(el('text', { class: 'lbl lbl--teal', x: a.L + 8, y: a.T + 14 }, `eccentric signal (log₁₀ e_{10 Hz} = ${loge(w.e)})`));
    const lab = el('text', { class: 'lbl lbl--qc', x: a.L + 8, y: a.T + 36 });
    svg.append(lab);
    root._wave = { qc, lab, a };
  }
  function renderBank(root) {
    const svg = root.querySelector('[data-plot="bank"]'), b = S.d.bank, t = S.d.waveforms.eccentric.t;
    const nc = b.q.length, nr = b.mc.length, cw = BANK.W / nc, ch = BANK.H / nr;
    const lo = Math.min(...b.templates.map((r) => r.snr)), hi = Math.max(...b.templates.map((r) => r.snr));
    const tail = t.findIndex((x) => x > -0.32);       // a thumbnail is each template's last ~0.35 s
    svg.replaceChildren(el('text', { class: 'lbl bank__title', x: BANK.L + BANK.W / 2, y: 20, 'text-anchor': 'middle' }, 'quasi-circular template bank'));
    b.q.forEach((q, j) => svg.append(el('text', { class: 'tick', x: BANK.L + (j + 0.5) * cw, y: BANK.T - 8, 'text-anchor': 'middle' }, `q ${q}`)));
    b.mc.forEach((mc, i) => svg.append(el('text', { class: 'tick', x: BANK.L - 6, y: BANK.T + (i + 0.5) * ch + 4, 'text-anchor': 'end' }, String(mc))));
    const my = BANK.T + BANK.H / 2;
    svg.append(el('text', { class: 'lbl', x: 16, y: my, 'text-anchor': 'middle', transform: `rotate(-90 16 ${my})` }, 'chirp mass / M☉'));
    const cells = b.templates.map((r, k) => {
      const x = BANK.L + (k % nc) * cw, y = BANK.T + Math.floor(k / nc) * ch;
      const g = el('g', { class: 'bank__cell' });
      const bg = el('rect', { x: x + 1.5, y: y + 1.5, width: cw - 3, height: ch - 3, class: 'bank__bg' });
      const px = (i) => x + 5 + (i - tail) / (t.length - 1 - tail) * (cw - 10), py = (h) => y + ch * 0.34 - h * ch * 0.22;
      const d = r.h.slice(tail).map((h, i) => `${i ? 'L' : 'M'}${px(i + tail).toFixed(1)} ${py(h).toFixed(1)}`).join('');
      const snr = el('text', { class: 'bank__snr', x: x + cw / 2, y: y + ch - 7, 'text-anchor': 'middle' }, r.snr.toFixed(1));
      g.append(bg, el('path', { class: 'bank__wave', d }), snr);
      svg.append(g);
      return { g, bg, x, y, heat: (r.snr - lo) / (hi - lo) };
    });
    svg.append(el('rect', { class: 'bank__box', x: BANK.L, y: BANK.T, width: BANK.W, height: BANK.H }));
    const scan = el('rect', { class: 'bank__scan', x: 0, y: 0, width: cw, height: ch });
    const now = el('text', { class: 'lbl lbl--qc', x: BANK.L + BANK.W / 2, y: BANK.T + BANK.H + 30, 'text-anchor': 'middle' });
    const best = el('text', { class: 'lbl bank__best', x: BANK.L + BANK.W / 2, y: BANK.T + BANK.H + 54, 'text-anchor': 'middle' });
    svg.append(scan, now, best);
    root._bank = { cells, scan, now, best, k: -1, timer: 0, shown: false };
    showTemplate(root, bestIndex(), true);
  }
  const bestIndex = () => { const t = S.d.bank.templates; return t.reduce((m, r, k) => (r.snr > t[m].snr ? k : m), 0); };
  // put template k on the waveform plot and the scan box on its cell; `done` = the scan has finished
  function showTemplate(root, k, done) {
    const b = S.d.bank, r = b.templates[k], B = root._bank, W = root._wave, c = B.cells[k];
    W.qc.setAttribute('d', line(S.d.waveforms.eccentric.t, r.h, W.a.px, W.a.py));
    W.lab.replaceChildren();
    rich(W.lab, `quasi-circular template (𝓜 = ${r.mc}, q = ${r.q})`);
    B.scan.style.transform = `translate(${c.x}px, ${c.y}px)`;
    B.scan.classList.toggle('is-best', done);
    B.now.textContent = done ? '' : `trying 𝓜 = ${r.mc}, q = ${r.q}: SNR ${r.snr.toFixed(1)}`;
    const seen = done ? b.templates : b.templates.slice(0, k + 1);
    const top = seen.reduce((m, x) => (x.snr > m.snr ? x : m));
    B.best.textContent = `${done ? 'best-fit' : 'best so far:'} SNR ${top.snr.toFixed(1)}` + (done ? `  (optimal ${b.rho_opt.toFixed(1)})` : '');
    B.cells.forEach((cell, i) => {
      const on = done || i <= k;
      cell.g.classList.toggle('is-seen', on);
      cell.bg.style.fillOpacity = on ? (0.1 + 0.5 * cell.heat).toFixed(2) : '';
    });
  }
  function startScan(root) {
    const B = root._bank;
    clearTimeout(B.timer);
    B.k = -1;
    B.cells.forEach((c) => { c.g.classList.remove('is-seen'); c.bg.style.fillOpacity = ''; });
    const step = () => {
      B.k += 1;
      if (B.k >= S.d.bank.templates.length) { showTemplate(root, bestIndex(), true); return; }
      showTemplate(root, B.k, false);
      B.timer = setTimeout(step, SCAN_MS);
    };
    B.timer = setTimeout(step, SCAN_DELAY);
  }
  // the scan plays when card 4 arrives (step 8) and only then: at step 9 the card is still on screen
  // and keeps the finished best-fit it was built with (slides are display:none, cards visibility:hidden)
  function watchBanks() {
    for (const r of roots) {
      const card = r.querySelector('[data-n="4"]'), B = r._bank;
      if (!B) continue;
      const vis = card.getBoundingClientRect().width > 0 && getComputedStyle(card).visibility === 'visible';
      if (vis && !B.shown && r.dataset.step === '8') startScan(r);
      if (!vis && B.shown) clearTimeout(B.timer);
      B.shown = vis;
    }
  }

  // --- card 5: p_det(e) of the fiducial binary; the draw is marked only by its e ---------------
  function renderPdet(root) {
    const svg = root.querySelector('[data-plot="pdet"]'), p = S.d.pdet;
    const a = axes(svg, { W: 440, H: 250, L: 52, x0: 0, x1: 0.6, y0: 0.34, y1: 0.5, xticks: [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6], yticks: [[0.35, '0.35'], [0.4, '0.40'], [0.45, '0.45']], xlab: 'e_{10 Hz}', ylab: 'p_{det}(θ)' });
    svg.append(el('path', { class: 'pdet--fixed', d: line(p.fixed.e, p.fixed.pdet, a.px, a.py) }));
    svg.append(el('path', { class: 'pdet--avg', d: line(p.averaged.e, p.averaged.pdet, a.px, a.py) }));
    if (S.cur.e <= 0.6) {
      const x = a.px(S.cur.e);
      svg.append(el('path', { class: 'marker--dash', d: `M${x} ${a.py(0.34)}V${a.T + 4}` }));
      svg.append(el('text', { class: 'lbl lbl--teal', x: x + (S.cur.e > 0.35 ? -6 : 6), y: a.T + 14, 'text-anchor': S.cur.e > 0.35 ? 'end' : 'start' }, `your binary: log₁₀ e = ${loge(S.cur.e)}`));
    }
    const lx = a.px(0.02), ly = a.py(0.375);
    svg.append(el('rect', { x: lx - 6, y: ly - 13, width: 160, height: 42, fill: '#f1efe9', opacity: 0.92 }));
    svg.append(el('path', { d: `M${lx} ${ly}h22`, stroke: '#4c72b0', 'stroke-width': 1.4 }));
    svg.append(el('text', { class: 'lbl', x: lx + 28, y: ly + 4 }, 'Fixed anomaly'));
    svg.append(el('path', { d: `M${lx} ${ly + 18}h22`, stroke: '#dd8452', 'stroke-width': 2.2 }));
    svg.append(el('text', { class: 'lbl', x: lx + 28, y: ly + 22 }, 'Anomaly averaged'));
  }

  function readout() {
    const c = S.cur;
    const txt = `<b class="${c.host}">${c.host.toUpperCase()}</b> · σ = ${kms(c.sigma)} km/s · m₁ = ${c.m1.toFixed(0)}, m₂ = ${c.m2.toFixed(0)} M☉ · v∞ = ${kms(c.vinf)} km/s · log<sub>10</sub> e<sub>10 Hz</sub> = ${loge(c.e)}`;
    roots.forEach((r) => { r.querySelector('.fwd__readout').innerHTML = txt; });
  }
  function renderAll() {
    readout();
    for (const r of roots) { renderHost(r); renderSigma(r); renderBinary(r); renderMass(r); renderEcc(r); renderPdet(r); }
  }
  function draw() { S.cur = drawOne(); renderAll(); }

  fetch(roots[0].dataset.src).then((r) => r.json()).then((d) => {
    S.d = d;
    roots.forEach(initSwarm);
    roots.forEach((r) => { renderWave(r); renderBank(r); });   // card 4 does not depend on the draw
    draw();
    for (const r of roots) {
      r.addEventListener('click', (ev) => {
        if (!ev.target.closest('[data-act="draw"]')) return;
        ev.stopPropagation();                          // a click here is not "next slide"
        draw();
      });
      r.querySelector('[data-plot="bank"]').addEventListener('click', (ev) => { ev.stopPropagation(); startScan(r); });   // replay
      r.querySelectorAll('[data-ctl="beta"]').forEach((inp) => {
        inp.addEventListener('input', () => { S.beta = Number(inp.value); roots.forEach(renderHost); });
        inp.addEventListener('keydown', (ev) => ev.stopPropagation());   // arrow keys move the slider, not the deck
      });
    }
    requestAnimationFrame(tick);
    setInterval(watchBanks, 150);
  });

  // KaTeX is deferred like this script; typeset each copy once it is there
  const typeset = () => roots.forEach((r) => window.renderMathInElement && renderMathInElement(r, { delimiters: [{ left: '\\(', right: '\\)', display: false }], throwOnError: false }));
  if (window.renderMathInElement) typeset(); else addEventListener('load', typeset);
})();
