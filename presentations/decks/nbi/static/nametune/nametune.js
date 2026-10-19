// page-12 "an aside on degeneracy & waveform length": Name That Tune.
// Three clips (short & loud / quiet through a wall / an impostor), each drawing the log10 Bayes
// factor a listener has accumulated by time t, in step with the audio. The curves and the clip list
// come from nametune.json (tools/nametune.py); the browser only plays and plots.
// The panel is mounted into the underlay's 16:9 box so it sits in the Canva page's empty corner.
(function () {
  const host = document.querySelector('.nt:not([data-done])');
  if (!host) return;
  host.dataset.done = '1';
  const BASE = host.dataset.src;
  const SVGNS = 'http://www.w3.org/2000/svg';
  const COLOURS = ['#5a6fa8', '#b3262e', '#c98a1b'];   // as before: 'through the wall' (teal) was dropped
  // plot geometry, in viewBox units
  const W = 1000, H = 300, X0 = 78, X1 = 900, Y0 = 222, Y1 = 14;
  const YMIN = -1, YMAX = 10, TMAX = 10;
  const PLAY = '<svg viewBox="0 0 10 10"><path d="M2 1l7 4-7 4z"/></svg>';
  const STOP = '<svg viewBox="0 0 10 10"><path d="M2 2h6v6H2z"/></svg>';

  const el = (tag, attrs, parent) => {
    const n = document.createElementNS(SVGNS, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.append(n);
    return n;
  };
  const xOf = (t) => X0 + (X1 - X0) * t / TMAX;
  const yOf = (v) => Y0 - (Y0 - Y1) * (Math.min(Math.max(v, YMIN), YMAX) - YMIN) / (YMAX - YMIN);

  const mount = (data) => {
    const slide = host.closest('.slide');
    const box = slide && slide.querySelector('.stage--underlay .stage__inner');
    if (!box) return;
    const panel = document.createElement('div');
    panel.className = 'nt-panel';
    const row = document.createElement('div');
    row.className = 'nt-row';
    const plot = el('svg', { class: 'nt-plot', viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: 'xMidYMid meet' });
    panel.append(row, plot);
    box.append(panel);

    // axes
    for (let v = 0; v <= YMAX; v += 2) {
      el('line', { class: 'nt-grid', x1: X0, x2: X1, y1: yOf(v), y2: yOf(v) }, plot);
      el('text', { x: X0 - 10, y: yOf(v) + 7, 'text-anchor': 'end', 'font-size': 20 }, plot).textContent = v;
    }
    el('path', { class: 'nt-axis', d: `M${X0} ${Y1}V${Y0}H${X1}` }, plot);
    for (let t = 0; t <= TMAX; t += 2) {
      el('line', { class: 'nt-axis', x1: xOf(t), x2: xOf(t), y1: Y0, y2: Y0 + 6 }, plot);
      el('text', { x: xOf(t), y: Y0 + 28, 'text-anchor': 'middle', 'font-size': 20 }, plot).textContent = t;
    }
    el('text', { x: X1, y: Y0 + 28, 'text-anchor': 'end', 'font-size': 20, dx: 60 }, plot).textContent = 's';
    // the GW reading of the same axis: listening longer = more cycles in band
    const xl = el('text', { x: (X0 + X1) / 2, y: Y0 + 62, 'text-anchor': 'middle', 'font-size': 21 }, plot);
    xl.textContent = 'time listened  ≈  number of cycles';
    const yl = el('text', { 'font-size': 21, 'text-anchor': 'middle', transform: `translate(24 ${(Y0 + Y1) / 2}) rotate(-90)` }, plot);
    yl.textContent = 'log₁₀ Bayes factor';
    const curves = el('g', {}, plot);
    const head = el('line', { class: 'nt-head', y1: Y1, y2: Y0 }, plot);
    head.style.display = 'none';
    const tag = el('text', { 'font-size': 20, 'font-weight': 600 }, plot);

    const audio = new Audio();
    audio.preload = 'auto';
    let active = null;           // {clip, variant, path, btn}
    let raf = 0;

    const variantOf = (clip) => clip.variants
      ? clip.variants.find((v) => v.snr_db === clip.chosen) || clip.variants[0] : clip;

    const draw = (t) => {
      const v = active.variant, c = active.clip;
      const n = Math.min(v.t.length, Math.floor(t * data.fps) + 1);
      let d = '';
      for (let i = 0; i < n; i++) d += (i ? 'L' : 'M') + xOf(v.t[i]).toFixed(1) + ' ' + yOf(v.log10B[i]).toFixed(1);
      active.path.setAttribute('d', d);
      const x = xOf(Math.min(t, c.duration));
      head.setAttribute('x1', x); head.setAttribute('x2', x);
      const last = v.log10B[n - 1] || 0;
      tag.setAttribute('x', Math.min(x + 8, X1 + 8));
      tag.setAttribute('y', Math.max(yOf(last) - 10, Y1 + 4));
      tag.textContent = last > YMAX ? `↑ ${Math.round(last)}` : '';
      // the impostor reads as the song it imitates until the listener's B says otherwise
      if (c.alt_answer) active.btn.querySelector('.nt-btn__answer').textContent = t < c.reveal ? c.alt_answer + '?' : c.answer;
      if (c.reveal != null && t >= c.reveal && !active.revealLine) {
        active.revealLine = el('line', { class: 'nt-reveal', stroke: active.colour, x1: xOf(c.reveal), x2: xOf(c.reveal), y1: Y1, y2: Y0 }, curves);
      }
    };

    const tick = () => {
      if (!active) return;
      draw(audio.currentTime);
      if (!audio.paused && !audio.ended) raf = requestAnimationFrame(tick);
    };

    const stop = (finished) => {
      cancelAnimationFrame(raf);
      if (!active) return;
      if (!audio.paused) audio.pause();
      if (finished) draw(active.clip.duration);
      active.path.classList.add('nt-curve--old');
      active.btn.setAttribute('aria-pressed', 'false');
      active.btn.querySelector('.nt-btn__icon').innerHTML = PLAY;
      if (finished) active.btn.querySelector('.nt-btn__answer').textContent = active.clip.answer;
      head.style.display = 'none';
      tag.textContent = '';
      active = null;
    };

    const play = (clip, btn, colour) => {
      const was = active && active.clip === clip;
      stop(false);
      if (was) return;
      const variant = variantOf(clip);
      const path = el('path', { class: 'nt-curve', stroke: colour }, curves);
      active = { clip, variant, path, btn, colour };
      head.style.display = '';
      btn.setAttribute('aria-pressed', 'true');
      btn.querySelector('.nt-btn__icon').innerHTML = STOP;
      audio.src = BASE + (variant.src || clip.src);
      audio.currentTime = 0;
      audio.play().then(tick, () => stop(false));
    };
    audio.addEventListener('ended', () => stop(true));

    const SLOTS = [
      { id: 'another_room', title: 'In another room' },
      { id: 'short_decisive', title: 'Short but decisive' },
      { id: 'impostor', title: 'The impostor' },
    ];
    SLOTS.forEach((slot, i) => {
      const clip = data.clips.find((c) => c.id === slot.id);
      const btn = document.createElement('button');
      btn.className = 'nt-btn';
      btn.style.setProperty('--c', COLOURS[i]);
      btn.setAttribute('aria-pressed', 'false');
      btn.innerHTML = `<span class="nt-btn__head"><span class="nt-btn__icon">${PLAY}</span><span></span></span>`
        + '<span class="nt-btn__sub"></span><span class="nt-btn__answer"></span>';
      btn.querySelector('.nt-btn__head span:last-child').textContent = `${i + 1} · ` + slot.title;
      btn.querySelector('.nt-btn__sub').textContent = clip ? clip.sub : 'clip not built yet';
      row.append(btn);
      if (!clip) { btn.disabled = true; return; }
      // blur, or the presenter's Space (= next slide) would also re-click the focused card
      btn.addEventListener('click', () => { btn.blur(); play(clip, btn, COLOURS[i]); });
      if (clip.variants) {
        const snr = document.createElement('span');
        snr.className = 'nt-snr';
        for (const v of clip.variants) {
          const b = document.createElement('span');     // not a <button>: it sits inside one
          b.setAttribute('role', 'radio');
          b.textContent = `${v.snr_db} dB`;
          b.title = `music ${v.snr_db} dB re the noise (${v.inband_snr_db} dB below 600 Hz)`;
          b.setAttribute('aria-pressed', String(v.snr_db === clip.chosen));
          b.addEventListener('click', (e) => {
            e.stopPropagation();
            clip.chosen = v.snr_db;
            snr.querySelectorAll('span').forEach((o) => o.setAttribute('aria-pressed', String(o === b)));
          });
          snr.append(b);
        }
        btn.querySelector('.nt-btn__sub').replaceWith(snr);
      }
    });

    const P = window.Presentations;
    if (P && P.stage && P.stage.onChange) P.stage.onChange(() => stop(false));
  };

  // the orbit cartoon goes under the Canva figure, in the same 16:9 box (no data needed)
  const orbits = host.querySelector('.nt-orbits');
  const box = host.closest('.slide') && host.closest('.slide').querySelector('.stage--underlay .stage__inner');
  if (orbits && box) box.append(orbits);
  if (host.dataset.player === '0') return;          // page-12: the figure alone; the player comes on page-12b

  fetch(BASE + 'nametune.json').then((r) => r.json()).then(mount, () => {});
})();
