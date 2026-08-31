// Event table as a colour grid. Green always means "good news for this event": on the risk
// columns that is Low, on the significance columns it is High. Data: riskgrid.json.
(function () {
  const root = document.querySelector('#rg-root:not([data-done])');
  if (!root) return;
  root.dataset.done = '1';

  const RANK = { Low: 0, Medium: 1, High: 2 };
  const TONE = ['good', 'mid', 'bad'];
  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  // risk: Low is good. significance: High is good, so the scale is reversed.
  const tone = (value, scale) => {
    const r = RANK[value];
    if (r === undefined) return '';
    return TONE[scale === 'significance' ? 2 - r : r];
  };

  fetch(root.dataset.src).then((r) => r.json()).then((d) => {
    const cols = d.columns;
    const head = ['<div class="rg__cell rg__cell--corner"></div>']
      .concat(cols.map((c) => `<div class="rg__head">${esc(c.label)}</div>`));
    const body = d.rows.map((row) => {
      const cells = cols.map((c) => {
        const v = row[c.key];
        return `<div class="rg__cell rg__cell--${tone(v, c.scale)}"><span>${esc(v)}</span></div>`;
      });
      return `<div class="rg__event">${esc(row.event)}</div>` + cells.join('');
    });
    root.style.setProperty('--rg-cols', cols.length);
    root.innerHTML = `<div class="rg__grid">${head.join('')}${body.join('')}</div>`
      + '<div class="rg__key">'
      + '<span class="rg__swatch rg__cell--good"></span>low risk / high significance'
      + '<span class="rg__swatch rg__cell--mid"></span>medium'
      + '<span class="rg__swatch rg__cell--bad"></span>high risk / low significance'
      + '</div>';
  }).catch(() => { root.innerHTML = '<p class="rg__err">(grid data failed to load)</p>'; });
})();
