"""cluster-incluster — hardening encounters, then an in-cluster eccentric merger (STORYBOARD.md).

Variant 1: wide view, three encounters with the orbit ellipses drawn live, then a fast shrink and merger as the next single approaches.
Variant 2: close-up on a bigger binary; two encounters with short fading trails, then the GW decay is drawn as a persistent track of nested shrinking loops with a burst at each pericentre.
Variant 3: bodies only (no ellipse) in a core+halo cluster; three quick encounters, pericentre bursts, merger, and the next single arrives too late — it swings past the remnant and leaves.
"""
import numpy as np
from manim import *
from style import *


class ClusterInCluster(ChannelScene):
    GROUP = 'dynamical'

    def construct(self):
        if VARIANT == 2:
            return self._v2()
        if VARIANT == 3:
            return self._v3()
        # 1. cluster core + hard binary at its centre
        cloud = self.dot_cloud(n=420, sigma=2.0, seed=3, radius=0.028, opacity=0.3)
        self.add(cloud)
        a, e, tilt, M = ValueTracker(2.5), ValueTracker(0.25), ValueTracker(0.4), ValueTracker(0.0)
        cx, cy = ValueTracker(0.0), ValueTracker(0.0)
        com = lambda: np.array([cx.get_value(), cy.get_value(), 0])

        def rel():
            th = true_anomaly(M.get_value(), e.get_value())
            return conic_point(a.get_value(), e.get_value(), th, ORIGIN, tilt.get_value())
        bh1, bh2 = self.bh(0.3), self.bh(0.3)
        bh1.add_updater(lambda m: m.move_to(com() + 0.5 * rel()))
        bh2.add_updater(lambda m: m.move_to(com() - 0.5 * rel()))
        orb1 = orbit_curve(1.25, 0.25, ORIGIN, 0.4, self.accent, opacity=0.6, stroke_width=2)
        orb2 = orbit_curve(1.25, 0.25, ORIGIN, 0.4 + np.pi, self.accent, opacity=0.6, stroke_width=2)
        orb1.add_updater(lambda m: m.become(orbit_curve(a.get_value() / 2, e.get_value(), com(), tilt.get_value(), self.accent, opacity=0.6, stroke_width=2)))
        orb2.add_updater(lambda m: m.become(orbit_curve(a.get_value() / 2, e.get_value(), com(), tilt.get_value() + np.pi, self.accent, opacity=0.6, stroke_width=2)))
        self.add(orb1, orb2, bh1, bh2)
        bh1.set_z_index(2); bh2.set_z_index(2)
        self.play(M.animate.increment_value(2 * np.pi), run_time=1.5, rate_func=linear)

        # 2. three binary–single encounters: each single is kicked out faster, the binary gets tighter
        #    (a↓), a new eccentricity and orientation, and a small recoil.
        encounters = [  # entry, exit (off-screen), new a, new e, new tilt, recoil (dx, dy)
            (np.array([-7.5, 3.6, 0]), np.array([7.6, -3.2, 0]), 2.0, 0.45, 1.6, (0.3, -0.2)),
            (np.array([7.5, 1.2, 0]), np.array([-4.5, 4.6, 0]), 1.6, 0.15, 2.6, (-0.4, 0.15)),
            (np.array([-1.5, -4.6, 0]), np.array([7.6, 3.2, 0]), 1.2, 0.6, 0.9, (0.25, 0.3)),
        ]
        for k, (p0, p3, a_new, e_new, tilt_new, (dx, dy)) in enumerate(encounters):
            single = self.bh(0.3, p0)
            trail = TracedPath(single[1].get_center, stroke_color=self.accent, stroke_width=2, stroke_opacity=0.5, dissipating_time=0.7)
            self.add(trail, single)
            c0 = com()
            path_in = CubicBezier(p0, 0.35 * p0 + 0.65 * c0 + np.array([0.6, -0.8, 0]) * (1 if k % 2 else -1), c0 + np.array([0.9, 0.5, 0]), c0 + np.array([0.9, -0.7, 0]))
            path_out = CubicBezier(path_in.get_end(), c0 + np.array([-0.8, -0.6, 0]), c0 + np.array([-0.6, 0.9, 0]), p3)
            self.play(MoveAlongPath(single, path_in), M.animate.increment_value(2 * np.pi), run_time=1.3, rate_func=linear)
            self.play(MoveAlongPath(single, path_out, rate_func=rush_into),
                      a.animate.set_value(a_new), e.animate.set_value(e_new), tilt.animate.set_value(tilt_new),
                      cx.animate.increment_value(dx), cy.animate.increment_value(dy),
                      M.animate.increment_value(2.5 * np.pi), run_time=1.0, rate_func=linear)
            self.remove(trail, single)

        # 3. tight and eccentric: GW emission shrinks and partly circularises the orbit *inside* the cluster,
        #    while the next single is still on its way in.
        nxt = self.bh(0.3, np.array([6.8, -3.6, 0]))
        self.add(nxt)
        self.play(a.animate.set_value(0.62), e.animate.set_value(0.3), M.animate.increment_value(14 * np.pi),
                  nxt.animate.move_to(np.array([3.6, -2.2, 0])), run_time=3.2, rate_func=linear)

        # 4. merger with the dot cloud still around it
        c_end = com()
        bh1.clear_updaters(); bh2.clear_updaters(); orb1.clear_updaters(); orb2.clear_updaters()
        remnant = self.bh(0.38, c_end)
        rings = VGroup(*[Circle(radius=0.05, color=self.accent, stroke_width=3, stroke_opacity=0.9).move_to(c_end) for _ in range(3)])
        self.remove(orb1, orb2)
        self.play(Transform(bh1, remnant), Transform(bh2, remnant), run_time=0.25)
        self.remove(bh2)
        self.play(LaggedStart(*[r.animate(rate_func=linear).scale(1.4 / 0.05 * (0.55 + 0.15 * i)).set_stroke(opacity=0.5) for i, r in enumerate(rings)], lag_ratio=0.25),
                  nxt.animate.move_to(np.array([3.3, -2.0, 0])), run_time=0.9, rate_func=linear)
        self.wait(0.2)

    # ---- variant 2: close-up, the GW decay drawn as a persistent track ------------------------------------------
    def _v2(self):
        cloud = self.dot_cloud(n=520, sigma=2.7, seed=4, radius=0.03, opacity=0.3)
        self.add(cloud)
        a, e, tilt, M = ValueTracker(3.4), ValueTracker(0.2), ValueTracker(0.3), ValueTracker(0.0)
        cx, cy = ValueTracker(-0.4), ValueTracker(0.2)
        com = lambda: np.array([cx.get_value(), cy.get_value(), 0])

        def rel():
            th = true_anomaly(M.get_value(), e.get_value())
            return conic_point(a.get_value(), e.get_value(), th, ORIGIN, tilt.get_value())
        bh1, bh2 = self.bh(0.34), self.bh(0.34)
        bh1.add_updater(lambda m: m.move_to(com() + 0.5 * rel()))
        bh2.add_updater(lambda m: m.move_to(com() - 0.5 * rel()))
        bh1.set_z_index(2); bh2.set_z_index(2)
        trails = [TracedPath(b[1].get_center, stroke_color=self.accent, stroke_width=2, stroke_opacity=0.45, dissipating_time=0.8) for b in (bh1, bh2)]
        self.add(*trails, bh1, bh2)
        self.play(M.animate.increment_value(2 * np.pi), run_time=1.6, rate_func=linear)

        # two hardening encounters (bodies with short fading trails, no ellipse yet)
        encounters = [
            (np.array([7.6, 3.4, 0]), np.array([-7.6, -3.2, 0]), 2.4, 0.5, 1.5, (0.4, -0.3)),
            (np.array([-7.6, -2.2, 0]), np.array([4.5, 4.6, 0]), 1.7, 0.7, 2.5, (-0.3, 0.3)),
        ]
        for k, (p0, p3, a_new, e_new, tilt_new, (dx, dy)) in enumerate(encounters):
            single = self.bh(0.34, p0)
            trail = TracedPath(single[1].get_center, stroke_color=self.accent, stroke_width=2, stroke_opacity=0.5, dissipating_time=0.7)
            self.add(trail, single)
            c0 = com()
            path_in = CubicBezier(p0, 0.35 * p0 + 0.65 * c0 + np.array([0.6, -0.8, 0]) * (1 if k % 2 else -1), c0 + np.array([1.1, 0.6, 0]), c0 + np.array([1.1, -0.8, 0]))
            path_out = CubicBezier(path_in.get_end(), c0 + np.array([-1.0, -0.7, 0]), c0 + np.array([-0.7, 1.1, 0]), p3)
            self.play(MoveAlongPath(single, path_in), M.animate.increment_value(2 * np.pi), run_time=1.2, rate_func=linear)
            self.play(MoveAlongPath(single, path_out, rate_func=rush_into),
                      a.animate.set_value(a_new), e.animate.set_value(e_new), tilt.animate.set_value(tilt_new),
                      cx.animate.increment_value(dx), cy.animate.increment_value(dy),
                      M.animate.increment_value(2.5 * np.pi), run_time=0.9, rate_func=linear)
            self.remove(trail, single)
        self.remove(*trails)

        # tight and eccentric: each pericentre burst shrinks and rounds the orbit; the persistent track records the nested loops
        tracks = [TracedPath(b[1].get_center, stroke_color=self.accent, stroke_width=2.2, stroke_opacity=0.55) for b in (bh1, bh2)]
        self.add(*tracks)
        nxt = self.bh(0.34, np.array([7.0, -3.6, 0]))
        self.add(nxt)
        m_next = 2 * np.pi * np.ceil(M.get_value() / (2 * np.pi) + 1e-9)
        for k, (a_new, e_new, rt) in enumerate([(1.25, 0.6, 1.6), (0.9, 0.48, 1.2), (0.62, 0.38, 0.9)]):
            self.play(M.animate.set_value(m_next + 2 * np.pi * (k + 1)), a.animate.set_value(a_new), e.animate.set_value(e_new),
                      nxt.animate.shift(np.array([-0.9, 0.4, 0])), run_time=rt, rate_func=linear)
            if k < 2:
                rings, burst = gw_rings(com(), self.accent, rmax=1.0)
                self.add(rings)
                self.play(burst, M.animate(rate_func=linear).increment_value(0.35 * np.pi), nxt.animate(rate_func=linear).shift(np.array([-0.25, 0.1, 0])), run_time=0.4)
                self.remove(rings)

        # merger with the dot cloud still around it and the next single still on its way
        c_end = com()
        for m in (bh1, bh2, *tracks):
            m.clear_updaters()
        for t in tracks:
            t.set_stroke(opacity=0.45)
        remnant = self.bh(0.42, c_end)
        rings = VGroup(*[Circle(radius=0.05, color=self.accent, stroke_width=3, stroke_opacity=0.9).move_to(c_end) for _ in range(3)])
        self.play(Transform(bh1, remnant), Transform(bh2, remnant), run_time=0.25)
        self.remove(bh2)
        self.play(LaggedStart(*[r.animate(rate_func=linear).scale(1.5 / 0.05 * (0.55 + 0.15 * i)).set_stroke(opacity=0.5) for i, r in enumerate(rings)], lag_ratio=0.25),
                  nxt.animate.shift(np.array([-0.3, 0.15, 0])), run_time=0.9, rate_func=linear)
        self.wait(0.3)

    # ---- variant 3: the race — bodies only, pericentre bursts, the next single arrives too late --------------------
    def _v3(self):
        core = self.dot_cloud(n=340, sigma=1.1, center=ORIGIN, seed=6, radius=0.03, opacity=0.42)
        halo = self.dot_cloud(n=300, sigma=2.8, center=ORIGIN, seed=9, radius=0.025, opacity=0.2)
        self.add(halo, core)
        a, e, tilt, M = ValueTracker(2.0), ValueTracker(0.25), ValueTracker(0.6), ValueTracker(0.0)
        cx, cy = ValueTracker(0.6), ValueTracker(0.3)
        com = lambda: np.array([cx.get_value(), cy.get_value(), 0])

        def rel():
            th = true_anomaly(M.get_value(), e.get_value())
            return conic_point(a.get_value(), e.get_value(), th, ORIGIN, tilt.get_value())
        bh1, bh2 = self.bh(0.3), self.bh(0.3)
        bh1.add_updater(lambda m: m.move_to(com() + 0.5 * rel()))
        bh2.add_updater(lambda m: m.move_to(com() - 0.5 * rel()))
        bh1.set_z_index(2); bh2.set_z_index(2)
        trails = [TracedPath(b[1].get_center, stroke_color=self.accent, stroke_width=1.8, stroke_opacity=0.45, dissipating_time=1.6) for b in (bh1, bh2)]
        self.add(*trails, bh1, bh2)
        self.play(M.animate.increment_value(2 * np.pi), run_time=1.2, rate_func=linear)

        # three quick hardening encounters, each single leaving faster than it came
        encounters = [
            (np.array([-7.5, 3.0, 0]), np.array([7.6, -3.6, 0]), 1.5, 0.45, 1.5, (0.3, -0.25), 1.0, 0.8),
            (np.array([7.5, -1.5, 0]), np.array([-5.0, 4.6, 0]), 1.15, 0.25, 2.6, (-0.35, 0.2), 0.9, 0.7),
            (np.array([-2.5, -4.6, 0]), np.array([7.6, 2.8, 0]), 0.9, 0.62, 0.9, (0.25, 0.25), 0.8, 0.55),
        ]
        for k, (p0, p3, a_new, e_new, tilt_new, (dx, dy), t_in, t_out) in enumerate(encounters):
            single = self.bh(0.3, p0)
            trail = TracedPath(single[1].get_center, stroke_color=self.accent, stroke_width=2, stroke_opacity=0.5, dissipating_time=0.7)
            self.add(trail, single)
            c0 = com()
            path_in = CubicBezier(p0, 0.35 * p0 + 0.65 * c0 + np.array([0.6, -0.8, 0]) * (1 if k % 2 else -1), c0 + np.array([0.9, 0.5, 0]), c0 + np.array([0.9, -0.7, 0]))
            path_out = CubicBezier(path_in.get_end(), c0 + np.array([-0.8, -0.6, 0]), c0 + np.array([-0.6, 0.9, 0]), p3)
            self.play(MoveAlongPath(single, path_in), M.animate.increment_value(2 * np.pi), run_time=t_in, rate_func=linear)
            self.play(MoveAlongPath(single, path_out, rate_func=rush_into),
                      a.animate.set_value(a_new), e.animate.set_value(e_new), tilt.animate.set_value(tilt_new),
                      cx.animate.increment_value(dx), cy.animate.increment_value(dy),
                      M.animate.increment_value(2.5 * np.pi), run_time=t_out, rate_func=linear)
            self.remove(trail, single)

        # the next single sets off from the far side of the core — but the binary is already radiating at every pericentre
        p_start, p_aim = np.array([-6.6, 3.6, 0]), com()
        nxt_at = lambda f: p_start + f * (p_aim - p_start)
        nxt = self.bh(0.3, p_start)
        nxt_trail = TracedPath(nxt[1].get_center, stroke_color=self.accent, stroke_width=2, stroke_opacity=0.5, dissipating_time=1.2)
        self.add(nxt_trail, nxt)
        m_next = 2 * np.pi * np.ceil(M.get_value() / (2 * np.pi) + 1e-9)
        fr = iter([0.18, 0.25, 0.36, 0.43, 0.55])
        for k, (a_new, e_new, rt) in enumerate([(0.7, 0.5, 1.1), (0.55, 0.4, 0.8), (0.42, 0.32, 0.6)]):
            self.play(M.animate.set_value(m_next + 2 * np.pi * (k + 1)), a.animate.set_value(a_new), e.animate.set_value(e_new),
                      nxt.animate.move_to(nxt_at(next(fr))), run_time=rt, rate_func=linear)
            if k < 2:
                rings, burst = gw_rings(com(), self.accent, rmax=0.9)
                self.add(rings)
                self.play(burst, M.animate(rate_func=linear).increment_value(0.35 * np.pi), nxt.animate(rate_func=linear).move_to(nxt_at(next(fr))), run_time=0.4)
                self.remove(rings)

        # merger before it gets there
        c_end = com()
        bh1.clear_updaters(); bh2.clear_updaters()
        self.remove(*trails)
        remnant = self.bh(0.38, c_end)
        rings = VGroup(*[Circle(radius=0.05, color=self.accent, stroke_width=3, stroke_opacity=0.9).move_to(c_end) for _ in range(3)])
        self.play(Transform(bh1, remnant), Transform(bh2, remnant), run_time=0.25)
        self.remove(bh2)
        self.play(LaggedStart(*[r.animate(rate_func=linear).scale(1.4 / 0.05 * (0.55 + 0.15 * i)).set_stroke(opacity=0.5) for i, r in enumerate(rings)], lag_ratio=0.25),
                  nxt.animate.move_to(nxt_at(0.62)), run_time=0.9, rate_func=linear)
        # too late: the single only swings past the remnant and leaves
        p = nxt[1].get_center()
        flyby = CubicBezier(p, c_end + 0.35 * (p - c_end) + np.array([0, -0.3, 0]), c_end + np.array([1.0, -1.0, 0]), np.array([7.6, 3.4, 0]))
        self.play(MoveAlongPath(nxt, flyby), run_time=1.2, rate_func=lambda u: u ** 1.4)
        self.wait(0.3)
