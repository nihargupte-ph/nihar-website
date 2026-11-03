#!/usr/bin/env python3
"""Sampling-efficiency histogram of the Mixture of Experts slide: static/moe/efficiency-hard.png.

The event counts were read off the pixels of tools/efficiency_source.png (events inside the hard
region). Every bar lands on a whole number of events to within 0.1, both curves sum to 246, and the
shares above 1 % reproduce the source's legend (48 % and 71 %), all asserted below.
The plot is lightly smoothed with a 1-2-1 kernel over neighbouring bins.

Run from the deck folder:  micromamba run -n django-nihar-website python tools/efficiency_hist.py
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

N = 246
ONE_NETWORK = np.array([9, 7, 8, 9, 9, 11, 11, 9, 11, 13, 13, 17, 14, 14, 13, 14, 10, 16, 13, 13, 6, 5, 1, 0], float)
EXPERTS = np.array([0, 2, 2, 3, 1, 3, 6, 6, 9, 10, 13, 16, 18, 23, 14, 22, 16, 18, 15, 25, 11, 11, 2, 0], float)
EDGES = np.logspace(-4, 0, 25)      # six bins a decade
THRESHOLD = 1e-2
INK, FILL = '#52514e', '#49bf94'    # sampled from the previous histogram


def smooth(counts):
    """1-2-1 over neighbouring bins, reflected at the ends so no events are lost."""
    return np.convolve(np.pad(counts, 1, mode='edge'), [.25, .5, .25], mode='valid')


def above(fractions):
    return fractions[EDGES[:-1] >= THRESHOLD * (1 - 1e-9)].sum()


assert ONE_NETWORK.sum() == EXPERTS.sum() == N
assert round(100 * above(ONE_NETWORK / N)) == 48 and round(100 * above(EXPERTS / N)) == 71

one, exp = smooth(ONE_NETWORK) / N, smooth(EXPERTS) / N
print(f'totals {one.sum():.3f} {exp.sum():.3f}; above 1 % after smoothing: {above(one):.1%} {above(exp):.1%}')

plt.rcParams.update({'text.usetex': True, 'font.family': 'serif', 'font.size': 21})
fig, ax = plt.subplots(figsize=(7, 3.2), dpi=200)
ax.hist(EDGES[:-1], EDGES, weights=exp, color=FILL, edgecolor='white', linewidth=.5, zorder=2)
ax.stairs(one, EDGES, color=INK, linewidth=2, zorder=3)
ax.plot([THRESHOLD] * 2, [0, .092], color=INK, linewidth=.9, linestyle=(0, (3, 2)), zorder=1)   # stops under the legend
ax.set_xscale('log')
ax.set_xlim(10 ** -4.2, 10 ** .2)
ax.set_xticks([1e-4, 1e-3, 1e-2, 1e-1, 1], [r'$10^{-4}$', r'$10^{-3}$', r'$10^{-2}$', r'$10^{-1}$', r'$1$'])
ax.minorticks_off()
ax.set_ylim(0, .125)
ax.set_yticks([0, .05, .1], ['0.00', '0.05', '0.10'])
ax.set_xlabel(r'sampling efficiency $\epsilon$')
ax.set_ylabel('fraction of events')
ax.spines[['top', 'right']].set_visible(False)
ax.legend(handles=[Patch(facecolor='none', edgecolor=INK, linewidth=2, label='one network, trained longer'),
                   Patch(facecolor=FILL, edgecolor=FILL, label='easy + hard expert')],
          loc='upper left', bbox_to_anchor=(.02, 1.06), frameon=False, fontsize=17, handlelength=1.6, labelspacing=.3)
fig.savefig('static/moe/efficiency-hard.png', bbox_inches='tight', pad_inches=.04, facecolor='white')
