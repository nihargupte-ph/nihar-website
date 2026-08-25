(function () {
  const P = Presentations; const states = {};
  for (const [iid, d] of Object.entries(P.data.interactions || {})) states[iid] = d.state;
  P.stage.keys(); P.stage.swipe(); P.stage.buttons(); P.hotspots.mount();
  P.stage.onChange((id) => { P.widgets.mountShown(id, states); if (P.comments) P.comments.onSlide(id); });
  if (P.comments) P.comments.mount();
  const hash = location.hash.slice(1);
  P.stage.go(hash && P.data.slides.some((s) => s.id === hash) ? hash : 0);
  P.stage.onChange((id) => history.replaceState(null, '', '#' + id));
})();
