/* ==========================================================================
   Blog Common Components — Reusable across all blog posts
   ========================================================================== */

/**
 * ControlPad2D — A 2D drag pad for controlling two parameters simultaneously.
 *
 * X-axis maps to one parameter, Y-axis (inverted: bottom=min, top=max) to another.
 * User clicks and drags a marker within the pad to set values.
 */
class ControlPad2D {
    constructor(containerId, { xMin, xMax, yMin, yMax, xDefault, yDefault, onChange }) {
        this.container = document.getElementById(containerId);
        this.xMin = xMin;
        this.xMax = xMax;
        this.yMin = yMin;
        this.yMax = yMax;
        this.onChange = onChange;
        this.dragging = false;

        // Normalized values [0, 1]
        this.xNorm = (xDefault - xMin) / (xMax - xMin);
        this.yNorm = (yDefault - yMin) / (yMax - yMin);

        this.canvas = this.container.querySelector('canvas.pad-bg');
        this.marker = this.container.querySelector('.pad-marker');

        this._setupCanvas();
        this._drawGrid();
        this._updateMarker();
        this._bindEvents();

        // Fire initial onChange
        this._fireChange();
    }

    _setupCanvas() {
        const dpr = window.devicePixelRatio || 1;
        const rect = this.container.getBoundingClientRect();
        this.canvas.width = rect.width * dpr;
        this.canvas.height = rect.height * dpr;
        this.ctx = this.canvas.getContext('2d');
        this.ctx.scale(dpr, dpr);
    }

    _drawGrid() {
        const w = this.container.offsetWidth;
        const h = this.container.offsetHeight;
        const ctx = this.ctx;

        ctx.clearRect(0, 0, w, h);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
        ctx.lineWidth = 1;

        // Vertical lines
        for (let i = 1; i < 4; i++) {
            const x = (w / 4) * i;
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, h);
            ctx.stroke();
        }

        // Horizontal lines
        for (let i = 1; i < 4; i++) {
            const y = (h / 4) * i;
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(w, y);
            ctx.stroke();
        }
    }

    _updateMarker() {
        this.marker.style.left = (this.xNorm * 100) + '%';
        // Y is inverted: yNorm=1 (max) should be at top (0%), yNorm=0 (min) at bottom (100%)
        this.marker.style.top = ((1 - this.yNorm) * 100) + '%';
    }

    _fireChange() {
        const xVal = this.xMin + this.xNorm * (this.xMax - this.xMin);
        const yVal = this.yMin + this.yNorm * (this.yMax - this.yMin);
        this.onChange(xVal, yVal);
    }

    _getPointerNorm(e) {
        const rect = this.container.getBoundingClientRect();
        let clientX, clientY;

        if (e.touches) {
            clientX = e.touches[0].clientX;
            clientY = e.touches[0].clientY;
        } else {
            clientX = e.clientX;
            clientY = e.clientY;
        }

        const xNorm = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
        // Invert Y: top of box = max, bottom = min
        const yNorm = Math.max(0, Math.min(1, 1 - (clientY - rect.top) / rect.height));
        return { xNorm, yNorm };
    }

    _onPointerDown(e) {
        e.preventDefault();
        this.dragging = true;
        this.marker.classList.add('active');
        const { xNorm, yNorm } = this._getPointerNorm(e);
        this.xNorm = xNorm;
        this.yNorm = yNorm;
        this._updateMarker();
        this._fireChange();
    }

    _onPointerMove(e) {
        if (!this.dragging) return;
        e.preventDefault();
        const { xNorm, yNorm } = this._getPointerNorm(e);
        this.xNorm = xNorm;
        this.yNorm = yNorm;
        this._updateMarker();
        this._fireChange();
    }

    _onPointerUp() {
        this.dragging = false;
        this.marker.classList.remove('active');
    }

    _bindEvents() {
        // Mouse
        this.container.addEventListener('mousedown', (e) => this._onPointerDown(e));
        document.addEventListener('mousemove', (e) => this._onPointerMove(e));
        document.addEventListener('mouseup', () => this._onPointerUp());

        // Touch
        this.container.addEventListener('touchstart', (e) => this._onPointerDown(e), { passive: false });
        this.container.addEventListener('touchmove', (e) => this._onPointerMove(e), { passive: false });
        this.container.addEventListener('touchend', () => this._onPointerUp());
    }

    getValue() {
        return {
            x: this.xMin + this.xNorm * (this.xMax - this.xMin),
            y: this.yMin + this.yNorm * (this.yMax - this.yMin),
        };
    }
}


/**
 * SpeechBubble — Undertale-style typewriter text display.
 *
 * Types out text letter-by-letter with a blinking cursor.
 * Click to skip to full message. Supports event-based message pools with debouncing.
 */
class SpeechBubble {
    constructor(elementId) {
        this.el = document.getElementById(elementId);
        this.charDelay = 30; // ms per character
        this.intervalId = null;
        this.currentMessage = '';
        this.currentIndex = 0;
        this.messages = {};
        this.lastTriggerTime = 0;
        this.debounceMs = 2000;

        // Click to skip
        this.el.addEventListener('click', () => this.skip());
    }

    say(message) {
        // Cancel any ongoing typing
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }

        this.currentMessage = message;
        this.currentIndex = 0;
        this.el.innerHTML = '<span class="cursor">\u258c</span>';

        this.intervalId = setInterval(() => {
            if (this.currentIndex < this.currentMessage.length) {
                const char = this.currentMessage[this.currentIndex];
                // Insert character before cursor
                const cursor = this.el.querySelector('.cursor');
                const textNode = document.createTextNode(char);
                this.el.insertBefore(textNode, cursor);
                this.currentIndex++;
            } else {
                clearInterval(this.intervalId);
                this.intervalId = null;
                // Remove cursor after typing completes
                const cursor = this.el.querySelector('.cursor');
                if (cursor) cursor.remove();
            }
        }, this.charDelay);
    }

    skip() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
        this.el.textContent = this.currentMessage;
    }

    setMessages(eventMap) {
        this.messages = eventMap;
    }

    trigger(eventName) {
        const now = Date.now();
        if (now - this.lastTriggerTime < this.debounceMs) return;

        const pool = this.messages[eventName];
        if (!pool || pool.length === 0) return;

        this.lastTriggerTime = now;
        const msg = pool[Math.floor(Math.random() * pool.length)];
        this.say(msg);
    }

    // Force trigger without debounce (for simulate button, page load, etc.)
    forceTrigger(eventName) {
        const pool = this.messages[eventName];
        if (!pool || pool.length === 0) return;

        this.lastTriggerTime = Date.now();
        const msg = pool[Math.floor(Math.random() * pool.length)];
        this.say(msg);
    }
}
