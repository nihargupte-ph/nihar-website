// Run: ~/.nvm/versions/node/v22.22.2/bin/node tests/presentations/js/stage.test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const ctx = { window: {}, document: { addEventListener() {}, querySelector() { return null; }, querySelectorAll() { return []; } } };
ctx.window.Presentations = { data: { slides: [] }, $: () => null };
vm.createContext(ctx);
vm.runInContext(readFileSync(new URL('../../../presentations/static/presentations/js/stage.js', import.meta.url), 'utf8'), ctx);
const S = ctx.window.Presentations.stage;

// vm.createContext runs stage.js in a separate V8 realm, so objects it returns
// carry that realm's Object.prototype, which fails deepStrictEqual's [[Prototype]]
// identity check even when every own-property value matches. Spreading into a
// plain object literal in this (outer) realm strips that mismatched prototype
// while still doing an exact, strict value comparison.
assert.deepStrictEqual({ ...S.frac2stage([0.5, 0.25, 0.1, 0.2]) }, { x: 960, y: 270, w: 192, h: 216 });

// letterboxed inner box: element 1000×700 → 16:9 content is 1000×562.5 centred vertically (offset 68.75)
const fake = { getBoundingClientRect: () => ({ left: 100, top: 50, width: 1000, height: 700 }) };
const [fx, fy] = S.px2frac(fake, 100 + 500, 50 + 68.75 + 281.25);
assert.ok(Math.abs(fx - 0.5) < 1e-9 && Math.abs(fy - 0.5) < 1e-9);
const [cx, cy] = S.px2frac(fake, 0, 0);
assert.equal(cx, 0); assert.equal(cy, 0);            // clamped

// pillarboxed inner box: element 1000×400 (wider than 16:9) → 16:9 content is
// 711.111…×400 centred horizontally (offset ox = (1000 - 711.111…)/2 ≈ 144.444…)
const fakeWide = { getBoundingClientRect: () => ({ left: 100, top: 50, width: 1000, height: 400 }) };
const ox = (1000 - (400 * 1920 / 1080)) / 2;
const [wfx, wfy] = S.px2frac(fakeWide, 100 + ox + (400 * 1920 / 1080) / 2, 50 + 200);
assert.ok(Math.abs(wfx - 0.5) < 1e-9 && Math.abs(wfy - 0.5) < 1e-9);
const [leftEdgeFx] = S.px2frac(fakeWide, 100 + ox, 50);
assert.ok(Math.abs(leftEdgeFx - 0) < 1e-9);
const [pillarFx, pillarFy] = S.px2frac(fakeWide, 100 + 10, 50 + 200);
assert.equal(pillarFx, 0); assert.equal(pillarFy, 0.5);   // clamped into the left pillar

console.log('stage math ok');
