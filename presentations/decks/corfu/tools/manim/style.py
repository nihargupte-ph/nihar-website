"""Shared look for the formation-channel animations (see STORYBOARD.md).

Every scene subclasses ChannelScene, which sets the deck background and exposes a few
helpers so all ten clips share one visual language: stars (soft glowing discs), black
holes (ink discs with a thin ring), gravitational-wave bursts (expanding rings), and a
faint dot cloud for clusters / nuclei.
"""
import os

import numpy as np
from manim import *

VARIANT = int(os.environ.get('CH_VARIANT', '1'))   # render.sh sets CH_VARIANT; scenes branch on it for alternative compositions

PAPER = '#fdfdfd'      # slide background (deck.yaml theme.bg)
INK = '#504c44'
ACCENT = {'field': '#8a857c', 'dynamical': '#b3262e', 'zkl': '#7a5c99', 'agn': '#2a7f7a'}
STAR_BLUE = '#6fa3d8'
STAR_ORANGE = '#e0a15a'
STAR_RED = '#d97a5a'
GAS = '#c9b98f'


class ChannelScene(Scene):
    GROUP = 'field'
    LABEL = ''          # optional 1–2 word caption at the bottom

    def setup(self):
        self.camera.background_color = PAPER
        self.accent = ACCENT[self.GROUP]

    # ---- primitives -------------------------------------------------------------------
    def star(self, radius=0.35, color=STAR_BLUE, pos=ORIGIN):
        glow = Circle(radius=radius * 1.9, color=color, fill_opacity=0.18, stroke_width=0).move_to(pos)
        body = Circle(radius=radius, color=color, fill_opacity=1, stroke_width=0).move_to(pos)
        return VGroup(glow, body)

    def bh(self, radius=0.18, pos=ORIGIN):
        ring = Circle(radius=radius * 1.45, color=self.accent, stroke_width=2).move_to(pos)
        body = Circle(radius=radius, color=INK, fill_opacity=1, stroke_width=0).move_to(pos)
        return VGroup(ring, body)

    def collapse(self, star_group, radius=0.18):
        """Star → BH: brief brightening, shrink, replaced by a bh() at the same spot."""
        pos = star_group[1].get_center()
        flash = Circle(radius=star_group[1].radius * 2.4, color=WHITE, fill_opacity=0.9, stroke_width=0).move_to(pos)
        new = self.bh(radius, pos)
        self.play(FadeIn(flash, run_time=0.15))
        self.play(FadeOut(flash), Transform(star_group, new), run_time=0.45)
        return star_group

    def gw_burst(self, pos, n=3, rmax=1.2, run_time=0.9):
        rings = VGroup(*[Circle(radius=0.05, color=self.accent, stroke_width=2.5, stroke_opacity=0.9).move_to(pos) for _ in range(n)])
        anims = [ring.animate(rate_func=linear).scale(rmax / 0.05).set_stroke(opacity=0) for ring in rings]
        self.play(LaggedStart(*anims, lag_ratio=0.25), run_time=run_time)
        self.remove(rings)

    def dot_cloud(self, n=300, sigma=1.6, center=ORIGIN, seed=0, color=INK, radius=0.025, opacity=0.35):
        rng = np.random.default_rng(seed)
        pts = rng.normal(0, sigma, size=(n, 2))
        return VGroup(*[Dot(center + np.array([x, y, 0]), radius=radius, color=color, fill_opacity=opacity) for x, y in pts])

    def label(self, text):
        if not text:
            return None
        t = Text(text, font_size=22, color=INK, weight=MEDIUM).to_edge(DOWN, buff=0.35)
        self.add(t)
        return t

    @staticmethod
    def ellipse_point(a, e, theta, center=ORIGIN, tilt=0.0):
        """Point on a Keplerian ellipse with focus at `center`, semi-major a, eccentricity e."""
        r = a * (1 - e * e) / (1 + e * np.cos(theta))
        x, y = r * np.cos(theta), r * np.sin(theta)
        c, s = np.cos(tilt), np.sin(tilt)
        return center + np.array([c * x - s * y, s * x + c * y, 0])


# ---- Keplerian timing helpers (generic; used by the dynamical scenes) ------------------------
def true_anomaly(M, e, iters=6):
    """Elliptic true anomaly from mean anomaly M (rad) by Newton iteration on Kepler's equation."""
    E = M if e < 0.8 else np.pi
    for _ in range(iters):
        E -= (E - e * np.sin(E) - M) / (1 - e * np.cos(E))
    return 2 * np.arctan2(np.sqrt(1 + e) * np.sin(E / 2), np.sqrt(1 - e) * np.cos(E / 2))


def anomaly_table(e, th0, th1, n=4000):
    """Theta samples in [th0, th1] and normalised time (0..1) with dtheta/dt ∝ (1 + e cos θ)^2.
    Works for ellipses (e<1) and hyperbolae (e>1, |θ| < arccos(-1/e)); interpolate with np.interp(t, tt, th)."""
    th = np.linspace(th0, th1, n)
    dt = 1.0 / (1 + e * np.cos(th)) ** 2
    tt = np.concatenate([[0], np.cumsum(0.5 * (dt[1:] + dt[:-1]) * np.diff(th))])
    return th, tt / tt[-1]


def conic_point(a, e, theta, center=ORIGIN, tilt=0.0):
    """Point on the conic r = p / (1 + e cos θ) with focus at `center`; p = a(1-e²) for e<1, a(e²-1) for e>1."""
    p = a * abs(1 - e * e)
    r = p / (1 + e * np.cos(theta))
    x, y = r * np.cos(theta), r * np.sin(theta)
    c, s = np.cos(tilt), np.sin(tilt)
    return center + np.array([c * x - s * y, s * x + c * y, 0])


def orbit_curve(a, e, center=ORIGIN, tilt=0.0, color=INK, stroke_width=1.5, opacity=0.5, n=240):
    """Closed ellipse (focus at `center`) as a thin VMobject, for drawing an orbit.
    Sampled densely in eccentric anomaly and joined as corners: smoothing overshoots on thin (e→1) ellipses."""
    E = np.linspace(0, 2 * np.pi, n)
    th = 2 * np.arctan2(np.sqrt(1 + e) * np.sin(E / 2), np.sqrt(1 - e) * np.cos(E / 2))
    pts = [conic_point(a, e, t, center, tilt) for t in th]
    m = VMobject(stroke_color=color, stroke_width=stroke_width, stroke_opacity=opacity)
    m.set_points_as_corners(pts + [pts[0]])
    return m


# ---- Roche geometry (appended; used by iso-smt / iso-che) ------------------------------------
def roche_lobe_points(m1, m2, sep, which=1, n=180):
    """Outline (n×3 array, closed) of the Roche lobe of star `which` (1 or 2) for masses m1, m2
    separated by `sep`, in a frame where star 1 sits at the origin and star 2 at (sep, 0).
    The lobe is the equipotential through L1 of the rotating-frame Roche potential."""
    M = m1 + m2
    xcm = sep * m2 / M
    def phi(x, y):
        r1 = np.hypot(x, y); r2 = np.hypot(x - sep, y)
        return -m1 / np.maximum(r1, 1e-6) - m2 / np.maximum(r2, 1e-6) - 0.5 * (M / sep ** 3) * ((x - xcm) ** 2 + y ** 2)
    xs = np.linspace(0.02 * sep, 0.98 * sep, 4000)
    xl1 = xs[np.argmax(phi(xs, 0 * xs))]
    phil1 = phi(xl1, 0.0)
    x0, sgn = (0.0, 1.0) if which == 1 else (sep, -1.0)
    th = np.linspace(0, 2 * np.pi, n, endpoint=False)
    rs = np.linspace(0.005 * sep, 1.2 * abs(xl1 - x0), 600)
    R, T = np.meshgrid(rs, th)
    f = phi(x0 + sgn * R * np.cos(T), R * np.sin(T)) - phil1
    hit = f >= 0
    idx = np.where(hit.any(axis=1), hit.argmax(axis=1), f.argmax(axis=1))
    r_lobe = rs[idx]
    pts = np.stack([x0 + sgn * r_lobe * np.cos(th), r_lobe * np.sin(th), 0 * th], axis=1)
    return pts, np.array([xl1, 0, 0])


def roche_lobes(m1, m2, sep, center=ORIGIN, color=INK, stroke_width=1.2, opacity=0.35):
    """Both Roche lobes (figure-of-eight) as a VGroup; star 1 at center, star 2 at center + sep·RIGHT.
    Returns (VGroup(lobe1, lobe2), L1 point)."""
    lobes = VGroup()
    for w in (1, 2):
        pts, l1 = roche_lobe_points(m1, m2, sep, w)
        v = VMobject(stroke_color=color, stroke_width=stroke_width, stroke_opacity=opacity)
        v.set_points_smoothly([center + p for p in pts] + [center + pts[0]])
        lobes.add(v)
    return lobes, center + l1


# ---- generic orbital helpers (appended; used by the ZKL / AGN scenes) ---------------------
def kepler_nu(M, e):
    """True anomaly for mean anomaly M (rad) and eccentricity e (Newton on Kepler's equation)."""
    M = np.mod(M, 2 * np.pi)
    E = M if e < 0.8 else np.pi
    for _ in range(15):
        E -= (E - e * np.sin(E) - M) / (1 - e * np.cos(E))
    return 2 * np.arctan2(np.sqrt(1 + e) * np.sin(E / 2), np.sqrt(1 - e) * np.cos(E / 2))


def rot2(p, ang):
    """Rotate an (x, y, 0) point about the z-axis."""
    c, s = np.cos(ang), np.sin(ang)
    return np.array([c * p[0] - s * p[1], s * p[0] + c * p[1], 0])


def project(p, incl=0.0, node=0.0):
    """Project an in-plane point onto the sky: tilt the plane by `incl` about the x-axis (foreshortens y),
    then rotate the line of nodes by `node`."""
    return rot2(np.array([p[0], p[1] * np.cos(incl), 0]), node)


def gw_rings_follow(scene, pos=ORIGIN, n=3, rmax=1.2, run_time=0.9, follow=None, stroke_width=2.5):
    """Like ChannelScene.gw_burst, but returns (rings, animation) so the burst can be composed into a
    longer self.play (e.g. Succession(Wait(t0), anim, Wait(rest))). If `follow` is a callable returning
    a point, the rings track it while expanding."""
    rings = VGroup(*[Circle(radius=0.05, color=scene.accent, stroke_width=stroke_width, stroke_opacity=0.9).move_to(pos) for _ in range(n)])
    if follow is not None:
        for ring in rings:
            ring.add_updater(lambda m: m.move_to(follow()))
    scene.add(rings)
    anim = LaggedStart(*[ring.animate(rate_func=linear).scale(rmax / 0.05).set_stroke(opacity=0) for ring in rings],
                       lag_ratio=0.25, run_time=run_time)
    return rings, anim


def at_time(anim, start, total):
    """Schedule `anim` (which must have an explicit run_time) to begin `start` seconds into a play of
    length `total`."""
    rest = max(total - start - anim.run_time, 0)
    parts = ([Wait(start)] if start > 0 else []) + [anim] + ([Wait(rest)] if rest > 0 else [])
    return Succession(*parts)


def gw_rings(pos, color, n=3, rmax=1.2, keep_opacity=0.0):
    """Like ChannelScene.gw_burst but non-blocking: returns (rings, animation) so the burst can be played
    together with other animations. Rings fade to `keep_opacity` (0 → remove them afterwards)."""
    rings = VGroup(*[Circle(radius=0.05, color=color, stroke_width=2.5, stroke_opacity=0.9).move_to(pos) for _ in range(n)])
    anim = LaggedStart(*[r.animate(rate_func=linear).scale(rmax / 0.05).set_stroke(opacity=keep_opacity) for r in rings], lag_ratio=0.25)
    return rings, anim


# ---- time-warp helpers (appended; generalised from scene_cluster_capture, used by single-capture v4) ----
def dwell_rate(cost):
    """rate_func that spends animation time ∝ `cost` (array sampled uniformly over the parameter's range):
    where cost is high the parameter advances slowly. Returns (rate_func, mean cost) so the caller can scale
    run_time by the mean to keep the pace of the cost≈1 stretches unchanged."""
    u = np.linspace(0, 1, len(cost))
    tau = np.concatenate([[0], np.cumsum(0.5 * (cost[1:] + cost[:-1]) * np.diff(u))])
    mean = tau[-1]
    tau = tau / mean
    return (lambda t: float(np.interp(t, tau, u))), mean


def dwell_time(cost, u):
    """Real-time fraction (0..1) at which a dwell_rate(cost) animation reaches parameter value u (0..1)."""
    uu = np.linspace(0, 1, len(cost))
    tau = np.concatenate([[0], np.cumsum(0.5 * (cost[1:] + cost[:-1]) * np.diff(uu))])
    return float(np.interp(u, uu, tau / tau[-1]))


def peri_dwell(M0, M1, k=3.0, sigma=0.35):
    """Cost over mean anomaly [M0, M1]: 1 far from pericentre, 1+k at M ≡ 0 (mod 2π), Gaussian width sigma."""
    M = np.linspace(M0, M1, 2000)
    d = np.abs((M + np.pi) % (2 * np.pi) - np.pi)
    return 1 + k * np.exp(-(d / sigma) ** 2)


def speed_dwell(pts, base, v_cap, p=4.0):
    """Cost (seconds per unit parameter) that caps the on-screen speed of a point track `pts` (n×3, sampled
    uniformly over the parameter in [0, 1]) at `v_cap` units/s. `base` (scalar or array) is the seconds per unit
    parameter at the unwarped pace; wherever the track would move faster than v_cap the clock is slowed (smooth
    soft-max with exponent p) so fast passages (pericentres) linger while the slow stretches keep their pace."""
    pts = np.asarray(pts, dtype=float)
    n = len(pts)
    du = 1.0 / (n - 1)
    v_u = np.linalg.norm(np.gradient(pts, du, axis=0), axis=1)      # units per unit parameter
    base = np.broadcast_to(np.asarray(base, dtype=float), (n,))
    v = v_u / base                                                  # units per real second at the base pace
    return base * (1 + (v / v_cap) ** p) ** (1 / p)
