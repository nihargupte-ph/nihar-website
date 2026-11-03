// The marginal distribution of log10 B_EAS/QCAS across the catalogue, drawn on its side
// (log B along x) as a small square panel. Data: eccbf.json (tools/digitize_eccbf.py).
(function () {
  const host = document.querySelector('.bf-answer [data-plot="eccbf"]');
  if (!host) return;

  const W = 440, H = 440, L = 58, R = 12, T = 12, XLAB = 52;
  const y0 = T, y1 = H - XLAB;
  const B0 = -1.3, B1 = 1.25;
  const px = (b) => L + (b - B0) / (B1 - B0) * (W - L - R);

  fetch(host.dataset.src).then((r) => r.json()).then((d) => {
    const [lo, hi, nb] = d.bins, wbin = (hi - lo) / nb;
    const counts = new Array(nb).fill(0);
    for (const p of d.population) {
      const k = Math.floor((p.b - lo) / wbin);
      if (k >= 0 && k < nb) counts[k]++;
    }
    for (const n of d.named) {
      const k = Math.floor((n.b - lo) / wbin);
      if (k >= 0 && k < nb) counts[k]++;
    }
    const cmax = Math.max(...counts, 1);
    const py = (c) => y1 - c / cmax * (y1 - y0 - 6);

    const out = [`<rect class="ec-frame" x="${L}" y="${y0}" width="${W - L - R}" height="${y1 - y0}"/>`];
    for (let b = -1; b <= 1.0001; b += 0.5) {
      const x = px(b).toFixed(1);
      out.push(`<line class="ec-grid" x1="${x}" y1="${y0}" x2="${x}" y2="${y1}"/>`);
      out.push(`<text class="ec-tick" x="${x}" y="${y1 + 17}" text-anchor="middle">${b.toFixed(1).replace('-', '−')}</text>`);
    }
    for (let c = 0; c <= cmax; c += 5) {
      const y = py(c).toFixed(1);
      out.push(`<line class="ec-grid" x1="${L}" y1="${y}" x2="${W - R}" y2="${y}"/>`);
      out.push(`<text class="ec-tick" x="${L - 8}" y="${+y + 5}" text-anchor="end">${c}</text>`);
    }
    counts.forEach((c, k) => {
      if (!c) return;
      const xa = px(lo + k * wbin), xb = px(lo + (k + 1) * wbin), y = py(c);
      out.push(`<rect class="ec-hist" x="${xa.toFixed(1)}" y="${y.toFixed(1)}" width="${(xb - xa - 0.5).toFixed(1)}" height="${(y1 - y).toFixed(1)}"/>`);
    });
    out.push(`<text class="ec-axis" x="${(L + W - R) / 2}" y="${H - 8}" text-anchor="middle">log<tspan class="ec-sub" dy="4">10</tspan><tspan dy="-4"> </tspan><tspan class="ec-cal">B</tspan></text>`);
    out.push(`<text class="ec-axis" transform="translate(16,${(y0 + y1) / 2}) rotate(-90)" text-anchor="middle">counts</text>`);

    host.setAttribute('viewBox', `0 0 ${W} ${H}`);
    host.innerHTML = out.join('');
  }).catch(() => { host.insertAdjacentHTML('afterend', '<p class="bf-note">(plot data failed to load)</p>'); });
})();
