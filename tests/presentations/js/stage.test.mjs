// Run: ~/.nvm/versions/node/v22.22.2/bin/node tests/presentations/js/stage.test.mjs
// Note: uses 'node:assert' (legacy, loose deepEqual) rather than 'node:assert/strict'
// because vm.createContext runs stage.js in a separate V8 realm, so objects it
// returns have a different Object.prototype identity than the outer realm's
// object literals; deepStrictEqual's [[Prototype]] === check fails on that even
// when all own-property values match (verified with util.isDeepStrictEqual on a
// trivial {x:1,y:2} cross-realm case). Legacy deepEqual compares values, not
// prototype identity, which is what this test needs.
import assert from 'node:assert';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const ctx = { window: {}, document: { addEventListener() {}, querySelector() { return null; }, querySelectorAll() { return []; } } };
ctx.window.Presentations = { data: { slides: [] }, $: () => null };
vm.createContext(ctx);
vm.runInContext(readFileSync(new URL('../../../presentations/static/presentations/js/stage.js', import.meta.url), 'utf8'), ctx);
const S = ctx.window.Presentations.stage;

assert.deepEqual(S.frac2stage([0.5, 0.25, 0.1, 0.2]), { x: 960, y: 270, w: 192, h: 216 });

// letterboxed inner box: element 1000×700 → 16:9 content is 1000×562.5 centred vertically (offset 68.75)
const fake = { getBoundingClientRect: () => ({ left: 100, top: 50, width: 1000, height: 700 }) };
const [fx, fy] = S.px2frac(fake, 100 + 500, 50 + 68.75 + 281.25);
assert.ok(Math.abs(fx - 0.5) < 1e-9 && Math.abs(fy - 0.5) < 1e-9);
const [cx, cy] = S.px2frac(fake, 0, 0);
assert.equal(cx, 0); assert.equal(cy, 0);            // clamped
console.log('stage math ok');
