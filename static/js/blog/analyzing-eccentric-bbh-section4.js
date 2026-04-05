/* ==========================================================================
   Analyzing Eccentric Binary Black Holes — Section 4
   Posterior distribution histograms.
   ========================================================================== */

/**
 * HistogramPlot — draws a histogram of samples with an injected value line.
 */
class HistogramPlot {
    constructor(canvasId, samples, injected, label, nBins) {
        this.canvas = document.getElementById(canvasId);
        const dpr = window.devicePixelRatio || 1;
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = rect.width * dpr;
        this.canvas.height = rect.height * dpr;
        this.ctx = this.canvas.getContext('2d');
        this.ctx.scale(dpr, dpr);
        this.w = rect.width;
        this.h = rect.height;

        this.samples = samples;
        this.injected = injected;
        this.label = label;
        this.nBins = nBins || 40;

        this.ml = 10;
        this.mr = 10;
        this.mt = 24;
        this.mb = 28;

        this._computeBins();
    }

    _computeBins() {
        const s = this.samples;
        const min = Math.min(...s);
        const max = Math.max(...s);
        const pad = (max - min) * 0.05 || 0.01;
        this.xMin = min - pad;
        this.xMax = max + pad;
        const binWidth = (this.xMax - this.xMin) / this.nBins;

        this.bins = new Array(this.nBins).fill(0);
        for (const v of s) {
            const idx = Math.min(Math.floor((v - this.xMin) / binWidth), this.nBins - 1);
            if (idx >= 0) this.bins[idx]++;
        }
        this.maxCount = Math.max(...this.bins);
        this.binWidth = binWidth;
    }

    _xToScreen(x) {
        return this.ml + (x - this.xMin) / (this.xMax - this.xMin) * (this.w - this.ml - this.mr);
    }

    draw(progress) {
        // progress: 0..1 for animated reveal
        const ctx = this.ctx;
        const { w, h, ml, mr, mt, mb } = this;
        const plotW = w - ml - mr;
        const plotH = h - mt - mb;

        ctx.clearRect(0, 0, w, h);

        // How many bins to show based on progress
        const binsToShow = Math.ceil(progress * this.nBins);

        // Draw histogram bars
        const barW = plotW / this.nBins;
        for (let i = 0; i < binsToShow; i++) {
            const barH = (this.bins[i] / this.maxCount) * plotH;
            const x = ml + i * barW;
            const y = mt + plotH - barH;

            ctx.fillStyle = 'rgba(239, 131, 118, 0.5)';
            ctx.fillRect(x, y, barW - 1, barH);
            ctx.strokeStyle = 'rgba(239, 131, 118, 0.7)';
            ctx.lineWidth = 0.5;
            ctx.strokeRect(x, y, barW - 1, barH);
        }

        // X-axis line
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(ml, mt + plotH);
        ctx.lineTo(w - mr, mt + plotH);
        ctx.stroke();

        // Injected value line
        if (progress > 0.5) {
            const injX = this._xToScreen(this.injected);
            const lineAlpha = Math.min(1, (progress - 0.5) * 4);
            ctx.strokeStyle = 'rgba(126, 200, 227, ' + lineAlpha + ')';
            ctx.lineWidth = 2;
            ctx.setLineDash([5, 3]);
            ctx.beginPath();
            ctx.moveTo(injX, mt);
            ctx.lineTo(injX, mt + plotH);
            ctx.stroke();
            ctx.setLineDash([]);

            // Injected label
            ctx.fillStyle = 'rgba(126, 200, 227, ' + lineAlpha + ')';
            ctx.font = '9px Courier New';
            ctx.fillText('injected', injX + 3, mt + 10);
        }

        // Title label
        ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
        ctx.font = '11px Courier New';
        ctx.fillText(this.label, ml + 2, mt - 8);

        // X-axis tick labels
        ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
        ctx.font = '9px Courier New';
        ctx.textAlign = 'left';
        ctx.fillText(this.xMin.toPrecision(3), ml, h - 4);
        ctx.textAlign = 'right';
        ctx.fillText(this.xMax.toPrecision(3), w - mr, h - 4);
        ctx.textAlign = 'left';
    }
}


/* ---------- Animated histogram reveal ---------- */

function animateHistograms(plots, duration, onComplete) {
    const startTime = performance.now();
    const durationMs = duration * 1000;

    function tick() {
        const elapsed = performance.now() - startTime;
        const progress = Math.min(elapsed / durationMs, 1);

        for (const p of plots) {
            p.draw(progress);
        }

        if (progress < 1) {
            requestAnimationFrame(tick);
        } else if (onComplete) {
            onComplete();
        }
    }
    requestAnimationFrame(tick);
}


/* ---------- Analyze button handler ---------- */

document.addEventListener('DOMContentLoaded', function () {
    var analyzeBtn = document.getElementById('analyze-btn');
    if (!analyzeBtn) return;

    analyzeBtn.addEventListener('click', function () {
        // Need the simulation params from Section 1
        var simResult = window.bbhSimulationResult;
        if (!simResult || simResult.status !== 'ok') return;

        analyzeBtn.disabled = true;

        // Show Section 4 with loading
        var section4 = document.getElementById('section-4');
        section4.style.display = '';
        section4.scrollIntoView({ behavior: 'smooth' });

        // Get the injected params from the simulation request
        // They're stored in the pads — read from the simulate params we sent
        var params = window.bbhSimulateParams;
        if (!params) {
            // Fallback: read from readout text
            params = {
                bh1_mass: 25, bh1_spin: 0.1,
                bh2_mass: 20, bh2_spin: 0.1,
                eccentricity: 0.2, mean_anomaly: 180
            };
        }

        var csrfToken = document.cookie
            .split('; ')
            .find(function(row) { return row.startsWith('csrftoken='); });
        csrfToken = csrfToken ? csrfToken.split('=')[1] : '';

        fetch(analyzeBtn.dataset.analyzeUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify(params),
        })
        .then(function (response) {
            if (!response.ok) return response.json().then(function (d) { throw new Error(d.message || 'Server error'); });
            return response.json();
        })
        .then(function (data) {
            if (data.status !== 'ok') throw new Error(data.message || 'Unknown error');

            // Initialize speech bubble
            var bubble4 = new SpeechBubble('speech-bubble-4');
            bubble4.say('DINGO found the signal! The dashed blue lines show the true values.');

            // Hide loading, show grid
            document.getElementById('loading-posteriors').style.display = 'none';
            document.getElementById('posteriors-grid').style.display = '';

            requestAnimationFrame(function () {
                var canvasMap = {
                    'm1': 'post-m1',
                    'm2': 'post-m2',
                    's1z': 'post-s1z',
                    's2z': 'post-s2z',
                    'ecc': 'post-ecc',
                    'anomaly': 'post-anomaly',
                };

                var plots = [];
                for (var key in canvasMap) {
                    var p = data.posteriors[key];
                    if (p) {
                        plots.push(new HistogramPlot(
                            canvasMap[key], p.samples, p.injected, p.label
                        ));
                    }
                }

                // Animate histograms filling in over 3 seconds, then show button
                animateHistograms(plots, 3, function () {
                    var btnWrap = document.getElementById('useful-btn-wrap');
                    if (btnWrap) btnWrap.style.display = '';
                });
            });
        })
        .catch(function (err) {
            analyzeBtn.disabled = false;
            var el = document.getElementById('loading-posteriors');
            if (el) {
                el.innerHTML = '<p style="color:#ef8376;">Error: ' +
                    (err.message || 'Analysis failed').replace(/</g, '&lt;') +
                    '</p><p>Try again.</p>';
            }
        });
    });

    // "Why is this useful?" button → show Section 5
    var usefulBtn = document.getElementById('useful-btn');
    if (usefulBtn) {
        usefulBtn.addEventListener('click', function () {
            var section5 = document.getElementById('section-5');
            if (section5) {
                section5.style.display = '';
                section5.scrollIntoView({ behavior: 'smooth' });
            }
        });
    }
});
