(function () {
  const P = Presentations; const C = (P.comments = {}); let all = []; let drawing = null; let pendingAnchor = null; let drawState = null;
  const panel = () => P.$('#comments-panel'), list = () => P.$('#comment-list'), form = () => P.$('#comment-form');
  const notice = () => P.$('#comment-notice');
  const bySlide = (id) => all.filter((c) => c.slide === id);
  async function load() { try { all = (await P.api.get(P.data.urls.comments)).comments; } catch (e) { all = []; } render(); }
  function render() {
    const id = P.stage.current(); const items = bySlide(id); const l = list(); if (!l) return; l.innerHTML = '';
    P.$('#comment-count').textContent = String(all.length);
    items.forEach((c) => { const d = P.el('div', { class: 'comment', 'data-id': c.id }); d.append(P.el('span', { class: 'num', text: c.anchor ? `${c.num}` : '' }), P.el('span', { class: 'who', text: c.author }), P.el('div', { html: c.html })); l.append(d); });
    if (!items.length) l.append(P.el('div', { class: 'too-small', text: 'No questions on this slide yet.' }));
    drawBoxes(id); markAnchors(id);
  }
  function drawBoxes(id) {
    const ov = P.stage.overlay(id); if (!ov) return; P.$$('.comment-box:not(.active),.comment-num', ov).forEach((e) => e.remove());
    bySlide(id).filter((c) => c.anchor && c.anchor.rect).forEach((c) => {
      const r = P.stage.rectEl('comment-box', c.anchor.rect); ov.append(r); const s = P.stage.frac2stage(c.anchor.rect);
      ov.append(P.stage.textEl(s.x + 10, s.y + 38, String(c.num), 'comment-num'));
      r.addEventListener('click', () => { open(true); const el = P.$(`.comment[data-id="${c.id}"]`); if (el) { el.scrollIntoView({ block: 'center' }); el.style.background = '#fff2'; setTimeout(() => (el.style.background = ''), 1200); } });
    });
  }
  function markAnchors(id) {
    const s = P.stage.slideEl(id); if (!s) return;
    P.$$('[data-anchor]', s).forEach((el) => {
      let m = P.$('.anchor-mark', el); if (!m) { m = P.el('span', { class: 'anchor-mark' }); el.append(m); m.addEventListener('click', () => { pendingAnchor = { anchor: el.dataset.anchor }; P.$('#comment-target').textContent = 'On: ' + el.dataset.anchor; open(true); }); }
      const n = bySlide(id).filter((c) => c.anchor && c.anchor.anchor === el.dataset.anchor).length; m.textContent = '💬 ' + (n || '');
    });
  }
  function open(v) { panel().classList.toggle('open', v); }
  function alertText(t) { const n = notice(); if (n) { n.textContent = t; n.hidden = false; } }
  function hideNotice() { const n = notice(); if (n) n.hidden = true; }
  function teardownDraw(removeRect) {
    if (!drawState) return; const st = drawState;
    st.ov.removeEventListener('pointerdown', st.down); st.ov.removeEventListener('pointermove', st.move); st.ov.removeEventListener('pointerup', st.up);
    st.ov.removeEventListener('pointercancel', st.cancel); st.ov.removeEventListener('lostpointercapture', st.cancel);
    document.removeEventListener('keydown', st.escKey);
    if (st.pointerId != null) { try { st.ov.releasePointerCapture(st.pointerId); } catch (err) {} st.pointerId = null; }
    st.ov.style.pointerEvents = ''; st.ov.style.cursor = ''; st.ov.style.touchAction = '';
    document.body.classList.remove('drawing');
    if (removeRect && st.rect) st.rect.remove();
    drawing = null; drawState = null;
  }
  function cancelDraw() { teardownDraw(true); }
  function startDraw() {
    if (drawState) cancelDraw();
    const id = P.stage.current(); const ov = P.stage.overlay(id); if (!ov) { alertText('This slide is a page — use the 💬 marks next to sections.'); return; }
    const inner = ov.parentElement; const st = { ov, start: null, rect: null, pointerId: null }; drawState = st;
    st.move = (e) => { if (!st.start) return; const [x, y] = P.stage.px2frac(inner, e.clientX, e.clientY); const r = [Math.min(st.start[0], x), Math.min(st.start[1], y), Math.abs(x - st.start[0]), Math.abs(y - st.start[1])]; if (st.rect) st.rect.remove(); st.rect = P.stage.rectEl('comment-box active', r); ov.append(st.rect); drawing = r; };
    st.down = (e) => { st.start = P.stage.px2frac(inner, e.clientX, e.clientY); try { ov.setPointerCapture(e.pointerId); st.pointerId = e.pointerId; } catch (err) {} e.preventDefault(); };
    st.up = (e) => {
      if (!st.start) return; st.move(e); let r = drawing;
      if (!r || r[2] < 0.02 || r[3] < 0.02) {
        const [x, y] = st.start; r = [Math.min(Math.max(0, x - 0.1), 0.8), Math.min(Math.max(0, y - 0.075), 0.85), 0.2, 0.15];
        if (st.rect) st.rect.remove(); st.rect = P.stage.rectEl('comment-box active', r); ov.append(st.rect);
      }
      pendingAnchor = { rect: r.map((v) => Math.round(v * 1000) / 1000) }; P.$('#comment-target').textContent = 'On the boxed region';
      teardownDraw(false); open(true); P.$('textarea', form()).focus();
    };
    st.cancel = () => cancelDraw();
    st.escKey = (e) => { if (e.key === 'Escape') cancelDraw(); };
    ov.style.pointerEvents = 'all'; ov.style.cursor = 'crosshair'; ov.style.touchAction = 'none'; document.body.classList.add('drawing');
    ov.addEventListener('pointerdown', st.down); ov.addEventListener('pointermove', st.move); ov.addEventListener('pointerup', st.up);
    ov.addEventListener('pointercancel', st.cancel); ov.addEventListener('lostpointercapture', st.cancel);
    document.addEventListener('keydown', st.escKey);
    open(false);
  }
  C.onSlide = () => { cancelDraw(); pendingAnchor = null; const t = P.$('#comment-target'); if (t) t.textContent = 'On this slide'; hideNotice(); render(); };
  C.mount = function () {
    if (!panel()) return;
    if (!notice()) { const n = P.el('div', { id: 'comment-notice', class: 'too-small' }); n.hidden = true; list().before(n); }
    load();
    P.$('#comment-toggle').addEventListener('click', () => open(!panel().classList.contains('open')));
    P.$('#comment-box-btn').addEventListener('click', startDraw);
    form().addEventListener('submit', async (e) => {
      e.preventDefault(); const f = form(); const body = f.body.value.trim(); if (!body) return;
      let r;
      try { r = await P.api.post(P.data.urls.comment, { slide: P.stage.current(), anchor: pendingAnchor, body, author_name: f.author_name.value, website: f.website.value }); }
      catch (err) { alertText('network error — try again'); return; }
      if (r.status === 201) { f.body.value = ''; pendingAnchor = null; P.$('#comment-target').textContent = 'On this slide'; P.$$('.comment-box.active').forEach((x) => x.remove()); hideNotice(); await load(); }
      else alertText(r.json.error || 'could not post');
    });
    if (P.data.mode !== 'archive') setInterval(load, 5000);
  };
})();
