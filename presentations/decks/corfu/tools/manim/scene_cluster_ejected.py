"""cluster-ejected — hardened by three-body encounters, ejected, circularised in the field (STORYBOARD.md).

Variant 1: wide view, cluster at left; the binary (orbit ellipse drawn live) is kicked out to the right and circularises.
Variant 2: close-up in the binary's own frame — the cluster slides past and recedes off-screen; no live ellipse, the light body's drawn track shows the orbit rounding.
Variant 3: wide view with the cluster's escape radius dashed; bodies-only binary hops outward with a recoil arrow per kick, its ellipse is only drawn once it is in the field.
"""
import numpy as np
from manim import *
from style import *


class ClusterEjected(ChannelScene):
    GROUP = 'dynamical'

    def construct(self):
        if VARIANT == 2:
            return self._v2()
        if VARIANT == 3:
            return self._v3()
        CL = np.array([-2.8, 0.0, 0.0])                        # cluster centre
        cloud = self.dot_cloud(n=380, sigma=1.3, center=CL, seed=3, radius=0.03, opacity=0.4)
        self.add(cloud)

        # ---- the hard binary: CM (cx, cy), semi-major a, eccentricity e, phase phi, orientation tilt ----
        cx, cy = ValueTracker(CL[0]), ValueTracker(CL[1])
        a, e, phi, tilt = ValueTracker(1.6), ValueTracker(0.3), ValueTracker(0.0), ValueTracker(0.4)
        cm = lambda: np.array([cx.get_value(), cy.get_value(), 0])
        rel = lambda th=None: self.ellipse_point(a.get_value(), e.get_value(), phi.get_value() if th is None else th, ORIGIN, tilt.get_value())
        heavy, light = self.bh(0.26, cm() - rel() / 4), self.bh(0.19, cm() + 3 * rel() / 4)
        heavy.add_updater(lambda m: m.move_to(cm() - rel() / 4)); light.add_updater(lambda m: m.move_to(cm() + 3 * rel() / 4))
        orbit = VMobject(stroke_color=self.accent, stroke_width=1.6, stroke_opacity=0.55)
        ths = np.linspace(0, 2 * np.pi, 90)
        orbit.add_updater(lambda m: m.set_points_smoothly([cm() + 3 * rel(th) / 4 for th in ths] + [cm() + 3 * rel(0) / 4]))
        heavy.set_z_index(2); light.set_z_index(2); orbit.set_z_index(1)
        self.add(orbit, heavy, light)
        self.play(phi.animate.increment_value(2 * np.pi), run_time=1.1, rate_func=linear)

        # ---- three-body encounters: each single leaves faster, the binary is left tighter and recoils ----
        def encounter(start, exit_pt, a_to, e_to, tilt_to, recoil, run_in=0.7, run_out=0.7):
            single = self.bh(0.2, start); single.set_z_index(2)
            trail = TracedPath(single[1].get_center, stroke_color=self.accent, stroke_width=2, stroke_opacity=0.6, dissipating_time=0.5)
            s = ValueTracker(0)
            c0 = cm()
            path = CubicBezier(start, c0 + (start - c0) * 0.25, c0 + 0.9 * (c0 - start) / np.linalg.norm(c0 - start) * 0.9, exit_pt)
            single.add_updater(lambda m: m.move_to(path.point_from_proportion(min(max(s.get_value(), 0), 1))))
            self.add(single, trail)
            self.play(s.animate.set_value(0.42), phi.animate.increment_value(1.5 * np.pi), run_time=run_in, rate_func=linear)
            # the exchange: binary hardens (Heggie), orbit re-oriented, CM kicked opposite to the escaping single
            self.play(s.animate.set_value(1.0), phi.animate.increment_value(2.5 * np.pi), a.animate.set_value(a_to), e.animate.set_value(e_to),
                      tilt.animate.set_value(tilt_to), cx.animate.increment_value(recoil[0]), cy.animate.increment_value(recoil[1]),
                      run_time=run_out, rate_func=lambda u: u ** 1.6)
            self.remove(single, trail)

        encounter(np.array([-6.6, 3.0, 0]), np.array([1.0, -4.5, 0]), 1.35, 0.5, 1.3, (0.35, 0.3))
        encounter(np.array([-6.7, -3.3, 0]), np.array([-1.5, 4.6, 0]), 1.15, 0.35, -0.6, (0.45, -0.35))
        # the last kick exceeds the escape speed: the binary trails out of the cluster
        ejected_trail = TracedPath(lambda: cm(), stroke_color=self.accent, stroke_width=2.5, stroke_opacity=0.35)
        self.add(ejected_trail)
        encounter(np.array([0.2, 4.4, 0]), np.array([-7.5, -1.0, 0]), 1.0, 0.55, 0.9, (1.4, 0.15), run_out=0.6)
        self.play(cx.animate.set_value(3.4), cy.animate.set_value(0.35), phi.animate.increment_value(4 * np.pi), run_time=1.9, rate_func=lambda u: 1 - (1 - u) ** 1.7)
        ejected_trail.clear_updaters()

        # ---- alone in the field for Gyr: GW emission at pericentre circularises and shrinks the orbit ----
        n = 3
        rings = VGroup(*[Circle(radius=0.05, color=self.accent, stroke_width=2.5, stroke_opacity=0.9).move_to(heavy[1].get_center()) for _ in range(n)])
        self.add(rings)
        burst = LaggedStart(*[r.animate(rate_func=linear).scale(1.3 / 0.05).set_stroke(opacity=0) for r in rings], lag_ratio=0.25, run_time=1.0)
        self.play(burst, phi.animate.increment_value(2 * np.pi), e.animate.set_value(0.35), run_time=1.0, rate_func=linear)
        self.remove(rings)
        self.play(phi.animate.increment_value(4 * np.pi), e.animate.set_value(0.0), a.animate.set_value(1.0), ejected_trail.animate.set_stroke(opacity=0.15), run_time=2.4, rate_func=linear)
        self.wait(0.25)

    # ---- variant 2: the frame follows the binary ---------------------------------------------------------
    def _v2(self):
        CL0 = np.array([-0.5, 0.2, 0])
        cloud = self.dot_cloud(n=440, sigma=1.9, center=CL0, seed=3, radius=0.032, opacity=0.4)
        c_cloud = cloud.get_center()
        ox, oy = ValueTracker(0.0), ValueTracker(0.0)      # binary displacement from the cluster; the cluster slides the other way
        off = lambda: np.array([ox.get_value(), oy.get_value(), 0])
        cloud.add_updater(lambda m: m.move_to(c_cloud - off()))
        self.add(cloud)
        a, e, phi, tilt = ValueTracker(2.4), ValueTracker(0.3), ValueTracker(0.0), ValueTracker(0.4)
        rel = lambda th=None: self.ellipse_point(a.get_value(), e.get_value(), phi.get_value() if th is None else th, ORIGIN, tilt.get_value())
        heavy, light = self.bh(0.34, -rel() / 4), self.bh(0.25, 3 * rel() / 4)
        heavy.add_updater(lambda m: m.move_to(-rel() / 4)); light.add_updater(lambda m: m.move_to(3 * rel() / 4))
        heavy.set_z_index(2); light.set_z_index(2)
        self.add(heavy, light)
        self.play(phi.animate.increment_value(2 * np.pi), run_time=1.2, rate_func=linear)

        def encounter(start, exit_pt, a_to, e_to, tilt_to, recoil, run_in=0.7, run_out=0.7):
            start, exit_pt = np.array(start, float), np.array(exit_pt, float)
            single = self.bh(0.27, start); single.set_z_index(2)
            trail = TracedPath(single[1].get_center, stroke_color=self.accent, stroke_width=2.2, stroke_opacity=0.6, dissipating_time=0.5)
            s = ValueTracker(0)
            path = CubicBezier(start, start * 0.25, -0.8 * start / np.linalg.norm(start), exit_pt)
            single.add_updater(lambda m: m.move_to(path.point_from_proportion(min(max(s.get_value(), 0), 1))))
            self.add(single, trail)
            self.play(s.animate.set_value(0.42), phi.animate.increment_value(1.5 * np.pi), run_time=run_in, rate_func=linear)
            self.play(s.animate.set_value(1.0), phi.animate.increment_value(2.5 * np.pi), a.animate.set_value(a_to), e.animate.set_value(e_to),
                      tilt.animate.set_value(tilt_to), ox.animate.increment_value(recoil[0]), oy.animate.increment_value(recoil[1]),
                      run_time=run_out, rate_func=lambda u: u ** 1.6)
            self.remove(single, trail)

        encounter([-7.6, 3.2, 0], [3.5, -4.6, 0], 2.0, 0.5, 1.3, (0.5, 0.4))
        encounter([-7.7, -3.0, 0], [2.0, 4.6, 0], 1.7, 0.35, -0.6, (0.6, -0.4))
        encounter([1.5, 4.6, 0], [-7.7, -2.0, 0], 1.5, 0.55, 0.9, (1.6, 0.3), run_out=0.6)
        # ejection: seen from the binary, the whole cluster slides away and out of view
        self.play(ox.animate.set_value(11.0), oy.animate.set_value(1.0), phi.animate.increment_value(4 * np.pi), run_time=1.9, rate_func=lambda u: 1 - (1 - u) ** 1.7)
        cloud.clear_updaters(); self.remove(cloud)
        # alone in the field: the light body's drawn track shows the ellipse rounding into a circle
        track = TracedPath(light[1].get_center, stroke_color=self.accent, stroke_width=1.4, stroke_opacity=0.3)
        self.add(track)
        rings, burst = gw_rings(heavy[1].get_center(), self.accent, rmax=1.4)
        self.add(rings)
        self.play(burst, phi.animate.increment_value(2 * np.pi), e.animate.set_value(0.4), run_time=1.0, rate_func=linear)
        self.remove(rings)
        self.play(phi.animate.increment_value(6 * np.pi), e.animate.set_value(0.0), a.animate.set_value(1.6), run_time=3.0, rate_func=linear)
        self.wait(0.3)

    # ---- variant 3: escape-radius view, bodies only until the field ------------------------------------------
    def _v3(self):
        CL = np.array([-2.6, 0.0, 0])
        R_ESC = 3.1
        core = self.dot_cloud(n=320, sigma=1.1, center=CL, seed=7, radius=0.03, opacity=0.42)
        halo = self.dot_cloud(n=220, sigma=2.3, center=CL, seed=8, radius=0.025, opacity=0.2)
        escape = DashedVMobject(Circle(radius=R_ESC, color=self.accent, stroke_width=1.6, stroke_opacity=0.55).move_to(CL), num_dashes=40)
        self.add(halo, core, escape)
        cx, cy = ValueTracker(CL[0] - 0.4), ValueTracker(CL[1] + 0.3)
        a, e, phi, tilt = ValueTracker(1.3), ValueTracker(0.3), ValueTracker(0.0), ValueTracker(0.6)
        cm = lambda: np.array([cx.get_value(), cy.get_value(), 0])
        rel = lambda th=None: self.ellipse_point(a.get_value(), e.get_value(), phi.get_value() if th is None else th, ORIGIN, tilt.get_value())
        heavy, light = self.bh(0.27, cm() - rel() / 4), self.bh(0.2, cm() + 3 * rel() / 4)
        heavy.add_updater(lambda m: m.move_to(cm() - rel() / 4)); light.add_updater(lambda m: m.move_to(cm() + 3 * rel() / 4))
        hops = TracedPath(lambda: cm(), stroke_color=self.accent, stroke_width=2.5, stroke_opacity=0.4)     # the binary's hop-by-hop path out
        heavy.set_z_index(2); light.set_z_index(2)
        self.add(hops, heavy, light)
        self.play(phi.animate.increment_value(2 * np.pi), run_time=1.0, rate_func=linear)

        def encounter(start, exit_pt, a_to, e_to, tilt_to, recoil, run_in=0.7, run_out=0.7):
            single = self.bh(0.2, start); single.set_z_index(2)
            trail = TracedPath(single[1].get_center, stroke_color=self.accent, stroke_width=2, stroke_opacity=0.6, dissipating_time=0.5)
            s = ValueTracker(0)
            c0 = cm()
            path = CubicBezier(start, c0 + (start - c0) * 0.25, c0 + 0.9 * (c0 - start) / np.linalg.norm(c0 - start) * 0.9, exit_pt)
            single.add_updater(lambda m: m.move_to(path.point_from_proportion(min(max(s.get_value(), 0), 1))))
            self.add(single, trail)
            self.play(s.animate.set_value(0.42), phi.animate.increment_value(1.5 * np.pi), run_time=run_in, rate_func=linear)
            self.play(s.animate.set_value(1.0), phi.animate.increment_value(2.5 * np.pi), a.animate.set_value(a_to), e.animate.set_value(e_to),
                      tilt.animate.set_value(tilt_to), cx.animate.increment_value(recoil[0]), cy.animate.increment_value(recoil[1]),
                      run_time=run_out, rate_func=lambda u: u ** 1.6)
            self.remove(single, trail)
            # the recoil, shown as a short arrow that fades
            c1 = cm(); kick = np.array([recoil[0], recoil[1], 0]); kick = kick / np.linalg.norm(kick)
            arrow = Arrow(c1 + 0.35 * kick, c1 + 1.3 * kick, buff=0, color=self.accent, stroke_width=3.5, max_tip_length_to_length_ratio=0.3)
            self.add(arrow)
            self.play(FadeOut(arrow), phi.animate.increment_value(np.pi), run_time=0.45, rate_func=linear)

        encounter(np.array([-7.6, 3.4, 0]), np.array([0.8, -4.6, 0]), 1.1, 0.5, 1.4, (0.55, 0.4))
        encounter(np.array([-7.6, -3.4, 0]), np.array([-0.8, 4.6, 0]), 0.95, 0.35, -0.5, (0.65, -0.5))
        encounter(np.array([-1.0, 4.6, 0]), np.array([-7.6, -1.5, 0]), 0.85, 0.55, 0.9, (1.9, 0.35), run_out=0.6)
        # the last kick carries it across the dashed escape radius
        self.play(cx.animate.set_value(3.8), cy.animate.set_value(0.7), phi.animate.increment_value(4 * np.pi), run_time=1.6, rate_func=lambda u: 1 - (1 - u) ** 1.7)
        hops.clear_updaters()
        # only now is its orbit drawn: GW emission rounds and shrinks it
        orbit = VMobject(stroke_color=self.accent, stroke_width=1.6, stroke_opacity=0.55)
        ths = np.linspace(0, 2 * np.pi, 90)
        orbit.add_updater(lambda m: m.set_points_smoothly([cm() + 3 * rel(th) / 4 for th in ths] + [cm() + 3 * rel(0) / 4]))
        orbit.update(0); orbit.set_z_index(1)
        self.add(orbit)
        self.play(FadeIn(orbit), phi.animate.increment_value(np.pi), run_time=0.5, rate_func=linear)
        rings, burst = gw_rings(heavy[1].get_center(), self.accent, rmax=1.2)
        self.add(rings)
        self.play(burst, phi.animate.increment_value(2 * np.pi), e.animate.set_value(0.35), run_time=1.0, rate_func=linear)
        self.remove(rings)
        self.play(phi.animate.increment_value(5 * np.pi), e.animate.set_value(0.0), a.animate.set_value(0.8), hops.animate.set_stroke(opacity=0.2), run_time=2.6, rate_func=linear)
        self.wait(0.3)
