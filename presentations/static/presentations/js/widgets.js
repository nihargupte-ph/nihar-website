(function () {
  const P = (window.Presentations = window.Presentations || {});
  const types = {};
  P.registerInteraction = (name, impl) => { types[name] = impl; };
  P.interactions = {
    def: (iid) => (P.data.interactions || {})[iid],
    input(iid, el, submit, prior) { const d = P.interactions.def(iid); types[d.type].input(el, d.config, submit, prior); },
    aggregate(iid, el, agg, ctx) { const d = P.interactions.def(iid); types[d.type].aggregate(el, d.config, agg, ctx); },
    // types may implement update(el, config, agg, ctx) → true to refresh a rendered aggregate in place
    update(iid, el, agg, ctx) { const d = P.interactions.def(iid); const t = types[d.type]; return !!(t.update && t.update(el, d.config, agg, ctx)); },
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
    const inverted = tag.startsWith('not:');
    const base = inverted ? tag.slice(4) : tag;
    let agg = null;
    try { agg = await P.api.get(P.data.urls.aggregate + encodeURIComponent(iid) + '/?tag=' + encodeURIComponent(tag)); } catch (e) { agg = null; }
    const live = P.$('.widget-body', el);
    if (agg && !agg.too_small && live && el.dataset.key === state + '|' + tag && P.interactions.update(iid, live, agg, { revealed: state === 'revealed', tag })) {
      const n = P.$('.n', el); if (n) n.textContent = `n = ${agg.n}`;
      return;
    }
    el.dataset.key = state + '|' + tag;
    el.innerHTML = '';
    el.append(P.el('h4', { text: d.config.prompt }));
    if (!agg) { el.append(P.el('div', { class: 'too-small', text: 'results not available' })); return; }
    const pick = (t) => { W.tag[iid] = t; render(iid, el, state); };
    const slice = P.el('div', { class: 'slice' });
    for (const t of (types[d.type].slicer === false ? [] : ['all', ...(P.data.expertise || [])])) {
      slice.append(P.el('button', { class: 'btn' + (t === base ? ' on' : ''), text: t, onclick: () => pick(t === 'all' ? 'all' : (inverted ? 'not:' + t : t)) }));
    }
    if (slice.children.length) {
      slice.append(P.el('button', {
        class: 'btn' + (inverted ? ' on' : ''), text: 'vs rest',
        title: 'show everyone except the selected group',
        onclick: () => { if (base === 'all') return; pick(inverted ? base : 'not:' + base); },
      }));
      el.append(slice);
    }
    const body = P.el('div', { class: 'widget-body' }); el.append(body);
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
