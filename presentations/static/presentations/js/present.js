(function () {
  const P = Presentations; const U = P.data.urls; const states = {}; let hideTimer = null;
  for (const [iid, d] of Object.entries(P.data.interactions || {})) states[iid] = d.state;
  const bar = P.$('#present-bar'), chrome = P.$('#deck-chrome'), ia = P.$('#present-interactions');
  const POLL_SECONDS = 90;                      // a poll runs 1:30, then ends itself
  const deadlines = {};                         // iid -> epoch ms the countdown ends
  function post(url, body) { return P.api.post(url, body); }
  async function setState(iid, s) {
    const r = await post(U.interaction + encodeURIComponent(iid) + '/' + s + '/');
    if (r.status !== 200) return false;
    states[iid] = s;
    if (s === 'open') deadlines[iid] = Date.now() + POLL_SECONDS * 1000; else delete deadlines[iid];
    P.emit('poll-state', { iid, state: s, deadline: deadlines[iid] || null });
    refresh();
    return true;
  }
  P.pollDeadline = (iid) => deadlines[iid] || null;
  // One button per interaction: start it, or end it (which reveals the result to the phones).
  function iaRow(iid) {
    const row = P.el('span', { class: 'ia', 'data-iid': iid }); row.append(P.el('span', { class: 'id', text: iid }));
    const open = states[iid] === 'open';
    row.append(P.el('button', { class: 'btn' + (open ? ' on' : ''), text: open ? 'End poll' : (states[iid] === 'revealed' ? 'Reopen poll' : 'Start poll'),
                                onclick: () => setState(iid, open ? 'revealed' : 'open') }));
    row.append(P.el('button', { class: 'btn', text: 'Clear poll', title: 'delete every answer given so far',
      onclick: async () => {
        if (!confirm('Delete every answer to this poll? People stay joined and can answer again.')) return;
        const r = await post(U.clear + encodeURIComponent(iid) + '/');
        if (r.status === 200) refresh();
      } }));
    return row;
  }
  function refresh() {
    const slide = P.data.slides[P.stage.index()]; ia.innerHTML = '';
    const ids = [...new Set([...(slide.ask || []), ...(slide.show || []).map((r) => r.id)])];
    ids.forEach((iid) => ia.append(iaRow(iid)));
    P.widgets.mountShown(slide.id, states); P.widgets.refreshAll(states);
  }
  // Landing on a slide that asks a still-hidden interaction starts its poll: nothing to click.
  function autoOpen(slideId) {
    const slide = (P.data.slides || []).find((s) => s.id === slideId);
    for (const iid of (slide && slide.ask) || []) {
      if (states[iid] === 'hidden') setState(iid, 'open');
      // already open (a reload, or a revisit): give the clock a fresh 1:30 rather than no clock at all
      else if (states[iid] === 'open' && !deadlines[iid]) { deadlines[iid] = Date.now() + POLL_SECONDS * 1000; refresh(); }
    }
  }
  setInterval(() => {
    for (const [iid, at] of Object.entries(deadlines)) if (Date.now() >= at) setState(iid, 'revealed');
  }, 1000);
  P.stage.keys(() => { const v = P.$('.slide:not([hidden]) video'); if (v) { v.paused ? v.play() : v.pause(); post(U.video, { playing: !v.paused, t: v.currentTime }); } else P.stage.next({ user: true }); });
  P.stage.buttons(); P.hotspots.mount(); if (P.comments) P.comments.mount();
  P.stage.onChange((id) => { if (!P.data.session.locked) post(U.goto, { slide: id }); refresh(); autoOpen(id); if (P.comments) P.comments.onSlide(id); });
  P.$('#lock-btn').addEventListener('click', async () => {
    const locked = P.$('#lock-btn').textContent === 'Unlock';
    if (!locked && !confirm('Lock this session? Interactions freeze and phones are sent to the archive.')) return;
    const r = await post(locked ? U.unlock : U.lock); if (r.status === 200) location.reload();
  });
  P.$('#new-session-btn').addEventListener('click', async () => {
    if (!confirm('Start a brand-new session? The current locked session stays archived.')) return;
    const r = await post(U.new); if (r.status === 200) location.reload();
  });
  if (!P.data.session.locked) {
    P.$$('video').forEach((v) => { v.addEventListener('play', () => post(U.video, { playing: true, t: v.currentTime })); v.addEventListener('pause', () => post(U.video, { playing: false, t: v.currentTime })); });
  }
  const wake = () => { bar.classList.remove('present-bar--hidden'); chrome.classList.remove('deck-chrome--hidden'); clearTimeout(hideTimer); hideTimer = setTimeout(() => { bar.classList.add('present-bar--hidden'); chrome.classList.add('deck-chrome--hidden'); }, 2000); };
  document.addEventListener('mousemove', wake); wake();
  P.sync.onState((st) => { P.$('#participants').textContent = `${st.participants} joined`; });
  P.sync.start(U.state, 1000);
  P.stage.go(P.data.session && P.data.session.current ? P.data.session.current : 0);
  autoOpen(P.stage.current());
  setInterval(() => { const slide = P.data.slides[P.stage.index()]; if ((slide.show || []).some((r) => states[r.id] === 'open' || states[r.id] === 'closed')) P.widgets.refreshAll(states); }, 2000);
})();
