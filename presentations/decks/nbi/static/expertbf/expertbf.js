// Fills the "__ (uniform, log-uni, expert prior)" blank on the event slides with what the
// *audience's* prior implies, live from the `ecc-prior` poll.
//
// The drawn curve is split between two models: eccentric with the uniform e prior (whose evidence
// ratio is the published uniform Bayes factor) and quasi-circular, a delta at e = 0. Mass at
// e_10Hz > 0.05 is "eccentric", the rest is indistinguishable from zero. So f = P(e > 0.05), the
// prior odds are O = f / (1 - f), and the blank shows the posterior odds O * B_uniform.
// (expertbf.json still carries the per-event Lambda fit from tools/expertbf.py as a consistency
// check of the published pairs; NS.bayesFactor below is that, and is no longer drawn.)
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

  // f = the curve's mass above the threshold (the bin it falls in split linearly), O = f / (1 - f)
  NS.priorOdds = function (weights, axis, thLog10) {
    if (!weights || !weights.length) return null;
    const w = (axis.max - axis.min) / axis.bins;
    let tot = 0, hi = 0;
    for (let k = 0; k < weights.length; k++) {
      const v = weights[k];
      if (!(v >= 0) || !isFinite(v)) return null;
      const a = axis.min + k * w;
      tot += v; hi += v * Math.min(1, Math.max(0, (a + w - thLog10) / w));
    }
    if (!(tot > 0)) return null;
    const f = hi / tot;
    return { f, odds: f >= 1 ? Infinity : f / (1 - f) };
  };

  // P(eccentric | data) from odds O (a Bayes factor at even prior odds, or O x B): O / (1 + O).
  // Near 1 it keeps the digits that matter: 17 -> 94%, 407 -> 99.8%, 10000 -> 99.99%.
  NS.prob = function (O) {
    if (O == null || !(O >= 0)) return '—';
    if (!isFinite(O)) return '100%';
    const p = O / (1 + O);
    if (p < 0.99) return (100 * p).toFixed(p < 0.1 ? 1 : 0) + '%';
    const short = Number((100 * (1 - p)).toPrecision(1));            // the shortfall from 100%, one figure
    if (short < 1e-3) return '>99.999%';
    const d = Math.max(1, -Math.floor(Math.log10(short)));
    return (100 - short).toFixed(d) + '%';
  };

  // Written out in full (6,300 not 6.3k): two significant figures, thousands separated; one decimal
  // below 10. Read as one significant figure anyway (see tools/expertbf.py).
  NS.format = function (v) {
    if (v == null || !isFinite(v) || v < 0) return '—';
    if (v < 10) return v.toFixed(1);
    return Number(v.toPrecision(2)).toLocaleString('en');
  };

  // Where the baseline and the cap height sit inside the ascender-to-descender word box
  // that pdftotext reports.  Tuned against the deck's own glyphs.
  const BASELINE = 0.79;
  const SIZE = 0.80;
  // how far past the two underscores the answer may run before it is scaled down
  const MAX_OVERRUN = 1.15;

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

  const explain = (ev, value, po, agg, odds) => {
    if (value == null) return ev.label + ': waiting for the eccentricity-prior poll.';
    return ev.label + ': ' + NS.format(value) + ' = prior odds × uniform-prior Bayes factor = '
      + po.odds.toPrecision(2) + ' × ' + Math.round(ev.quoted.uniform).toLocaleString('en') + '.\nPrior odds from the audience\'s mixture (n = '
      + agg.n + '): f = P(' + odds.label + ') = ' + po.f.toFixed(2) + ', odds f/(1−f). Mass below '
      + odds.threshold + ' counts as quasi-circular (a delta at e = 0), mass above as the eccentric model.\nSource: '
      + ev.source + '.';
  };
  const oddsOf = (data, agg) => (agg && agg.mean ? NS.priorOdds(agg.mean, data.axis, data.odds.threshold_log10) : null);

  const paint = (data, agg) => {
    const byId = {};
    for (const ev of data.events) for (const s of ev.slides) byId[s] = ev;
    for (const host of hosts) {
      const ev = byId[host.dataset.slide];
      const n = ev && node(host);
      if (!n) continue;
      const b = ev.blank;
      // Start at the blank's left edge, which is just after ", " — centring instead closed up the
      // comma and let "1,698, 750" read as the single number 1,698,750.
      n.text.setAttribute('x', (b.x * n.box.width).toFixed(2));
      n.text.setAttribute('y', ((b.y + b.h * BASELINE) * n.box.height).toFixed(2));
      const size = b.h * SIZE * n.box.height;
      n.text.setAttribute('font-size', size.toFixed(2));
      const po = oddsOf(data, agg);
      const value = po && ev.quoted && ev.quoted.uniform ? po.odds * ev.quoted.uniform : null;
      n.text.setAttribute('class', 'xbf-text' + (value == null ? ' xbf-text--none' : ''));
      // textContent would clobber the <title>, so write the label node only
      const label = n.text.lastChild && n.text.lastChild.nodeType === 3
        ? n.text.lastChild : n.text.appendChild(document.createTextNode(''));
      label.data = NS.format(value);
      // An answer is usually wider than the two underscores it replaces, and left unchecked it
      // swallowed the space before "(uniform…". Allow it the blank plus that space, then scale to
      // fit. Never below 70% — a number nobody can read from the back of the room is worse.
      // the widened gaps are the true room; an old two-underscore blank may run on into the space after it
      const room = b.w * (b.w * 1440 > 30 ? 1 : MAX_OVERRUN) * n.box.width;
      const wide = n.text.getComputedTextLength();
      if (wide > room) n.text.setAttribute('font-size', (size * Math.max(0.7, room / wide)).toFixed(2));
      n.text.firstChild.textContent = explain(ev, value, po, agg || {}, data.odds);
      hover(host, ev, n, value);
      host.title = n.text.firstChild.textContent;
      host.textContent = label.data;
    }
    for (const tb of data.tables || []) for (const host of hosts) if (tb.slides.includes(host.dataset.slide)) table(host, tb, agg, data);
  };

  // Hovering (or tapping) any of the three numbers swaps them for P(eccentric) = O / (1 + O): the printed
  // uniform and log-uniform Bayes factors at even prior odds, the expert one with the audience's odds
  // already in. The three probabilities are wider than the numbers, so they share one pill that starts
  // on the first number and runs on over the line for as long as the pointer is there.
  function hover(host, ev, n, value) {
    const svg = n.text.ownerSVGElement, V = n.box;
    if (!host._hover) {
      const boxes = [ev.numbers && ev.numbers.uniform, ev.numbers && ev.numbers.log_uniform, ev.blank].filter(Boolean);
      const b0 = boxes[0];
      const g = svgEl('g', { class: 'xbf-prob', visibility: 'hidden' });
      const r = svgEl('rect', { class: 'xbf-prob__pill', y: (b0.y * V.height).toFixed(1), height: (b0.h * V.height).toFixed(1), rx: (b0.h * V.height * 0.25).toFixed(1) });
      const t = svgEl('text', { class: 'xbf-prob__t', x: (b0.x * V.width).toFixed(1), y: ((b0.y + b0.h * BASELINE) * V.height).toFixed(1), 'font-size': (b0.h * SIZE * V.height).toFixed(1) });
      g.append(r, t);
      svg.append(g);
      let pinned = false;
      const show = (on) => g.setAttribute('visibility', on || pinned ? 'visible' : 'hidden');
      for (const b of boxes) {
        const hit = svgEl('rect', { class: 'xbf-prob__hit', x: (b.x * V.width).toFixed(1), y: (b.y * V.height).toFixed(1), width: (b.w * V.width).toFixed(1), height: (b.h * V.height).toFixed(1) });
        hit.addEventListener('pointerenter', () => show(true));
        hit.addEventListener('pointerleave', () => show(false));
        hit.addEventListener('click', (e) => { e.stopPropagation(); pinned = !pinned; show(pinned); });   // tap on a phone; not "next slide"
        svg.append(hit);
      }
      host._hover = { r, t, b0 };
    }
    const { r, t, b0 } = host._hover, q = ev.quoted || {};
    t.textContent = [q.uniform, q.log_uniform, value].map((O) => (O == null ? '—' : NS.prob(O))).join(',  ');
    const pad = b0.h * V.height * 0.2;
    r.setAttribute('x', (b0.x * V.width - pad).toFixed(1));
    r.setAttribute('width', (t.getComputedTextLength() + 2 * pad).toFixed(1));
  }

  // page-22's glitch-mitigation table, redrawn over the Canva one: uniform prior as published, and
  // the same row times the audience's prior odds. log10, coloured like Table 5 of Gupte+ 2024.
  const SHADES = ['#FABCA4', '#FED7B0', '#FFFAD6', '#E6F4C1', '#C8E7B3', '#ABDAAF', '#92CEA9', '#8DCCA8', '#84BB9F', '#79B597'];
  const shade = (lg) => SHADES[Math.max(0, Math.min(SHADES.length - 1, Math.floor(lg / 0.5)))];
  const svgEl = (tag, attrs, text) => { const e = document.createElementNS(SVGNS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (text != null) e.textContent = text; return e; };
  function table(host, tb, agg, data) {
    const slide = host.closest('.slide');
    const svg = slide && slide.querySelector('.stage--underlay .stage__inner > svg');
    if (!svg || !svg.viewBox || !svg.viewBox.baseVal) return;
    const V = svg.viewBox.baseVal, x0 = tb.box.x * V.width, y0 = tb.box.y * V.height, W = tb.box.w * V.width, H = tb.box.h * V.height;
    if (!host._table) {
      const g = svgEl('g', { class: 'xbf-table' });
      g.append(svgEl('rect', { x: x0, y: y0, width: W, height: H, fill: '#fff' }));
      const c1 = x0 + 0.40 * W, c2 = x0 + 0.70 * W, cw = 0.29 * W, head = 0.25 * H, rh = (H - head) / tb.rows.length;
      const t = (x, y, s, attrs) => g.append(svgEl('text', { x, y, 'text-anchor': 'middle', class: 'xbf-table__t', ...attrs }, s));
      t(c1 + cw, y0 + 0.30 * head, `${tb.qcp_model}  log₁₀ℬ`, { 'font-size': 15 });
      t(c1 + cw / 2, y0 + 0.78 * head, 'uniform', { 'font-size': 15 });
      t(c2 + cw / 2, y0 + 0.78 * head, 'expert prior', { 'font-size': 15, 'font-weight': 600 });
      const cells = tb.rows.map((r, i) => {
        const y = y0 + head + i * rh;
        t(x0 + 0.02 * W, y + rh * 0.62, r.label, { 'text-anchor': 'start', 'font-size': 15, 'font-family': 'monospace' });
        const u = r.quoted_log10.uniform;
        g.append(svgEl('rect', { x: c1, y: y + 2, width: cw, height: rh - 4, fill: shade(u) }));
        t(c1 + cw / 2, y + rh * 0.62, u.toFixed(2), { 'font-size': 16 });
        const box = svgEl('rect', { x: c2, y: y + 2, width: cw, height: rh - 4, fill: '#eee' });
        const val = svgEl('text', { x: c2 + cw / 2, y: y + rh * 0.62, 'text-anchor': 'middle', 'font-size': 16, 'font-weight': 600, class: 'xbf-table__t' }, '—');
        const tip = svgEl('title'); box.append(tip);
        g.append(box, val);
        return { box, val, tip, row: r };
      });
      svg.append(g);
      host._table = cells;
    }
    const po = oddsOf(data, agg);
    for (const c of host._table) {
      const b = po ? po.odds * c.row.quoted.uniform : null;
      const lg = b != null && b > 0 ? Math.log10(b) : null;
      c.val.textContent = lg == null ? '—' : lg.toFixed(1);
      c.box.setAttribute('fill', lg == null ? '#eee' : shade(lg));
      c.tip.textContent = explain(c.row, b, po, agg || {}, data.odds);
    }
  }

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
