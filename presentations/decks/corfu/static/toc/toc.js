// Table-of-contents slide: drop the session's join QR and its URL into the bottom-right corner.
// On the phone/archive there is no #qr-box, so the printed link stands on its own.
(function () {
  const root = document.querySelector('#toc-root:not([data-done])');
  if (!root) return;
  root.dataset.done = '1';
  const P = window.Presentations;
  if (!P || !P.data || P.data.mode !== 'present') return;
  const qr = document.querySelector('#qr-box');
  if (!qr) return;
  const svg = qr.querySelector('svg');
  if (svg) root.querySelector('.toc__qr').append(svg.cloneNode(true));
  const url = qr.querySelector('div');
  if (url && url.textContent.trim()) root.querySelector('.toc__url').textContent = url.textContent.trim();
})();
