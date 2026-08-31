"""cluster-capture — resonant binary–single encounter, GW capture at a close pass (STORYBOARD.md).

The tangled phase is a real (softened, equal-mass) three-body integration with a fixed seed; at a chosen
close pair passage the animation cuts over to a scripted e≈1 inspiral and the third body is flung out.

Variant 1: wide view, binary–single; fading trails, then ellipses drawn for the captured pair.
Variant 2: close-up on the resonant tangle (larger bodies, sparser cloud) whose full path record stays drawn under the captured pair's shrinking ellipse.
Variant 3: binary–binary encounter (4-body integration): the two binaries exchange partners in the tangle, one cross-pair is GW-captured and the two leftovers fly off.
"""
import numpy as np
from manim import *
from style import *

SEED, T_CUT, DT, SCALE = 44, 16.87, 0.002, 1.4       # seed/cut found offline: pair (0,1) at d=0.15, third at 2.6
SEED4, T_CUT4, PAIR4 = 1, 8.65, (1, 2)               # variant 3 (binary–binary): cross pair (1,2) at d=0.15, others at >2.5


def three_body(seed=SEED, T=T_CUT + 0.1, dt=DT, soft=0.05):
    """Binary (a=1, circular) at the origin + single from the left; returns positions X[t, body, xy]."""
    rng = np.random.default_rng(seed)
    x, v = np.zeros((3, 2)), np.zeros((3, 2))
    ph = rng.uniform(0, 2 * np.pi)
    vc = np.sqrt(2.0) / 2
    x[0] = [0.5 * np.cos(ph), 0.5 * np.sin(ph)]; x[1] = -x[0]
    v[0] = vc * np.array([-np.sin(ph), np.cos(ph)]); v[1] = -v[0]
    b, vinf = rng.uniform(-1.2, 1.2), rng.uniform(0.2, 0.5)
    x[2] = [-6, b]; v[2] = [vinf, 0]
    v -= v.mean(0); x -= x.mean(0)
    def acc(x):
        d = x[None, :, :] - x[:, None, :]
        r2 = (d ** 2).sum(-1) + soft ** 2
        np.fill_diagonal(r2, np.inf)
        return (d / r2[..., None] ** 1.5).sum(1)
    n = int(T / dt); X = np.zeros((n, 3, 2)); A = acc(x)
    for k in range(n):
        v += 0.5 * dt * A; x += dt * v; A = acc(x); v += 0.5 * dt * A; X[k] = x
    return X


def four_body(seed=SEED4, T=T_CUT4 + 0.1, dt=DT, soft=0.05):
    """Two binaries (a=1, circular) at x=∓4 drifting towards each other; returns positions X[t, body, xy] (variant 3)."""
    rng = np.random.default_rng(seed)
    x, v = np.zeros((4, 2)), np.zeros((4, 2))
    for k, (cx, cy, vx) in enumerate([(-4, 0, 0.35), (4, 0, -0.35)]):
        ph = rng.uniform(0, 2 * np.pi); vc = np.sqrt(2.0) / 2; b = rng.uniform(-1, 1)
        x[2 * k] = [cx + 0.5 * np.cos(ph), cy + b + 0.5 * np.sin(ph)]; x[2 * k + 1] = [cx - 0.5 * np.cos(ph), cy + b - 0.5 * np.sin(ph)]
        v[2 * k] = [vx - vc * np.sin(ph), vc * np.cos(ph)]; v[2 * k + 1] = [vx + vc * np.sin(ph), -vc * np.cos(ph)]
    v -= v.mean(0); x -= x.mean(0)
    def acc(x):
        d = x[None, :, :] - x[:, None, :]
        r2 = (d ** 2).sum(-1) + soft ** 2
        np.fill_diagonal(r2, np.inf)
        return (d / r2[..., None] ** 1.5).sum(1)
    n = int(T / dt); X = np.zeros((n, 4, 2)); A = acc(x)
    for k in range(n):
        v += 0.5 * dt * A; x += dt * v; A = acc(x); v += 0.5 * dt * A; X[k] = x
    return X


def dwell_rate(cost):
    """rate_func that spends animation time ∝ `cost` (array sampled uniformly over the parameter's range):
    where cost is high the parameter advances slowly. Returns (rate_func, mean cost) so the caller can scale
    run_time by the mean to keep the pace of the cost≈1 stretches unchanged."""
    u = np.linspace(0, 1, len(cost))
    tau = np.concatenate([[0], np.cumsum(0.5 * (cost[1:] + cost[:-1]) * np.diff(u))])
    mean = tau[-1]
    tau = tau / mean
    return (lambda t: float(np.interp(t, tau, u))), mean


def peri_dwell(M0, M1, k=3.0, sigma=0.35):
    """Cost over mean anomaly [M0, M1]: 1 far from pericentre, 1+k at M ≡ 0 (mod 2π), Gaussian width sigma."""
    M = np.linspace(M0, M1, 2000)
    d = np.abs((M + np.pi) % (2 * np.pi) - np.pi)
    return 1 + k * np.exp(-(d / sigma) ** 2)


class ClusterCapture(ChannelScene):
    GROUP = 'dynamical'

    def construct(self):
        if VARIANT == 2:
            return self._v2()
        if VARIANT == 3:
            return self._v3()
        X = three_body()
        tt = np.arange(len(X)) * DT
        origin = -SCALE * np.append(0.5 * (X[0, 0] + X[0, 1]), 0)    # put the initial binary near the frame centre
        def pos(i, t):
            return origin + SCALE * np.array([np.interp(t, tt, X[:, i, 0]), np.interp(t, tt, X[:, i, 1]), 0])

        cloud = self.dot_cloud(n=420, sigma=2.0, seed=5, center=origin + np.array([0.3, 0.2, 0]), radius=0.028, opacity=0.3)
        self.add(cloud)
        ts = ValueTracker(0.0)
        bodies = [self.bh(0.3, pos(i, 0)) for i in range(3)]
        for i, b in enumerate(bodies):
            b.add_updater(lambda m, i=i: m.move_to(pos(i, ts.get_value())))
            b.set_z_index(2)
        trails = [TracedPath(b[1].get_center, stroke_color=self.accent, stroke_width=2, stroke_opacity=0.5, dissipating_time=3.0) for b in bodies]
        self.add(*trails, *bodies)
        # 1. the single flies in, 2. resonant encounter: partners swap chaotically
        self.play(ts.animate.set_value(5.0), run_time=1.5, rate_func=linear)
        self.play(ts.animate.set_value(T_CUT), run_time=5.0, rate_func=linear)
        for b in bodies:
            b.clear_updaters()
        self.remove(trails[0], trails[1])
        p0, p1, p2 = pos(0, T_CUT), pos(1, T_CUT), pos(2, T_CUT)
        v2 = (pos(2, T_CUT) - pos(2, T_CUT - 0.3)); v2 /= np.linalg.norm(v2)
        vpair = 0.5 * ((pos(0, T_CUT) + pos(1, T_CUT)) - (pos(0, T_CUT - 0.5) + pos(1, T_CUT - 0.5)))
        # 3. GW burst at the close pass binds bodies 0 and 1 on the spot; body 2 is flung away
        c = 0.5 * (p0 + p1)
        sep = p0 - p1
        tilt = np.arctan2(sep[1], sep[0])
        rel_v = (pos(0, T_CUT) - pos(0, T_CUT - 0.05)) - (pos(1, T_CUT) - pos(1, T_CUT - 0.05))
        sgn = np.sign(np.cross(sep[:2], rel_v[:2])) or 1.0
        a, e, M = ValueTracker(2.4), ValueTracker(0.92), ValueTracker(0.0)
        cx, cy = ValueTracker(c[0]), ValueTracker(c[1])
        com = lambda: np.array([cx.get_value(), cy.get_value(), 0])
        def rel():
            th = true_anomaly(M.get_value(), e.get_value())
            return conic_point(a.get_value(), e.get_value(), sgn * th, ORIGIN, tilt)
        bodies[0].add_updater(lambda m: m.move_to(com() + 0.5 * rel()))
        bodies[1].add_updater(lambda m: m.move_to(com() - 0.5 * rel()))
        def ell(k):   # each body's own ellipse (a/2, focus at the COM); symmetric about the apsidal line, so `sgn` is irrelevant
            return orbit_curve(a.get_value() / 2, e.get_value(), com(), tilt + (0 if k == 0 else np.pi), self.accent, stroke_width=2, opacity=0.55)
        orb = [ell(0), ell(1)]
        for k, o in enumerate(orb):
            o.add_updater(lambda m, k=k: m.become(ell(k)))
        rings, burst = gw_rings(c, self.accent, rmax=1.3)
        far = p2 + v2 * 12
        self.add(rings)
        self.play(burst, FadeIn(orb[0]), FadeIn(orb[1]), bodies[2].animate(rate_func=rush_into).move_to(far),
                  M.animate(rate_func=linear).set_value(0.6 * np.pi), run_time=1.2)
        self.remove(rings)
        # 4. e≈1 orbit shrinks over a few pericentre passages, a burst at each
        drift = 0.6 * vpair
        for k, (a_new, e_new, rt) in enumerate([(1.6, 0.87, 1.9), (1.1, 0.8, 1.4), (0.9, 0.72, 1.0)]):
            self.play(M.animate.increment_value(2 * np.pi - (0.6 if k == 0 else 0.5) * np.pi), a.animate.set_value(a_new), e.animate.set_value(e_new),
                      cx.animate.increment_value(drift[0]), cy.animate.increment_value(drift[1]), run_time=rt, rate_func=linear)
            if k < 2:
                rings, burst = gw_rings(com(), self.accent, rmax=1.0)
                self.add(rings)
                self.play(burst, M.animate(rate_func=linear).increment_value(0.5 * np.pi), run_time=0.5)
                self.remove(rings)
        # 5. merger; the last thin ellipse stays faint for the card face
        c_end = com()
        for m in bodies[:2] + orb:
            m.clear_updaters()
        for o in orb:
            o.set_stroke(opacity=0.45)
        remnant = self.bh(0.38, c_end)
        rings = VGroup(*[Circle(radius=0.05, color=self.accent, stroke_width=3, stroke_opacity=0.9).move_to(c_end) for _ in range(3)])
        self.play(Transform(bodies[0], remnant), Transform(bodies[1], remnant), run_time=0.25)
        self.remove(bodies[1])
        self.play(LaggedStart(*[r.animate(rate_func=linear).scale(1.4 / 0.05 * (0.55 + 0.15 * i)).set_stroke(opacity=0.5) for i, r in enumerate(rings)], lag_ratio=0.25), run_time=0.9)
        self.wait(0.2)

    # ---- shared second half for variants 2–3 (mirrors variant 1's scripted capture + inspiral) -----------------
    def _bind_and_inspiral(self, bodies, pos, tcut, pair, others, size=0.38, rmax=1.3, drift_scale=0.6, dwell=0.0, stretch=1.0):
        """GW burst at t=tcut binds `pair` on an e≈1 orbit that shrinks over a few pericentre passages; `others` are
        flung out along their current velocities; ends on the merger with the last thin ellipse kept faint.
        dwell>0 slows the pair's motion near each pericentre (cost 1+dwell there, run_times scaled to keep the
        apocentre pace); stretch multiplies every orbital run_time on top of that."""
        i, j = pair
        p_i, p_j = pos(i, tcut), pos(j, tcut)
        c = 0.5 * (p_i + p_j)
        sep = p_i - p_j
        tilt = np.arctan2(sep[1], sep[0])
        rel_v = (pos(i, tcut) - pos(i, tcut - 0.05)) - (pos(j, tcut) - pos(j, tcut - 0.05))
        sgn = np.sign(np.cross(sep[:2], rel_v[:2])) or 1.0
        vpair = 0.5 * ((pos(i, tcut) + pos(j, tcut)) - (pos(i, tcut - 0.5) + pos(j, tcut - 0.5)))
        a, e, M = ValueTracker(2.4), ValueTracker(0.92), ValueTracker(0.0)
        cx, cy = ValueTracker(c[0]), ValueTracker(c[1])
        com = lambda: np.array([cx.get_value(), cy.get_value(), 0])
        def rel():
            th = true_anomaly(M.get_value(), e.get_value())
            return conic_point(a.get_value(), e.get_value(), sgn * th, ORIGIN, tilt)
        bodies[i].add_updater(lambda m: m.move_to(com() + 0.5 * rel()))
        bodies[j].add_updater(lambda m: m.move_to(com() - 0.5 * rel()))
        def ell(k):
            return orbit_curve(a.get_value() / 2, e.get_value(), com(), tilt + (0 if k == 0 else np.pi), self.accent, stroke_width=2, opacity=0.55)
        orb = [ell(0), ell(1)]
        for k, o in enumerate(orb):
            o.add_updater(lambda m, k=k: m.become(ell(k)))
        rings, burst = gw_rings(c, self.accent, rmax=rmax)
        flings = []
        for k in others:
            v = pos(k, tcut) - pos(k, tcut - 0.3); v /= np.linalg.norm(v)
            flings.append(bodies[k].animate(rate_func=rush_into).move_to(pos(k, tcut) + v * 12))
        def m_rate(M0, M1, rt):
            """(rate_func, run_time) for advancing M from M0 to M1 with the pericentre dwell applied."""
            if dwell <= 0:
                return linear, rt
            rf, mean = dwell_rate(peri_dwell(M0, M1, k=dwell))
            return rf, rt * mean * stretch
        rf, rt = m_rate(0.0, 0.6 * np.pi, 1.2)
        self.add(rings)
        self.play(burst, FadeIn(orb[0]), FadeIn(orb[1]), *flings, M.animate(rate_func=rf).set_value(0.6 * np.pi), run_time=rt)
        self.remove(rings)
        drift = drift_scale * vpair
        for k, (a_new, e_new, rt) in enumerate([(1.6, 0.87, 1.9), (1.1, 0.8, 1.4), (0.9, 0.72, 1.0)]):
            dM = 2 * np.pi - (0.6 if k == 0 else 0.5) * np.pi
            rf, rt = m_rate(M.get_value(), M.get_value() + dM, rt)
            self.play(M.animate(rate_func=rf).increment_value(dM), a.animate.set_value(a_new), e.animate.set_value(e_new),
                      cx.animate.increment_value(drift[0]), cy.animate.increment_value(drift[1]), run_time=rt, rate_func=linear)
            if k < 2:
                rings, burst = gw_rings(com(), self.accent, rmax=1.0)
                rf, rt = m_rate(M.get_value(), M.get_value() + 0.5 * np.pi, 0.5)
                self.add(rings)
                self.play(burst, M.animate(rate_func=rf).increment_value(0.5 * np.pi), run_time=rt)
                self.remove(rings)
        c_end = com()
        for m in (bodies[i], bodies[j], *orb):
            m.clear_updaters()
        for o in orb:
            o.set_stroke(opacity=0.45)
        remnant = self.bh(size, c_end)
        rings = VGroup(*[Circle(radius=0.05, color=self.accent, stroke_width=3, stroke_opacity=0.9).move_to(c_end) for _ in range(3)])
        self.play(Transform(bodies[i], remnant), Transform(bodies[j], remnant), run_time=0.25)
        self.remove(bodies[j])
        self.play(LaggedStart(*[r.animate(rate_func=linear).scale(1.4 / 0.05 * (0.55 + 0.15 * k)).set_stroke(opacity=0.5) for k, r in enumerate(rings)], lag_ratio=0.25), run_time=0.9)
        self.wait(0.2)

    # ---- variant 2: close-up on the tangle, whose record stays drawn ----------------------------------------------
    def _v2(self):
        S = 1.5
        X = three_body()
        tt = np.arange(len(X)) * DT
        c0 = np.append(0.5 * (X[0, 0] + X[0, 1]), 0)
        origin = -S * (c0 + np.array([-2.1, 0.4, 0]))         # frame centred on the region the resonant tangle sweeps
        def pos(i, t):
            return origin + S * np.array([np.interp(t, tt, X[:, i, 0]), np.interp(t, tt, X[:, i, 1]), 0])
        cloud = self.dot_cloud(n=240, sigma=2.8, seed=5, center=np.array([0.2, 0.1, 0]), radius=0.04, opacity=0.28)
        self.add(cloud)
        t0 = 3.5
        ts = ValueTracker(t0)
        bodies = [self.bh(0.34, pos(i, t0)) for i in range(3)]
        for i, b in enumerate(bodies):
            b.add_updater(lambda m, i=i: m.move_to(pos(i, ts.get_value())))
            b.set_z_index(2)
        trails = [TracedPath(b[1].get_center, stroke_color=self.accent, stroke_width=1.8, stroke_opacity=0.4) for b in bodies]   # persistent
        self.add(*trails, *bodies)
        # time warp: sim time advances at the old pace while the bodies are far apart, ~half as fast when the
        # closest pair is within ~0.7 (sim units), so the close passages of the tangle read clearly
        def close_cost(s0, s1, k=1.4, d0=0.7):
            st = np.linspace(s0, s1, 2000)
            P = np.stack([np.interp(st, tt, X[:, i, j]) for i in range(3) for j in range(2)], 1).reshape(-1, 3, 2)
            dmin = np.min([np.hypot(*(P[:, i] - P[:, j]).T) for i, j in ((0, 1), (0, 2), (1, 2))], axis=0)
            return 1 + k * np.exp(-(dmin / d0) ** 2)
        for s0, s1, rt in ((t0, 5.0, 0.8), (5.0, T_CUT, 4.6)):
            rf, mean = dwell_rate(close_cost(s0, s1))
            self.play(ts.animate(rate_func=rf).set_value(s1), run_time=rt * mean)
        for b in bodies:
            b.clear_updaters()
        for t in trails:                    # the tangle's record stays, faded, under the new orbit
            t.clear_updaters(); t.set_stroke(opacity=0.18)
        self._bind_and_inspiral(bodies, pos, T_CUT, (0, 1), [2], size=0.42, rmax=1.5, dwell=4.0, stretch=1.0)

    # ---- variant 3: binary–binary encounter (4-body integration), exchange + capture ---------------------------
    def _v3(self):
        S = 1.4
        X = four_body()
        tt = np.arange(len(X)) * DT
        origin = np.array([-0.8, 0.3, 0])
        def pos(i, t):
            return origin + S * np.array([np.interp(t, tt, X[:, i, 0]), np.interp(t, tt, X[:, i, 1]), 0])
        cloud = self.dot_cloud(n=420, sigma=2.2, seed=5, center=origin + np.array([0.2, 0.2, 0]), radius=0.028, opacity=0.3)
        self.add(cloud)
        t0 = 2.5
        ts = ValueTracker(t0)
        bodies = [self.bh(0.3, pos(i, t0)) for i in range(4)]
        for i, b in enumerate(bodies):
            b.add_updater(lambda m, i=i: m.move_to(pos(i, ts.get_value())))
            b.set_z_index(2)
        trails = [TracedPath(b[1].get_center, stroke_color=self.accent, stroke_width=2, stroke_opacity=0.5, dissipating_time=3.0) for b in bodies]
        self.add(*trails, *bodies)
        # 1. two binaries approach, 2. resonant 4-body tangle
        self.play(ts.animate.set_value(5.8), run_time=1.6, rate_func=linear)
        self.play(ts.animate.set_value(T_CUT4), run_time=4.0, rate_func=linear)
        for b in bodies:
            b.clear_updaters()
        self.remove(*[trails[k] for k in PAIR4])
        # 3–5. one member of each binary is captured by the other's partner; the two leftovers fly off
        self._bind_and_inspiral(bodies, pos, T_CUT4, PAIR4, [k for k in range(4) if k not in PAIR4], drift_scale=0.25)
