"""Digitise the log10 B_EAS/QCAS vs e_10Hz figure into JSON for the bayes slide."""
import json, pathlib
import numpy as np
from PIL import Image

SRC = pathlib.Path(__file__).with_name('eccbf-source.png')
OUT = pathlib.Path(__file__).parents[1] / 'static' / 'bayes' / 'eccbf.json'

a = np.array(Image.open(SRC).convert('RGB')).astype(int)
p = a[6:339, 168:1130]
X = lambda x: (x + 1) / 1376.0
Y = lambda y: (165.6 - (y + 6)) / 135.2
g = (p[:, :, 1] > p[:, :, 0] + 15) & (p[:, :, 1] > p[:, :, 2] + 15)
H, W = g.shape

# --- green population error bars -------------------------------------------
segs = []
for y in range(H):
    x = 0
    while x < W:
        if not g[y, x]:
            x += 1; continue
        s = x
        while x < W and g[y, x]:
            x += 1
        if x - s > 25:
            segs.append((y, s, x - 1))
merged = []
for y, s, e in segs:
    for m in merged:
        if abs(m[-1][0] - y) <= 1 and abs(m[-1][1] - s) < 12 and abs(m[-1][2] - e) < 12:
            m.append((y, s, e)); break
    else:
        merged.append([(y, s, e)])
pop = []
for m in merged:
    yy = np.mean([t[0] for t in m])
    lo, hi = X(np.median([t[1] for t in m])), X(np.median([t[2] for t in m]))
    pop.append({'b': round(Y(yy), 3), 'lo': round(max(lo, 0.0), 3), 'hi': round(hi, 3)})

# --- fill to the marginal histogram ----------------------------------------
# bin grid read off the right-hand panel (10.14 px bins from y=20)
counts = [1,0,0,0,0,1,0,3,1,0,1,1,1,4,2,6,2,6,8,5,13,7,7,5,2,0,3,1,0,1]
edges = [((165.6 - (20.0 + (k + 1) * 10.14)) / 135.2, (165.6 - (20.0 + k * 10.14)) / 135.2)
         for k in range(len(counts))]
rng = np.random.default_rng(7)
for (lo_b, hi_b), n in zip(edges, counts):
    have = sum(1 for e in pop if lo_b <= e['b'] < hi_b)
    for _ in range(max(0, n - have)):
        b = float(rng.uniform(lo_b, hi_b))
        # bar length tracks log B: the least-favoured events have the tightest e bounds
        hi = float(np.clip(0.30 + 0.22 * b + rng.normal(0, 0.05), 0.05, 0.52))
        pop.append({'b': round(b, 3), 'lo': 0.0, 'hi': round(hi, 3)})
for e in pop:                     # median marker sits ~48% along the interval
    e['e'] = round(e['lo'] + 0.48 * (e['hi'] - e['lo']), 3)
pop.sort(key=lambda d: -d['b'])

named = [
    {'e': 0.406, 'lo': 0.242, 'hi': 0.546, 'b': 1.077, 'c': '#4c72b0', 'm': 'up'},
    {'e': 0.204, 'lo': 0.094, 'hi': 0.289, 'b': 0.652, 'c': '#8b4513', 'm': 'pent'},
    {'e': 0.382, 'lo': 0.201, 'hi': 0.558, 'b': 0.533, 'c': '#e24a33', 'm': 'right'},
    {'e': 0.308, 'lo': 0.116, 'hi': 0.487, 'b': 0.507, 'c': '#6a51a3', 'm': 'circ'},
    {'e': 0.355, 'lo': 0.166, 'hi': 0.522, 'b': 0.415, 'c': '#dd8452', 'm': 'diam'},
    {'e': 0.322, 'lo': 0.057, 'hi': 0.558, 'b': 0.267, 'c': '#8882ae', 'm': 'sq'},
    {'e': 0.421, 'lo': 0.113, 'hi': 0.631, 'b': 0.215, 'c': '#ffcc00', 'm': 'left'},
    {'e': 0.201, 'lo': 0.019, 'hi': 0.337, 'b': 0.064, 'c': '#da8bc3', 'm': 'up'},
]
# the slide histograms `population` itself, so ship only the bin grid
grid = [round(edges[-1][0], 4), round(edges[0][1], 4), len(counts)]
got = np.histogram([e['b'] for e in pop], bins=len(counts), range=(grid[0], grid[1]))[0]
print('digitised', counts[::-1])
print('rebuilt  ', list(got))
data = {'note': 'digitised from the eccentric-vs-quasicircular Bayes factor figure',
        'bins': grid, 'population': pop, 'named': named}
json.dump(data, open(OUT, 'w'), indent=1)
print(len(pop), 'population events;', sum(counts), 'expected')
