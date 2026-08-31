(function () {
  const P = Presentations; const U = P.data.urls; let following = true; let live = null; const states = {}; const answered = {};
  for (const [iid, d] of Object.entries(P.data.interactions || {})) states[iid] = d.state;
  const panel = P.$('#ask-panel'), pill = P.$('#follow-pill');
  P.stage.swipe(); P.stage.buttons(); P.hotspots.mount(); if (P.comments) P.comments.mount();
  P.$$('.slide-video').forEach((v) => { v.controls = true; });   // phones have no key handler — give them native controls
  P.stage.onChange((id, n, o) => { if (o.user) { following = id === live; pill.hidden = following; } P.widgets.mountShown(id, states); if (P.comments) P.comments.onSlide(id); });
  pill.addEventListener('click', () => { following = true; pill.hidden = true; if (live) P.stage.go(live); });
  function renderAsk() {
    const open = Object.entries(states).filter(([, s]) => s === 'open').map(([iid]) => iid);
    panel.hidden = !open.length;
    for (const iid of open) {
      if (P.$(`.ask[data-iid="${CSS.escape(iid)}"]`, panel)) continue;
      const d = P.interactions.def(iid); const box = P.el('div', { class: 'ask', 'data-iid': iid }); panel.append(box);
      box.append(P.el('div', { class: 'prompt', text: d.config.prompt })); const body = P.el('div'); box.append(body); const msg = P.el('div', { class: 'n' }); box.append(msg);
      P.interactions.input(iid, body, async (payload) => {
        const r = await P.api.post(U.respond + encodeURIComponent(iid) + '/', payload);
        msg.textContent = r.status === 200 ? '✓ answered — you can change it while it stays open' : (r.json.error || 'could not submit');
        if (r.status === 200) answered[iid] = payload;
      }, answered[iid]);
    }
    P.$$('.ask', panel).forEach((b) => { if (!open.includes(b.dataset.iid)) b.remove(); });
  }
  P.sync.onState((st) => {
    if (st.locked) { location.href = '/presentations/' + P.data.slug + '/'; return; }
    Object.assign(states, st.interactions || {}); live = st.slide;
    if (following && live && live !== P.stage.current()) P.stage.go(live);
    renderAsk(); P.widgets.refreshAll(states);
    const v = P.$('.slide:not([hidden]) video'); if (v && st.video && st.video.playing === false) v.pause();
  });
  P.stage.go(P.data.session && P.data.session.current ? P.data.session.current : 0);
  P.sync.start(U.state, 1500);
})();
