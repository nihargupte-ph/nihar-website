/* ==========================================================================
   Section 5 — Astrophysical Implications
   Galaxy, particle simulations, eccentricity histograms.
   ========================================================================== */

var S5 = {};

S5.COLORS = {
    nsc: '#ff6b6b',
    gc: '#4da6ff',
    iso: '#66bb6a',
    gw: '#ffd700',
};

function s5SetupCanvas(canvas) {
    var dpr = window.devicePixelRatio || 1;
    var rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    var ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    return { ctx: ctx, w: rect.width, h: rect.height };
}

/* ==========================================================================
   Subsection 1: Milky Way Galaxy
   ========================================================================== */

function drawGalaxy(canvasId) {
    var canvas = document.getElementById(canvasId);
    if (!canvas) return;
    var s = s5SetupCanvas(canvas);
    var ctx = s.ctx, w = s.w, h = s.h;
    var cx = w / 2, cy = h / 2;

    // Seeded RNG matching Manim (seed=7)
    var seed = 7;
    function rng() { var x = Math.sin(seed++ * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); }
    function gaussRng() {
        var u1 = rng() + 0.001, u2 = rng();
        return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
    }

    var radius = Math.min(w, h) * 0.42;

    // --- Spiral arms (ported from Manim make_spiral_galaxy) ---
    // theta = offset + 1.8 * ln(t + 0.3), r = radius * t / 3.0
    var armDots = 150;
    for (var arm = 0; arm < 2; arm++) {
        var offsetAngle = arm * Math.PI;
        for (var i = 0; i < armDots; i++) {
            var t = 0.25 + 2.8 * i / armDots;
            var theta = offsetAngle + 1.8 * Math.log(t + 0.3);
            var r = radius * t / 3.0;
            // Scatter perpendicular to arm
            var spread = 0.08 * r + 0.03 * radius / 3;
            var dx = gaussRng() * spread;
            var dy = gaussRng() * spread;
            var sx = cx + r * Math.cos(theta) + dx;
            var sy = cy + r * Math.sin(theta) + dy;
            var brightness = 0.3 + rng() * 0.5;
            var sz = 0.5 + rng() * 1.2;
            // Interpolate blue-ish to white
            var bv = Math.floor(brightness * 255);
            var rv = Math.floor(140 + brightness * 80);
            var gv = Math.floor(170 + brightness * 60);
            ctx.fillStyle = 'rgba(' + rv + ',' + gv + ',' + bv + ',' + brightness + ')';
            ctx.beginPath();
            ctx.arc(sx, sy, sz, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    // --- Central bulge — denser, yellower ---
    for (var b = 0; b < 80; b++) {
        var br = Math.abs(gaussRng()) * radius * 0.12;
        var bth = rng() * 2 * Math.PI;
        var bx = cx + br * Math.cos(bth);
        var by = cy + br * Math.sin(bth);
        var bBright = 0.5 + rng() * 0.5;
        var bSz = 0.8 + rng() * 1.8;
        // Yellow to white
        var yR = Math.floor(200 + bBright * 55);
        var yG = Math.floor(180 + bBright * 50);
        var yB = Math.floor(80 + bBright * 100);
        ctx.fillStyle = 'rgba(' + yR + ',' + yG + ',' + yB + ',' + bBright + ')';
        ctx.beginPath();
        ctx.arc(bx, by, bSz, 0, Math.PI * 2);
        ctx.fill();
    }

    // --- Halo objects (sparse, representing GCs) ---
    for (var h2 = 0; h2 < 30; h2++) {
        var hr = rng() * radius * 0.8 + radius * 0.5;
        var hth = rng() * 2 * Math.PI;
        var hx = cx + hr * Math.cos(hth);
        var hy = cy + hr * Math.sin(hth);
        var hSz = 0.8 + rng() * 1.5;
        ctx.fillStyle = 'rgba(100,160,230,' + (0.2 + rng() * 0.3) + ')';
        ctx.beginPath();
        ctx.arc(hx, hy, hSz, 0, Math.PI * 2);
        ctx.fill();
    }

    // --- Dense globular cluster clump (upper-left) ---
    var gcCx = cx - radius * 0.55, gcCy = cy - radius * 0.45;
    for (var k = 0; k < 60; k++) {
        var gr = Math.abs(gaussRng()) * radius * 0.06;
        var gth = rng() * 2 * Math.PI;
        var gx = gcCx + gr * Math.cos(gth);
        var gy = gcCy + gr * Math.sin(gth);
        var gBright = Math.max(0.3, 1.0 - gr / (radius * 0.15));
        var gSz = 0.5 + rng() * 1.2;
        var gcR = Math.floor(160 + gBright * 80);
        var gcG = Math.floor(190 + gBright * 50);
        ctx.fillStyle = 'rgba(' + gcR + ',' + gcG + ',255,' + gBright + ')';
        ctx.beginPath();
        ctx.arc(gx, gy, gSz, 0, Math.PI * 2);
        ctx.fill();
    }

    // --- Labeled boxes ---
    var boxSize = 50;

    // NSC box — center
    var nscBox = { x: cx - boxSize / 2, y: cy - boxSize / 2 };
    ctx.strokeStyle = S5.COLORS.nsc;
    ctx.lineWidth = 2;
    ctx.strokeRect(nscBox.x, nscBox.y, boxSize, boxSize);
    ctx.fillStyle = S5.COLORS.nsc;
    ctx.font = '11px Courier New';
    ctx.fillText('Nuclear Star', nscBox.x - 15, nscBox.y + boxSize + 14);
    ctx.fillText('Cluster', nscBox.x + 2, nscBox.y + boxSize + 27);

    // GC box — upper left
    var gcBox = { x: gcCx - boxSize / 2, y: gcCy - boxSize / 2 };
    ctx.strokeStyle = S5.COLORS.gc;
    ctx.lineWidth = 2;
    ctx.strokeRect(gcBox.x, gcBox.y, boxSize, boxSize);
    ctx.fillStyle = S5.COLORS.gc;
    ctx.fillText('Globular', gcBox.x, gcBox.y - 16);
    ctx.fillText('Cluster', gcBox.x, gcBox.y - 3);

    // Isolated binary box — lower right on arm
    var isoX = cx + radius * 0.4, isoY = cy + radius * 0.35;
    var isoBox = { x: isoX - boxSize / 2, y: isoY - boxSize / 2 };
    ctx.strokeStyle = S5.COLORS.iso;
    ctx.lineWidth = 2;
    ctx.strokeRect(isoBox.x, isoBox.y, boxSize, boxSize);
    ctx.fillStyle = '#ffffff';
    ctx.beginPath(); ctx.arc(isoX - 8, isoY, 3, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(isoX + 8, isoY, 3, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = S5.COLORS.iso;
    ctx.fillText('Isolated', isoBox.x - 5, isoBox.y + boxSize + 14);
    ctx.fillText('Binaries', isoBox.x - 5, isoBox.y + boxSize + 27);
}


/* ==========================================================================
   Subsection 2: Particle Simulations
   ========================================================================== */

function ClusterSim(canvasId, sigma, color, numParticles, clusterType) {
    this.canvas = document.getElementById(canvasId);
    var s = s5SetupCanvas(this.canvas);
    this.ctx = s.ctx;
    this.w = s.w;
    this.h = s.h;
    this.sigma = sigma;
    this.color = color;
    this.particles = [];
    this.boundPairs = [];
    this.gwRipples = [];
    this.elapsed = 0;
    this.clusterType = clusterType || 'gc'; // 'gc' or 'nsc'

    this.vScale = 0.5;

    for (var i = 0; i < numParticles; i++) {
        this.particles.push({
            x: 10 + Math.random() * (this.w - 20),
            y: 10 + Math.random() * (this.h - 20),
            vx: this._gaussRand() * this.sigma * this.vScale * 0.01,
            vy: this._gaussRand() * this.sigma * this.vScale * 0.01,
            captured: false,
        });
    }
}

ClusterSim.prototype._gaussRand = function () {
    var u1 = Math.random(), u2 = Math.random();
    return Math.sqrt(-2 * Math.log(u1 + 0.001)) * Math.cos(2 * Math.PI * u2);
};

ClusterSim.prototype.setSigma = function (s) { this.sigma = s; };

ClusterSim.prototype.step = function (dt) {
    this.elapsed += dt;
    var CAPTURE_SCALE = 14;
    var vRef = this.sigma * this.vScale * 0.01;
    var particles = this.particles;

    for (var i = 0; i < particles.length; i++) {
        var p = particles[i];
        if (p.captured) continue;
        p.vx += this._gaussRand() * this.sigma * this.vScale * 0.003 * dt;
        p.vy += this._gaussRand() * this.sigma * this.vScale * 0.003 * dt;
        var speed = Math.sqrt(p.vx * p.vx + p.vy * p.vy);
        var targetSpeed = this.sigma * this.vScale * 0.01;
        if (speed > 0.001) {
            var factor = 1 + (targetSpeed / speed - 1) * 0.02;
            p.vx *= factor;
            p.vy *= factor;
        }
        p.x += p.vx * dt * 60;
        p.y += p.vy * dt * 60;
        if (p.x < 3) { p.x = 3; p.vx = Math.abs(p.vx); }
        if (p.x > this.w - 3) { p.x = this.w - 3; p.vx = -Math.abs(p.vx); }
        if (p.y < 3) { p.y = 3; p.vy = Math.abs(p.vy); }
        if (p.y > this.h - 3) { p.y = this.h - 3; p.vy = -Math.abs(p.vy); }
    }

    // Warmup period — show only Maxwell-Boltzmann motion before captures begin
    var CAPTURE_DELAY = 5.0; // seconds
    if (this.elapsed < CAPTURE_DELAY) {
        return;
    }

    for (var a = 0; a < particles.length; a++) {
        if (particles[a].captured) continue;
        for (var b = a + 1; b < particles.length; b++) {
            if (particles[b].captured) continue;
            var dx = particles[a].x - particles[b].x;
            var dy = particles[a].y - particles[b].y;
            var dist = Math.sqrt(dx * dx + dy * dy);
            var dvx = particles[a].vx - particles[b].vx;
            var dvy = particles[a].vy - particles[b].vy;
            var vRel = Math.sqrt(dvx * dvx + dvy * dvy);
            var bCapture = CAPTURE_SCALE * Math.pow(vRef / (vRel + 0.0001), 2.0 / 7.0);
            if (dist < bCapture) {
                particles[a].captured = true;
                particles[b].captured = true;
                var midX = (particles[a].x + particles[b].x) / 2;
                var midY = (particles[a].y + particles[b].y) / 2;
                // Eccentricity from relative velocity:
                // Higher v_rel (NSC) → higher eccentricity (closer to 1)
                // Lower v_rel (GC) → lower eccentricity
                var vNorm = vRel / (vRef + 0.001);
                var ecc;
                if (this.clusterType === 'nsc') {
                    ecc = Math.min(0.95, Math.max(0.5, 0.6 + vNorm * 0.2 + Math.random() * 0.15));
                } else {
                    ecc = Math.min(0.6, Math.max(0.05, 0.1 + vNorm * 0.15 + Math.random() * 0.1));
                }
                this.boundPairs.push({
                    cx: midX, cy: midY,
                    a: Math.max(10, dist / 2),
                    e: ecc, phase: 0,
                    tilt: Math.random() * Math.PI,
                });
                this.gwRipples.push({ x: midX, y: midY, r: 0, alpha: 1.0 });
                this.gwRipples.push({ x: midX, y: midY, r: 5, alpha: 0.8 });
                this.gwRipples.push({ x: midX, y: midY, r: 10, alpha: 0.6 });
                break;
            }
        }
    }

    for (var bp = 0; bp < this.boundPairs.length; bp++) {
        var pair = this.boundPairs[bp];
        var omega = 0.08 / Math.pow(pair.a / 20, 1.5);
        var eF = Math.pow(1 + pair.e * Math.cos(pair.phase), 2) / Math.pow(1 - pair.e * pair.e, 1.5);
        pair.phase += omega * eF * dt * 60;
        pair.a *= (1 - 0.0002 * dt * 60);
        pair.e *= (1 - 0.0001 * dt * 60);
        if (pair.a < 5) pair.a = 5;
        if (pair.e < 0.05) pair.e = 0.05;
    }

    for (var g = this.gwRipples.length - 1; g >= 0; g--) {
        this.gwRipples[g].r += 80 * dt;
        this.gwRipples[g].alpha -= 1.5 * dt;
        if (this.gwRipples[g].alpha <= 0) this.gwRipples.splice(g, 1);
    }
};

ClusterSim.prototype.draw = function () {
    var ctx = this.ctx;
    ctx.clearRect(0, 0, this.w, this.h);

    for (var i = 0; i < this.particles.length; i++) {
        var p = this.particles[i];
        if (p.captured) continue;
        ctx.fillStyle = 'rgba(255,255,255,0.08)';
        ctx.beginPath(); ctx.arc(p.x, p.y, 5, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#ffffff';
        ctx.beginPath(); ctx.arc(p.x, p.y, 2, 0, Math.PI * 2); ctx.fill();
    }

    for (var bp = 0; bp < this.boundPairs.length; bp++) {
        var pair = this.boundPairs[bp];
        var r = pair.a * (1 - pair.e * pair.e) / (1 + pair.e * Math.cos(pair.phase));
        var x1 = pair.cx + r * 0.5 * Math.cos(pair.phase + pair.tilt);
        var y1 = pair.cy + r * 0.5 * Math.sin(pair.phase + pair.tilt);
        var x2 = pair.cx - r * 0.5 * Math.cos(pair.phase + pair.tilt);
        var y2 = pair.cy - r * 0.5 * Math.sin(pair.phase + pair.tilt);
        ctx.fillStyle = S5.COLORS.nsc;
        ctx.beginPath(); ctx.arc(x1, y1, 3, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.arc(x2, y2, 3, 0, Math.PI * 2); ctx.fill();
    }

    for (var g = 0; g < this.gwRipples.length; g++) {
        var rip = this.gwRipples[g];
        ctx.strokeStyle = 'rgba(255,215,0,' + Math.max(0, rip.alpha) + ')';
        ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.arc(rip.x, rip.y, rip.r, 0, Math.PI * 2); ctx.stroke();
    }
};


/* ---------- Isolated Binary ---------- */

function IsolatedBinarySim(canvasId, initialEcc) {
    this.canvas = document.getElementById(canvasId);
    var s = s5SetupCanvas(this.canvas);
    this.ctx = s.ctx;
    this.w = s.w;
    this.h = s.h;
    this.a = Math.min(this.w, this.h) * 0.35;
    this.e = initialEcc || 0.3;
    this.phase = 0;
    this.elapsed = 0;
}

IsolatedBinarySim.prototype.step = function (dt) {
    this.elapsed += dt;
    // Fast orbits
    var omega = 0.3 / Math.pow(this.a / 20, 1.5);
    var eF = Math.pow(1 + this.e * Math.cos(this.phase), 2) / Math.pow(1 - this.e * this.e + 0.001, 1.5);
    this.phase += omega * eF * dt * 60;
    // Fast eccentricity decay (Peters-Matthews, accelerated for visual effect)
    // e decays to ~0 over the 10s simulation with many orbits
    var decayRate = 0.008;
    this.e *= (1 - decayRate * dt * 60);
    this.a *= (1 - 0.001 * dt * 60);
    if (this.e < 0.0005) this.e = 0.0005;
    if (this.a < 10) this.a = 10;
};

IsolatedBinarySim.prototype.draw = function () {
    var ctx = this.ctx;
    var cx = this.w / 2, cy = this.h / 2;
    ctx.clearRect(0, 0, this.w, this.h);

    var a = this.a, e = this.e;
    var b = a * Math.sqrt(1 - e * e);
    ctx.strokeStyle = 'rgba(102,187,106,0.2)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.ellipse(cx, cy, a, b, 0, 0, Math.PI * 2);
    ctx.stroke();

    var r = a * (1 - e * e) / (1 + e * Math.cos(this.phase));
    var x1 = cx + r * 0.5 * Math.cos(this.phase);
    var y1 = cy + r * 0.5 * Math.sin(this.phase);
    var x2 = cx - r * 0.5 * Math.cos(this.phase);
    var y2 = cy - r * 0.5 * Math.sin(this.phase);

    // Larger dots for isolated binary
    ctx.fillStyle = 'rgba(102,187,106,0.15)';
    ctx.beginPath(); ctx.arc(x1, y1, 12, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(x2, y2, 12, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = S5.COLORS.iso;
    ctx.beginPath(); ctx.arc(x1, y1, 6, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(x2, y2, 6, 0, Math.PI * 2); ctx.fill();

    ctx.fillStyle = 'rgba(255,255,255,0.4)';
    ctx.font = '10px Courier New';
    ctx.fillText('e = ' + this.e.toFixed(3), 6, 14);
};


/* ==========================================================================
   Subsection 3: Eccentricity Histograms
   ========================================================================== */

function S5HistogramPlot(canvasId, samples, label, color, nBins, xMinShared, xMaxShared) {
    this.canvas = document.getElementById(canvasId);
    var s = s5SetupCanvas(this.canvas);
    this.ctx = s.ctx;
    this.w = s.w;
    this.h = s.h;
    this.label = label;
    this.color = color;
    this.nBins = nBins || 40;
    this.ml = 16; this.mr = 16; this.mt = 36; this.mb = 36;

    if (xMinShared !== undefined && xMaxShared !== undefined) {
        this.xMin = xMinShared;
        this.xMax = xMaxShared;
    } else {
        var min = Math.min.apply(null, samples);
        var max = Math.max.apply(null, samples);
        var pad = (max - min) * 0.05 || 0.01;
        this.xMin = min - pad;
        this.xMax = max + pad;
    }
    var binWidth = (this.xMax - this.xMin) / this.nBins;
    this.bins = new Array(this.nBins).fill(0);
    for (var i = 0; i < samples.length; i++) {
        var idx = Math.min(Math.floor((samples[i] - this.xMin) / binWidth), this.nBins - 1);
        if (idx >= 0) this.bins[idx]++;
    }
    this.maxCount = Math.max.apply(null, this.bins);
}

S5HistogramPlot.prototype.draw = function (progress) {
    var ctx = this.ctx;
    var w = this.w, h = this.h;
    var ml = this.ml, mr = this.mr, mt = this.mt, mb = this.mb;
    var plotW = w - ml - mr, plotH = h - mt - mb;
    ctx.clearRect(0, 0, w, h);

    var binsToShow = Math.ceil(progress * this.nBins);
    var barW = plotW / this.nBins;

    for (var i = 0; i < binsToShow; i++) {
        var barH = (this.bins[i] / this.maxCount) * plotH;
        ctx.fillStyle = this.color.replace(')', ',0.5)').replace('rgb', 'rgba');
        ctx.fillRect(ml + i * barW, mt + plotH - barH, barW - 1, barH);
    }

    ctx.strokeStyle = 'rgba(255,255,255,0.3)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(ml, mt + plotH); ctx.lineTo(w - mr, mt + plotH);
    ctx.stroke();

    ctx.fillStyle = this.color;
    ctx.font = '20px Courier New';
    ctx.fillText(this.label, ml + 4, mt - 10);

    ctx.fillStyle = 'rgba(255,255,255,0.5)';
    ctx.font = '16px Courier New';
    ctx.textAlign = 'left';
    ctx.fillText(this.xMin.toFixed(1), ml, h - 8);
    ctx.textAlign = 'right';
    ctx.fillText(this.xMax.toFixed(1), w - mr, h - 8);
    ctx.textAlign = 'center';
    ctx.fillText('log\u2081\u2080(e)', w / 2, h - 8);
    ctx.textAlign = 'left';
};


/* ==========================================================================
   Initialization
   ========================================================================== */

document.addEventListener('DOMContentLoaded', function () {
    var zoomBtn = document.getElementById('zoom-btn');
    var simBtn = document.getElementById('sim-channels-btn');
    var nscSlider = document.getElementById('nsc-sigma');
    var gcSlider = document.getElementById('gc-sigma');
    var nscVal = document.getElementById('nsc-sigma-val');
    var gcVal = document.getElementById('gc-sigma-val');

    if (!zoomBtn) return;

    var nscSim = null, gcSim = null, isoSim = null;
    var simAnimId = null;
    var SIM_DURATION = 15; // seconds (5s warmup + 10s captures)

    // Draw galaxy when section becomes visible
    var observer = new MutationObserver(function () {
        var s5 = document.getElementById('section-5');
        if (s5 && s5.style.display !== 'none' && !S5.galaxyDrawn) {
            S5.galaxyDrawn = true;
            setTimeout(function () { drawGalaxy('galaxy-canvas'); }, 150);
        }
    });
    var s5El = document.getElementById('section-5');
    if (s5El) observer.observe(s5El, { attributes: true, attributeFilter: ['style'] });

    var isoSlider = document.getElementById('iso-ecc');
    var isoVal = document.getElementById('iso-ecc-val');

    // Slider updates
    if (nscSlider) nscSlider.addEventListener('input', function () {
        nscVal.textContent = this.value;
        if (nscSim) nscSim.setSigma(parseInt(this.value));
    });
    if (gcSlider) gcSlider.addEventListener('input', function () {
        gcVal.textContent = this.value;
        if (gcSim) gcSim.setSigma(parseInt(this.value));
    });
    if (isoSlider) isoSlider.addEventListener('input', function () {
        isoVal.textContent = parseFloat(this.value).toFixed(2);
    });

    // --- Zoom In button: show subsection 2 (but don't start sims) ---
    zoomBtn.addEventListener('click', function () {
        document.getElementById('arrow-1-2').style.display = '';
        document.getElementById('sub-sims').style.opacity = '1';
        zoomBtn.disabled = true;
        zoomBtn.style.opacity = '0.4';
    });

    // --- Simulate button: start sims, run for SIM_DURATION, then show histograms ---
    simBtn.addEventListener('click', function () {
        simBtn.disabled = true;
        simBtn.style.opacity = '0.4';

        // Initialize simulations
        nscSim = new ClusterSim('nsc-sim-canvas', parseInt(nscSlider.value), S5.COLORS.nsc, 25, 'nsc');
        gcSim = new ClusterSim('gc-sim-canvas', parseInt(gcSlider.value), S5.COLORS.gc, 25, 'gc');
        var isoEcc = document.getElementById('iso-ecc');
        isoSim = new IsolatedBinarySim('iso-sim-canvas', isoEcc ? parseFloat(isoEcc.value) : 0.3);

        var lastTime = 0;
        function simLoop(time) {
            var dt = lastTime === 0 ? 0.016 : Math.min((time - lastTime) / 1000, 0.05);
            lastTime = time;

            nscSim.step(dt);
            nscSim.draw();
            gcSim.step(dt);
            gcSim.draw();
            isoSim.step(dt);
            isoSim.draw();

            // Check if simulation time is up
            if (nscSim.elapsed < SIM_DURATION) {
                simAnimId = requestAnimationFrame(simLoop);
            } else {
                // Simulation done — show subsection 3
                showHistograms();
            }
        }
        simAnimId = requestAnimationFrame(simLoop);
    });

    function showHistograms() {
        document.getElementById('arrow-2-3').style.display = '';
        var subHists = document.getElementById('sub-hists');
        subHists.style.opacity = '1';

        var nscSigma = parseInt(nscSlider.value);
        var gcSigma = parseInt(gcSlider.value);
        var simParams = window.bbhSimulateParams || { bh1_mass: 25, bh2_mass: 20 };

        var csrfToken = document.cookie
            .split('; ')
            .find(function (r) { return r.startsWith('csrftoken='); });
        csrfToken = csrfToken ? csrfToken.split('=')[1] : '';

        var eccDistUrl = simBtn.dataset.eccUrl;
        var fetched = []; // collect samples + plot args, then build plots after all done

        function buildAndAnimate() {
            // Compute shared x-axis range across all three datasets
            var globalMin = Infinity, globalMax = -Infinity;
            for (var i = 0; i < fetched.length; i++) {
                var s = fetched[i].samples;
                for (var j = 0; j < s.length; j++) {
                    if (s[j] < globalMin) globalMin = s[j];
                    if (s[j] > globalMax) globalMax = s[j];
                }
            }
            var pad = (globalMax - globalMin) * 0.05 || 0.01;
            globalMin -= pad;
            globalMax += pad;

            var histPlots = [];
            for (var k = 0; k < fetched.length; k++) {
                var f = fetched[k];
                histPlots.push(new S5HistogramPlot(
                    f.canvasId, f.samples, f.label, f.color, 40, globalMin, globalMax
                ));
            }

            var startTime = performance.now();
            function tick() {
                var p = Math.min((performance.now() - startTime) / 3000, 1);
                histPlots.forEach(function (h) { h.draw(p); });
                if (p < 1) requestAnimationFrame(tick);
            }
            requestAnimationFrame(tick);
        }

        var completed = 0;
        function fetchDist(channel, sigma, canvasId, label, color) {
            fetch(eccDistUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ channel: channel, sigma: sigma, m1: simParams.bh1_mass, m2: simParams.bh2_mass }),
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.status === 'ok' && data.samples.length > 0) {
                    fetched.push({ canvasId: canvasId, samples: data.samples, label: label, color: color });
                }
                completed++;
                if (completed >= 3) buildAndAnimate();
            })
            .catch(function () {
                completed++;
                if (completed >= 3) buildAndAnimate();
            });
        }

        fetchDist('nsc', nscSigma, 'hist-nsc', 'NSC (\u03c3=' + nscSigma + ' km/s)', S5.COLORS.nsc);
        fetchDist('gc', gcSigma, 'hist-gc', 'GC (\u03c3=' + gcSigma + ' km/s)', S5.COLORS.gc);
        fetchDist('isolated', 0, 'hist-iso', 'Isolated Binary', S5.COLORS.iso);
    }
});
