Presentations.registerInteraction('text', {
  input(el, config, submit, prior) {
    const P = Presentations;
    const i = P.el('input', { class: 'txt', maxlength: String(config.max_len || 80), placeholder: 'type…', value: prior ? prior.text : '' });
    const b = P.el('button', { class: 'btn btn--primary', text: 'Submit', style: 'margin-top:.5rem', onclick: () => submit({ text: i.value }) });
    i.addEventListener('keydown', (e) => { if (e.key === 'Enter') b.click(); });
    el.append(i, b);
  },
  aggregate(el, config, agg) {
    const P = Presentations; const wrap = P.el('div', { class: 'wordcloud' }); el.append(wrap);
    const entries = Object.entries(agg.counts).sort((a, b) => b[1] - a[1]); const max = entries.length ? entries[0][1] : 1;
    entries.forEach(([w, c], i) => wrap.append(P.el('span', { text: w, style: `font-size:${(0.8 + 2.2 * c / max).toFixed(2)}rem;opacity:${(0.55 + 0.45 * c / max).toFixed(2)};color:var(--accent-${(i % 3) + 1}, var(--accent))` })));
    if (!entries.length) wrap.append(P.el('span', { class: 'too-small', text: 'no words yet' }));
  },
});
