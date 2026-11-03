(function () {
  const qs = document.querySelectorAll('.bf-q'), box = document.getElementById('bf-answer'); if (!box) return;
  const render = () => { if (window.renderMathInElement) renderMathInElement(box.closest('.slide-page') || box.parentElement, { delimiters: [{ left: '\\[', right: '\\]', display: true }, { left: '\\(', right: '\\)', display: false }], throwOnError: false }); };
  // KaTeX scripts are deferred like this one; auto-render may or may not be defined yet
  if (window.renderMathInElement) render(); else addEventListener('load', render);
  qs.forEach((b) => b.addEventListener('click', (ev) => {
    ev.stopPropagation();
    const q = b.dataset.q, was = b.classList.contains('active');
    qs.forEach((x) => x.classList.remove('active')); box.querySelectorAll('article').forEach((a) => a.classList.remove('active'));
    if (was) { box.hidden = true; return; }
    b.classList.add('active'); box.querySelector(`article[data-q="${q}"]`).classList.add('active'); box.hidden = false;
    box.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }));
  const q0 = new URLSearchParams(location.search).get('q'); if (q0) { const b = document.querySelector(`.bf-q[data-q="${q0}"]`); if (b) b.click(); }   // ?q=trials opens a question directly
  document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape' && !box.hidden) { box.hidden = true; qs.forEach((x) => x.classList.remove('active')); } });
})();
