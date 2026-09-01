// Fills the "__ (uniform, log-uni, expert prior)" blank on the event slides with the
// Bayes factor the *audience's* prior implies, live from the `ecc-prior` poll.
//
// Everything static (the per-event likelihood-ratio curve Lambda, binned onto the poll's
// 88-bin log10 e axis, and the constant k) is precomputed by tools/expertbf.py into
// expertbf.json; the browser only does the dot product B = k * sum(w_i Lambda_i).
//
// The slides are Canva SVG exports whose text is outlines, so the answer is drawn as an
// SVG <text> *inside the underlay's own viewBox*: SVG positions text by its baseline, so
// the number lands on the underscores at any window size with no CSS geometry to keep in
// sync.  The blank's box is stored in the json as viewBox fractions, read off the source
// PDF with `pdftotext -bbox`.
//
// Aggregates are 403 for non-staff while the poll is hidden/open, so a failed fetch just
// leaves the dash: no session, no responses and a still-closed poll all degrade to "—".
(function () {
  const NS = (window.ExpertBF = window.ExpertBF || {});

  // --- the pure maths, exported for the node parity test -------------------------
  NS.bayesFactor = function (weights, lambda, k) {
    if (!weights || !lambda || weights.length !== lambda.length) return null;
    let total = 0, sum = 0;
    for (let i = 0; i < lambda.length; i++) {
      const w = weights[i];
      if (!(w >= 0) || !isFinite(w)) return null;
      total += w; sum += w * lambda[i];
    }
    return total > 0 ? k * sum / total : null;
  };

  // Compact enough to fit the gap the underscores leave: 2 significant figures,
  // one decimal below 10, a k suffix above 1000.
  NS.format = function (v) {
    if (v == null || !isFinite(v) || v < 0) return '—';
    if (v < 10) return v.toFixed(1);
    if (v < 1000) { const p = Math.pow(10, Math.floor(Math.log10(v)) - 1); return String(Math.round(v / p) * p); }
    if (v < 1e6) { const t = v / 1000; return (t < 10 ? t.toFixed(1) : String(Math.round(t / 10) * 10)) + 'k'; }
    return v.toExponential(1).replace('e+', 'e');
  };

  // Where the baseline and the cap height sit inside the ascender-to-descender word box
  // that pdftotext reports.  Tuned against the deck's own glyphs.
  const BASELINE = 0.79;
  const SIZE = 0.80;

  if (typeof document === 'undefined' || NS.mounted) return;
  const hosts = Array.from(document.querySelectorAll('.xbf:not([data-done])'));
  if (!hosts.length) return;
  NS.mounted = true;
  hosts.forEach((h) => { h.dataset.done = '1'; });

  const P = window.Presentations;
  if (!P || !P.data) return;
  const IID = 'ecc-prior';
  const SRC = hosts[0].dataset.src;
  const SVGNS = 'http://www.w3.org/2000/svg';

  // The marker div only carries the slide id and the no-JS dash; the number itself is
  // drawn into the underlay svg, so keep the wrapper out of the way.
  for (const host of hosts) {
    const page = host.closest('.slide-page');
    if (page) page.classList.add('xbf-passthrough');
  }

  const node = (host) => {
    if (host._node) return host._node;
    const slide = host.closest('.slide');
    const svg = slide && slide.querySelector('.stage--underlay .stage__inner > svg');
    if (!svg || !svg.viewBox || !svg.viewBox.baseVal) return null;
    const t = document.createElementNS(SVGNS, 'text');
    t.setAttribute('class', 'xbf-text');
    t.append(document.createElementNS(SVGNS, 'title'));
    svg.append(t);
    host._node = { text: t, box: svg.viewBox.baseVal };
    return host._node;
  };

  const explain = (ev, value, agg) => {
    if (!ev.fittable) return ev.label + ': not computable — ' + ev.reason;
    if (value == null) return ev.label + ': waiting for the eccentricity-prior poll.';
    const spread = ev.sigma_sensitivity.map((s) => s.B).filter((b) => b != null);
    const lo = Math.min.apply(null, spread), hi = Math.max.apply(null, spread);
    return ev.label + ': B = ' + value.toPrecision(3) + ' under the audience\'s mixture prior (n = '
      + agg.n + ').\nFitted from the quoted ' + NS.format(ev.quoted.uniform) + ' (uniform) and '
      + NS.format(ev.quoted.log_uniform) + ' (log-uniform), giving a likelihood-ratio bump at e = '
      + ev.e_star.toFixed(2) + '; the published e_10Hz posterior is ' + ev.posterior.e
      + ' [' + ev.posterior.lo + ', ' + ev.posterior.hi + '].\nHalving/tripling the fitted likelihood '
      + 'width moves a fiducial expert prior\'s answer over ' + NS.format(lo) + '–' + NS.format(hi)
      + ', so read this as one significant figure.\nSource: ' + ev.source + '.';
  };

  const paint = (data, agg) => {
    const byId = {};
    for (const ev of data.events) for (const s of ev.slides) byId[s] = ev;
    for (const host of hosts) {
      const ev = byId[host.dataset.slide];
      const n = ev && node(host);
      if (!n) continue;
      const b = ev.blank;
      n.text.setAttribute('x', (b.x * n.box.width).toFixed(2));
      n.text.setAttribute('y', ((b.y + b.h * BASELINE) * n.box.height).toFixed(2));
      n.text.setAttribute('font-size', (b.h * SIZE * n.box.height).toFixed(2));
      const value = ev.fittable && agg && agg.mean
        ? NS.bayesFactor(agg.mean, ev.lambda, ev.k) : null;
      n.text.setAttribute('class', 'xbf-text' + (value == null ? ' xbf-text--none' : ''));
      // textContent would clobber the <title>, so write the label node only
      const label = n.text.lastChild && n.text.lastChild.nodeType === 3
        ? n.text.lastChild : n.text.appendChild(document.createTextNode(''));
      label.data = NS.format(value);
      n.text.firstChild.textContent = explain(ev, value, agg || {});
      host.title = n.text.firstChild.textContent;
      host.textContent = label.data;
    }
  };

  const load = async () => {
    let data = NS.data;
    if (!data) {
      try { data = NS.data = await P.api.get(SRC); } catch (e) { return; }
    }
    let agg = null;
    try { agg = await P.api.get(P.data.urls.aggregate + encodeURIComponent(IID) + '/'); } catch (e) { agg = null; }
    paint(data, agg);
  };

  load();
  setInterval(load, 4000);
  if (P.stage && P.stage.onChange) P.stage.onChange(() => load());
})();
