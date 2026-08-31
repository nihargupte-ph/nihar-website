(async function () {
  const plot = document.getElementById('posterior-plot');
  const data = await (await fetch(plot.dataset.src)).json();
  const css = getComputedStyle(document.documentElement);
  const accent = css.getPropertyValue('--accent').trim() || '#37b49f';
  const fg = css.getPropertyValue('--fg').trim() || '#eee';
  function smooth(y, k) { if (!k) return y; const out = y.map((_, i) => { let s = 0, n = 0; for (let j = i - k; j <= i + k; j++) if (y[j] != null) { s += y[j]; n++; } return s / n; }); return out; }
  function draw() {
    const k = Number(document.getElementById('smooth').value);
    Plotly.react(plot, [{ x: data.e, y: smooth(data.p, k), type: 'scatter', fill: 'tozeroy', line: { color: accent } }],
      { paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { color: fg }, margin: { t: 10, r: 10 }, xaxis: { title: 'e' }, yaxis: { title: 'p(e)' } }, { displayModeBar: false, responsive: true });
  }
  document.getElementById('smooth').addEventListener('input', draw);
  draw();
})();
