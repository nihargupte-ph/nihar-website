/* Catalog of Eccentric Binary Black Holes — page logic.
 *
 * Renders one box per observing run (O1, O2, O3, O4a), each a responsive
 * grid of per-event cards. Each card plays back a precomputed pyseobnr
 * two-body trajectory + h+ waveform (one early-inspiral cycle, looped
 * slowly), draws a glowing-orb / spacetime-mesh visualization on top of
 * it, and exposes the underlying posteriors via a hover tooltip with
 * three 2D heatmaps.
 *
 * No client-side physics: orbit positions and h+ values come from the
 * precomputed `static/data/trajectories_ecc.h5` shipped by the
 * `catalog_posteriors` view. Visual layers (glow, spin asymmetry, mesh
 * warping) are pure Canvas2D.
 */
(function () {
    "use strict";

    // ---------------------------------------------------------------------
    // Constants
    // ---------------------------------------------------------------------

    // Time-scale: wall-clock seconds per second of physical inspiral. Each
    // event plays at the same physical-time -> wall-clock-time ratio, so
    // longer inspirals stay longer than shorter ones. Long events stay
    // long; short events stay short.
    const TIME_SCALE          = 80;
    const G_OVER_C3           = 4.925491025543576e-6; // s per solar mass
    // After the EOB inspiral hits merger, we transition to a single Kerr
    // remnant for this many wall-clock seconds and ripple the spacetime
    // mesh with a damped sinusoid (the QNM ringdown).
    const RINGDOWN_DURATION_S = 6;
    const TRAIL_SAMPLES  = 480;  // ring buffer length per orb
    const TRAIL_SEGMENTS = 30;   // alpha-fade chunks
    const MESH_N         = 16;   // 16x16 spacetime grid
    const MESH_TILT      = 0.45;
    const KERR_K_MASS    = 0.022;
    const KERR_K_LT      = 0.012;
    // Visual scale of the TT-gauge tidal displacement applied to mesh
    // vertices in the wave zone. Position is multiplied by ~half this
    // value at peak strain (after normalization by the per-event peak),
    // so 0.18 yields ~9% deformation of the vertex coordinate at the
    // orbital boundary.
    const GW_AMP_SCALE   = 0.18;
    const HEATMAP_BINS   = 32;
    const TOOLTIP_HIDE_DELAY_MS = 80;

    // ---- Population-prior reweighting ----------------------------------
    //
    // The page lets the user select a sharp two-bin prior on the
    // population fraction of eccentric events. Below QC_BOUNDARY a sample
    // is "quasicircular", at or above it the sample is "eccentric". The
    // user-selected fraction f is the new prior probability that an
    // event is eccentric (P_new(ecc) = f, P_new(qc) = 1 - f).
    //
    // The original analyses used an approximately-uniform prior on
    // eccentricity over [0, ~0.5], which gives a baseline P_orig(qc) ≈
    // 0.05/0.5 = 0.1. The reweighting factor for a sample i is
    //
    //   factor(i) = P_new(bin_i) / P_orig(bin_i)
    //
    // and the new posterior weight is w_orig(i) * factor(i). After SIR
    // the original weights are uniform 1.0 so the new weight reduces to
    // factor alone.
    const QC_BOUNDARY = 0.05;
    // Fallback P_ORIG_QC when the server doesn't ship a per-event value.
    const P_ORIG_QC_DEFAULT = 0.1;
    const PRIOR_OPTIONS = {
        // null == uniform prior / no reweighting.
        'uniform': null,
        '0.023':   0.023,
        '0.001':   0.001,
    };
    let CURRENT_PRIOR_KEY = '0.023';

    // Fixed set of events highlighted as having observational support
    // for eccentricity (Gupte et al. 2025 Table 2 + selected O3 events).
    // Events with eccentricity data that are NOT part of the paper's
    // analyzed set.  Hidden by default; visible under "all events".
    const NOT_IN_PAPER = new Set([
        'GW230630_070659',
    ]);

    const ECCENTRIC_HIGHLIGHT_EVENTS = new Set([
        'GW190701_203306',
        'GW200129_065458',
        'GW200208_222617',
        'GW230706_104333',
        'GW230709_122727',
        'GW230820_212515',
        'GW231001_140220',
        'GW231114_043211',
        'GW231221_135041',
        'GW231223_032836',
        'GW231224_024321',
        'GW240104_164932',
    ]);

    // Per-event prior factors. The original eccentricity prior was
    // uniform on [0, e_max] where e_max varies by event (0.5 for most
    // O3 events, up to ~0.8 for some O4a). The server ships
    // ``ev.p_orig_qc = 0.05 / e_max`` so the reweighting uses the
    // correct baseline per event.
    function priorFactorsFor(ev, key) {
        const f = PRIOR_OPTIONS[key];
        if (f == null) return { qc: 1, ecc: 1, isUniform: true };
        var pqc = (ev.p_orig_qc != null) ? ev.p_orig_qc : P_ORIG_QC_DEFAULT;
        var pecc = 1 - pqc;
        return {
            qc:  (1 - f) / pqc,
            ecc: f / pecc,
            isUniform: false,
        };
    }

    // Pick the bin (qc or ecc) with the higher log-posterior under the
    // current prior. Falls back to whichever bin has a precomputed
    // trajectory if only one is available; returns null if neither.
    function activeBinFor(ev, key) {
        const factors = priorFactorsFor(ev, key);
        const trajs = ev.trajectories || {};
        const hasQc  = !!(trajs.qc  && trajs.qc.t  && trajs.qc.t.length  > 1);
        const hasEcc = !!(trajs.ecc && trajs.ecc.t && trajs.ecc.t.length > 1);
        if (!hasQc && !hasEcc) return null;
        if (hasQc && !hasEcc) return 'qc';
        if (hasEcc && !hasQc) return 'ecc';
        // Both bins available: log-score = ll_max + log(factor).
        const llQc  = (ev.ll_max_qc  != null) ? ev.ll_max_qc  : -Infinity;
        const llEcc = (ev.ll_max_ecc != null) ? ev.ll_max_ecc : -Infinity;
        const scoreQc  = llQc  + Math.log(factors.qc);
        const scoreEcc = llEcc + Math.log(factors.ecc);
        return scoreQc >= scoreEcc ? 'qc' : 'ecc';
    }

    // Compute reweighted per-sample weights for an event under the
    // current prior. Cached on the event object so the tooltip
    // heatmaps don't recompute on every show.
    //
    // The build script SIRs every event to uniform 1.0 weights so the
    // server doesn't ship the column at all; we synthesize it here on
    // first access.
    function reweightedWeightsFor(ev, key) {
        if (ev._reweighted && ev._reweighted.key === key) {
            return ev._reweighted.weights;
        }
        const factors = priorFactorsFor(ev, key);
        const e = ev.eccentricity;
        const n = e.length;
        const out = new Float64Array(n);
        if (factors.isUniform) {
            for (var i = 0; i < n; i++) out[i] = 1;
        } else {
            for (var i = 0; i < n; i++) {
                out[i] = (e[i] < QC_BOUNDARY) ? factors.qc : factors.ecc;
            }
        }
        ev._reweighted = { key: key, weights: out };
        return out;
    }

    // Per-orb colors. m1 is the larger BH (pyseobnr enforces m1 >= m2 in
    // the Python wrapper), m2 is the smaller. Both are warm "red-hot" hues.
    const ORB_M1_COLOR = [255,  70, 40];   // red-hot   (larger BH)
    const ORB_M2_COLOR = [255, 150, 30];   // orange    (smaller BH)

    const PALETTE = {
        bg:      '#000000',
        text:    '#dee6ee',
        soft:    '#acb4bd',
        muted:   '#838383',
        teal:    '#108bac',
        cyan:    '#29e6ff',
        red:     '#e63929',
        magenta: '#942941',
        maroon:  '#520000',
    };

    // 5-stop "iron" colormap matching the BH glow palette: black -> dark
    // red -> red (m1) -> orange (m2) -> white-hot. Density peaks ping the
    // brightest hue, consistent with the orbs' rim-stripe color.
    const COLORMAP_STOPS = [
        [0.00, [0,     0,   0]],   // bg
        [0.30, [60,   10,   5]],   // dark red
        [0.60, [255,  70,  40]],   // ORB_M1_COLOR (red)
        [0.85, [255, 150,  30]],   // ORB_M2_COLOR (orange)
        [1.00, [255, 245, 200]],   // white-hot
    ];

    // Shared IntersectionObserver for all event boxes.
    let SHARED_IO = null;
    const IO_BOX_LOOKUP = new WeakMap();
    // Global registry of every constructed EventBox so prior changes can
    // broadcast to them all in one pass.
    const ALL_EVENT_BOXES = [];

    // ---------------------------------------------------------------------
    // Bootstrap
    // ---------------------------------------------------------------------

    document.addEventListener("DOMContentLoaded", init);

    const RUN_IDS = ["O1", "O2", "O3", "O4a"];

    function init() {
        const root = document.querySelector(".catalog-blog");
        if (!root) return;

        wireModeSelector(root);
        wirePriorSelector(root);
        wireEventFilter(root);

        // Each run has its own box with its own loading + grid pair. We
        // fetch the posteriors for every run in a single request and then
        // distribute the events into the right box. Boxes that end up
        // with zero events show an "(no events)" message.
        const boxes = [];
        for (let i = 0; i < RUN_IDS.length; i++) {
            const id = RUN_IDS[i];
            const box = document.getElementById("run-" + id);
            if (!box) continue;
            boxes.push({
                run: id,
                el: box,
                loadingEl: box.querySelector(".o4a-loading"),
                gridEl: box.querySelector(".o4a-event-grid"),
            });
        }
        if (boxes.length === 0) return;

        const url = root.dataset.posteriorsUrl;
        if (!url) return;

        fetch(url)
            .then(function (resp) { return resp.json(); })
            .then(function (payload) {
                if (payload.status !== "ok") {
                    throw new Error(payload.message || "Failed to load posteriors");
                }

                // Unhide every grid container BEFORE constructing the
                // cards so getBoundingClientRect returns nonzero widths.
                for (let i = 0; i < boxes.length; i++) {
                    const b = boxes[i];
                    const events = (payload.runs && payload.runs[b.run]) || {};
                    const nEvents = Object.keys(events).length;
                    if (nEvents === 0) {
                        b.loadingEl.textContent = "(no events)";
                        continue;
                    }
                    b.loadingEl.hidden = true;
                    b.gridEl.hidden = false;
                    b.events = events;
                }

                // Defer card construction one frame so the layout has
                // settled and canvas widths are real. Build all runs in
                // a single frame so the IntersectionObserver in
                // EventBox.observeAll sees one combined batch.
                requestAnimationFrame(function () {
                    const allBoxes = [];
                    for (let i = 0; i < boxes.length; i++) {
                        const b = boxes[i];
                        if (!b.events) continue;
                        const built = buildGrid(b.events, b.gridEl);
                        for (let j = 0; j < built.length; j++) {
                            allBoxes.push(built[j]);
                        }
                    }
                    requestAnimationFrame(function () {
                        for (let i = 0; i < allBoxes.length; i++) allBoxes[i].init();
                        EventBox.observeAll(allBoxes);
                    });
                });
            })
            .catch(function (err) {
                for (let i = 0; i < boxes.length; i++) {
                    boxes[i].loadingEl.textContent =
                        "Failed to load posteriors: " + err.message;
                }
            });
    }

    // Wire up the pretty / expert mode toggle.
    function wireModeSelector(root) {
        var modeBtns = root.querySelectorAll('.mode-btn');
        var introSections = {
            tldr:   root.querySelector('.intro-tldr'),
            pretty: root.querySelector('.intro-pretty'),
            expert: root.querySelector('.intro-expert'),
        };
        if (!modeBtns.length) return;

        modeBtns.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var mode = btn.dataset.mode;
                modeBtns.forEach(function (b) {
                    b.classList.toggle('is-active', b === btn);
                });
                Object.keys(introSections).forEach(function (key) {
                    if (introSections[key]) introSections[key].hidden = (key !== mode);
                });
            });
        });
    }

    // Wire up the two-level prior selector:
    //   1. Belief toggle: "I [do / do not] believe every eccentricity is
    //      equally likely."  "do" = uniform prior (no reweighting).
    //   2. Fraction buttons (visible only when "do not"): "I believe
    //      [2.3% / 0.1%] of events are eccentric."
    function wirePriorSelector(root) {
        var beliefBtns = root.querySelectorAll('.prior-belief-btn');
        var fractionBtns = root.querySelectorAll('.prior-btn');
        var fractionSentence = root.querySelector('.prior-fraction-sentence');
        if (!beliefBtns.length || !fractionBtns.length) return;

        // Track which fraction is selected (persisted across belief toggles).
        var activeFraction = '0.023';

        function broadcast(key) {
            if (key === CURRENT_PRIOR_KEY) return;
            CURRENT_PRIOR_KEY = key;
            for (var j = 0; j < ALL_EVENT_BOXES.length; j++) {
                ALL_EVENT_BOXES[j].setPrior(key);
            }
        }

        function setBeliefDo() {
            beliefBtns[0].classList.add('is-active');
            beliefBtns[1].classList.remove('is-active');
            if (fractionSentence) fractionSentence.hidden = true;
            broadcast('uniform');
        }

        function setBeliefDoNot() {
            beliefBtns[0].classList.remove('is-active');
            beliefBtns[1].classList.add('is-active');
            if (fractionSentence) fractionSentence.hidden = false;
            broadcast(activeFraction);
        }

        beliefBtns[0].addEventListener('click', setBeliefDo);
        beliefBtns[1].addEventListener('click', setBeliefDoNot);

        for (var i = 0; i < fractionBtns.length; i++) {
            (function (btn) {
                btn.addEventListener('click', function () {
                    var key = btn.dataset.fraction;
                    if (!(key in PRIOR_OPTIONS) || key === 'uniform') return;
                    activeFraction = key;
                    for (var j = 0; j < fractionBtns.length; j++) {
                        fractionBtns[j].classList.toggle('is-active',
                                                         fractionBtns[j] === btn);
                    }
                    // Only broadcast if "do not" is currently selected.
                    if (beliefBtns[1].classList.contains('is-active')) {
                        broadcast(key);
                    }
                });
            })(fractionBtns[i]);
        }
    }

    // Wire up the event filter toggle: "only analyzed events" vs "all events".
    function wireEventFilter(root) {
        var filterBtns = root.querySelectorAll('.filter-btn');
        if (!filterBtns.length) return;

        for (var i = 0; i < filterBtns.length; i++) {
            (function (btn) {
                btn.addEventListener('click', function () {
                    for (var j = 0; j < filterBtns.length; j++) {
                        filterBtns[j].classList.toggle('is-active',
                                                       filterBtns[j] === btn);
                    }
                    root.classList.toggle('show-all-events',
                                          btn.dataset.filter === 'all');
                });
            })(filterBtns[i]);
        }
    }

    // Build the cards for one run's events into ``container`` and return
    // them. Init + IntersectionObserver registration is left to the
    // caller so all runs can be initialized in one batch.
    function buildGrid(events, container) {
        const names = Object.keys(events).sort();
        const boxes = [];
        for (let i = 0; i < names.length; i++) {
            const name = names[i];
            const ev = events[name];
            const card = new EventBox(name, ev);
            container.appendChild(card.el);
            boxes.push(card);
        }
        return boxes;
    }

    // ---------------------------------------------------------------------
    // Helpers
    // ---------------------------------------------------------------------

    // Sampling importance resampling. Returns N indices into `weights`,
    // each drawn with probability proportional to weights[i]. With N
    // equal to the original sample count this preserves all the
    // information in the weighted posterior while giving back an
    // equally-weighted sample set the heatmap binner can consume
    // directly.
    function importanceResample(weights, N) {
        const M = weights.length;
        if (M === 0 || N === 0) return new Int32Array(0);
        const cum = new Float64Array(M);
        let acc = 0;
        for (let i = 0; i < M; i++) {
            const w = weights[i] > 0 ? weights[i] : 0;
            acc += w;
            cum[i] = acc;
        }
        const total = acc;
        const out = new Int32Array(N);
        if (total <= 0) {
            // Degenerate weights (all zero / negative) — fall back to
            // uniform random sampling so we still draw something.
            for (let i = 0; i < N; i++) out[i] = Math.floor(Math.random() * M);
            return out;
        }
        for (let i = 0; i < N; i++) {
            const r = Math.random() * total;
            let lo = 0, hi = M - 1;
            while (lo < hi) {
                const mid = (lo + hi) >> 1;
                if (cum[mid] < r) lo = mid + 1;
                else hi = mid;
            }
            out[i] = lo;
        }
        return out;
    }

    // True iff the given weight array is non-uniform within tolerance.
    // Avoids paying the SIR cost when the file has equal weights.
    function weightsAreNonUniform(weights) {
        if (!weights || weights.length < 2) return false;
        const w0 = weights[0];
        const tol = Math.max(1e-12, Math.abs(w0) * 1e-9);
        for (let i = 1; i < weights.length; i++) {
            if (Math.abs(weights[i] - w0) > tol) return true;
        }
        return false;
    }

    function clamp(v, lo, hi) {
        return v < lo ? lo : (v > hi ? hi : v);
    }

    // Linear quantile on an already-sorted typed array.
    function quantileSorted(sorted, q) {
        const n = sorted.length;
        if (n === 0) return NaN;
        if (n === 1) return sorted[0];
        const idx = q * (n - 1);
        const lo = Math.floor(idx);
        const hi = Math.ceil(idx);
        return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
    }

    // Median + symmetric 90% credible interval (5th, 95th percentiles)
    // from an array of samples. ``decimals`` controls the formatted
    // string precision. Returns {med, lo, hi} as fixed-width strings
    // ready for display.
    function medianAndCI(samples, decimals) {
        const arr = new Float64Array(samples.length);
        for (let i = 0; i < samples.length; i++) arr[i] = samples[i];
        Array.prototype.sort.call(arr, function (a, b) { return a - b; });
        const med = quantileSorted(arr, 0.5);
        const lo  = quantileSorted(arr, 0.05);
        const hi  = quantileSorted(arr, 0.95);
        return {
            med: med.toFixed(decimals),
            hi: '+' + (hi - med).toFixed(decimals),
            // Unicode minus sign (U+2212) so the "-" doesn't render as
            // a hyphen on narrow glyph stacks.
            lo: '\u2212' + (med - lo).toFixed(decimals),
        };
    }

    function lerp(a, b, t) {
        return a + (b - a) * t;
    }

    function lerpColor(c0, c1, t) {
        return [
            Math.round(lerp(c0[0], c1[0], t)),
            Math.round(lerp(c0[1], c1[1], t)),
            Math.round(lerp(c0[2], c1[2], t)),
        ];
    }

    function colormapMonotone(t) {
        if (t <= 0) {
            const c = COLORMAP_STOPS[0][1];
            return 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
        }
        if (t >= 1) {
            const c = COLORMAP_STOPS[COLORMAP_STOPS.length - 1][1];
            return 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
        }
        for (let i = 0; i < COLORMAP_STOPS.length - 1; i++) {
            const lo = COLORMAP_STOPS[i], hi = COLORMAP_STOPS[i + 1];
            if (t >= lo[0] && t <= hi[0]) {
                const f = (t - lo[0]) / (hi[0] - lo[0]);
                const c = lerpColor(lo[1], hi[1], f);
                return 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
            }
        }
        return PALETTE.bg;
    }

    function setupCanvas(canvas) {
        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        canvas.width = Math.max(1, Math.round(rect.width * dpr));
        canvas.height = Math.max(1, Math.round(rect.height * dpr));
        const ctx = canvas.getContext('2d');
        ctx.scale(dpr, dpr);
        return { ctx: ctx, w: rect.width, h: rect.height };
    }

    // ---------------------------------------------------------------------
    // EventBox: lifecycle owner of one card
    // ---------------------------------------------------------------------

    class EventBox {
        constructor(name, ev) {
            this.name = name;
            this.ev = ev;
            this.tAccum = 0;
            this.lastFrameMs = 0;
            this.rafId = 0;
            this.running = false;
            // Tracked by the IntersectionObserver — independent of
            // ``running`` because a setPrior() call may pause the
            // animation while the card is still in view.
            this.isVisible = false;
            this.tooltip = null;
            this.tooltipHideTimer = 0;
            // Bin (qc/ecc) currently driving the orbit + h+ renderers.
            // Recomputed via setPrior whenever the global prior changes.
            this._noData = !!ev._noData;
            this.activeBin = this._noData ? null : activeBinFor(ev, CURRENT_PRIOR_KEY);

            const card = document.createElement("div");
            card.className = "o4a-event-card";

            const nameEl = document.createElement("div");
            nameEl.className = "ev-name";
            nameEl.textContent = name;
            // Highlight events with observational support for eccentricity.
            if (ECCENTRIC_HIGHLIGHT_EVENTS.has(name)) {
                nameEl.classList.add('ev-name--eccentric');
            }
            card.appendChild(nameEl);

            if (this._noData) {
                // Event has no eccentricity analysis — show placeholder.
                const placeholder = document.createElement("p");
                placeholder.className = "ev-no-ecc-data";
                placeholder.textContent = "no eccentricity data";
                card.appendChild(placeholder);
                card.classList.add("no-ecc-data");
                this._orbitCanvas = null;
                this._hpCanvas = null;
            } else {
                // Always create the canvases if any trajectory exists, even
                // if the currently-active bin is null — a later prior change
                // might activate the other bin and we don't want to rebuild
                // the DOM. The placeholder text only shows up for events
                // with no trajectories at all.
                const trajs = ev.trajectories || {};
                const hasAnyTraj = (
                    (trajs.qc && trajs.qc.t && trajs.qc.t.length > 1) ||
                    (trajs.ecc && trajs.ecc.t && trajs.ecc.t.length > 1)
                );

                if (hasAnyTraj) {
                    const orbitCanvas = document.createElement("canvas");
                    orbitCanvas.className = "ev-orbit";
                    card.appendChild(orbitCanvas);

                    const hpCanvas = document.createElement("canvas");
                    hpCanvas.className = "ev-hp";
                    card.appendChild(hpCanvas);

                    this._orbitCanvas = orbitCanvas;
                    this._hpCanvas = hpCanvas;
                } else {
                    const placeholder = document.createElement("p");
                    placeholder.className = "ev-no-waveform";
                    placeholder.textContent = "(no waveform available)";
                    card.appendChild(placeholder);
                    this._orbitCanvas = null;
                    this._hpCanvas = null;
                }
            }

            // Events not in the paper reuse the no-ecc-data hiding rule
            // so they only appear under "all events".
            if (NOT_IN_PAPER.has(name)) {
                card.classList.add("no-ecc-data");
            }

            this.el = card;
            this._nameEl = nameEl;
            IO_BOX_LOOKUP.set(card, this);
            ALL_EVENT_BOXES.push(this);
        }

        // Look up the trajectory currently selected for this event under
        // the global prior. Returns null if no trajectory is available.
        currentTraj() {
            if (!this.activeBin) return null;
            return this.ev.trajectories[this.activeBin];
        }

        init() {
            this._buildRenderers();
            this._nameEl.addEventListener('mouseenter', this._onNameEnter.bind(this));
            this._nameEl.addEventListener('mouseleave', this._onNameLeave.bind(this));
        }

        // Construct OrbitRenderer + HpRenderer against the active
        // trajectory. Safe to call repeatedly: tears down any prior
        // renderer state and starts fresh from the new traj.
        _buildRenderers() {
            this.orbit = null;
            this.hp = null;
            if (!this._orbitCanvas) return;
            const traj = this.currentTraj();
            if (!traj) return;
            this.orbit = new OrbitRenderer(this._orbitCanvas, traj, traj.ml || {});
            this.hp = new HpRenderer(this._hpCanvas, traj);
        }

        // Re-pick the active bin under a new prior key. Rebuilds the
        // renderers if the active bin actually changed; restarts the
        // animation if the card is currently in view. Also invalidates
        // the lazy tooltip so the heatmaps reweight on next hover.
        setPrior(key) {
            if (this._noData) return;
            // Tear down the tooltip lazily — built on next hover.
            if (this.tooltip) {
                this.tooltip.destroy();
                this.tooltip = null;
            }
            const newBin = activeBinFor(this.ev, key);
            if (newBin === this.activeBin) return;
            this.stop();
            this.activeBin = newBin;
            this.tAccum = 0;
            if (this._orbitCanvas) {
                this._buildRenderers();
            }
            if (this.isVisible && this.orbit) this.start();
        }

        _onNameEnter() {
            if (this._noData) return;
            window.clearTimeout(this.tooltipHideTimer);
            if (!this.tooltip) {
                this.tooltip = new HoverTooltip(this);
            }
            this.tooltip.show(this._nameEl);
        }

        _onNameLeave() {
            if (this._noData) return;
            this._scheduleTooltipHide();
        }

        _cancelTooltipHide() {
            window.clearTimeout(this.tooltipHideTimer);
        }

        _scheduleTooltipHide() {
            const self = this;
            this.tooltipHideTimer = window.setTimeout(function () {
                if (self.tooltip) self.tooltip.hide();
            }, TOOLTIP_HIDE_DELAY_MS);
        }

        start() {
            if (this.running || !this.orbit) return;
            const now = performance.now();
            // If we've been paused for >1s, reset trails to avoid drawing
            // a stale "jump" segment from the previous position.
            if (this.lastFrameMs && (now - this.lastFrameMs) > 1000) {
                this.orbit.resetTrails();
            }
            this.lastFrameMs = now;
            this.running = true;
            const self = this;
            const tick = function (mostRecent) {
                if (!self.running) return;
                const dt = Math.min((mostRecent - self.lastFrameMs) / 1000, 1 / 30);
                self.lastFrameMs = mostRecent;
                self.tAccum += dt;
                self.orbit.draw(self.tAccum);
                self.hp.draw(self.tAccum);
                self.rafId = requestAnimationFrame(tick);
            };
            this.rafId = requestAnimationFrame(tick);
        }

        stop() {
            if (!this.running) return;
            this.running = false;
            cancelAnimationFrame(this.rafId);
        }

        static observeAll(boxes) {
            if (!SHARED_IO) {
                SHARED_IO = new IntersectionObserver(function (entries) {
                    for (let i = 0; i < entries.length; i++) {
                        const e = entries[i];
                        const box = IO_BOX_LOOKUP.get(e.target);
                        if (!box) continue;
                        box.isVisible = e.isIntersecting;
                        if (e.isIntersecting) box.start();
                        else                  box.stop();
                    }
                }, { rootMargin: '200px 0px', threshold: [0, 0.01] });
            }
            for (let i = 0; i < boxes.length; i++) {
                // Observe any card that has canvases — even if the
                // current prior selects no bin, a later prior change
                // might activate one. The IO callback gates animation
                // on whether `orbit` exists at intersection time.
                if (boxes[i]._orbitCanvas) SHARED_IO.observe(boxes[i].el);
            }
        }
    }

    // ---------------------------------------------------------------------
    // OrbitRenderer: pure playback of precomputed (x1, y1, x2, y2) arrays
    // ---------------------------------------------------------------------

    class OrbitRenderer {
        constructor(canvas, traj, ml) {
            const setup = setupCanvas(canvas);
            this.canvas = canvas;
            this.ctx = setup.ctx;
            this.w = setup.w;
            this.h = setup.h;
            this.x1 = traj.x1;
            this.y1 = traj.y1;
            this.x2 = traj.x2;
            this.y2 = traj.y2;
            this.N = traj.t.length;

            // Per-event wall-clock playback duration: physical inspiral
            // length scaled by the global TIME_SCALE constant.
            const physDuration = traj.t[this.N - 1] - traj.t[0];
            this.playbackDuration = Math.max(0.001, physDuration * TIME_SCALE);

            this.m1 = (ml.mass_1 != null) ? ml.mass_1 : 30;
            this.m2 = (ml.mass_2 != null) ? ml.mass_2 : 30;
            this.chi1 = (ml.chi_1 != null) ? ml.chi_1 : 0;
            this.chi2 = (ml.chi_2 != null) ? ml.chi_2 : 0;
            // NR-fit remnant properties from pesummary (precomputed).
            this.finalMass = (ml.final_mass != null) ? ml.final_mass : this.m1 + this.m2;
            this.finalChi  = (ml.final_spin != null) ? ml.final_spin : 0.69;

            // World bounds — manual loop, never spread.
            let maxR = 0;
            for (let i = 0; i < this.N; i++) {
                const a = Math.abs(this.x1[i]);
                const b = Math.abs(this.y1[i]);
                const c = Math.abs(this.x2[i]);
                const d = Math.abs(this.y2[i]);
                if (a > maxR) maxR = a;
                if (b > maxR) maxR = b;
                if (c > maxR) maxR = c;
                if (d > maxR) maxR = d;
            }
            this.maxR = (maxR > 0 ? maxR : 1) * 1.4;

            // Trail ring buffers.
            this.trail1 = new Array(TRAIL_SAMPLES);
            this.trail2 = new Array(TRAIL_SAMPLES);
            for (let i = 0; i < TRAIL_SAMPLES; i++) {
                this.trail1[i] = null;
                this.trail2[i] = null;
            }
            this.trailHead = 0;
            this.trailLen = 0;

            // Mesh base topology — built once.
            this.meshL = 1.6 * this.maxR;
            const N1 = MESH_N + 1;
            this.meshBaseX = new Float32Array(N1 * N1);
            this.meshBaseY = new Float32Array(N1 * N1);
            this.meshZ = new Float32Array(N1 * N1);
            const step = (2 * this.meshL) / MESH_N;
            for (let j = 0; j < N1; j++) {
                for (let i = 0; i < N1; i++) {
                    const idx = j * N1 + i;
                    this.meshBaseX[idx] = -this.meshL + i * step;
                    this.meshBaseY[idx] = -this.meshL + j * step;
                }
            }

            // GW tidal state: precomputed h+ / h_x arrays from pyseobnr
            // (both inspiral and post-merger ringdown), the physical time
            // bounds of each segment, the per-event visualization speed
            // of light c_vis (chosen so the wave traverses the mesh
            // diameter in 10% of the inspiral physical duration), and
            // the strain peak used to normalize amplitudes.
            this.hp     = traj.hp;
            this.hc     = traj.hc || null;
            this.hpRing = (traj.hp_ringdown && traj.hp_ringdown.length > 1)
                          ? traj.hp_ringdown : null;
            this.hcRing = (traj.hc_ringdown && traj.hc_ringdown.length > 1)
                          ? traj.hc_ringdown : null;
            this.tRingArr = (traj.t_ringdown && traj.t_ringdown.length > 1)
                            ? traj.t_ringdown : null;
            this.tPhys0 = traj.t[0];
            this.tPhys1 = traj.t[this.N - 1];
            this.cVis = (2 * this.meshL) / Math.max(0.001, 0.10 * physDuration);

            let pk = 0;
            for (let i = 0; i < this.N; i++) {
                const a = Math.abs(this.hp[i]);
                if (a > pk) pk = a;
                if (this.hc) {
                    const b = Math.abs(this.hc[i]);
                    if (b > pk) pk = b;
                }
            }
            if (this.hpRing) {
                for (let i = 0; i < this.hpRing.length; i++) {
                    const a = Math.abs(this.hpRing[i]);
                    if (a > pk) pk = a;
                }
            }
            if (this.hcRing) {
                for (let i = 0; i < this.hcRing.length; i++) {
                    const a = Math.abs(this.hcRing[i]);
                    if (a > pk) pk = a;
                }
            }
            this.hpPeak = pk || 1;

            // Per-vertex tidal output, refilled each frame.
            this.meshDx = new Float32Array(N1 * N1);
            this.meshDy = new Float32Array(N1 * N1);
            this.meshTidalMag = new Float32Array(N1 * N1);
        }

        resetTrails() {
            for (let i = 0; i < TRAIL_SAMPLES; i++) {
                this.trail1[i] = null;
                this.trail2[i] = null;
            }
            this.trailHead = 0;
            this.trailLen = 0;
        }

        _worldToScreen(x, y) {
            const cx = this.w / 2;
            const cy = this.h / 2;
            const scale = Math.min(this.w, this.h) / (2 * this.maxR);
            return [cx + x * scale, cy - y * scale];
        }

        _positionAt(frac) {
            const idxF = frac * (this.N - 1);
            const i0 = Math.floor(idxF);
            const i1 = Math.min(i0 + 1, this.N - 1);
            const f = idxF - i0;
            return {
                x1: this.x1[i0] + (this.x1[i1] - this.x1[i0]) * f,
                y1: this.y1[i0] + (this.y1[i1] - this.y1[i0]) * f,
                x2: this.x2[i0] + (this.x2[i1] - this.x2[i0]) * f,
                y2: this.y2[i0] + (this.y2[i1] - this.y2[i0]) * f,
            };
        }

        _pushTrail(p) {
            this.trail1[this.trailHead] = { x: p.x1, y: p.y1 };
            this.trail2[this.trailHead] = { x: p.x2, y: p.y2 };
            this.trailHead = (this.trailHead + 1) % TRAIL_SAMPLES;
            if (this.trailLen < TRAIL_SAMPLES) this.trailLen++;
        }

        _orderedTrail(buf) {
            const out = new Array(this.trailLen);
            const startIdx = (this.trailHead - this.trailLen + TRAIL_SAMPLES) % TRAIL_SAMPLES;
            for (let i = 0; i < this.trailLen; i++) {
                out[i] = buf[(startIdx + i) % TRAIL_SAMPLES];
            }
            return out;
        }

        _computeMeshZ(p) {
            const N1 = MESH_N + 1;
            const orbs = [
                { x: p.x1, y: p.y1, m: this.m1, chi: this.chi1 },
                { x: p.x2, y: p.y2, m: this.m2, chi: this.chi2 },
            ];
            for (let j = 0; j < N1; j++) {
                for (let i = 0; i < N1; i++) {
                    const idx = j * N1 + i;
                    const vx = this.meshBaseX[idx];
                    const vy = this.meshBaseY[idx];
                    let z = 0;
                    for (let k = 0; k < 2; k++) {
                        const o = orbs[k];
                        const dx = vx - o.x;
                        const dy = vy - o.y;
                        const r2 = dx * dx + dy * dy;
                        const r = Math.sqrt(r2);
                        const r_min = 0.06 * Math.sqrt(o.m / 30) * this.maxR;
                        const r_eff = Math.max(r, r_min);
                        z -= KERR_K_MASS * o.m / r_eff;
                        const theta = Math.atan2(dy, dx);
                        z -= KERR_K_LT * o.chi * o.m * Math.sin(theta) /
                             Math.max(r_eff * r_eff, r_min * r_min);
                    }
                    this.meshZ[idx] = z;
                }
            }
        }

        _computeMeshZRemnant() {
            // After merger: only the static well of the merged Kerr
            // remnant at the origin. The post-merger ripples now come
            // from the real pyseobnr ringdown polarizations via
            // _computeMeshTidal, not from an analytic damped sinusoid.
            const N1 = MESH_N + 1;
            const M = this.finalMass;
            const rMin = 0.06 * Math.sqrt(M / 30) * this.maxR;
            for (let j = 0; j < N1; j++) {
                for (let i = 0; i < N1; i++) {
                    const idx = j * N1 + i;
                    const vx = this.meshBaseX[idx];
                    const vy = this.meshBaseY[idx];
                    const r = Math.sqrt(vx * vx + vy * vy);
                    this.meshZ[idx] = -KERR_K_MASS * M / Math.max(r, rMin);
                }
            }
        }

        _sampleStrainAtPhysT(tPhys, arr, len, tStart, tEnd) {
            // Linear interp into a uniformly-sampled strain array.
            // Outside [tStart, tEnd] return 0 (the GW hasn't reached the
            // vertex yet at retarded time tPhys) or the boundary value.
            if (tPhys <= tStart) return 0;
            if (tPhys >= tEnd)   return arr[len - 1];
            const f = (tPhys - tStart) / (tEnd - tStart);
            const idxF = f * (len - 1);
            const i0 = Math.floor(idxF);
            const i1 = Math.min(i0 + 1, len - 1);
            const fr = idxF - i0;
            return arr[i0] + (arr[i1] - arr[i0]) * fr;
        }

        _computeMeshTidal(tPhys, hpArr, hcArr, len, tStart, tEnd, rOrbit) {
            // For each mesh vertex outside r_orbit (the "wave zone"),
            // apply the TT-gauge tidal displacement of a free test
            // particle: dx = 1/2 (h+ x + hx y), dy = 1/2 (-h+ y + hx x).
            // h+ and hx at the vertex are looked up at the retarded time
            // t_phys - (r - r_orbit)/c_vis so the wave propagates outward.
            // Amplitude has a 1/r radiation falloff and is normalized by
            // the per-event peak strain.
            const N1 = MESH_N + 1;
            const ampScale = GW_AMP_SCALE / this.hpPeak;
            for (let j = 0; j < N1; j++) {
                for (let i = 0; i < N1; i++) {
                    const idx = j * N1 + i;
                    const vx = this.meshBaseX[idx];
                    const vy = this.meshBaseY[idx];
                    const r = Math.sqrt(vx * vx + vy * vy);
                    if (r <= rOrbit || !hpArr) {
                        this.meshDx[idx] = 0;
                        this.meshDy[idx] = 0;
                        this.meshTidalMag[idx] = 0;
                        continue;
                    }
                    const tau = (r - rOrbit) / this.cVis;
                    const tRet = tPhys - tau;
                    const hpV = this._sampleStrainAtPhysT(tRet, hpArr, len, tStart, tEnd);
                    const hcV = hcArr
                        ? this._sampleStrainAtPhysT(tRet, hcArr, len, tStart, tEnd)
                        : 0;
                    const falloff = rOrbit > 0 ? (rOrbit / r) : (this.meshL * 0.25 / r);
                    const amp = ampScale * falloff;
                    this.meshDx[idx] = 0.5 * amp * ( hpV * vx + hcV * vy);
                    this.meshDy[idx] = 0.5 * amp * (-hpV * vy + hcV * vx);
                    this.meshTidalMag[idx] =
                        falloff * Math.sqrt(hpV * hpV + hcV * hcV) / this.hpPeak;
                }
            }
        }

        _meshScreen(idx) {
            const wx = this.meshBaseX[idx] + this.meshDx[idx];
            const wy = this.meshBaseY[idx] + this.meshDy[idx];
            const z = this.meshZ[idx];
            const cx = this.w / 2;
            const cy = this.h / 2;
            const scale = Math.min(this.w, this.h) / (2 * this.maxR);
            const sx = cx + wx * scale;
            // Negative z near masses -> push the screen-y down (well dips).
            const sy = cy - wy * scale - z * MESH_TILT * scale;
            return [sx, sy];
        }

        _drawMesh() {
            const ctx = this.ctx;
            const N1 = MESH_N + 1;
            const depthScale = 1 / 0.30;
            // Mesh fades to pure black far from the BHs (invisible against
            // the page background) and lights up to a dim red where the
            // depth is greatest, so the only visible portion of the mesh
            // is the dim "halo" of warped spacetime moving with each orb.
            // The tidal-magnitude term lights up the wave zone in the same
            // hue, so the GW pattern reads as a brighter ripple against
            // the dark background.
            const baseColor = [0,   0,   0];
            const wellColor = [64,  18, 10];

            const colorFor = function (zAvg, tidalAvg) {
                const dDepth = clamp(-zAvg * depthScale, 0, 1);
                const dTidal = clamp(tidalAvg * 4.0, 0, 1);
                const d = clamp(dDepth + dTidal * 0.85, 0, 1);
                const c = lerpColor(baseColor, wellColor, d);
                const a = d * 0.9;
                return [
                    'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + a.toFixed(3) + ')',
                    0.4 + d * 1.1,
                ];
            };

            // Horizontal polylines.
            for (let j = 0; j < N1; j++) {
                for (let i = 0; i < MESH_N; i++) {
                    const a = j * N1 + i;
                    const b = j * N1 + i + 1;
                    const cs = colorFor(
                        (this.meshZ[a] + this.meshZ[b]) * 0.5,
                        (this.meshTidalMag[a] + this.meshTidalMag[b]) * 0.5
                    );
                    ctx.strokeStyle = cs[0];
                    ctx.lineWidth = cs[1];
                    const pa = this._meshScreen(a);
                    const pb = this._meshScreen(b);
                    ctx.beginPath();
                    ctx.moveTo(pa[0], pa[1]);
                    ctx.lineTo(pb[0], pb[1]);
                    ctx.stroke();
                }
            }
            // Vertical polylines.
            for (let i = 0; i < N1; i++) {
                for (let j = 0; j < MESH_N; j++) {
                    const a = j * N1 + i;
                    const b = (j + 1) * N1 + i;
                    const cs = colorFor(
                        (this.meshZ[a] + this.meshZ[b]) * 0.5,
                        (this.meshTidalMag[a] + this.meshTidalMag[b]) * 0.5
                    );
                    ctx.strokeStyle = cs[0];
                    ctx.lineWidth = cs[1];
                    const pa = this._meshScreen(a);
                    const pb = this._meshScreen(b);
                    ctx.beginPath();
                    ctx.moveTo(pa[0], pa[1]);
                    ctx.lineTo(pb[0], pb[1]);
                    ctx.stroke();
                }
            }
        }

        _drawTrail(buf, color) {
            if (this.trailLen < 2) return;
            const ctx = this.ctx;
            const ordered = this._orderedTrail(buf);
            const n = ordered.length;
            ctx.lineWidth = 1.4;
            ctx.lineCap = 'round';

            const segLen = Math.max(1, Math.floor(n / TRAIL_SEGMENTS));
            for (let seg = 0; seg < n; seg += segLen) {
                const segEnd = Math.min(seg + segLen + 1, n);
                const alpha = 0.10 + (seg / n) * 0.50;
                ctx.strokeStyle = 'rgba(' + color[0] + ',' + color[1] + ',' + color[2] + ',' + alpha.toFixed(3) + ')';
                ctx.beginPath();
                let started = false;
                for (let i = seg; i < segEnd; i++) {
                    const pt = ordered[i];
                    if (!pt) continue;
                    const sp = this._worldToScreen(pt.x, pt.y);
                    if (!started) { ctx.moveTo(sp[0], sp[1]); started = true; }
                    else          { ctx.lineTo(sp[0], sp[1]); }
                }
                if (started) ctx.stroke();
            }
        }

        _drawOrb(sx, sy, mass, chi, physT, baseColor) {
            const ctx = this.ctx;
            // Schwarzschild radius: r_s = 2m in geometrized units.
            // Trajectory coords are in units of M_total, so r_s = 2*(mass/M_total).
            const M_total = this.m1 + this.m2;
            const scale = Math.min(this.w, this.h) / (2 * this.maxR);
            const rPx = Math.max(2, 2 * (mass / M_total) * scale);
            const rimWidth = Math.max(1.5, rPx * 0.22);

            // Soft warm glow halo using the orb's base color.
            const r0 = baseColor[0], g0 = baseColor[1], b0 = baseColor[2];
            const halo = ctx.createRadialGradient(sx, sy, rPx * 0.6, sx, sy, rPx * 4.0);
            halo.addColorStop(0.00, 'rgba(' + r0 + ',' + g0 + ',' + b0 + ',0.55)');
            halo.addColorStop(0.30, 'rgba(' + Math.round(r0 * 0.85) + ',' +
                                              Math.round(g0 * 0.50) + ',' +
                                              Math.round(b0 * 0.30) + ',0.28)');
            halo.addColorStop(0.65, 'rgba(' + Math.round(r0 * 0.45) + ',' +
                                              Math.round(g0 * 0.20) + ',' +
                                              Math.round(b0 * 0.10) + ',0.10)');
            halo.addColorStop(1.00, 'rgba(0,0,0,0)');
            ctx.fillStyle = halo;
            ctx.fillRect(sx - rPx * 4.0, sy - rPx * 4.0, rPx * 8.0, rPx * 8.0);

            // Black BH interior.
            ctx.fillStyle = '#000';
            ctx.beginPath();
            ctx.arc(sx, sy, rPx, 0, Math.PI * 2);
            ctx.fill();

            // Solid base rim in the orb's color.
            ctx.strokeStyle = 'rgb(' + r0 + ',' + g0 + ',' + b0 + ')';
            ctx.lineWidth = rimWidth;
            ctx.beginPath();
            ctx.arc(sx, sy, rPx, 0, Math.PI * 2);
            ctx.stroke();

            // Kerr horizon angular velocity: Omega_H = chi / (2 * r_+),
            // where r_+ = (m/M)(1 + sqrt(1 - chi^2)) in geometric units.
            // Convert to physical rad/s via M_total * G/c^3.
            const mFrac = mass / M_total;
            const rPlus = mFrac * (1 + Math.sqrt(1 - chi * chi));
            const omegaH = rPlus > 0 ? chi / (2 * rPlus) : 0;
            const omegaPhys = omegaH / (M_total * G_OVER_C3);
            const spinAngle = Math.PI / 6 - omegaPhys * physT;
            const stripeHalfWidth = Math.PI / 14;  // ~13 degrees half-width
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = rimWidth;
            ctx.lineCap = 'round';
            ctx.beginPath();
            ctx.arc(sx, sy, rPx, spinAngle - stripeHalfWidth, spinAngle + stripeHalfWidth);
            ctx.stroke();
            ctx.lineCap = 'butt';
        }

        draw(t) {
            const ctx = this.ctx;
            ctx.clearRect(0, 0, this.w, this.h);

            // Total cycle = inspiral playback + ringdown. Position within
            // the cycle determines which phase we're in.
            const totalCycle = this.playbackDuration + RINGDOWN_DURATION_S;
            let cycleT = t % totalCycle;
            if (cycleT < 0) cycleT += totalCycle;

            const phase = (cycleT < this.playbackDuration) ? 'inspiral' : 'ringdown';

            // Reset trails on a fresh inspiral start (loop wrap or
            // ringdown -> inspiral transition).
            if (this._lastPhase !== phase && phase === 'inspiral') {
                this.resetTrails();
            }
            // Also reset trails when entering ringdown so the static
            // inspiral trail doesn't linger over the rippling mesh.
            if (this._lastPhase !== phase && phase === 'ringdown') {
                this.resetTrails();
            }
            this._lastPhase = phase;

            if (phase === 'inspiral') {
                const frac = cycleT / this.playbackDuration;
                const p = this._positionAt(frac);
                this._pushTrail(p);
                this._computeMeshZ(p);

                // GW tidal deformation in the wave zone (r > r_orbit).
                const fracPhysT = this.tPhys0 + frac * (this.tPhys1 - this.tPhys0);
                const rOrbit = Math.max(
                    Math.sqrt(p.x1 * p.x1 + p.y1 * p.y1),
                    Math.sqrt(p.x2 * p.x2 + p.y2 * p.y2)
                );
                this._computeMeshTidal(
                    fracPhysT, this.hp, this.hc, this.N,
                    this.tPhys0, this.tPhys1, rOrbit
                );

                this._drawMesh();

                this._drawTrail(this.trail1, ORB_M1_COLOR);
                this._drawTrail(this.trail2, ORB_M2_COLOR);

                const s1 = this._worldToScreen(p.x1, p.y1);
                const s2 = this._worldToScreen(p.x2, p.y2);
                this._drawOrb(s1[0], s1[1], this.m1, this.chi1, fracPhysT, ORB_M1_COLOR);
                this._drawOrb(s2[0], s2[1], this.m2, this.chi2, fracPhysT, ORB_M2_COLOR);
            } else {
                const ringT = cycleT - this.playbackDuration;
                const ringPhase = ringT / RINGDOWN_DURATION_S;

                // Static well of the merged Kerr remnant.
                this._computeMeshZRemnant();

                // GW tidal deformation across the entire mesh, sourced
                // by the real pyseobnr post-merger polarizations.
                if (this.hpRing && this.tRingArr) {
                    const ringTStart = this.tRingArr[0];
                    const ringTEnd = this.tRingArr[this.tRingArr.length - 1];
                    const ringPhysSpan = ringTEnd - ringTStart;
                    const tRingPhys = ringTStart + ringPhase * ringPhysSpan;
                    this._computeMeshTidal(
                        tRingPhys, this.hpRing, this.hcRing,
                        this.hpRing.length, ringTStart, ringTEnd, 0
                    );
                } else {
                    // No ringdown polarizations -> clear any leftover
                    // tidal field from the inspiral phase.
                    for (let i = 0; i < this.meshDx.length; i++) {
                        this.meshDx[i] = 0;
                        this.meshDy[i] = 0;
                        this.meshTidalMag[i] = 0;
                    }
                }

                this._drawMesh();

                // Single Kerr remnant at the origin: NR-fit remnant mass
                // and spin, rendered with the m1 color.  Continue the
                // physical clock past merger for the spin tick.
                const physDur = this.tPhys1 - this.tPhys0;
                const remnantPhysT = this.tPhys1 + ringT * (physDur / this.playbackDuration);
                const merged = this._worldToScreen(0, 0);
                this._drawOrb(merged[0], merged[1], this.finalMass, this.finalChi, remnantPhysT, ORB_M1_COLOR);
            }
        }
    }

    // ---------------------------------------------------------------------
    // HpRenderer: pure playback of precomputed h+ array
    // ---------------------------------------------------------------------

    class HpRenderer {
        constructor(canvas, traj) {
            const setup = setupCanvas(canvas);
            this.canvas = canvas;
            this.ctx = setup.ctx;
            this.w = setup.w;
            this.h = setup.h;
            this.hp = traj.hp;
            this.N = this.hp.length;

            // Post-merger ringdown hp from pyseobnr (the polarization
            // continues past merger via attached QNM modes). May be
            // missing or single-sample for events where pyseobnr produced
            // no ringdown samples; the renderer guards against that.
            this.hpRing = (traj.hp_ringdown && traj.hp_ringdown.length > 1)
                ? traj.hp_ringdown
                : null;
            this.NRing = this.hpRing ? this.hpRing.length : 0;

            // Match the orbit renderer's per-event playback duration.
            const physDuration = traj.t[traj.t.length - 1] - traj.t[0];
            this.playbackDuration = Math.max(0.001, physDuration * TIME_SCALE);

            // y-range across BOTH inspiral and ringdown so the merger
            // peak doesn't clip and the ringdown decay stays in frame.
            let lo = Infinity, hi = -Infinity;
            for (let i = 0; i < this.N; i++) {
                const v = this.hp[i];
                if (v < lo) lo = v;
                if (v > hi) hi = v;
            }
            if (this.hpRing) {
                for (let i = 0; i < this.NRing; i++) {
                    const v = this.hpRing[i];
                    if (v < lo) lo = v;
                    if (v > hi) hi = v;
                }
            }
            const span = (hi - lo) || 1;
            this.yMin = lo - 0.10 * span;
            this.yMax = hi + 0.10 * span;
        }

        _yToScreen(y) {
            const pad = 4;
            return pad + (1 - (y - this.yMin) / (this.yMax - this.yMin)) * (this.h - 2 * pad);
        }

        _sample(i) {
            let ii = i % this.N;
            if (ii < 0) ii += this.N;
            const i0 = Math.floor(ii);
            const i1 = (i0 + 1) % this.N;
            const f = ii - i0;
            return this.hp[i0] + (this.hp[i1] - this.hp[i0]) * f;
        }

        draw(t) {
            const ctx = this.ctx;
            ctx.clearRect(0, 0, this.w, this.h);

            // Baseline.
            ctx.strokeStyle = 'rgba(172, 180, 189, 0.18)';
            ctx.lineWidth = 1;
            const y0 = this._yToScreen(0);
            ctx.beginPath();
            ctx.moveTo(0, y0);
            ctx.lineTo(this.w, y0);
            ctx.stroke();

            // The full canvas x-axis represents the inspiral + ringdown
            // cycle. Inspiral occupies x in [0, xMerger]; ringdown — drawn
            // analytically as a damped sinusoid since the EOB dynamics
            // stop at merger — occupies x in [xMerger, w]. The waveform is
            // drawn as a single continuous polyline so the transition at
            // merger is C0-continuous.
            const totalCycle = this.playbackDuration + RINGDOWN_DURATION_S;
            let cycleT = t % totalCycle;
            if (cycleT < 0) cycleT += totalCycle;
            const xMerger = (this.playbackDuration / totalCycle) * this.w;

            let inspiralEndIdx;
            let inRingdown = false;
            let ringFrac = 0;
            if (cycleT < this.playbackDuration) {
                inspiralEndIdx = (cycleT / this.playbackDuration) * (this.N - 1);
            } else {
                inspiralEndIdx = this.N - 1;
                inRingdown = true;
                ringFrac = (cycleT - this.playbackDuration) / RINGDOWN_DURATION_S;
            }

            ctx.strokeStyle = 'rgba(255, 100, 50, 0.95)';
            ctx.lineWidth = 1.3;
            ctx.lineJoin = 'round';
            ctx.beginPath();

            // Inspiral: precomputed hp samples mapped to [0, xMerger].
            const lastFull = Math.floor(inspiralEndIdx);
            for (let i = 0; i <= lastFull; i++) {
                const sx = (i / (this.N - 1)) * xMerger;
                const sy = this._yToScreen(this.hp[i]);
                if (i === 0) ctx.moveTo(sx, sy);
                else         ctx.lineTo(sx, sy);
            }
            if (lastFull < this.N - 1) {
                const f = inspiralEndIdx - lastFull;
                const v = this.hp[lastFull] + (this.hp[lastFull + 1] - this.hp[lastFull]) * f;
                const sx = (inspiralEndIdx / (this.N - 1)) * xMerger;
                const sy = this._yToScreen(v);
                ctx.lineTo(sx, sy);
            }

            // Ringdown: progressive draw of pyseobnr's post-merger hp
            // samples (attached QNM modes), mapped onto x in [xMerger, w].
            // The first ringdown sample equals hp at merger, so the join
            // with the inspiral path is value-continuous.
            if (inRingdown && this.hpRing) {
                const ringEndIdx = ringFrac * (this.NRing - 1);
                const lastRingFull = Math.floor(ringEndIdx);
                for (let i = 0; i <= lastRingFull; i++) {
                    const sx = xMerger + (i / (this.NRing - 1)) * (this.w - xMerger);
                    const sy = this._yToScreen(this.hpRing[i]);
                    ctx.lineTo(sx, sy);
                }
                if (lastRingFull < this.NRing - 1) {
                    const f = ringEndIdx - lastRingFull;
                    const v = this.hpRing[lastRingFull] +
                              (this.hpRing[lastRingFull + 1] - this.hpRing[lastRingFull]) * f;
                    const sx = xMerger + (ringEndIdx / (this.NRing - 1)) * (this.w - xMerger);
                    ctx.lineTo(sx, this._yToScreen(v));
                }
            }

            ctx.stroke();
        }
    }

    // ---------------------------------------------------------------------
    // HeatmapThumbnail: a single 2D posterior density panel
    // ---------------------------------------------------------------------

    class HeatmapThumbnail {
        constructor(canvas, xs, ys, mlX, mlY, xLabel, yLabel) {
            const setup = setupCanvas(canvas);
            this.canvas = canvas;
            this.ctx = setup.ctx;
            this.w = setup.w;
            this.h = setup.h;
            this.xs = xs;
            this.ys = ys;
            // Maximum-likelihood point coordinates in (x, y) space.
            // Passed in directly (not as an index into xs/ys) so callers
            // can resample the posterior with SIR while still marking
            // the true ML sample at its original location.
            this.mlX = mlX;
            this.mlY = mlY;
            this.xLabel = xLabel;
            this.yLabel = yLabel;

            // Range with 5% padding via manual loops.
            let xLo = Infinity, xHi = -Infinity, yLo = Infinity, yHi = -Infinity;
            for (let i = 0; i < xs.length; i++) {
                const xv = xs[i], yv = ys[i];
                if (xv < xLo) xLo = xv;
                if (xv > xHi) xHi = xv;
                if (yv < yLo) yLo = yv;
                if (yv > yHi) yHi = yv;
            }
            const xPad = (xHi - xLo) * 0.05 || 1;
            const yPad = (yHi - yLo) * 0.05 || 1;
            this.xLo = xLo - xPad; this.xHi = xHi + xPad;
            this.yLo = yLo - yPad; this.yHi = yHi + yPad;

            // 2D bin count grid.
            const B = HEATMAP_BINS;
            const bins = new Float32Array(B * B);
            const xRange = this.xHi - this.xLo;
            const yRange = this.yHi - this.yLo;
            for (let i = 0; i < xs.length; i++) {
                const bx = Math.floor((xs[i] - this.xLo) / xRange * B);
                const by = Math.floor((ys[i] - this.yLo) / yRange * B);
                if (bx >= 0 && bx < B && by >= 0 && by < B) {
                    bins[by * B + bx] += 1;
                }
            }
            // Bilinear smooth into a 2B x 2B display grid.
            const D = B * 2;
            const smooth = new Float32Array(D * D);
            const at = function (i, j) {
                if (i < 0) i = 0; if (i >= B) i = B - 1;
                if (j < 0) j = 0; if (j >= B) j = B - 1;
                return bins[j * B + i];
            };
            let maxV = 0;
            for (let j = 0; j < B; j++) {
                for (let i = 0; i < B; i++) {
                    const v00 = at(i, j);
                    const v10 = at(i + 1, j);
                    const v01 = at(i, j + 1);
                    const v11 = at(i + 1, j + 1);
                    smooth[(2 * j) * D + 2 * i] = v00;
                    smooth[(2 * j) * D + 2 * i + 1] = (v00 + v10) * 0.5;
                    smooth[(2 * j + 1) * D + 2 * i] = (v00 + v01) * 0.5;
                    smooth[(2 * j + 1) * D + 2 * i + 1] = (v00 + v10 + v01 + v11) * 0.25;
                    if (v00 > maxV) maxV = v00;
                }
            }
            this.display = smooth;
            this.D = D;
            this.maxV = maxV || 1;
        }

        draw() {
            const ctx = this.ctx;
            const w = this.w, h = this.h;
            ctx.fillStyle = PALETTE.bg;
            ctx.fillRect(0, 0, w, h);

            const ml = 36, mr = 8, mt = 8, mb = 30; // margins
            const plotW = w - ml - mr;
            const plotH = h - mt - mb;

            const D = this.D;
            const cellW = plotW / D;
            const cellH = plotH / D;
            for (let j = 0; j < D; j++) {
                for (let i = 0; i < D; i++) {
                    const v = this.display[j * D + i];
                    if (v <= 0) continue;
                    const t = Math.sqrt(v / this.maxV); // sqrt boost low end
                    ctx.fillStyle = colormapMonotone(t);
                    // Flip y so low data y -> high screen y (canvas down).
                    const dx = ml + i * cellW;
                    const dy = mt + (D - 1 - j) * cellH;
                    // +0.6 overlap to avoid hairline gaps.
                    ctx.fillRect(dx, dy, cellW + 0.6, cellH + 0.6);
                }
            }

            // ML "x" marker.
            const xML = this.mlX;
            const yML = this.mlY;
            const sx = ml + ((xML - this.xLo) / (this.xHi - this.xLo)) * plotW;
            const sy = mt + (1 - (yML - this.yLo) / (this.yHi - this.yLo)) * plotH;
            const r = 5;
            ctx.lineWidth = 2.5;
            ctx.strokeStyle = 'rgba(0, 0, 0, 0.7)';
            ctx.beginPath();
            ctx.moveTo(sx - r, sy - r); ctx.lineTo(sx + r, sy + r);
            ctx.moveTo(sx + r, sy - r); ctx.lineTo(sx - r, sy + r);
            ctx.stroke();
            ctx.lineWidth = 1.5;
            ctx.strokeStyle = PALETTE.text;
            ctx.beginPath();
            ctx.moveTo(sx - r, sy - r); ctx.lineTo(sx + r, sy + r);
            ctx.moveTo(sx + r, sy - r); ctx.lineTo(sx - r, sy + r);
            ctx.stroke();

            // Axis frame.
            ctx.strokeStyle = 'rgba(172, 180, 189, 0.25)';
            ctx.lineWidth = 1;
            ctx.strokeRect(ml, mt, plotW, plotH);

            // --- Axis tick numbers ---
            var tickFont = "8px 'JetBrains Mono', 'Courier New', monospace";
            ctx.font = tickFont;
            ctx.fillStyle = PALETTE.muted;
            var xRange = this.xHi - this.xLo;
            var yRange = this.yHi - this.yLo;

            // Pick decimal places based on value magnitude.
            function fmtTick(val, range) {
                if (range > 100) return Math.round(val).toString();
                if (range > 10) return val.toFixed(1);
                if (range > 1) return val.toFixed(2);
                return val.toFixed(3);
            }

            // X-axis: ticks at left edge, center, and right edge of plot.
            var xTicks = [this.xLo, (this.xLo + this.xHi) / 2, this.xHi];
            ctx.textAlign = 'center';
            var tickY = mt + plotH + 11;
            for (var ti = 0; ti < xTicks.length; ti++) {
                var xFrac = (xTicks[ti] - this.xLo) / xRange;
                var xPx = ml + xFrac * plotW;
                ctx.fillText(fmtTick(xTicks[ti], xRange), xPx, tickY);
            }

            // Y-axis: ticks at bottom edge, center, and top edge of plot.
            var yTicks = [this.yLo, (this.yLo + this.yHi) / 2, this.yHi];
            ctx.textAlign = 'right';
            var tickX = ml - 3;
            for (var ti = 0; ti < yTicks.length; ti++) {
                var yFrac = (yTicks[ti] - this.yLo) / yRange;
                // Flip: low data y -> high screen y.
                var yPx = mt + (1 - yFrac) * plotH + 3;
                ctx.fillText(fmtTick(yTicks[ti], yRange), tickX, yPx);
            }

            // --- Axis labels ---
            ctx.fillStyle = PALETTE.soft;
            ctx.font = "10px 'JetBrains Mono', 'Courier New', monospace";
            ctx.textAlign = 'center';
            ctx.fillText(this.xLabel, ml + plotW / 2, h - 4);
            ctx.save();
            ctx.translate(8, mt + plotH / 2);
            ctx.rotate(-Math.PI / 2);
            ctx.textAlign = 'center';
            ctx.fillText(this.yLabel, 0, 0);
            ctx.restore();
        }
    }

    // ---------------------------------------------------------------------
    // HoverTooltip: lazy-built floating posterior popup
    // ---------------------------------------------------------------------

    class HoverTooltip {
        constructor(box) {
            this.box = box;
            this.el = null;
            this.built = false;
            this._onScroll = null;
        }

        _build() {
            const tt = document.createElement('div');
            tt.className = 'o4a-tooltip';
            tt.hidden = true;

            const ev = this.box.ev;
            // ML marker coordinates: prefer the active bin's MAP index
            // so the marker tracks the prior selection. Events with no
            // active bin have no usable MAP to mark — fall back to
            // sample 0 so the heatmaps still render (the marker is the
            // only visual that suffers).
            const traj = this.box.currentTraj();
            const mlIdx = (traj && traj.ml && traj.ml.ml_idx != null)
                ? traj.ml.ml_idx
                : 0;

            // Reweight the posterior under the current population prior
            // and SIR-resample so the heatmaps reflect the user's prior
            // choice. Same set of resampled indices is reused across all
            // three panels for a consistent realization.
            const weights = reweightedWeightsFor(ev, CURRENT_PRIOR_KEY);
            let resampleIdx = null;
            if (weightsAreNonUniform(weights)) {
                resampleIdx = importanceResample(weights, weights.length);
            }
            const pickSamples = function (arr) {
                if (!resampleIdx) return arr;
                const out = new Float64Array(resampleIdx.length);
                for (let i = 0; i < resampleIdx.length; i++) {
                    out[i] = arr[resampleIdx[i]];
                }
                return out;
            };

            const panels = [
                {
                    xRaw: ev.mass_1, yRaw: ev.mass_2,
                    xl: 'mass_1', yl: 'mass_2',
                },
                {
                    xRaw: ev.chi_1, yRaw: ev.chi_2,
                    xl: 'spin_1', yl: 'spin_2',
                },
                {
                    xRaw: ev.eccentricity, yRaw: ev.relativistic_anomaly,
                    xl: 'eccentricity', yl: 'relativistic anomaly',
                },
            ];

            const panelRow = document.createElement('div');
            panelRow.className = 'tt-panel-row';
            tt.appendChild(panelRow);

            for (let i = 0; i < panels.length; i++) {
                const p = panels[i];
                const cv = document.createElement('canvas');
                cv.className = 'tt-panel';
                panelRow.appendChild(cv);

                // Resampled samples for binning + ML marker pulled from
                // the original (unresampled) arrays at the ML index.
                const xs = pickSamples(p.xRaw);
                const ys = pickSamples(p.yRaw);
                const mlX = p.xRaw[mlIdx];
                const mlY = p.yRaw[mlIdx];

                // Defer thumbnail construction across rAFs to avoid jank.
                requestAnimationFrame(function () {
                    const thumb = new HeatmapThumbnail(cv, xs, ys, mlX, mlY, p.xl, p.yl);
                    thumb.draw();
                });
            }

            // --- median + 90% CI stats block ---
            //
            // Computed from the reweighted resampled cloud so the
            // numbers match what the user sees in the heatmaps above.
            // Each row: label, median, +hi / -lo asymmetric 90% CI,
            // unit. Six parameters: m1, m2, chi_1, chi_2, e, anomaly.
            const STATS_ROWS = [
                { key: 'mass_1',               label: 'm\u2081',       dec: 1, unit: 'M\u2299' },
                { key: 'mass_2',               label: 'm\u2082',       dec: 1, unit: 'M\u2299' },
                { key: 'chi_1',                label: '\u03c7\u2081', dec: 2, unit: '' },
                { key: 'chi_2',                label: '\u03c7\u2082', dec: 2, unit: '' },
                { key: 'eccentricity',         label: 'e',             dec: 3, unit: '' },
                { key: 'relativistic_anomaly', label: 'l',             dec: 2, unit: 'rad' },
            ];
            const statsEl = document.createElement('div');
            statsEl.className = 'tt-stats';
            for (let i = 0; i < STATS_ROWS.length; i++) {
                const row = STATS_ROWS[i];
                const samples = pickSamples(ev[row.key]);
                const fmt = medianAndCI(samples, row.dec);

                const rowEl = document.createElement('div');
                rowEl.className = 'tt-stat-row';

                const labEl = document.createElement('span');
                labEl.className = 'tt-stat-label';
                labEl.textContent = row.label;
                rowEl.appendChild(labEl);

                const valEl = document.createElement('span');
                valEl.className = 'tt-stat-value';
                valEl.textContent = fmt.med;
                rowEl.appendChild(valEl);

                const ciEl = document.createElement('span');
                ciEl.className = 'tt-stat-ci';
                const hiEl = document.createElement('sup');
                hiEl.textContent = fmt.hi;
                const loEl = document.createElement('sub');
                loEl.textContent = fmt.lo;
                ciEl.appendChild(hiEl);
                ciEl.appendChild(loEl);
                rowEl.appendChild(ciEl);

                if (row.unit) {
                    const unitEl = document.createElement('span');
                    unitEl.className = 'tt-stat-unit';
                    unitEl.textContent = row.unit;
                    rowEl.appendChild(unitEl);
                }

                statsEl.appendChild(rowEl);
            }
            tt.appendChild(statsEl);

            const self = this;
            tt.addEventListener('mouseenter', function () { self.box._cancelTooltipHide(); });
            tt.addEventListener('mouseleave', function () { self.box._scheduleTooltipHide(); });

            // Hide on scroll — simpler than chasing the anchor.
            this._onScroll = function () { self.hide(); };
            window.addEventListener('scroll', this._onScroll, { passive: true });

            document.body.appendChild(tt);
            this.el = tt;
            this.built = true;
        }

        show(anchorEl) {
            if (!this.built) this._build();
            this.el.hidden = false;
            // Force layout for size measurement.
            const ttRect = this.el.getBoundingClientRect();
            const aRect = anchorEl.getBoundingClientRect();
            const margin = 8;
            // Prefer right of the anchor.
            let left = aRect.right + margin;
            let top = aRect.top;
            if (left + ttRect.width > window.innerWidth - margin) {
                left = aRect.left - ttRect.width - margin;
            }
            if (left < margin) {
                left = clamp(aRect.left, margin, window.innerWidth - ttRect.width - margin);
                top = aRect.bottom + margin;
            }
            if (top + ttRect.height > window.innerHeight - margin) {
                top = window.innerHeight - ttRect.height - margin;
            }
            if (top < margin) top = margin;
            this.el.style.left = left + 'px';
            this.el.style.top = top + 'px';
        }

        hide() {
            if (!this.built) return;
            this.el.hidden = true;
        }

        // Tear down the tooltip DOM and listeners. Used when the
        // population prior changes — the next hover rebuilds the panels
        // against the freshly reweighted posterior.
        destroy() {
            if (this._onScroll) {
                window.removeEventListener('scroll', this._onScroll);
                this._onScroll = null;
            }
            if (this.el && this.el.parentNode) {
                this.el.parentNode.removeChild(this.el);
            }
            this.el = null;
            this.built = false;
        }
    }

})();
