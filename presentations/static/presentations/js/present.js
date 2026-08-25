(function () {
  const P = Presentations; const U = P.data.urls; const states = {}; let hideTimer = null;
  for (const [iid, d] of Object.entries(P.data.interactions || {})) states[iid] = d.state;
  const bar = P.$('#present-bar'), chrome = P.$('#deck-chrome'), qr = P.$('#qr-box'), ia = P.$('#present-interactions');
  const STATES = ['hidden', 'open', 'closed', 'revealed'];
  function post(url, body) { return P.api.post(url, body); }
  function iaRow(iid) {
    const row = P.el('span', { class: 'ia', 'data-iid': iid }); row.append(P.el('span', { class: 'id', text: iid }));
    for (const s of STATES) row.append(P.el('button', { class: 'btn' + (states[iid] === s ? ' on' : ''), text: s, onclick: async () => { const r = await post(U.interaction + encodeURIComponent(iid) + '/' + s + '/'); if (r.status === 200) { states[iid] = s; refresh(); } } }));
    return row;
  }
  function refresh() {
    const slide = P.data.slides[P.stage.index()]; ia.innerHTML = '';
    const ids = [...new Set([...(slide.ask || []), ...(slide.show || []).map((r) => r.id), ...(P.$('#all-interactions').value ? [P.$('#all-interactions').value] : [])])];
    ids.forEach((iid) => ia.append(iaRow(iid)));
    P.widgets.mountShown(slide.id, states); P.widgets.refreshAll(states);
  }
  P.$('#all-interactions').addEventListener('change', refresh);
  P.stage.keys(() => { const v = P.$('.slide:not([hidden]) video'); if (v) { v.paused ? v.play() : v.pause(); post(U.video, { playing: !v.paused, t: v.currentTime }); } else P.stage.next({ user: true }); });
  P.stage.buttons(); P.hotspots.mount(); if (P.comments) P.comments.mount();
  P.stage.onChange((id) => { post(U.goto, { slide: id }); refresh(); if (P.comments) P.comments.onSlide(id); });
  P.$('#qr-toggle').addEventListener('click', () => { qr.hidden = !qr.hidden; });
  P.$('#lock-btn').addEventListener('click', async () => {
    const locked = P.$('#lock-btn').textContent === 'Unlock';
    if (!locked && !confirm('Lock this session? Interactions freeze and phones are sent to the archive.')) return;
    const r = await post(locked ? U.unlock : U.lock); if (r.status === 200) location.reload();
  });
  P.$$('video').forEach((v) => { v.addEventListener('play', () => post(U.video, { playing: true, t: v.currentTime })); v.addEventListener('pause', () => post(U.video, { playing: false, t: v.currentTime })); });
  const wake = () => { bar.classList.remove('present-bar--hidden'); chrome.classList.remove('deck-chrome--hidden'); clearTimeout(hideTimer); hideTimer = setTimeout(() => { bar.classList.add('present-bar--hidden'); chrome.classList.add('deck-chrome--hidden'); }, 2000); };
  document.addEventListener('mousemove', wake); wake();
  P.sync.onState((st) => { P.$('#participants').textContent = `${st.participants} joined`; });
  P.sync.start(U.state, 1000);
  P.stage.go(P.data.session && P.data.session.current ? P.data.session.current : 0);
  setInterval(() => { const slide = P.data.slides[P.stage.index()]; if ((slide.show || []).some((r) => states[r.id] === 'open' || states[r.id] === 'closed')) P.widgets.refreshAll(states); }, 2000);
})();
