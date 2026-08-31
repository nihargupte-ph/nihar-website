"""Line-art icons for the formation-channel cards (slide 05).

    micromamba run -n django-nihar-website python tools/channelicons.py

Writes static/channels/icons/<channel-id>-<1..5>.svg: five different compositions per
channel, all drawn from the same small set of parametric helpers so they share one
style (200×200 viewBox, transparent background, 3px round strokes, ink #504c44, one
accent per group). Pick one per channel with tools/iconpicker.py.
"""
import math
import random
from pathlib import Path

DECK = Path(__file__).resolve().parents[1]
OUT = DECK / 'static' / 'channels' / 'icons'
INK = '#504c44'
ACCENT = {'field': '#8a857c', 'dynamical': '#b3262e', 'agn': '#2a7f7a', 'zkl': '#7a5c99'}
GROUP = {'iso-smt': 'field', 'iso-ce': 'field', 'iso-che': 'field',
         'cluster-ejected': 'dynamical', 'cluster-incluster': 'dynamical', 'cluster-capture': 'dynamical',
         'single-capture': 'dynamical', 'triples': 'zkl', 'zkl-smbh': 'zkl', 'agn': 'agn'}
SW = 3


# ---- primitives (all return SVG fragments) -------------------------------------------------------
def _f(v):
    return f'{v:.1f}'.rstrip('0').rstrip('.')


def _attrs(stroke=None, dash=None, fill=None, sw=None, opacity=None, extra=''):
    a = []
    if stroke: a.append(f'stroke="{stroke}"')
    if sw is not None: a.append(f'stroke-width="{_f(sw)}"')
    if dash: a.append(f'stroke-dasharray="{dash}"')
    if fill: a.append(f'fill="{fill}"')
    if opacity is not None: a.append(f'opacity="{_f(opacity)}"')
    if extra: a.append(extra)
    return (' ' + ' '.join(a)) if a else ''


def dot(cx, cy, r, fill=INK, stroke='none', **kw):
    """Filled disc (a body); pass extra=tint(...) for a light fill instead of `fill`."""
    f = '' if 'fill=' in kw.get('extra', '') else f' fill="{fill}"'
    return f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(r)}"{f} stroke="{stroke}"{_attrs(**kw)}/>'


def ring(cx, cy, r, **kw):
    """Stroked circle (an orbit, a boundary, a ripple)."""
    return f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(r)}"{_attrs(**kw)}/>'


def orbit(cx, cy, rx, ry, rot=0, **kw):
    """Ellipse rotated by `rot` degrees about its centre."""
    t = f' transform="rotate({_f(rot)} {_f(cx)} {_f(cy)})"' if rot else ''
    return f'<ellipse cx="{_f(cx)}" cy="{_f(cy)}" rx="{_f(rx)}" ry="{_f(ry)}"{t}{_attrs(**kw)}/>'


def on_orbit(cx, cy, rx, ry, rot, theta):
    """Point on that ellipse at parametric angle theta (degrees)."""
    t, r = math.radians(theta), math.radians(rot)
    x, y = rx * math.cos(t), ry * math.sin(t)
    return cx + x * math.cos(r) - y * math.sin(r), cy + x * math.sin(r) + y * math.cos(r)


def orbit_tangent(rx, ry, rot, theta):
    t, r = math.radians(theta), math.radians(rot)
    dx, dy = -rx * math.sin(t), ry * math.cos(t)
    return math.degrees(math.atan2(dx * math.sin(r) + dy * math.cos(r), dx * math.cos(r) - dy * math.sin(r)))


def path(d, **kw):
    return f'<path d="{d}"{_attrs(**kw)}/>'


def poly(pts, close=False, **kw):
    d = 'M' + ' L'.join(f'{_f(x)} {_f(y)}' for x, y in pts) + (' Z' if close else '')
    return path(d, **kw)


def smooth(pts, **kw):
    """Catmull-Rom → cubic Bézier through the points."""
    if len(pts) < 3:
        return poly(pts, **kw)
    d = f'M{_f(pts[0][0])} {_f(pts[0][1])}'
    for i in range(len(pts) - 1):
        p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, len(pts) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f' C{_f(c1[0])} {_f(c1[1])} {_f(c2[0])} {_f(c2[1])} {_f(p2[0])} {_f(p2[1])}'
    return path(d, **kw)


def head(x, y, angle, size=9, **kw):
    """Open arrowhead at (x, y) pointing along `angle` (degrees, screen coords)."""
    a = math.radians(angle)
    pts = []
    for s in (150, -150):
        b = a + math.radians(s)
        pts.append((x + size * math.cos(b), y + size * math.sin(b)))
    return poly([pts[0], (x, y), pts[1]], **kw)


def arrow(x1, y1, x2, y2, bend=0, size=9, **kw):
    """Straight (bend=0) or quadratic-bent arrow; bend = sideways offset of the control point."""
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    L = math.hypot(x2 - x1, y2 - y1) or 1
    nx, ny = -(y2 - y1) / L, (x2 - x1) / L
    cx, cy = mx + nx * bend, my + ny * bend
    ang = math.degrees(math.atan2(y2 - cy, x2 - cx))
    return path(f'M{_f(x1)} {_f(y1)} Q{_f(cx)} {_f(cy)} {_f(x2)} {_f(y2)}', **kw) + head(x2, y2, ang, size, **kw)


def arc(cx, cy, r, a0, a1, **kw):
    """Circular arc from angle a0 to a1 (degrees, increasing = clockwise on screen)."""
    x0, y0 = cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0))
    x1, y1 = cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1))
    large = 1 if abs(a1 - a0) > 180 else 0
    sweep = 1 if a1 > a0 else 0
    return path(f'M{_f(x0)} {_f(y0)} A{_f(r)} {_f(r)} 0 {large} {sweep} {_f(x1)} {_f(y1)}', **kw)


def arc_arrow(cx, cy, r, a0, a1, size=8, **kw):
    """Arc with an arrowhead at its a1 end (a rotation / a swirl)."""
    x1, y1 = cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1))
    tangent = a1 + (90 if a1 > a0 else -90)
    return arc(cx, cy, r, a0, a1, **kw) + head(x1, y1, tangent, size, **kw)


def spiral(cx, cy, r0, r1, turns, a0=0, n=80, **kw):
    """Archimedean spiral from radius r0 to r1 over `turns` turns."""
    pts = []
    for i in range(n + 1):
        f = i / n
        r, a = r0 + (r1 - r0) * f, math.radians(a0) + 2 * math.pi * turns * f
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return smooth(pts, **kw), pts


def hyperbola(fx, fy, q, e, rot, span=1.0, n=40):
    """Points of a hyperbolic orbit about focus (fx, fy): pericentre distance q, eccentricity e>1,
    pericentre direction `rot` degrees; `span` = fraction of the asymptotic half-angle to draw."""
    th_inf = math.acos(-1 / e)
    p = q * (1 + e)
    pts = []
    for i in range(n + 1):
        th = -span * th_inf + 2 * span * th_inf * i / n
        r = p / (1 + e * math.cos(th))
        a = th + math.radians(rot)
        pts.append((fx + r * math.cos(a), fy + r * math.sin(a)))
    return pts


def burst(cx, cy, r, n=8, inner=0.45, **kw):
    """Sparkle: n rays alternating long/short (a GW burst, a flash)."""
    out = []
    for i in range(n):
        a = math.radians(360 * i / n - 90)
        L = r if i % 2 == 0 else r * 0.6
        out.append(poly([(cx + inner * r * math.cos(a), cy + inner * r * math.sin(a)), (cx + L * math.cos(a), cy + L * math.sin(a))], **kw))
    return ''.join(out)


def ripples(cx, cy, radii, a0, a1, **kw):
    """Concentric arcs (GW ripples) between angles a0..a1."""
    return ''.join(arc(cx, cy, r, a0, a1, **kw) for r in radii)


def wave(x0, y0, x1, y1, amp=4, n=3, **kw):
    """Sine wave from (x0,y0) to (x1,y1) with n periods."""
    L = math.hypot(x1 - x0, y1 - y0); ux, uy = (x1 - x0) / L, (y1 - y0) / L; nx, ny = -uy, ux
    pts = []
    for i in range(int(n * 12) + 1):
        f = i / (n * 12); s = amp * math.sin(2 * math.pi * n * f)
        pts.append((x0 + ux * L * f + nx * s, y0 + uy * L * f + ny * s))
    return smooth(pts, **kw)


def cluster(cx, cy, R, n, seed, r_dot=3.2, avoid=None, core=0.5, fill=INK):
    """Dot cluster: n discs within radius R, denser at the centre; `avoid` = (x, y, radius) kept clear."""
    rng = random.Random(seed)
    pts = []
    tries = 0
    while len(pts) < n and tries < 4000:
        tries += 1
        rr = R * (rng.random() ** (1 - core)); a = rng.random() * 2 * math.pi
        x, y = cx + rr * math.cos(a), cy + rr * math.sin(a)
        if avoid and math.hypot(x - avoid[0], y - avoid[1]) < avoid[2]:
            continue
        if any(math.hypot(x - px, y - py) < 2.6 * r_dot for px, py in pts):
            continue
        pts.append((x, y))
    return ''.join(dot(x, y, r_dot, fill=fill) for x, y in pts)


def roche(cx, cy, sep, q=1.0, k=1.0):
    """Figure-8 Roche lobes for two bodies at cx∓sep/2 (heavier on the left for q<1); returns a path d."""
    xl, xr = cx - sep / 2, cx + sep / 2
    rl, rr = 0.58 * sep * k, 0.58 * sep * k * q
    L1 = xl + sep * (1 / (1 + q ** 0.5)) if q != 1 else cx
    d = (f'M{_f(L1)} {_f(cy)} C{_f(L1 - rl * 0.2)} {_f(cy - rl * 0.8)} {_f(xl - rl * 1.1)} {_f(cy - rl * 1.05)} {_f(xl - rl * 1.05)} {_f(cy)} '
         f'C{_f(xl - rl * 1.1)} {_f(cy + rl * 1.05)} {_f(L1 - rl * 0.2)} {_f(cy + rl * 0.8)} {_f(L1)} {_f(cy)} '
         f'C{_f(L1 + rr * 0.2)} {_f(cy - rr * 0.8)} {_f(xr + rr * 1.1)} {_f(cy - rr * 1.05)} {_f(xr + rr * 1.05)} {_f(cy)} '
         f'C{_f(xr + rr * 1.1)} {_f(cy + rr * 1.05)} {_f(L1 + rr * 0.2)} {_f(cy + rr * 0.8)} {_f(L1)} {_f(cy)}')
    return d, L1


def blob(cx, cy, r, seed, wobble=0.12, n=14, **kw):
    """Wobbly closed curve (a diffuse envelope)."""
    rng = random.Random(seed)
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n; rr = r * (1 + wobble * (rng.random() * 2 - 1))
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    pts = pts + pts[:2]
    s = smooth(pts, **kw)
    return s


def tint(color, alpha=0.16):
    return f'fill="{color}" fill-opacity="{alpha}"'


def svg(body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">'
            f'<g fill="none" stroke="{INK}" stroke-width="{SW}" stroke-linecap="round" stroke-linejoin="round">{body}</g></svg>')


# ---- compositions --------------------------------------------------------------------------------
def iso_smt(v, A):
    if v == 1:  # Roche lobes + stream + disk
        d, L1 = roche(100, 100, 100, q=0.75)
        return (path(d, dash='6 6', stroke=A) + dot(52, 100, 27, fill=INK) +
                smooth([(L1, 100), (118, 92), (134, 86), (146, 90)], stroke=A) + head(146, 90, 30, 8, stroke=A) +
                orbit(148, 100, 20, 8, -20, stroke=A) + dot(148, 100, 6))
    if v == 2:  # donor filling its lobe (teardrop) feeding an edge-on disk
        return (path('M40 100 C40 60 70 48 96 62 L122 84 C110 100 110 100 122 116 L96 138 C70 152 40 140 40 100 Z', extra=tint(A)) +
                smooth([(122, 100), (134, 94), (146, 96)], stroke=A, dash='4 5') + head(146, 96, 10, 7, stroke=A) +
                orbit(158, 104, 26, 7, -12, extra=tint(A)) + dot(158, 104, 5) +
                ring(158, 104, 13, stroke=A, dash='3 4', sw=2))
    if v == 3:  # face-on disk built by a spiral stream from the donor
        s, _ = spiral(132, 108, 42, 8, 1.6, a0=180, stroke=A)
        return (dot(50, 78, 22, extra=tint(A), stroke=INK) + s + ring(132, 108, 20, stroke=A, sw=2) + ring(132, 108, 30, stroke=A, sw=2, opacity=0.6) +
                dot(132, 108, 6) + head(*on_orbit(132, 108, 8, 8, 0, 0), -90, 7, stroke=A))
    if v == 4:  # hourglass of matter between two stars, circular orbit stays circular
        return (ring(100, 100, 74, dash='5 7', stroke=A) + dot(48, 100, 20) + dot(152, 100, 12) +
                path('M62 84 C96 90 116 96 140 98 L140 102 C116 104 96 110 62 116 Z', stroke=A, extra=tint(A)) + head(144, 100, 0, 8, stroke=A) +
                arc_arrow(100, 100, 74, -60, -30, 7, stroke=INK, sw=2) + arc_arrow(100, 100, 74, 120, 150, 7, stroke=INK, sw=2))
    # 5: the orbit shrinks step by step while the stream flows: three stages, top to bottom
    out = ''
    for i, (y, sep, rd) in enumerate(((38, 72, 13), (100, 52, 10), (162, 32, 6))):
        out += ring(100, y, sep / 2, stroke=A, dash='4 5', sw=2) + dot(100 - sep / 2, y, rd) + dot(100 + sep / 2, y, rd * 0.55)
        if i < 2:
            out += path(f'M{_f(100 - sep / 2 + rd)} {y} Q100 {y - 7} {_f(100 + sep / 2 - rd * 0.55 - 2)} {y}', stroke=A) + head(100 + sep / 2 - rd * 0.55 - 2, y, 20, 6, stroke=A)
            out += arrow(160, y + 30, 160, y + 54, size=6, stroke=INK, sw=2)
    return out


def iso_ce(v, A):
    if v == 1:  # dashed envelope with two cores and a spiral-in
        s, pts = spiral(100, 100, 58, 14, 1.4, a0=200, stroke=A)
        ang = math.degrees(math.atan2(pts[-1][1] - pts[-2][1], pts[-1][0] - pts[-2][0]))
        return (ring(100, 100, 74, dash='7 7', extra=tint(A), stroke=A) + s + head(*pts[-1], ang, 8, stroke=A) +
                dot(100, 100, 9) + dot(*pts[-1], 6))
    if v == 2:  # wobbly cloud envelope, two cores, curved arrow between
        return (blob(100, 100, 72, seed=3, extra=tint(A), stroke=A) + blob(100, 100, 52, seed=8, wobble=0.1, stroke=A, sw=2, opacity=0.6) +
                dot(80, 108, 9) + dot(120, 92, 9) + arc_arrow(100, 100, 30, 150, 330, 7, stroke=INK, sw=2))
    if v == 3:  # envelope being shed: expanding arcs with outward arrows around a tight pair
        out = ''
        for a in range(0, 360, 45):
            x, y = 100 + 52 * math.cos(math.radians(a)), 100 + 52 * math.sin(math.radians(a))
            x2, y2 = 100 + 82 * math.cos(math.radians(a)), 100 + 82 * math.sin(math.radians(a))
            out += arrow(x, y, x2, y2, size=7, stroke=A, sw=2)
        return (out + ring(100, 100, 42, dash='4 6', stroke=A, extra=tint(A)) + ring(100, 100, 16, stroke=INK, sw=2) +
                dot(100 - 16, 100, 7) + dot(100 + 16, 100, 7))
    if v == 4:  # before → after: wide pair in an envelope, tight pair with the envelope gone
        return (ring(54, 100, 44, extra=tint(A), stroke=A) + dot(36, 100, 8) + dot(72, 100, 8) +
                arrow(102, 100, 124, 100, size=8, stroke=INK) +
                dot(151, 100, 6) + dot(165, 100, 6) + ring(158, 100, 12, sw=2, stroke=INK) +
                ''.join(poly([(158 + 26 * math.cos(math.radians(a)), 100 + 26 * math.sin(math.radians(a))), (158 + 38 * math.cos(math.radians(a)), 100 + 38 * math.sin(math.radians(a)))], stroke=A, sw=2) for a in range(0, 360, 40)))
    # 5: cutaway envelope with a plunging track that ends on the core; puffs leaving the rim
    s, pts = spiral(100, 100, 66, 6, 2.2, a0=-40, stroke=INK, sw=2.5)
    puffs = ''.join(arc(100 + 86 * math.cos(math.radians(a)), 100 + 86 * math.sin(math.radians(a)), 9, a - 110, a + 110, stroke=A, sw=2) for a in (20, 100, 200, 300))
    return ring(100, 100, 72, stroke=A, extra=tint(A)) + s + dot(100, 100, 8) + dot(*pts[0], 6) + puffs


def iso_che(v, A):
    if v == 1:  # two stars each spinning, well inside their dashed lobes
        d, _ = roche(100, 100, 92, q=1)
        return (path(d, dash='6 6', stroke=A) + dot(54, 100, 17, extra=tint(A), stroke=INK) + dot(146, 100, 17, extra=tint(A), stroke=INK) +
                arc_arrow(54, 100, 25, 200, 340, 7, stroke=A) + arc_arrow(146, 100, 25, 200, 340, 7, stroke=A))
    if v == 2:  # edge-on: oblate stars with bulges pointing at each other, spin axes
        return (orbit(100, 100, 80, 18, 0, stroke=A, dash='4 6', sw=2) +
                orbit(58, 100, 24, 18, 0, extra=tint(A), stroke=INK) + orbit(142, 100, 24, 18, 0, extra=tint(A), stroke=INK) +
                path('M58 66 V134 M142 66 V134', stroke=A, sw=2, dash='3 4') +
                arc_arrow(58, 100, 30, 250, 290, 6, stroke=A, sw=2) + arc_arrow(142, 100, 30, 250, 290, 6, stroke=A, sw=2) +
                path('M82 96 Q100 100 118 96 M82 104 Q100 100 118 104', stroke=INK, sw=2, opacity=0.7))
    if v == 3:  # mixing swirls inside each star
        sl, _ = spiral(62, 100, 3, 20, 1.5, a0=0, stroke=A, sw=2.5)
        sr, _ = spiral(138, 100, 3, 20, 1.5, a0=180, stroke=A, sw=2.5)
        return (ring(62, 100, 26) + ring(138, 100, 26) + sl + sr +
                ring(100, 100, 82, dash='5 7', sw=2, stroke=A) + head(62 + 20, 100, 90, 7, stroke=A) + head(138 - 20, 100, -90, 7, stroke=A))
    if v == 4:  # tight fast orbit: speed lines around a compact pair, roomy lobes never filled
        d, _ = roche(100, 100, 44, q=1, k=1.5)
        return (path(d, dash='5 5', stroke=A) + dot(78, 100, 8) + dot(122, 100, 8) +
                ring(100, 100, 22, stroke=INK, sw=2) + head(100, 78, 0, 6, sw=2) + head(100, 122, 180, 6, sw=2) +
                arc_arrow(78, 100, 13, 200, 340, 5, stroke=A, sw=2) + arc_arrow(122, 100, 13, 200, 340, 5, stroke=A, sw=2))
    # 5: cutaway star: core, meridians (rotation) and mixing arrows core→surface, small companion
    out = ring(84, 100, 44, extra=tint(A), stroke=INK) + dot(84, 100, 9, fill=A)
    for a in (-30, 90, 210):
        x0, y0 = 84 + 14 * math.cos(math.radians(a)), 100 + 14 * math.sin(math.radians(a))
        x1, y1 = 84 + 36 * math.cos(math.radians(a)), 100 + 36 * math.sin(math.radians(a))
        out += arrow(x0, y0, x1, y1, bend=8, size=7, stroke=A, sw=2)
    out += orbit(84, 100, 44, 12, 0, stroke=INK, sw=1.5, dash='3 4') + arc_arrow(84, 100, 54, 240, 300, 7, stroke=INK, sw=2)
    out += dot(158, 100, 12) + path('M134 100 H142', stroke=INK, sw=2, dash='2 4')
    return out


def cluster_ejected(v, A):
    if v == 1:  # round cluster, binary flying out top-right
        return (cluster(88, 112, 52, 34, seed=11, avoid=(150, 50, 40)) + ring(88, 112, 60, dash='4 7', sw=2, stroke=A, opacity=0.7) +
                arrow(112, 88, 152, 48, size=9, stroke=A) + dot(160, 40, 5) + dot(172, 30, 5) + ring(166, 35, 12, stroke=A, sw=2))
    if v == 2:  # dense tinted core with a binary trailing motion lines out to the left
        return (dot(126, 104, 50, fill=A, opacity=0.14, stroke='none') + cluster(126, 104, 44, 30, seed=5, core=0.7) +
                poly([(84, 92), (46, 60)], stroke=A, dash='3 5') + poly([(88, 106), (52, 80)], stroke=A, dash='3 5', opacity=0.5) +
                dot(38, 52, 6) + dot(26, 42, 6) + ring(32, 47, 12, stroke=A, sw=2) + head(30, 44, 225, 8, stroke=A))
    if v == 3:  # cluster low-left, binary far top-right on a long dashed trajectory
        return (cluster(60, 140, 40, 22, seed=2) + smooth([(92, 112), (118, 84), (146, 58), (166, 44)], stroke=A, dash='5 6') +
                head(166, 44, -38, 8, stroke=A) + orbit(160, 36, 16, 9, -35, stroke=A, sw=2) +
                dot(*on_orbit(160, 36, 16, 9, -35, 30), 5) + dot(*on_orbit(160, 36, 16, 9, -35, 210), 5))
    if v == 4:  # three-body recoil at the edge: single one way, binary the other
        return (cluster(100, 100, 46, 28, seed=9, avoid=(100, 46, 22)) + ring(100, 100, 54, dash='4 7', sw=2, stroke=A, opacity=0.6) +
                dot(100, 48, 4.5) + arrow(100, 40, 100, 14, size=7, stroke=A, sw=2.5) +
                orbit(154, 50, 14, 8, 30, stroke=A, sw=2) + dot(*on_orbit(154, 50, 14, 8, 30, 0), 5) + dot(*on_orbit(154, 50, 14, 8, 30, 180), 5) +
                arrow(120, 62, 140, 56, size=7, stroke=A, sw=2.5) + arrow(150, 74, 176, 86, size=7, stroke=A, sw=2.5))
    # 5: tidal radius boundary; binary crossing it with a trail of dashes
    return (ring(100, 106, 78, dash='6 8', sw=2, stroke=A) + cluster(96, 110, 46, 30, seed=17) +
            ''.join(dot(x, y, 2.2, fill=A) for x, y in ((128, 84), (140, 74), (152, 64))) +
            dot(166, 48, 6) + dot(180, 40, 6) + ring(173, 44, 13, stroke=A, sw=2) + head(160, 54, -40, 8, stroke=A))


def cluster_incluster(v, A):
    if v == 1:  # cluster with a contact pair at the centre, ripples both sides
        return (cluster(100, 100, 70, 34, seed=21, avoid=(100, 100, 46)) +
                dot(94, 100, 7) + dot(106, 100, 7) + ripples(100, 100, (20, 30, 40), -40, 40, stroke=A) + ripples(100, 100, (20, 30, 40), 140, 220, stroke=A))
    if v == 2:  # tiny ellipse orbit at the centre + expanding rings
        return (cluster(100, 100, 70, 38, seed=33, avoid=(100, 100, 40)) + orbit(100, 100, 12, 7, 25, stroke=A, sw=2) +
                dot(*on_orbit(100, 100, 12, 7, 25, 0), 5) + dot(*on_orbit(100, 100, 12, 7, 25, 180), 5) +
                ring(100, 100, 22, stroke=A, sw=2) + ring(100, 100, 30, stroke=A, sw=2, opacity=0.5))
    if v == 3:  # merging: two overlapping tinted discs with a spiral-in track
        s, pts = spiral(100, 100, 30, 6, 1.5, a0=90, stroke=A, sw=2.5)
        return (cluster(100, 100, 70, 34, seed=41, avoid=(100, 100, 42)) + dot(93, 100, 12, extra=tint(A), stroke=INK) + dot(107, 100, 12, extra=tint(A), stroke=INK) + s)
    if v == 4:  # hardening: neighbours nudge the pair (inward arrows), then a ripple
        out = cluster(100, 100, 70, 30, seed=52, avoid=(100, 100, 44))
        for a in (30, 150, 270):
            x0, y0 = 100 + 40 * math.cos(math.radians(a)), 100 + 40 * math.sin(math.radians(a))
            x1, y1 = 100 + 22 * math.cos(math.radians(a)), 100 + 22 * math.sin(math.radians(a))
            out += arrow(x0, y0, x1, y1, size=6, stroke=A, sw=2)
        return out + dot(95, 100, 5.5) + dot(105, 100, 5.5) + ring(100, 100, 11, stroke=INK, sw=2)
    # 5: sketchy globular (dashed outline + dots), tight off-centre pair, wavy GW lines leaving
    return (ring(100, 100, 74, dash='5 7', sw=2, stroke=A) + cluster(100, 100, 62, 30, seed=63, avoid=(78, 116, 30)) +
            dot(72, 118, 5) + dot(84, 114, 5) + wave(96, 104, 134, 72, amp=4, n=3, stroke=A, sw=2) + wave(88, 128, 124, 154, amp=4, n=3, stroke=A, sw=2))


def cluster_capture(v, A):
    if v == 1:  # binary + single: incoming intruder, tangle, out comes an eccentric pair
        ell = orbit(140, 116, 44, 12, -30, stroke=A)
        p, q = on_orbit(140, 116, 44, 12, -30, 0), on_orbit(140, 116, 44, 12, -30, 180)
        return (ring(56, 70, 16, sw=2, stroke=INK) + dot(44, 62, 5) + dot(68, 78, 5) +
                smooth([(20, 150), (48, 118), (66, 96)], stroke=A, dash='4 5') + head(66, 96, -50, 7, stroke=A) +
                smooth([(76, 86), (94, 74), (84, 100), (108, 88), (96, 112), (120, 104)], stroke=INK, sw=2) +
                ell + dot(*p, 5) + dot(*q, 5))
    if v == 2:  # binary + binary head-on, result: one very thin ellipse (and an escaper)
        return (orbit(48, 52, 18, 10, 20, stroke=INK, sw=2) + dot(*on_orbit(48, 52, 18, 10, 20, 0), 4.5) + dot(*on_orbit(48, 52, 18, 10, 20, 180), 4.5) +
                orbit(152, 52, 18, 10, -20, stroke=INK, sw=2) + dot(*on_orbit(152, 52, 18, 10, -20, 0), 4.5) + dot(*on_orbit(152, 52, 18, 10, -20, 180), 4.5) +
                arrow(66, 66, 86, 84, size=7, stroke=A, sw=2) + arrow(134, 66, 114, 84, size=7, stroke=A, sw=2) +
                orbit(100, 134, 62, 14, 0, stroke=A) + dot(*on_orbit(100, 134, 62, 14, 0, 180), 5) + dot(*on_orbit(100, 134, 62, 14, 0, 0), 5) +
                arrow(112, 100, 130, 168, size=0, stroke=INK, sw=1.5, dash='3 4') + dot(132, 172, 3.5) + head(132, 172, 75, 6, stroke=INK, sw=1.5))
    if v == 3:  # three tangled tracks (the chaotic phase) resolving into a thin ellipse
        return (smooth([(24, 40), (60, 70), (48, 110), (84, 96), (70, 60), (100, 84)], stroke=INK, sw=2) +
                smooth([(20, 120), (50, 130), (70, 100), (94, 118)], stroke=INK, sw=2, opacity=0.7) +
                smooth([(40, 176), (56, 140), (82, 150), (96, 128)], stroke=A, sw=2) +
                orbit(136, 118, 52, 11, -35, stroke=A) + dot(*on_orbit(136, 118, 52, 11, -35, 0), 5) + dot(*on_orbit(136, 118, 52, 11, -35, 180), 5) +
                dot(24, 40, 4) + dot(20, 120, 4) + dot(40, 176, 4))
    if v == 4:  # strip: approach → tangle → eccentric ellipse
        return (dot(30, 100, 5) + ring(30, 100, 12, sw=2, stroke=INK) + dot(30, 88, 4) + arrow(46, 100, 60, 100, size=6, stroke=INK, sw=2) +
                smooth([(72, 92), (84, 84), (80, 104), (96, 98), (90, 116), (106, 108), (100, 90), (116, 100)], stroke=A, sw=2.2) +
                arrow(124, 100, 138, 100, size=6, stroke=INK, sw=2) +
                orbit(166, 100, 26, 7, -70, stroke=A) + dot(*on_orbit(166, 100, 26, 7, -70, 0), 4.5) + dot(*on_orbit(166, 100, 26, 7, -70, 180), 4.5))
    # 5: the outcome close-up: pericentre burst on a very eccentric orbit, third body escaping
    p = on_orbit(96, 112, 64, 18, -20, 180)
    return (orbit(96, 112, 64, 18, -20, stroke=A) + dot(*p, 6) + dot(*on_orbit(96, 112, 64, 18, -20, 140), 5) +
            burst(p[0], p[1], 22, 8, 0.55, stroke=A, sw=2) +
            arrow(132, 76, 166, 44, size=8, stroke=INK, sw=2) + dot(170, 40, 4.5))


def triples(v, A):
    if v == 1:  # hierarchical: tilted inner ellipse, wide outer ellipse with the third body
        return (orbit(100, 100, 86, 56, 0, stroke=INK, dash='5 7', sw=2) + dot(*on_orbit(100, 100, 86, 56, 0, 20), 7) +
                orbit(100, 100, 26, 14, -40, stroke=A) + dot(*on_orbit(100, 100, 26, 14, -40, 0), 5.5) + dot(*on_orbit(100, 100, 26, 14, -40, 180), 5.5))
    if v == 2:  # the inner orbit rocks: double-headed arc arrow for the inclination swing
        return (ring(100, 100, 82, stroke=INK, dash='5 7', sw=2) + dot(*on_orbit(100, 100, 82, 82, 0, -60), 7) +
                orbit(100, 100, 30, 12, -30, stroke=A) + dot(*on_orbit(100, 100, 30, 12, -30, 0), 5) + dot(*on_orbit(100, 100, 30, 12, -30, 180), 5) +
                arc(100, 100, 48, 200, 260, stroke=A, sw=2) + head(*on_orbit(100, 100, 48, 48, 0, 200), 110, 6, stroke=A, sw=2) + head(*on_orbit(100, 100, 48, 48, 0, 260), 350, 6, stroke=A, sw=2) +
                arc(100, 100, 48, 20, 80, stroke=A, sw=2) + head(*on_orbit(100, 100, 48, 48, 0, 20), 290, 6, stroke=A, sw=2) + head(*on_orbit(100, 100, 48, 48, 0, 80), 170, 6, stroke=A, sw=2))
    if v == 3:  # ZKL cycle: the inner orbit drawn twice — round now, thin and tilted later
        return (orbit(100, 100, 88, 50, 0, stroke=INK, dash='5 7', sw=2) + dot(*on_orbit(100, 100, 88, 50, 0, 160), 7) +
                ring(100, 100, 22, stroke=A, dash='4 4', sw=2) + orbit(100, 100, 34, 9, -35, stroke=A) +
                dot(100, 100, 5.5) + dot(*on_orbit(100, 100, 34, 9, -35, 0), 5) +
                arrow(100 + 20, 100 - 22, 100 + 34, 100 - 28, bend=-6, size=6, stroke=A, sw=2))
    if v == 4:  # edge-on: outer orbit as a flat line, inner ellipse standing up at a steep angle
        return (orbit(100, 104, 86, 8, 0, stroke=INK, dash='5 7', sw=2) + dot(*on_orbit(100, 104, 86, 8, 0, 180), 7) +
                orbit(118, 104, 30, 10, -70, stroke=A) + dot(*on_orbit(118, 104, 30, 10, -70, 0), 5) + dot(*on_orbit(118, 104, 30, 10, -70, 180), 5) +
                poly([(118, 44), (118, 164)], stroke=A, dash='2 5', sw=1.5, opacity=0.6))
    # 5: nested inner ellipses at successive rotations (the orbit precesses), faint→bold
    out = ring(100, 100, 84, stroke=INK, dash='5 7', sw=2) + dot(*on_orbit(100, 100, 84, 84, 0, 30), 7)
    for i, rot in enumerate((-80, -50, -20)):
        out += orbit(100, 100, 32, 12, rot, stroke=A, opacity=0.3 + 0.35 * i, sw=2 + 0.5 * i)
    return out + dot(*on_orbit(100, 100, 32, 12, -20, 0), 5) + dot(*on_orbit(100, 100, 32, 12, -20, 180), 5)


def agn(v, A):
    def pair(cx, cy, r=4, sep=9, rot=0):
        a = math.radians(rot)
        return (dot(cx - sep / 2 * math.cos(a), cy - sep / 2 * math.sin(a), r) + dot(cx + sep / 2 * math.cos(a), cy + sep / 2 * math.sin(a), r) +
                ring(cx, cy, sep, stroke=INK, sw=1.5))
    if v == 1:  # face-on rings around a big central dot, embedded pairs, inward migration arrows
        out = dot(100, 100, 14) + ''.join(ring(100, 100, r, stroke=A, sw=2, opacity=0.9 - 0.15 * i) for i, r in enumerate((32, 50, 68, 86)))
        out += pair(100 + 59 * math.cos(math.radians(-40)), 100 + 59 * math.sin(math.radians(-40)), rot=50)
        out += pair(100 + 77 * math.cos(math.radians(160)), 100 + 77 * math.sin(math.radians(160)), rot=250)
        out += arrow(*on_orbit(100, 100, 74, 74, 0, 70), *on_orbit(100, 100, 44, 44, 0, 70), size=7, stroke=INK, sw=2)
        return out
    if v == 2:  # edge-on lens with a gap where the pair sits
        return (path('M14 100 C40 78 160 78 186 100 C160 122 40 122 14 100 Z', stroke=A, extra=tint(A)) + dot(100, 100, 12) +
                path('M60 100 C80 92 120 92 140 100', stroke=A, sw=1.5, dash='3 4') +
                pair(148, 100, r=3.5, sep=8, rot=0) + path('M138 84 V116', stroke=INK, sw=1.5, dash='2 3') + path('M158 84 V116', stroke=INK, sw=1.5, dash='2 3'))
    if v == 3:  # spiral arms, a highlighted ring (migration trap) holding a pair
        s1, _ = spiral(100, 100, 18, 88, 0.9, a0=0, stroke=A, sw=2)
        s2, _ = spiral(100, 100, 18, 88, 0.9, a0=180, stroke=A, sw=2)
        return (dot(100, 100, 13) + s1 + s2 + ring(100, 100, 52, stroke=INK, dash='3 5', sw=1.5) +
                pair(*on_orbit(100, 100, 52, 52, 0, 120), rot=30) + arc_arrow(100, 100, 52, 20, 70, 6, stroke=INK, sw=2))
    if v == 4:  # disk seen at a tilt with a jet along the axis; pair on the disk
        return (orbit(100, 104, 82, 30, 0, stroke=A, extra=tint(A)) + orbit(100, 104, 44, 16, 0, stroke=A, sw=2, opacity=0.6) +
                dot(100, 104, 12) + path('M100 92 V34 M100 116 V174', stroke=INK, sw=2.5) + head(100, 34, -90, 7) + head(100, 174, 90, 7) +
                pair(*on_orbit(100, 104, 64, 23, 0, 35), rot=-20) + arc(100, 104, 64, 60, 100, stroke=INK, sw=1.5, dash='3 4'))
    # 5: zoomed arc of the disk (thick band) with a pair carving a gap and sliding inward
    return (arc(40, 200, 140, 260, 340, stroke=A, sw=16, opacity=0.25) + arc(40, 200, 140, 260, 340, stroke=A, sw=2) +
            arc(40, 200, 124, 270, 340, stroke=A, sw=2, opacity=0.5) + arc(40, 200, 156, 260, 335, stroke=A, sw=2, opacity=0.5) +
            pair(*on_orbit(40, 200, 140, 140, 0, 300), r=5, sep=13, rot=30) +
            arrow(*on_orbit(40, 200, 168, 168, 0, 300), *on_orbit(40, 200, 150, 150, 0, 300), size=7, stroke=INK, sw=2) + dot(40, 200, 34) +
            arc_arrow(40, 200, 140, 318, 330, 7, stroke=INK, sw=2))


def zkl_smbh(v, A):
    if v == 1:  # big central dot, wide circular orbit, pair on it on a tilted little ellipse
        p = on_orbit(100, 100, 74, 74, 0, -35)
        return (dot(100, 100, 22) + ring(100, 100, 74, stroke=INK, dash='5 7', sw=2) +
                orbit(p[0], p[1], 22, 10, 40, stroke=A) + dot(*on_orbit(p[0], p[1], 22, 10, 40, 0), 5) + dot(*on_orbit(p[0], p[1], 22, 10, 40, 180), 5))
    if v == 2:  # the inner orbit stretches: round → thin, arrows along the long axis
        p = on_orbit(100, 100, 70, 70, 0, 150)
        return (dot(100, 100, 20) + ring(100, 100, 70, stroke=INK, dash='5 7', sw=2) +
                ring(p[0], p[1], 14, stroke=A, dash='3 4', sw=2) + orbit(p[0], p[1], 30, 8, -30, stroke=A) +
                dot(*on_orbit(p[0], p[1], 30, 8, -30, 0), 5) + dot(*p, 5) +
                arrow(*on_orbit(p[0], p[1], 17, 4, -30, 180), *on_orbit(p[0], p[1], 40, 4, -30, 180), size=6, stroke=A, sw=2) +
                arrow(*on_orbit(p[0], p[1], 17, 4, -30, 0), *on_orbit(p[0], p[1], 40, 4, -30, 0), size=6, stroke=A, sw=2))
    if v == 3:  # SMBH with an accretion ring; pair’s ellipse at high tilt, swing arrow
        p = on_orbit(100, 100, 76, 76, 0, 30)
        return (dot(100, 100, 18) + ring(100, 100, 30, stroke=INK, sw=2, opacity=0.6) + ring(100, 100, 76, stroke=INK, dash='5 7', sw=2) +
                orbit(p[0], p[1], 26, 9, 70, stroke=A) + dot(*on_orbit(p[0], p[1], 26, 9, 70, 0), 5) + dot(*on_orbit(p[0], p[1], 26, 9, 70, 180), 5) +
                arc(p[0], p[1], 34, 100, 160, stroke=A, sw=2) + head(*on_orbit(p[0], p[1], 34, 34, 0, 100), 190, 6, stroke=A, sw=2) + head(*on_orbit(p[0], p[1], 34, 34, 0, 160), 70, 6, stroke=A, sw=2))
    if v == 4:  # edge-on: wide orbit is a flat line, pair's ellipse strongly inclined
        return (dot(100, 102, 20) + orbit(100, 102, 84, 10, 0, stroke=INK, dash='5 7', sw=2) +
                orbit(160, 102, 24, 9, -65, stroke=A) + dot(*on_orbit(160, 102, 24, 9, -65, 0), 5) + dot(*on_orbit(160, 102, 24, 9, -65, 180), 5) +
                poly([(160, 60), (160, 144)], stroke=A, dash='2 5', sw=1.5, opacity=0.6))
    # 5: zoom on the pair with its elongating ellipse; the SMBH is a big arc in the corner
    return (dot(26, 174, 44) + arc(26, 174, 74, -70, 10, stroke=INK, dash='5 7', sw=2) +
            ring(122, 84, 24, stroke=A, dash='4 4', sw=2) + orbit(122, 84, 52, 14, -35, stroke=A) +
            dot(*on_orbit(122, 84, 52, 14, -35, 180), 6) + dot(122, 84, 6) +
            arrow(96, 118, 70, 140, size=7, stroke=INK, sw=2, dash='3 3'))


def single_capture(v, A):
    if v == 1:  # one body sweeps past the other on a hyperbola; flash at pericentre; the dashed ellipse it is left on
        fx, fy = 108, 100
        h = hyperbola(fx, fy, 16, 1.5, 180, span=0.86)
        return (dot(fx, fy, 8) + smooth(h, stroke=INK, sw=2.5) + dot(*h[0], 5.5) +
                head(*h[-1], math.degrees(math.atan2(h[-1][1] - h[-2][1], h[-1][0] - h[-2][0])), 7) +
                burst(fx - 16, fy, 20, 8, 0.55, stroke=A, sw=2) + orbit(fx + 28.6, fy, 44, 33, 0, stroke=A, dash='5 6', sw=2))
    if v == 2:  # two dots inbound (arrows), ripples at pericentre, a thin bound ellipse
        p = on_orbit(112, 100, 62, 16, 0, 180)
        return (arrow(20, 40, 44, 82, bend=10, size=8, stroke=INK) + dot(18, 36, 6) +
                arrow(60, 170, 46, 118, bend=-10, size=8, stroke=INK) + dot(62, 174, 6) +
                orbit(112, 100, 62, 16, 0, stroke=A) + dot(p[0] + 3, p[1], 5) + dot(*on_orbit(112, 100, 62, 16, 0, 200), 5) +
                ripples(p[0], p[1], (14, 22, 30), 120, 240, stroke=A, sw=2))
    if v == 3:  # before → after strip
        return (poly([(16, 56), (72, 64)], stroke=INK, sw=2) + head(72, 64, 8, 7, sw=2) + dot(16, 56, 5) +
                poly([(70, 140), (18, 150)], stroke=INK, sw=2) + head(18, 150, 191, 7, sw=2) + dot(70, 140, 5) +
                arrow(86, 100, 108, 100, size=8, stroke=A) +
                orbit(152, 100, 40, 9, -60, stroke=A) + dot(*on_orbit(152, 100, 40, 9, -60, 0), 5) + dot(*on_orbit(152, 100, 40, 9, -60, 180), 5))
    if v == 4:  # one flyby that never leaves: the incoming hyperbola bends into a closed ellipse
        h = hyperbola(100, 108, 14, 2.2, 90, span=0.75)
        inc = h[: len(h) // 2 + 1]
        return (dot(100, 108, 9) + smooth(inc, stroke=INK, sw=2.5) + dot(*inc[0], 5) +
                orbit(100, 108 - 52, 22, 66, 0, stroke=A) + dot(*on_orbit(100, 56, 22, 66, 0, 90), 5) +
                head(*on_orbit(100, 56, 22, 66, 0, 200), orbit_tangent(22, 66, 0, 200) + 180, 7, stroke=A))
    # 5: the burst itself: pericentre flash with waves running out, dots close together on a very thin orbit
    p = on_orbit(100, 100, 78, 20, -25, 0)
    return (orbit(100, 100, 78, 20, -25, stroke=A) + dot(p[0] - 6, p[1] + 2, 5) + dot(*on_orbit(100, 100, 78, 20, -25, 12), 5) +
            burst(p[0], p[1], 20, 8, 0.6, stroke=A, sw=2) +
            wave(p[0] + 22, p[1] - 18, p[0] + 44, p[1] - 44, amp=3.5, n=2.5, stroke=INK, sw=2) + wave(p[0] + 26, p[1] + 6, p[0] + 56, p[1] + 10, amp=3.5, n=2.5, stroke=INK, sw=2))


DRAW = {'iso-smt': iso_smt, 'iso-ce': iso_ce, 'iso-che': iso_che, 'cluster-ejected': cluster_ejected,
        'cluster-incluster': cluster_incluster, 'cluster-capture': cluster_capture, 'triples': triples,
        'agn': agn, 'zkl-smbh': zkl_smbh, 'single-capture': single_capture}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for cid, fn in DRAW.items():
        for v in range(1, 6):
            (OUT / f'{cid}-{v}.svg').write_text(svg(fn(v, ACCENT[GROUP[cid]])) + '\n')
    print(f'wrote {len(DRAW) * 5} icons to {OUT}')


if __name__ == '__main__':
    main()
