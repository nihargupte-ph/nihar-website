// LVK mass-plot embed (19-massplot.html): load the page only once the slide is shown, and keep the
// keyboard with the deck so Space / arrows keep working after a click on the plot.
(function () {
  const frame = document.querySelector('.mp__frame:not([data-done])');
  if (!frame) return;
  frame.dataset.done = '1';
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
