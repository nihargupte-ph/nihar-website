(function () {
  const P = (window.Presentations = window.Presentations || {});
  const dataEl = document.querySelector('#deck-data');
  P.data = dataEl ? JSON.parse(dataEl.textContent) : {};
  P.$ = (sel, root) => (root || document).querySelector(sel);
  P.$$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  P.escape = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  P.el = function (tag, attrs, children) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === 'text') e.textContent = v; else if (k === 'html') e.innerHTML = v;
      else if (k === 'class') e.className = v; else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v);
    }
    for (const c of children || []) e.append(c);
    return e;
  };
  const csrf = () => (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/) || [])[1] || '';
  P.api = {
    async get(url) { const r = await fetch(url, { credentials: 'same-origin', cache: 'no-store' }); return r.ok ? r.json() : Promise.reject(await r.json().catch(() => ({ status: r.status }))); },
    async post(url, body) {
      const r = await fetch(url, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() }, body: JSON.stringify(body || {}) });
      return { status: r.status, json: await r.json().catch(() => ({})) };
    },
  };
  P.emit = function (name, detail) { document.dispatchEvent(new CustomEvent('pres:' + name, { detail })); };
  P.on = function (name, cb) { document.addEventListener('pres:' + name, (e) => cb(e.detail)); };
})();
