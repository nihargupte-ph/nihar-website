/* ==========================================================================
   Analyzing Eccentric Binary Black Holes — Section 2
   Animated playback of trajectory, polarizations, and whitened strain.
   ========================================================================== */

const COLORS = {
    bh1: '#ef8376',       // coral
    bh2: '#7ec8e3',       // light blue
    hp: '#ef8376',
    hc: '#7ec8e3',
    signal: '#ef8376',
    noise: 'rgba(255, 255, 255, 0.25)',
    grid: 'rgba(255, 255, 255, 0.08)',
    axis: 'rgba(255, 255, 255, 0.3)',
    text: 'rgba(255, 255, 255, 0.55)',
    cursor: 'rgba(255, 255, 255, 0.5)',
};

const PLAYBACK_DURATION = 10; // seconds of screen time


/* ---------- Canvas Utility ---------- */

function setupCanvas(canvas) {
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    return { ctx, w: rect.width, h: rect.height };
}


/* ---------- TrajectoryPlot ---------- */

class TrajectoryPlot {
    constructor(canvasId, data, globalTMin, globalTMax) {
        this.canvas = document.getElementById(canvasId);
        const { ctx, w, h } = setupCanvas(this.canvas);
        this.ctx = ctx;
        this.w = w;
        this.h = h;
        this.data = data; // { t, x1, y1, x2, y2 }
        this.globalTMin = globalTMin;
        this.globalTMax = globalTMax;

        // Compute spatial bounds
        const allX = data.x1.concat(data.x2);
        const allY = data.y1.concat(data.y2);
        const pad = 1.15;
        this.maxR = Math.max(
            Math.max(...allX.map(Math.abs)),
            Math.max(...allY.map(Math.abs))
        ) * pad;
    }

    _toScreen(x, y) {
        const cx = this.w / 2;
        const cy = this.h / 2;
        const scale = Math.min(this.w, this.h) / (2 * this.maxR);
        return [cx + x * scale, cy - y * scale];
    }

    // Find the index in data.t closest to (but not exceeding) tCurrent
    _timeToIndex(tCurrent) {
        const t = this.data.t;
        if (tCurrent <= t[0]) return 0;
        if (tCurrent >= t[t.length - 1]) return t.length - 1;
        // Binary search
        let lo = 0, hi = t.length - 1;
        while (lo < hi) {
            const mid = (lo + hi + 1) >> 1;
            if (t[mid] <= tCurrent) lo = mid;
            else hi = mid - 1;
        }
        return lo;
    }

    draw(tCurrent) {
        const ctx = this.ctx;
        const { w, h } = this;
        ctx.clearRect(0, 0, w, h);

        // Grid crosshairs
        ctx.strokeStyle = COLORS.grid;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(w / 2, 0); ctx.lineTo(w / 2, h);
        ctx.moveTo(0, h / 2); ctx.lineTo(w, h / 2);
        ctx.stroke();

        const idx = this._timeToIndex(tCurrent);

        // Draw trails
        this._drawTrail(this.data.x1, this.data.y1, idx, COLORS.bh1);
        this._drawTrail(this.data.x2, this.data.y2, idx, COLORS.bh2);

        // Draw current position dots
        if (idx >= 0) {
            const [sx1, sy1] = this._toScreen(this.data.x1[idx], this.data.y1[idx]);
            const [sx2, sy2] = this._toScreen(this.data.x2[idx], this.data.y2[idx]);
            this._drawDot(sx1, sy1, 5, COLORS.bh1);
            this._drawDot(sx2, sy2, 5, COLORS.bh2);
        }

        // Label
        ctx.fillStyle = COLORS.text;
        ctx.font = '11px Courier New';
        ctx.fillText('Binary Trajectory', 8, 16);
    }

    _drawTrail(xArr, yArr, endIdx, color) {
        const ctx = this.ctx;
        if (endIdx < 1) return;

        ctx.lineWidth = 1.2;
        ctx.lineCap = 'round';

        const segLen = Math.max(1, Math.floor(endIdx / 20));
        for (let seg = 0; seg < endIdx; seg += segLen) {
            const segEnd = Math.min(seg + segLen + 1, endIdx);
            const alpha = 0.1 + (seg / endIdx) * 0.5;
            ctx.strokeStyle = color.replace(')', `, ${alpha})`).replace('rgb', 'rgba');
            ctx.beginPath();
            for (let i = seg; i < segEnd; i++) {
                const [sx, sy] = this._toScreen(xArr[i], yArr[i]);
                if (i === seg) ctx.moveTo(sx, sy);
                else ctx.lineTo(sx, sy);
            }
            ctx.stroke();
        }
    }

    _drawDot(x, y, r, color) {
        const ctx = this.ctx;
        const grad = ctx.createRadialGradient(x, y, 0, x, y, r * 3);
        grad.addColorStop(0, color.replace(')', ', 0.4)').replace('rgb', 'rgba'));
        grad.addColorStop(1, 'transparent');
        ctx.fillStyle = grad;
        ctx.fillRect(x - r * 3, y - r * 3, r * 6, r * 6);
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fill();
    }
}


/* ---------- TimeSeriesPlot ---------- */

class TimeSeriesPlot {
    constructor(canvasId, options, globalTMin, globalTMax) {
        this.canvas = document.getElementById(canvasId);
        const { ctx, w, h } = setupCanvas(this.canvas);
        this.ctx = ctx;
        this.w = w;
        this.h = h;
        this.label = options.label || '';
        this.series = options.series || [];
        this.yLabel = options.yLabel || '';

        // Use global time range so all plots share the same x-axis
        this.tMin = globalTMin;
        this.tMax = globalTMax;

        // Compute y range from all series
        let yMin = Infinity, yMax = -Infinity;
        for (const s of this.series) {
            for (const v of s.y) {
                if (isFinite(v)) {
                    yMin = Math.min(yMin, v);
                    yMax = Math.max(yMax, v);
                }
            }
        }
        const yPad = (yMax - yMin) * 0.1 || 1e-22;
        this.yMin = yMin - yPad;
        this.yMax = yMax + yPad;

        this.ml = 50;
        this.mr = 10;
        this.mt = 20;
        this.mb = 20;
    }

    _tToX(t) {
        return this.ml + (t - this.tMin) / (this.tMax - this.tMin) * (this.w - this.ml - this.mr);
    }

    _yToY(y) {
        return this.mt + (1 - (y - this.yMin) / (this.yMax - this.yMin)) * (this.h - this.mt - this.mb);
    }

    draw(tCurrent) {
        const ctx = this.ctx;
        const { w, h, ml, mr, mt, mb } = this;
        ctx.clearRect(0, 0, w, h);

        const plotH = h - mt - mb;

        // Background grid
        ctx.strokeStyle = COLORS.grid;
        ctx.lineWidth = 0.5;
        for (let i = 0; i <= 4; i++) {
            const y = mt + (plotH / 4) * i;
            ctx.beginPath();
            ctx.moveTo(ml, y); ctx.lineTo(w - mr, y);
            ctx.stroke();
        }

        // Axes
        ctx.strokeStyle = COLORS.axis;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(ml, mt); ctx.lineTo(ml, h - mb);
        ctx.lineTo(w - mr, h - mb);
        ctx.stroke();

        // Draw each series up to tCurrent
        for (const s of this.series) {
            ctx.strokeStyle = s.color;
            ctx.lineWidth = s.lineWidth || 1;
            ctx.beginPath();
            let started = false;
            for (let i = 0; i < s.t.length; i++) {
                if (s.t[i] > tCurrent) break;
                const sx = this._tToX(s.t[i]);
                const sy = this._yToY(s.y[i]);
                if (!started) { ctx.moveTo(sx, sy); started = true; }
                else { ctx.lineTo(sx, sy); }
            }
            ctx.stroke();
        }

        // Cursor line
        const cursorX = this._tToX(tCurrent);
        ctx.strokeStyle = COLORS.cursor;
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 3]);
        ctx.beginPath();
        ctx.moveTo(cursorX, mt);
        ctx.lineTo(cursorX, h - mb);
        ctx.stroke();
        ctx.setLineDash([]);

        // Labels
        ctx.fillStyle = COLORS.text;
        ctx.font = '11px Courier New';
        ctx.fillText(this.label, ml + 4, mt + 14);

        if (this.yLabel) {
            ctx.save();
            ctx.translate(12, h / 2);
            ctx.rotate(-Math.PI / 2);
            ctx.fillText(this.yLabel, 0, 0);
            ctx.restore();
        }

        ctx.fillText('Time (s)', w - mr - 50, h - 4);
    }
}


/* ---------- SyncedPlayback ---------- */

class SyncedPlayback {
    constructor(plots, globalTMin, globalTMax, duration, onComplete) {
        this.plots = plots;
        this.globalTMin = globalTMin;
        this.globalTMax = globalTMax;
        this.duration = duration * 1000; // ms
        this.startTime = null;
        this.animId = null;
        this.onComplete = onComplete || null;
    }

    start() {
        this.startTime = performance.now();
        this._tick();
    }

    _tick() {
        const elapsed = performance.now() - this.startTime;
        let linearProgress = Math.min(elapsed / this.duration, 1);
        // Ease-in: spend more time on early inspiral
        const progress = Math.pow(linearProgress, 0.7);

        // Map progress to physical time
        const tCurrent = this.globalTMin + progress * (this.globalTMax - this.globalTMin);

        for (const p of this.plots) {
            p.draw(tCurrent);
        }

        if (linearProgress < 1) {
            this.animId = requestAnimationFrame(() => this._tick());
        } else if (this.onComplete) {
            this.onComplete();
            this.onComplete = null;
        }
    }

    stop() {
        if (this.animId) cancelAnimationFrame(this.animId);
    }
}


/* ---------- Main render function (called from section1.js) ---------- */

function renderSection2(data) {
    if (data.status !== 'ok') return;

    // Initialize Section 2 speech bubble
    var bubble2 = new SpeechBubble('speech-bubble-2');
    bubble2.say('Here come the results from the lab...');

    // Compute global time range across ALL data
    const allTimes = [
        data.trajectory.t[0], data.trajectory.t[data.trajectory.t.length - 1],
        data.polarizations.t[0], data.polarizations.t[data.polarizations.t.length - 1],
        data.strain.H1.t[0], data.strain.H1.t[data.strain.H1.t.length - 1],
    ];
    const globalTMin = Math.min(...allTimes);
    const globalTMax = Math.max(...allTimes);

    setTimeout(() => {
        document.getElementById('loading-panels').style.display = 'none';
        document.getElementById('content-panels').style.display = '';

        requestAnimationFrame(() => {
            const trajectoryPlot = new TrajectoryPlot(
                'trajectory-canvas', data.trajectory, globalTMin, globalTMax
            );

            const hpPlot = new TimeSeriesPlot('hp-canvas', {
                label: 'h+ polarization',
                yLabel: 'h+',
                series: [{ t: data.polarizations.t, y: data.polarizations.hp, color: COLORS.hp, lineWidth: 1.5 }],
            }, globalTMin, globalTMax);

            const h1Plot = new TimeSeriesPlot('h1-strain-canvas', {
                label: 'H1 Whitened Strain',
                yLabel: 'H1',
                series: [
                    { t: data.strain.H1.t, y: data.strain.H1.noise_plus_signal, color: COLORS.noise, lineWidth: 0.8 },
                    { t: data.strain.H1.t, y: data.strain.H1.signal, color: COLORS.signal, lineWidth: 1.5 },
                ],
            }, globalTMin, globalTMax);

            const l1Plot = new TimeSeriesPlot('l1-strain-canvas', {
                label: 'L1 Whitened Strain',
                yLabel: 'L1',
                series: [
                    { t: data.strain.L1.t, y: data.strain.L1.noise_plus_signal, color: COLORS.noise, lineWidth: 0.8 },
                    { t: data.strain.L1.t, y: data.strain.L1.signal, color: COLORS.signal, lineWidth: 1.5 },
                ],
            }, globalTMin, globalTMax);

            const playback = new SyncedPlayback(
                [trajectoryPlot, hpPlot, h1Plot, l1Plot],
                globalTMin, globalTMax,
                PLAYBACK_DURATION,
                function () {
                    // Show divider and Section 3 after playback completes
                    var divider = document.getElementById('divider-2-3');
                    if (divider) divider.style.display = '';
                    var section3 = document.getElementById('section-3');
                    if (section3) {
                        section3.style.display = '';
                        section3.scrollIntoView({ behavior: 'smooth' });
                    }
                }
            );
            playback.start();
        });
    }, 500);
}
