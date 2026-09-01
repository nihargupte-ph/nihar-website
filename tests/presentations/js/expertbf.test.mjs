// Python/JS parity for the expert-prior Bayes factor.
// Reads a prior (88 bin masses, JSON) on stdin, prints {event id: B} on stdout.
// Driven by tests/presentations/test_corfu_expertbf.py, which compares against
// the same dot product done in tools/expertbf.py.
//
// Run by hand: echo "[...88 numbers...]" | node tests/presentations/js/expertbf.test.mjs
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const root = new URL('../../../presentations/decks/corfu/', import.meta.url);
const data = JSON.parse(readFileSync(new URL('static/expertbf/expertbf.json', root), 'utf8'));

// expertbf.js bails out of its DOM work as soon as it finds no `.xbf` elements, but the
// pure helpers are hung off window.ExpertBF before that, so a stub document is enough.
const ctx = { window: {}, document: { querySelectorAll: () => [] } };
vm.createContext(ctx);
vm.runInContext(readFileSync(new URL('static/expertbf/expertbf.js', root), 'utf8'), ctx);
const NS = ctx.window.ExpertBF;

const weights = JSON.parse(readFileSync(0, 'utf8'));
const out = {};
for (const ev of data.events) {
  out[ev.id] = ev.fittable ? NS.bayesFactor(weights, ev.lambda, ev.k) : null;
}
process.stdout.write(JSON.stringify(out));
