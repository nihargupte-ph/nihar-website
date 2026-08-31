// Live eccentricity-prior poll slide. The drawing / plotting logic is the engine's `prior`
// interaction type (static/presentations/js/interactions/prior.js); this file only builds the
// side column: the session's join QR (so the audience can scan it off the projector) and the
// countdown, which the widget renders and we relocate here.
(function () {
  const root = document.querySelector('#pp-root:not([data-done])');
  if (!root) return;
  root.dataset.done = '1';
  const P = window.Presentations;
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
