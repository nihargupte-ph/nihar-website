/* Concept search + notes layer for the mindmap viewer.
   Degrades to a plain viewer when the index JSON is missing. */
window.MindmapNotes = (function () {
    'use strict';

    let panzoom, content, container, wrapper, svgObject;
    let index = null;          // parsed <stem>-index.json
    let byId = {};             // concept id -> concept
    let targets = {};          // concept id -> overlay div
    let panFactorCache = null;

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
        if (panFactorCache) return panFactorCache;
        const before = content.getBoundingClientRect().left;
        const p = panzoom.getPan();
        panzoom.pan(p.x + 10, p.y, { animate: false });
        const after = content.getBoundingClientRect().left;
        panzoom.pan(p.x, p.y, { animate: false });
        panFactorCache = (after - before) / 10 || 1;
        return panFactorCache;
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
        panFactorCache = null; // scale change may change the factor
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
                window.addEventListener('resize', buildOverlays);
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
