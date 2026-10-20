// LVK mass-plot embed (19-massplot.html): load the page only once the slide is shown, and when the
// pointer leaves the frame hand focus back to the deck so Space / arrows keep working.
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
  frame.addEventListener('mouseleave', () => {
    if (document.activeElement === frame) { frame.blur(); window.focus(); }
  });
})();
