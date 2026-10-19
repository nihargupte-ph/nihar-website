// Live catalog embed (18-catalog.html): load the page only once the slide is actually shown, then
// scroll it gently past the site navbar to the catalog title. Same origin, so the scroll is allowed.
// When the pointer leaves the frame, hand focus back to the deck so Space / arrows keep working.
(function () {
  const frame = document.querySelector('.cat__frame:not([data-done])');
  if (!frame) return;
  frame.dataset.done = '1';

  const scrollIn = () => {
    let win, doc;
    try { win = frame.contentWindow; doc = frame.contentDocument; } catch (e) { return; }
    if (!doc) return;
    const target = doc.querySelector('.catalog-title');
    const y = target ? target.getBoundingClientRect().top + win.scrollY - 24 : 220;
    setTimeout(() => win.scrollTo({ top: y, behavior: 'smooth' }), 900);
  };
  frame.addEventListener('load', scrollIn);

  const io = new IntersectionObserver((entries) => {
    if (entries.some((e) => e.isIntersecting) && !frame.getAttribute('src')) {
      frame.src = frame.dataset.src;
      io.disconnect();
    }
  });
  io.observe(frame);

  frame.addEventListener('mouseleave', () => {
    if (document.activeElement === frame) { frame.blur(); window.focus(); }
  });
})();
