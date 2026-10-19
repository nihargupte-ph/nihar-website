// Spike-and-slab prior toy: pi(e) = w delta(e) + (1-w) U(e), with a Gaussian likelihood
// L(e) shared by every panel. The bottom row is each prior multiplied by that same L:
// under M1 the posterior stays a delta, under M2 it is L renormalised, and the mixture keeps
// a spike whose weight is w L(0) / [w L(0) + (1-w) int L]. The Bayes factor of the uniform
// model against the spike, B_U = int L / L(0), is read off the same likelihood and displayed.
// One Gaussian likelihood in e, shared by both widgets on this slide.
const BF_LIK = (function () {
  // deliberately broad: L only falls to ~14% of its peak by e = 1, so the posterior is
  // largely prior-dominated and shifting the fiducial prior visibly drags it around.
  const MU = 0.3, SIG = 0.35, N = 400;
  const lik = (e) => Math.exp(-((e - MU) * (e - MU)) / (2 * SIG * SIG));
  // int_0^1 f(e) L(e) de by the trapezoid rule
  const integrate = (f) => {
    let s = 0;
    for (let i = 0; i < N; i++) {
      const a = i / N, b = (i + 1) / N;
      s += (f(a) * lik(a) + f(b) * lik(b)) / 2 / N;
    }
    return s;
  };
  return { MU, SIG, lik, integrate, L0: lik(0) };
})();

(function () {
  const root = document.getElementById('bf-mix'); if (!root) return;
  const W = 200, H = 84, L = 14, R = 8, T = 10, B = 16, y0 = H - B, x0 = L, x1 = W - R;
  const ctl = (k) => root.querySelector(`[data-ctl="${k}"]`), out = (k) => root.querySelector(`[data-out="${k}"]`);
  const svg = (k) => root.querySelector(`[data-plot="${k}"]`);
  const axes = `<line class="ax" x1="${x0}" y1="${y0}" x2="${x1}" y2="${y0}"/><line class="ax" x1="${x0}" y1="${T}" x2="${x0}" y2="${y0}"/>`
    + `<text class="lbl" x="${x0}" y="${H - 4}">0</text><text class="lbl" x="${x1}" y="${H - 4}" text-anchor="end">e</text>`;
  const spike = (h) => `<line class="c1" x1="${x0 + 1}" y1="${y0}" x2="${x0 + 1}" y2="${y0 - h}"/><path class="c1" d="M${x0 - 3},${y0 - h + 5} L${x0 + 1},${y0 - h} L${x0 + 5},${y0 - h + 5}"/>`;
  const flat = (h) => `<line class="c2" x1="${x0 + 1}" y1="${y0 - h}" x2="${x1}" y2="${y0 - h}"/>`;
  const HS = y0 - T - 4, HU = 22;
  const LNB = Math.log10(BF_LIK.integrate(() => 1) / BF_LIK.L0);

  svg('spike').innerHTML = axes + spike(HS);
  svg('unif').innerHTML = axes + flat(HU);

  const update = () => {
    const w = +ctl('w').value;
    out('w').value = w.toFixed(2);
    svg('mix').innerHTML = axes + spike(4 + (HS - 4) * w) + flat(2 + (HU - 2) * (1 - w));
    out('lnb').value = LNB.toFixed(2);
    out('odds').value = (Math.log10((1 - w) / w) + LNB).toFixed(2);
  };
  root.querySelectorAll('[data-ctl]').forEach((el) => el.addEventListener('input', update));
  update();
})();

// Fiducial choices of p(e | lambda) to slide between.
(function () {
  const root = document.getElementById('bf-prior'); if (!root) return;
  const EMIN = 0.01;
  const PRIORS = [
    { name: 'Uniform, \\(p(e) \\propto 1\\)', f: () => 1 },
    { name: 'Thermal, \\(p(e) \\propto 2e\\)', f: (e) => 2 * e },
    { name: 'Log-uniform, \\(p(e) \\propto 1/e\\)', f: (e) => 1 / Math.max(e, EMIN) },
    { name: 'Beta(2, 5)', f: (e) => e * Math.pow(1 - e, 4) },
  ];
  const W = 300, H = 170, L = 34, R = 10, T = 12, B = 28, y0 = H - B, x0 = L, x1 = W - R;
  const svg = root.querySelector('[data-plot="prior"]');
  const slider = root.querySelector('[data-ctl="prior"]'), name = root.querySelector('[data-out="name"]');
  slider.max = String(PRIORS.length - 1);

  const path = (ys, px, py) => {
    let d = `M${px(0).toFixed(1)},${py(ys[0]).toFixed(1)}`;
    for (let i = 1; i < ys.length; i++) d += ` L${px(i / (ys.length - 1)).toFixed(1)},${py(ys[i]).toFixed(1)}`;
    return d;
  };

  const draw = () => {
    const p = PRIORS[+slider.value];
    const N = 240;
    const pr = [], po = [], lk = [];
    for (let i = 0; i <= N; i++) {
      const e = i / N, v = Math.max(p.f(e), 0), l = BF_LIK.lik(e);
      pr.push(v); lk.push(l); po.push(v * l);             // posterior ∝ prior × the shared likelihood
    }
    // each curve is drawn against its own peak: the shapes are what matter, not the normalisation
    const nrm = (a) => { const m = Math.max(...a) || 1; return a.map((v) => v / m); };
    const px = (e) => x0 + e * (x1 - x0), py = (v) => y0 - v * 0.88 * (y0 - T);
    const dPr = path(nrm(pr), px, py), dPo = path(nrm(po), px, py), dLk = path(nrm(lk), px, py);
    svg.innerHTML =
      `<line class="ax" x1="${x0}" y1="${y0}" x2="${x1}" y2="${y0}"/>`
      + `<line class="ax" x1="${x0}" y1="${T}" x2="${x0}" y2="${y0}"/>`
      + `<path class="pr-area" d="${dPo} L${px(1).toFixed(1)},${y0} L${px(0).toFixed(1)},${y0} Z"/>`
      + `<path class="pr-lik" d="${dLk}"/><path class="pr-line" d="${dPr}"/><path class="pr-post" d="${dPo}"/>`
      + `<text class="lbl" x="${x0}" y="${H - 14}">0</text>`
      + `<text class="lbl" x="${x1}" y="${H - 14}" text-anchor="end">1</text>`
      + `<text class="lbl" x="${(x0 + x1) / 2}" y="${H - 3}" text-anchor="middle">e</text>`;
    name.innerHTML = p.name;
    if (window.renderMathInElement) {
      renderMathInElement(name, { delimiters: [{ left: '\\(', right: '\\)', display: false }], throwOnError: false });
    }
  };
  slider.addEventListener('input', draw);
  if (window.renderMathInElement) draw(); else addEventListener('load', draw);
})();
