(function () {
  const P = (window.Presentations = window.Presentations || {});
  const S = (P.sync = {});
  let timer = null, last = -1, onVis = null; const cbs = [];
  S.onState = (cb) => cbs.push(cb);
  S.start = function (url, interval) {
    S.stop();
    const tick = async () => {
      try {
        const st = await P.api.get(url);
        if (st && typeof st.v === 'number' && st.v > last) { last = st.v; cbs.forEach((cb) => cb(st)); }
      } catch (e) { /* offline blip: keep polling */ }
    };
    tick(); timer = setInterval(tick, interval || 1500);
    onVis = () => { if (!document.hidden) tick(); };
    document.addEventListener('visibilitychange', onVis);
  };
  S.stop = () => { if (timer) clearInterval(timer); timer = null; if (onVis) document.removeEventListener('visibilitychange', onVis); onVis = null; };
  S.reset = () => { last = -1; };
})();
