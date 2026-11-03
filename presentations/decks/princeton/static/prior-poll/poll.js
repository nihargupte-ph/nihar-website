// Live eccentricity-prior poll slide. The drawing / plotting logic is the engine's `prior`
// interaction type (static/presentations/js/interactions/prior.js); this file only builds the
// side column: the session's join QR (so the audience can scan it off the projector) and the
// countdown, which the widget renders and we relocate here.
(function () {
  const root = document.querySelector('#pp-root:not([data-done])');
  if (!root) return;
  root.dataset.done = '1';
  const P = window.Presentations;

  // Once the poll is closed the widget reports the mixture's mass above e = 0.05; say it as a share of
  // events (the fraction itself, not the odds f/(1-f)). Follows the widget's expertise filter.
  const belief = root.querySelector('.pp__belief');
  const share = (f) => {
    if (f <= 0) return 'no';
    if (f >= 0.995) return 'all';
    if (f >= 0.5) return `${Math.round(f * 10)} in 10`;
    const n = 1 / f;
    return `1 in ${n < 20 ? Math.round(n) : Number(n.toPrecision(2)).toLocaleString('en')}`;
  };
  root.addEventListener('prior-odds', (e) => {
    const d = e.detail;
    belief.hidden = !d;
    if (d) belief.innerHTML = `We believe that <b>${share(d.f)}</b> events have an eccentricity above 0.05`;
  });

  if (!P || !P.data || P.data.mode !== 'present') return;

  const qr = document.querySelector('#qr-box');
  const box = root.querySelector('.pp__qr');
  if (qr && box) {
    const svg = qr.querySelector('svg');
    if (svg) box.append(svg.cloneNode(true));
    const url = qr.querySelector('div');
    if (url) box.append(Object.assign(document.createElement('div'), { className: 'pp__url', textContent: url.textContent }));
  }

  // The widget is rebuilt whenever the poll's state changes, so re-adopt its clock each time.
  const slot = root.querySelector('.pp__clock');
  const adopt = () => {
    const clock = root.querySelector('.pp__widget .prior-clock');
    if (clock && slot && clock.parentElement !== slot) slot.append(clock);
  };
  new MutationObserver(adopt).observe(root.querySelector('.pp__widget'), { childList: true, subtree: true });
  adopt();
})();
