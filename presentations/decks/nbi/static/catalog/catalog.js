// Live catalog embed (18-catalog.html): load the page only once the slide is actually shown, then
// scroll it gently past the site navbar to the catalog title. Same origin, so the scroll is allowed.
// A click in the frame would keep the keyboard there, so focus goes straight back to the deck.
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

  // A click inside the frame gives it the keyboard, and keys typed in another page never reach the
  // deck (so the arrows stopped working). The deck's window loses focus at that moment: take it straight
  // back. The click itself still lands -- mouse events go to whatever is under the pointer.
  addEventListener('blur', () => setTimeout(() => {
    if (document.activeElement === frame) { frame.blur(); window.focus(); }
  }, 0));
})();
