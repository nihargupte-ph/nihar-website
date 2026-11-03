// EOB flowchart: typeset each copy's maths once. The archive page holds all six reveal steps,
// so select only roots not yet done; KaTeX is deferred too and may not be there yet.
(function () {
  const run = () => {
    if (!window.renderMathInElement) return;
    document.querySelectorAll('.eob:not([data-done])').forEach(root => {
      root.dataset.done = '1';
      renderMathInElement(root, { delimiters: [{ left: '\\(', right: '\\)', display: false }], throwOnError: false });
    });
  };
  if (window.renderMathInElement) run(); else addEventListener('load', run);
})();
