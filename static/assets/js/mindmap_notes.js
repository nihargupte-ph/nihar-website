/* Concept search + notes layer for the mindmap viewer.
   Degrades to a plain viewer when the index JSON is missing. */
window.MindmapNotes = (function () {
    'use strict';

    let panzoom, content, container, wrapper, svgObject;
    let index = null;          // parsed <stem>-index.json
    let byId = {};             // concept id -> concept
    let targets = {};          // concept id -> overlay div
    let matches = [], activeIdx = -1;
    let history = [];

    function vbToEl(x, y) {
        const vb = index.viewBox;
        const W = svgObject.clientWidth, H = svgObject.clientHeight;
        const s = Math.min(W / vb[2], H / vb[3]);
        const ox = (W - s * vb[2]) / 2, oy = (H - s * vb[3]) / 2;
        return [(x - vb[0]) * s + ox, (y - vb[1]) * s + oy];
    }

    function buildOverlays() {
        const layer = document.getElementById('overlay-layer');
        layer.innerHTML = '';
        targets = {};
        for (const c of index.concepts) {
            const [x0, y0] = vbToEl(c.bbox[0], c.bbox[1]);
            const [x1, y1] = vbToEl(c.bbox[2], c.bbox[3]);
            const div = document.createElement('div');
            div.className = 'concept-target';
            div.style.left = x0 + 'px';
            div.style.top = y0 + 'px';
            div.style.width = (x1 - x0) + 'px';
            div.style.height = (y1 - y0) + 'px';
            div.dataset.conceptId = c.id;
            layer.appendChild(div);
            targets[c.id] = div;
        }
    }

    function panFactor() {
        var t = content.style.transform || '';
        var scaleIdx = t.indexOf('scale(');
        var translateIdx = t.indexOf('translate(');
        if (scaleIdx !== -1 && translateIdx !== -1 && scaleIdx < translateIdx) {
            return panzoom.getScale() || 1;
        }
        return 1;
    }

    function centerOn(concept) {
        const [x0, y0] = vbToEl(concept.bbox[0], concept.bbox[1]);
        const [x1, y1] = vbToEl(concept.bbox[2], concept.bbox[3]);
        const cRect = container.getBoundingClientRect();
        const targetScale = Math.min(
            50,
            Math.max(0.1, 0.4 * Math.min(cRect.width / (x1 - x0), cRect.height / (y1 - y0)))
        );
        panzoom.zoom(targetScale, { animate: false });
        requestAnimationFrame(function () {
            const el = targets[concept.id].getBoundingClientRect();
            const dx = (cRect.left + cRect.width / 2) - (el.left + el.width / 2);
            const dy = (cRect.top + cRect.height / 2) - (el.top + el.height / 2);
            const f = panFactor();
            const p = panzoom.getPan();
            panzoom.pan(p.x + dx / f, p.y + dy / f, { animate: true });
        });
    }

    function flash(id) {
        const el = targets[id];
        if (!el) return;
        el.classList.remove('hit-flash');
        void el.offsetWidth; // restart animation
        el.classList.add('hit-flash');
    }

    function escapeHtml(s) {
        return s.replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    function snippet(text, q) {
        const i = text.toLowerCase().indexOf(q);
        if (i < 0) return '';
        const a = Math.max(0, i - 40), b = Math.min(text.length, i + q.length + 40);
        const pre = escapeHtml(text.slice(a, i));
        const hit = escapeHtml(text.slice(i, i + q.length));
        const post = escapeHtml(text.slice(i + q.length, b));
        return (a > 0 ? '…' : '') + pre + '<mark>' + hit + '</mark>' + post +
               (b < text.length ? '…' : '');
    }

    function clearHits() {
        for (const id in targets) {
            targets[id].classList.remove('hit', 'hit-active');
        }
    }

    // Re-adds .hit/.hit-active for the current match state. Needed because
    // buildOverlays() (called on resize) rebuilds the overlay divs from
    // scratch, wiping any classes applied by search().
    function reapplyHits() {
        for (const c of matches) {
            if (targets[c.id]) targets[c.id].classList.add('hit');
        }
        if (activeIdx >= 0 && matches[activeIdx] && targets[matches[activeIdx].id]) {
            targets[matches[activeIdx].id].classList.add('hit-active');
        }
    }

    function search(q) {
        q = q.trim().toLowerCase();
        clearHits();
        matches = [];
        activeIdx = -1;
        const results = document.getElementById('search-results');
        const nav = document.getElementById('search-nav');
        if (q.length < 2) {
            results.hidden = true;
            nav.hidden = true;
            return;
        }
        const inTitle = [], inText = [];
        for (const c of index.concepts) {
            if (c.title.toLowerCase().includes(q)) inTitle.push(c);
            else if (c.text.toLowerCase().includes(q)) inText.push(c);
        }
        matches = inTitle.concat(inText);
        results.innerHTML = '';
        for (const c of matches) {
            const div = document.createElement('div');
            div.className = 'search-result';
            div.innerHTML = '<div class="sr-title">' + escapeHtml(c.title) + '</div>' +
                '<div class="sr-snippet">' + (snippet(c.text, q) || snippet(c.title, q)) + '</div>';
            div.addEventListener('mousedown', function (e) {
                e.preventDefault();
                selectMatch(matches.indexOf(c), true);
            });
            results.appendChild(div);
            if (targets[c.id]) targets[c.id].classList.add('hit');
        }
        results.hidden = matches.length === 0;
        nav.hidden = matches.length === 0;
        updateCounter();
    }

    function updateCounter() {
        document.getElementById('search-counter').textContent =
            matches.length ? (activeIdx + 1) + ' of ' + matches.length : '';
        const rows = document.querySelectorAll('.search-result');
        rows.forEach(function (r, i) { r.classList.toggle('selected', i === activeIdx); });
        if (activeIdx >= 0 && rows[activeIdx]) rows[activeIdx].scrollIntoView({ block: 'nearest' });
    }

    function selectMatch(i, closeDropdown) {
        if (!matches.length) return;
        activeIdx = (i + matches.length) % matches.length;
        const c = matches[activeIdx];
        for (const id in targets) targets[id].classList.remove('hit-active');
        if (targets[c.id]) targets[c.id].classList.add('hit-active');
        updateCounter();
        centerOn(c);
        flash(c.id);
        if (closeDropdown) document.getElementById('search-results').hidden = true;
        if (window.MindmapNotes._onSelect) window.MindmapNotes._onSelect(c);
    }

    function renderMath(el) {
        if (window.renderMathInElement) {
            renderMathInElement(el, {
                delimiters: [
                    { left: '$$', right: '$$', display: true },
                    { left: '$', right: '$', display: false },
                ],
                throwOnError: false,
            });
        }
    }

    function chipRow(rowEl, ids) {
        const chips = rowEl.querySelector('.chips');
        chips.innerHTML = '';
        rowEl.hidden = ids.length === 0;
        for (const id of ids) {
            const c = byId[id];
            if (!c) continue;
            const b = document.createElement('button');
            b.className = 'chip';
            b.textContent = c.title;
            b.addEventListener('click', function () {
                centerOn(c);
                flash(c.id);
                openPanel(c, true);
            });
            chips.appendChild(b);
        }
    }

    function openPanel(concept, push) {
        const panel = document.getElementById('concept-panel');
        const current = panel.dataset.conceptId;
        if (push && current && current !== concept.id) history.push(current);
        panel.dataset.conceptId = concept.id;
        panel.hidden = false;
        document.getElementById('panel-back').hidden = history.length === 0;
        document.getElementById('panel-title').textContent = concept.title;
        const textEl = document.getElementById('panel-text');
        textEl.innerHTML = escapeHtml(concept.text).replace(/\n/g, '<br>');
        renderMath(textEl);
        const ctx = document.getElementById('panel-context');
        ctx.hidden = !concept.context;
        ctx.textContent = concept.context || '';
        chipRow(document.getElementById('panel-links-out'), concept.links_out);
        chipRow(document.getElementById('panel-links-in'), concept.links_in);
    }

    function initPanel() {
        document.getElementById('panel-close').addEventListener('click', function () {
            document.getElementById('concept-panel').hidden = true;
            document.getElementById('concept-panel').dataset.conceptId = '';
            history = [];
        });
        document.getElementById('panel-back').addEventListener('click', function () {
            const prev = history.pop();
            if (prev && byId[prev]) {
                centerOn(byId[prev]);
                openPanel(byId[prev], false);
            }
            document.getElementById('panel-back').hidden = history.length === 0;
        });
        // clicks on overlay targets — but not drags
        let downXY = null;
        container.addEventListener('mousedown', function (e) {
            downXY = [e.clientX, e.clientY];
        });
        container.addEventListener('click', function (e) {
            if (downXY && Math.hypot(e.clientX - downXY[0], e.clientY - downXY[1]) > 5) return;
            const t = e.target.closest('.concept-target');
            if (t && byId[t.dataset.conceptId]) {
                openPanel(byId[t.dataset.conceptId], true);
            }
        });

        // Touch tap on overlay targets. The template's own touchstart handler
        // calls preventDefault() (passive: false) to drive custom pan/pinch,
        // which suppresses the synthesized mouse events a touch would
        // otherwise generate — including click. So taps never reach the
        // click listener above on touch devices; handle them here instead.
        // A pinch (2+ touches at any point in the gesture) must never open
        // the panel, so once flagged it stays flagged until every finger
        // lifts and a fresh gesture begins.
        let touchStartXY = null;
        let touchIsPinch = false;
        container.addEventListener('touchstart', function (e) {
            if (e.touches.length >= 2) {
                touchIsPinch = true;
                touchStartXY = null;
                return;
            }
            if (e.touches.length === 1) {
                touchIsPinch = false;
                touchStartXY = [e.touches[0].clientX, e.touches[0].clientY];
            }
        });
        container.addEventListener('touchend', function (e) {
            const wasPinch = touchIsPinch, start = touchStartXY;
            if (e.touches.length === 0) {
                touchIsPinch = false;
            }
            touchStartXY = null;
            if (wasPinch || !start) return;
            const t = e.changedTouches[0];
            if (!t) return;
            const moved = Math.hypot(t.clientX - start[0], t.clientY - start[1]);
            if (moved >= 8) return;
            const el = document.elementFromPoint(t.clientX, t.clientY);
            const target = el && el.closest('.concept-target');
            if (target && byId[target.dataset.conceptId]) {
                openPanel(byId[target.dataset.conceptId], true);
            }
        });

        window.MindmapNotes._onSelect = function (c) { openPanel(c, true); };
    }

    function initSearch() {
        document.getElementById('search-bar').hidden = false;
        const input = document.getElementById('concept-search');
        input.addEventListener('input', function () { search(input.value); });
        input.addEventListener('keydown', function (e) {
            const results = document.getElementById('search-results');
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                results.hidden = false;
                selectMatch(activeIdx + 1, false);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                selectMatch(activeIdx - 1, false);
            } else if (e.key === 'Enter') {
                e.preventDefault();
                selectMatch(Math.max(activeIdx, 0), true);
            } else if (e.key === 'Escape') {
                results.hidden = true;
                input.blur();
            }
        });
        document.getElementById('search-prev').addEventListener('click', function () {
            selectMatch(activeIdx - 1, false);
        });
        document.getElementById('search-next').addEventListener('click', function () {
            selectMatch(activeIdx + 1, false);
        });
    }

    function init(opts) {
        panzoom = opts.panzoom;
        content = opts.content;
        container = opts.container;
        wrapper = opts.wrapper;
        svgObject = document.getElementById('svg-object');
        const url = svgObject.dataset.indexUrl;
        if (!url) return;
        fetch(url)
            .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
            .then(function (data) {
                index = data;
                for (const c of index.concepts) byId[c.id] = c;
                buildOverlays();
                initSearch();
                initPanel();
                window.addEventListener('resize', function () {
                    buildOverlays();
                    reapplyHits();
                });
                if (window.MindmapNotes._onIndexLoaded) {
                    window.MindmapNotes._onIndexLoaded();
                }
            })
            .catch(function () { /* no index — plain viewer */ });
    }

    return {
        init: init,
        centerOn: centerOn,
        flash: flash,
        _state: function () { return { index: index, byId: byId, targets: targets }; },
    };
})();
