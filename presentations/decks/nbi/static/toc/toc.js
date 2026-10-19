// Table-of-contents slide: the corner QR points at the archive (static/toc/archive-qr.svg, made with
// the python qrcode package); while presenting it is swapped for the live session's join QR.
(function () {
  const root = document.querySelector('#toc-root:not([data-done])');
  if (!root) return;
  root.dataset.done = '1';
  const P = window.Presentations;
  if (!P || !P.data || P.data.mode !== 'present') return;
  const qr = document.querySelector('#qr-box');
  if (!qr) return;
  const svg = qr.querySelector('svg');
  if (svg) root.querySelector('.toc__qr').replaceChildren(svg.cloneNode(true));
})();
