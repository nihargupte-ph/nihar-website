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
