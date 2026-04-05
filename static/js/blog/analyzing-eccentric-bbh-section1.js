/* ==========================================================================
   Analyzing Eccentric Binary Black Holes — Section 1
   Black hole renderers, eccentricity renderer, and initialization wiring.
   ========================================================================== */

/**
 * BlackHoleRenderer — Draws a black hole on a canvas.
 * Circle size = mass, dashed spinning ring = spin.
 */
class BlackHoleRenderer {
    constructor(canvas) {
        this.canvas = canvas;
        const dpr = window.devicePixelRatio || 1;
        this.dpr = dpr;
        this.cssW = 200;
        this.cssH = 120;
        this.canvas.width = this.cssW * dpr;
        this.canvas.height = this.cssH * dpr;
        this.canvas.style.width = this.cssW + 'px';
        this.canvas.style.height = this.cssH + 'px';
        this.ctx = this.canvas.getContext('2d');
        this.ctx.scale(dpr, dpr);

        this.mass = 30;
        this.spin = 0;
        this.spinAngle = 0;
    }

    update(mass, spin) {
        this.mass = mass;
        this.spin = spin;
    }

    draw(dt) {
        const ctx = this.ctx;
        const w = this.cssW;
        const h = this.cssH;
        const cx = w / 2;
        const cy = h / 2;

        ctx.clearRect(0, 0, w, h);

        // Radius scales with mass: 10 M☉ → 10px, 120 M☉ → 45px
        const radius = 10 + Math.max(0, this.mass - 10) * (35 / 110);

        // Glow
        const gradient = ctx.createRadialGradient(cx, cy, radius * 0.5, cx, cy, radius * 2.5);
        gradient.addColorStop(0, 'rgba(239, 131, 118, 0.25)');
        gradient.addColorStop(0.5, 'rgba(239, 131, 118, 0.08)');
        gradient.addColorStop(1, 'rgba(239, 131, 118, 0)');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, w, h);

        // Spin ring (dashed, rotating)
        this.spinAngle += this.spin * 3 * dt;
        const ringRadius = radius + 6;
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(this.spinAngle);
        ctx.setLineDash([8, 6]);
        ctx.strokeStyle = 'rgba(239, 131, 118, 0.6)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(0, 0, ringRadius, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.restore();

        // Black hole body
        ctx.fillStyle = '#0a0a0a';
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx.fill();

        // Inner highlight
        const innerGrad = ctx.createRadialGradient(cx - radius * 0.2, cy - radius * 0.2, 0, cx, cy, radius);
        innerGrad.addColorStop(0, 'rgba(255, 255, 255, 0.06)');
        innerGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = innerGrad;
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx.fill();
    }
}


/**
 * EccentricityRenderer — Draws an orbital ellipse with a body at the focus.
 * Solves Kepler's equation for proper anomaly positioning.
 */
class EccentricityRenderer {
    constructor(canvas) {
        this.canvas = canvas;
        const dpr = window.devicePixelRatio || 1;
        this.dpr = dpr;
        this.cssW = 200;
        this.cssH = 120;
        this.canvas.width = this.cssW * dpr;
        this.canvas.height = this.cssH * dpr;
        this.canvas.style.width = this.cssW + 'px';
        this.canvas.style.height = this.cssH + 'px';
        this.ctx = this.canvas.getContext('2d');
        this.ctx.scale(dpr, dpr);

        this.eccentricity = 0;
        this.meanAnomaly = 0; // in radians
    }

    update(eccentricity, meanAnomalyDeg) {
        this.eccentricity = eccentricity;
        this.meanAnomaly = meanAnomalyDeg * Math.PI / 180;
    }

    // Solve Kepler's equation M = E - e*sin(E) for E via Newton's method
    _solveKepler(M, e) {
        let E = M; // initial guess
        for (let i = 0; i < 10; i++) {
            E = E - (E - e * Math.sin(E) - M) / (1 - e * Math.cos(E));
        }
        return E;
    }

    draw(dt) {
        const ctx = this.ctx;
        const w = this.cssW;
        const h = this.cssH;
        const cx = w / 2;
        const cy = h / 2;
        const e = this.eccentricity;

        ctx.clearRect(0, 0, w, h);

        // Ellipse parameters
        const a = 50; // semi-major axis (px)
        const b = a * Math.sqrt(1 - e * e); // semi-minor axis
        const focusOffset = a * e; // distance from center to focus

        // Draw orbit ellipse
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.35)';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.ellipse(cx, cy, a, b, 0, 0, Math.PI * 2);
        ctx.stroke();

        // Draw focus point (where the central mass is)
        ctx.fillStyle = '#ef8376';
        ctx.beginPath();
        ctx.arc(cx + focusOffset, cy, 3, 0, Math.PI * 2);
        ctx.fill();

        // Solve Kepler's equation for eccentric anomaly
        const E = this._solveKepler(this.meanAnomaly, e);

        // Convert to position on ellipse
        const orbX = cx + a * Math.cos(E);
        const orbY = cy - b * Math.sin(E); // negative because canvas Y is inverted

        // Draw orbiting body
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(orbX, orbY, 4, 0, Math.PI * 2);
        ctx.fill();

        // Draw line from focus to orbiting body
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(cx + focusOffset, cy);
        ctx.lineTo(orbX, orbY);
        ctx.stroke();
        ctx.setLineDash([]);
    }
}


/* ---------- Shared animation loop ---------- */

const allRenderers = [];
let lastAnimTime = 0;

function animationLoop(time) {
    const dt = lastAnimTime === 0 ? 0.016 : (time - lastAnimTime) / 1000;
    lastAnimTime = time;
    for (const r of allRenderers) {
        r.draw(dt);
    }
    requestAnimationFrame(animationLoop);
}


/* ---------- Initialization ---------- */

document.addEventListener('DOMContentLoaded', function () {

    // --- Speech Bubble ---
    const bubble = new SpeechBubble('speech-bubble');
    bubble.setMessages({
        'load': [
            'Hey. Welcome to the binary black hole lab. Click the pads on the left to choose your parameters. Don\'t stay for too long, I have work to do.'
        ],
        'bh_change': [
            'The heavier the black holes, the louder the gravitational waves.',
            'More unequal mass ratios are harder to model. Don\'t make my life too complicated.',
            'A rapidly spinning black hole drags spacetime along with it.',
            'Spinning faster and faster. You know you can\'t spin faster than the speed of light right?',
        ],
        'ecc_change': [
            'Going eccentric huh? I like it, eccentric binary black holes create bursts of energy.',
            'Higher eccentricity means the orbit is more elongated.',
            'The anomaly tells us where the black holes start on their orbit.',
            'Eccentricity is '
        ],
        'simulate': [
            'Let\'s send this over to Palis at the lab, she can simulate your parameters. '
        ],
        'simulate_done': [
            'I just heard from Palis at the lab, looks like your crazy parameters actually worked.'
        ],
        'simulate_error': [
            'Hmm, Palis is out having coffee or something. Should we try again?'
        ]
    });
    bubble.forceTrigger('load');

    // --- Black Hole Renderers ---
    const bh1Renderer = new BlackHoleRenderer(document.getElementById('bh1-canvas'));
    const bh2Renderer = new BlackHoleRenderer(document.getElementById('bh2-canvas'));
    const eccRenderer = new EccentricityRenderer(document.getElementById('orbit-canvas'));

    allRenderers.push(bh1Renderer, bh2Renderer, eccRenderer);

    // --- Control Pads ---

    // Box 1: Black Hole 1 — Mass (15-30) x Spin (0-0.5)
    const bh1Pad = new ControlPad2D('bh1-pad', {
        xMin: 15, xMax: 30,
        yMin: 0, yMax: 0.5,
        xDefault: 25, yDefault: 0.1,
        onChange(mass, spin) {
            bh1Renderer.update(mass, spin);
            document.getElementById('bh1-values').textContent =
                'Mass: ' + mass.toFixed(0) + ' M\u2609 | Spin: ' + spin.toFixed(2);
            bubble.trigger('bh_change');
        }
    });

    // Box 2: Black Hole 2 — Mass (15-30) x Spin (0-0.5)
    const bh2Pad = new ControlPad2D('bh2-pad', {
        xMin: 15, xMax: 30,
        yMin: 0, yMax: 0.5,
        xDefault: 20, yDefault: 0.1,
        onChange(mass, spin) {
            bh2Renderer.update(mass, spin);
            document.getElementById('bh2-values').textContent =
                'Mass: ' + mass.toFixed(0) + ' M\u2609 | Spin: ' + spin.toFixed(2);
            bubble.trigger('bh_change');
        }
    });

    // Box 3: Eccentricity (0-0.5) x Anomaly (0-360)
    const eccPad = new ControlPad2D('orbit-pad', {
        xMin: 0, xMax: 0.5,
        yMin: 0, yMax: 360,
        xDefault: 0.2, yDefault: 180,
        onChange(ecc, anomaly) {
            eccRenderer.update(ecc, anomaly);
            document.getElementById('orbit-values').textContent =
                'Ecc: ' + ecc.toFixed(2) + ' | Anomaly: ' + anomaly.toFixed(0) + '\u00b0';
            bubble.trigger('ecc_change');
        }
    });

    // --- Simulate Button ---
    const simBtn = document.getElementById('simulate-btn');
    simBtn.addEventListener('click', function () {
        const params = {
            bh1_mass: bh1Pad.getValue().x,
            bh1_spin: bh1Pad.getValue().y,
            bh2_mass: bh2Pad.getValue().x,
            bh2_spin: bh2Pad.getValue().y,
            eccentricity: eccPad.getValue().x,
            mean_anomaly: eccPad.getValue().y,
        };

        bubble.forceTrigger('simulate');
        simBtn.disabled = true;

        // Store params for Section 4 (analyze)
        window.bbhSimulateParams = params;

        // Get CSRF token from cookie
        const csrfToken = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];

        // Show Section 2 with loading state
        const section2 = document.getElementById('section-2');
        section2.style.display = '';
        section2.scrollIntoView({ behavior: 'smooth' });

        fetch(simBtn.dataset.simulateUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken || '',
            },
            body: JSON.stringify(params),
        })
        .then(response => {
            if (!response.ok) return response.json().then(d => { throw new Error(d.message || 'Server error'); });
            return response.json();
        })
        .then(data => {
            if (data.status !== 'ok') throw new Error(data.message || 'Unknown error');

            window.bbhSimulationResult = data;
            bubble.forceTrigger('simulate_done');

            // Lock Section 1
            document.getElementById('section-1').classList.add('locked');

            // Trigger Section 2 rendering (defined in section2.js)
            if (typeof renderSection2 === 'function') {
                renderSection2(data);
            }
        })
        .catch(function (err) {
            simBtn.disabled = false;
            bubble.forceTrigger('simulate_error');

            // Show error in Section 2 panel instead of loading forever
            var msg = err.message || 'Simulation failed';
            var el = document.getElementById('loading-panels');
            if (el) {
                el.innerHTML = '<p style="color:#ef8376;">Error: ' +
                    msg.replace(/</g, '&lt;') + '</p><p>Try different parameters.</p>';
            }
        });
    });

    // --- Start Animation Loop ---
    requestAnimationFrame(animationLoop);
});
