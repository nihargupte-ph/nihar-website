(function () {
  const P = Presentations; const C = (P.comments = {}); let all = []; let drawing = null; let pendingAnchor = null;
  const panel = () => P.$('#comments-panel'), list = () => P.$('#comment-list'), form = () => P.$('#comment-form');
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
    const ov = P.stage.overlay(id); if (!ov) return; P.$$('.comment-box,.comment-num', ov).forEach((e) => e.remove());
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
  function startDraw() {
    const id = P.stage.current(); const ov = P.stage.overlay(id); if (!ov) { alertText('This slide is a page — use the 💬 marks next to sections.'); return; }
    const inner = ov.parentElement; ov.style.pointerEvents = 'all'; ov.style.cursor = 'crosshair'; let start = null, rect = null;
    const move = (e) => { if (!start) return; const [x, y] = P.stage.px2frac(inner, e.clientX, e.clientY); const r = [Math.min(start[0], x), Math.min(start[1], y), Math.abs(x - start[0]), Math.abs(y - start[1])]; if (rect) rect.remove(); rect = P.stage.rectEl('comment-box active', r); ov.append(rect); drawing = r; };
    const down = (e) => { start = P.stage.px2frac(inner, e.clientX, e.clientY); e.preventDefault(); };
    const up = (e) => {
      if (!start) return; move(e); let r = drawing; if (!r || r[2] < 0.02 || r[3] < 0.02) { const [x, y] = start; r = [Math.max(0, x - 0.1), Math.max(0, y - 0.075), 0.2, 0.15]; if (rect) rect.remove(); rect = P.stage.rectEl('comment-box active', r); ov.append(rect); }
      pendingAnchor = { rect: r.map((v) => Math.round(v * 1000) / 1000) }; P.$('#comment-target').textContent = 'On the boxed region'; start = null;
      ov.style.pointerEvents = ''; ov.style.cursor = ''; ov.removeEventListener('pointerdown', down); ov.removeEventListener('pointermove', move); ov.removeEventListener('pointerup', up); open(true); P.$('textarea', form()).focus();
    };
    ov.addEventListener('pointerdown', down); ov.addEventListener('pointermove', move); ov.addEventListener('pointerup', up); open(false);
  }
  function alertText(t) { const l = list(); l.prepend(P.el('div', { class: 'too-small', text: t })); }
  C.onSlide = () => { pendingAnchor = null; const t = P.$('#comment-target'); if (t) t.textContent = 'On this slide'; render(); };
  C.mount = function () {
    if (!panel()) return; load();
    P.$('#comment-toggle').addEventListener('click', () => open(!panel().classList.contains('open')));
    P.$('#comment-box-btn').addEventListener('click', startDraw);
    form().addEventListener('submit', async (e) => {
      e.preventDefault(); const f = form(); const body = f.body.value.trim(); if (!body) return;
      const r = await P.api.post(P.data.urls.comment, { slide: P.stage.current(), anchor: pendingAnchor, body, author_name: f.author_name.value, website: f.website.value });
      if (r.status === 201) { f.body.value = ''; pendingAnchor = null; P.$('#comment-target').textContent = 'On this slide'; P.$$('.comment-box.active').forEach((x) => x.remove()); await load(); }
      else alertText(r.json.error || 'could not post');
    });
    if (P.data.mode !== 'archive') setInterval(load, 5000);
  };
})();
