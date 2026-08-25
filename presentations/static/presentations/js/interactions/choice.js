(function () {
  const P = (window.Presentations = window.Presentations || {});
  const types = {};
  P.registerInteraction = (name, impl) => { types[name] = impl; };
  P.interactions = {
    def: (iid) => (P.data.interactions || {})[iid],
    input(iid, el, submit, prior) { const d = P.interactions.def(iid); types[d.type].input(el, d.config, submit, prior); },
    aggregate(iid, el, agg, ctx) { const d = P.interactions.def(iid); types[d.type].aggregate(el, d.config, agg, ctx); },
  };
  const W = (P.widgets = { tag: {} });
  function box(slide, ref) {
    const iid = ref.id;
    if (slide.kind === 'html') {
      return P.$(`[data-interaction="${CSS.escape(iid)}"]`, P.stage.slideEl(slide.id));
    }
    const host = P.stage.widgets(slide.id); if (!host) return null;
    let el = P.$(`.widget[data-iid="${CSS.escape(iid)}"]`, host);
    if (!el) {
      el = P.el('div', { class: 'widget', 'data-iid': iid }); host.append(el);
      const s = P.stage.frac2stage(ref.rect);
      Object.assign(el.style, { left: (s.x / 19.2) + '%', top: (s.y / 10.8) + '%', width: (s.w / 19.2) + '%', height: (s.h / 10.8) + '%' });
    }
    return el;
  }
  async function render(iid, el, state) {
    el.classList.add('widget'); el.dataset.iid = iid;
    const d = P.interactions.def(iid); if (!d) return;
    if (state === 'hidden') { el.innerHTML = ''; el.style.visibility = 'hidden'; return; }
    el.style.visibility = 'visible';
    if (state === 'closed' && P.data.mode !== 'present') { el.innerHTML = ''; el.append(P.el('h4', { text: d.config.prompt }), P.el('div', { class: 'too-small', text: 'waiting for reveal' })); return; }
    if (state === 'open' && P.data.mode !== 'present') { el.innerHTML = ''; el.append(P.el('h4', { text: d.config.prompt }), P.el('div', { class: 'too-small', text: 'open — answer on your phone' })); return; }
    const tag = W.tag[iid] || 'all';
    let agg = null;
    try { agg = await P.api.get(P.data.urls.aggregate + encodeURIComponent(iid) + '/?tag=' + encodeURIComponent(tag)); } catch (e) { agg = null; }
    el.innerHTML = '';
    el.append(P.el('h4', { text: d.config.prompt }));
    if (!agg) { el.append(P.el('div', { class: 'too-small', text: 'results not available' })); return; }
    const slice = P.el('div', { class: 'slice' });
    for (const t of ['all', ...(P.data.expertise || [])]) {
      slice.append(P.el('button', { class: 'btn' + (t === tag ? ' on' : ''), text: t, onclick: () => { W.tag[iid] = t; render(iid, el, state); } }));
    }
    el.append(slice);
    const body = P.el('div'); el.append(body);
    if (agg.too_small) { body.append(P.el('div', { class: 'too-small', text: `n = ${agg.n} — too small to show` })); return; }
    P.interactions.aggregate(iid, body, agg, { revealed: state === 'revealed', tag });
    el.append(P.el('div', { class: 'n', text: `n = ${agg.n}` }));
  }
  W.mountShown = function (slideId, states) {
    const slide = (P.data.slides || []).find((s) => s.id === slideId); if (!slide) return;
    for (const ref of slide.show || []) { const el = box(slide, ref); if (el) render(ref.id, el, states[ref.id] || 'hidden'); }
  };
  W.refreshAll = function (states) { P.$$('.widget[data-iid]').forEach((el) => render(el.dataset.iid, el, states[el.dataset.iid] || 'hidden')); };
})();

Presentations.registerInteraction('choice', {
  input(el, config, submit, prior) {
    const P = Presentations; const grid = P.el('div', { class: 'choice-grid' }); el.append(grid);
    config.options.forEach((o) => {
      const b = P.el('button', { class: 'btn' + (prior && prior.choice === o ? ' picked' : ''), text: o, onclick: () => { grid.querySelectorAll('button').forEach((x) => x.classList.remove('picked')); b.classList.add('picked'); submit({ choice: o }); } });
      grid.append(b);
    });
  },
  aggregate(el, config, agg, ctx) {
    const P = Presentations; const wrap = P.el('div', { class: 'bars' }); el.append(wrap);
    const max = Math.max(1, ...Object.values(agg.counts));
    for (const o of config.options) {
      const c = agg.counts[o] || 0; const pct = agg.n ? Math.round(100 * c / agg.n) : 0;
      const row = P.el('div', { class: 'bar' + (ctx.revealed && config.answer === o ? ' correct' : '') });
      row.append(P.el('b', { text: o }), P.el('span', {}, [Object.assign(P.el('i'), { style: `width:${100 * c / max}%` })]), P.el('span', { text: `${pct}%` }));
      wrap.append(row);
    }
  },
});
