"""triples — field triples, von Zeipel–Kozai–Lidov cycles (STORYBOARD.md).

Variant 1: wide view — static tilted outer orbit, inner ellipse redrawn live, BHs collapse first, 2.5 cycles, merger at centre.
Variant 2: close-up on the inner binary (it fills the frame, the tertiary skims the edge); the inner ellipse leaves a faint
           snapshot every quarter cycle, so the e/i track is drawn as a nested family of ellipses.
Variant 3: the tertiary orbit is seen nearly edge-on (a thin line) and the inner plane flips from face-on toward that line at
           each eccentricity maximum; the stars survive into the first cycle and collapse mid-clip, then 3 faster cycles.
"""
import numpy as np
from manim import *
from style import *


class Triples(ChannelScene):
    GROUP = 'zkl'

    def construct(self):
        if VARIANT == 2:
            return self.construct_v2()
        if VARIANT == 3:
            return self.construct_v3()
        c = ORIGIN
        NODE = np.radians(25)            # line of nodes of the outer orbit on the sky
        INCL_OUT = np.radians(52)        # outer orbit plane tilt
        A_OUT, E_OUT = 4.6, 0.22
        q = 0.45                         # m2 / (m1 + m2) of the inner binary
        # ---- trackers -------------------------------------------------------------------
        M_in = ValueTracker(0.0)         # inner mean anomaly
        M_out = ValueTracker(np.radians(250))
        a_in = ValueTracker(2.3)
        zkl = ValueTracker(0.0)          # ZKL phase in cycles: e/i exchange
        E_MIN, E_MAX = 0.10, 0.85
        INC_TILT = np.radians(48)        # how far the inner plane tilts toward the outer one at e max

        def e_in():
            return E_MIN + (E_MAX - E_MIN) * 0.5 * (1 - np.cos(2 * np.pi * zkl.get_value()))

        def incl_in():
            return INC_TILT * 0.5 * (1 - np.cos(2 * np.pi * zkl.get_value()))

        def rel():
            nu = kepler_nu(M_in.get_value(), e_in())
            return project(self.ellipse_point(a_in.get_value(), e_in(), nu), incl_in(), NODE)

        def pos1():
            return c - q * rel()

        def pos2():
            return c + (1 - q) * rel()

        def pos3():
            nu = kepler_nu(M_out.get_value(), E_OUT)
            return c + project(self.ellipse_point(A_OUT, E_OUT, nu), INCL_OUT, NODE)

        # ---- static outer orbit + moving inner ellipse -------------------------------------
        outer = ParametricFunction(lambda th: c + project(self.ellipse_point(A_OUT, E_OUT, th), INCL_OUT, NODE),
                                   t_range=[0, 2 * np.pi], color=INK, stroke_width=2, stroke_opacity=0.4)
        inner = always_redraw(lambda: ParametricFunction(
            lambda th: c + (1 - q) * project(self.ellipse_point(a_in.get_value(), e_in(), th), incl_in(), NODE),
            t_range=[0, 2 * np.pi], color=self.accent, stroke_width=2.5, stroke_opacity=0.7))
        self.add(outer, inner)
        # ---- bodies -----------------------------------------------------------------------
        s1 = self.star(0.55, STAR_BLUE, pos1())
        s2 = self.star(0.45, STAR_BLUE, pos2())
        s3 = self.star(0.5, STAR_ORANGE, pos3())
        s1.add_updater(lambda m: m.move_to(pos1()))
        s2.add_updater(lambda m: m.move_to(pos2()))
        s3.add_updater(lambda m: m.move_to(pos3()))
        self.add(s1, s2, s3)
        P_IN = 0.8                        # inner period (s); outer star makes ~0.8 orbit in the clip
        W_IN, W_OUT = 2 * np.pi / P_IN, 2 * np.pi * 0.8 / 11.5

        def drift(dt_):
            return [M_in.animate.increment_value(W_IN * dt_), M_out.animate.increment_value(W_OUT * dt_)]

        # 1. a quiet inner orbit, tertiary far out
        self.play(*drift(1.2), run_time=1.2, rate_func=linear)
        # 2. both inner stars collapse to black holes (flashes follow the moving stars)
        f1 = Circle(radius=1.2, color=WHITE, fill_opacity=0.9, stroke_width=0)
        f2 = Circle(radius=1.0, color=WHITE, fill_opacity=0.9, stroke_width=0)
        f1.add_updater(lambda m: m.move_to(pos1())); f2.add_updater(lambda m: m.move_to(pos2()))
        self.play(FadeIn(f1), FadeIn(f2), *drift(0.2), run_time=0.2, rate_func=linear)
        b1, b2 = self.bh(0.32, pos1()), self.bh(0.28, pos2())
        self.play(FadeOut(f1), FadeOut(f2), Transform(s1, b1), Transform(s2, b2), *drift(0.5), run_time=0.5, rate_func=linear)
        self.remove(f1, f2)
        # 3. secular ZKL cycles: e up while the inner plane tilts toward the outer one, then back — 2.5 cycles
        T_ZKL = 6.0
        self.play(zkl.animate.set_value(2.5), *drift(T_ZKL), run_time=T_ZKL, rate_func=linear)
        # 4. at the eccentricity maximum: GW bursts at pericentre, the inner orbit shrinks and merges eccentric
        T_M = 2.0
        trace = inner.copy().clear_updaters().set_stroke(opacity=0.3, width=2)
        self.add(trace)
        r1, burst1 = gw_rings_follow(self, n=3, rmax=1.6, run_time=0.8, follow=lambda: c, stroke_width=3)
        r2, burst2 = gw_rings_follow(self, n=3, rmax=1.6, run_time=0.8, follow=lambda: c, stroke_width=3)
        self.play(a_in.animate.set_value(0.32), M_in.animate.increment_value(W_IN * 2.6 * T_M),
                  M_out.animate.increment_value(W_OUT * T_M),
                  at_time(burst1, 0.3, T_M), at_time(burst2, 1.15, T_M),
                  run_time=T_M, rate_func=linear)
        self.remove(r1, r2)
        # final ellipse (eccentric, tiny) stays as a faint trace; bodies merge into one BH
        self.remove(inner)
        s1.clear_updaters(); s2.clear_updaters()
        remnant = self.bh(0.4, c)
        r3, burst3 = gw_rings_follow(self, n=4, rmax=2.2, run_time=1.3, follow=lambda: c, stroke_width=3)
        self.play(Transform(s1, remnant), Transform(s2, remnant.copy()), burst3,
                  M_out.animate.increment_value(W_OUT * 1.3), run_time=1.3, rate_func=linear)
        self.remove(r3)
        halo = VGroup(*[Circle(radius=r, color=self.accent, stroke_width=2.5, stroke_opacity=o).move_to(c) for r, o in ((0.75, 0.6), (1.1, 0.35))])
        self.play(FadeIn(halo), M_out.animate.increment_value(W_OUT * 0.4), run_time=0.4, rate_func=linear)

    # ---- shared machinery for variants 2 / 3 ------------------------------------------------
    def _triple(self, node, incl_out, a_out, e_out, a0, e_min, e_max, inc_tilt, m_out0, q=0.45):
        """Build trackers, position functions and the two orbit curves; returns a dict."""
        c = ORIGIN
        M_in, M_out, a_in, zkl = ValueTracker(0.0), ValueTracker(m_out0), ValueTracker(a0), ValueTracker(0.0)

        def e_in():
            return e_min + (e_max - e_min) * 0.5 * (1 - np.cos(2 * np.pi * zkl.get_value()))

        def incl_in():
            return inc_tilt * 0.5 * (1 - np.cos(2 * np.pi * zkl.get_value()))

        def rel():
            nu = kepler_nu(M_in.get_value(), e_in())
            return project(self.ellipse_point(a_in.get_value(), e_in(), nu), incl_in(), node)

        def pos1():
            return c - q * rel()

        def pos2():
            return c + (1 - q) * rel()

        def pos3():
            nu = kepler_nu(M_out.get_value(), e_out)
            return c + project(self.ellipse_point(a_out, e_out, nu), incl_out, node)

        outer = ParametricFunction(lambda th: c + project(self.ellipse_point(a_out, e_out, th), incl_out, node),
                                   t_range=[0, 2 * np.pi], color=INK, stroke_width=2, stroke_opacity=0.4)
        inner = always_redraw(lambda: ParametricFunction(
            lambda th: c + (1 - q) * project(self.ellipse_point(a_in.get_value(), e_in(), th), incl_in(), node),
            t_range=[0, 2 * np.pi], color=self.accent, stroke_width=2.5, stroke_opacity=0.7))
        return dict(c=c, M_in=M_in, M_out=M_out, a_in=a_in, zkl=zkl, pos1=pos1, pos2=pos2, pos3=pos3, outer=outer, inner=inner)

    def _collapse_pair(self, T, s1, s2, drift, r1=0.32, r2=0.28, f1r=1.2, f2r=1.0):
        f1 = Circle(radius=f1r, color=WHITE, fill_opacity=0.9, stroke_width=0)
        f2 = Circle(radius=f2r, color=WHITE, fill_opacity=0.9, stroke_width=0)
        f1.add_updater(lambda m: m.move_to(T['pos1']())); f2.add_updater(lambda m: m.move_to(T['pos2']()))
        self.play(FadeIn(f1), FadeIn(f2), *drift(0.2), run_time=0.2, rate_func=linear)
        b1, b2 = self.bh(r1, T['pos1']()), self.bh(r2, T['pos2']())
        self.play(FadeOut(f1), FadeOut(f2), Transform(s1, b1), Transform(s2, b2), *drift(0.5), run_time=0.5, rate_func=linear)
        self.remove(f1, f2)

    def _merge(self, T, s1, s2, drift, W_IN, W_OUT, a_final=0.32, rmax=1.6, halo=((0.75, 0.6), (1.1, 0.35))):
        c, inner = T['c'], T['inner']
        T_M = 2.0
        trace = inner.copy().clear_updaters().set_stroke(opacity=0.3, width=2)
        self.add(trace)
        r1, burst1 = gw_rings_follow(self, n=3, rmax=rmax, run_time=0.8, follow=lambda: c, stroke_width=3)
        r2, burst2 = gw_rings_follow(self, n=3, rmax=rmax, run_time=0.8, follow=lambda: c, stroke_width=3)
        self.play(T['a_in'].animate.set_value(a_final), T['M_in'].animate.increment_value(W_IN * 2.6 * T_M),
                  T['M_out'].animate.increment_value(W_OUT * T_M),
                  at_time(burst1, 0.3, T_M), at_time(burst2, 1.15, T_M), run_time=T_M, rate_func=linear)
        self.remove(r1, r2, inner)
        s1.clear_updaters(); s2.clear_updaters()
        remnant = self.bh(0.4, c)
        r3, burst3 = gw_rings_follow(self, n=4, rmax=rmax + 0.6, run_time=1.3, follow=lambda: c, stroke_width=3)
        self.play(Transform(s1, remnant), Transform(s2, remnant.copy()), burst3,
                  T['M_out'].animate.increment_value(W_OUT * 1.3), run_time=1.3, rate_func=linear)
        self.remove(r3)
        h = VGroup(*[Circle(radius=r, color=self.accent, stroke_width=2.5, stroke_opacity=o).move_to(c) for r, o in halo])
        self.play(FadeIn(h), T['M_out'].animate.increment_value(W_OUT * 0.4), run_time=0.4, rate_func=linear)

    def construct_v2(self):
        T = self._triple(node=np.radians(12), incl_out=np.radians(62), a_out=5.6, e_out=0.12, a0=3.1,
                         e_min=0.08, e_max=0.88, inc_tilt=np.radians(55), m_out0=np.radians(230))
        c, M_in, M_out, zkl, inner = T['c'], T['M_in'], T['M_out'], T['zkl'], T['inner']
        self.add(T['outer'], inner)
        s1 = self.star(0.7, STAR_BLUE, T['pos1']())
        s2 = self.star(0.58, STAR_BLUE, T['pos2']())
        s3 = self.star(0.45, STAR_ORANGE, T['pos3']())
        s1.add_updater(lambda m: m.move_to(T['pos1']()))
        s2.add_updater(lambda m: m.move_to(T['pos2']()))
        s3.add_updater(lambda m: m.move_to(T['pos3']()))
        self.add(s1, s2, s3)
        P_IN = 1.0
        W_IN, W_OUT = 2 * np.pi / P_IN, 2 * np.pi * 0.7 / 11.5

        def drift(dt_):
            return [M_in.animate.increment_value(W_IN * dt_), M_out.animate.increment_value(W_OUT * dt_)]

        # 1. quiet binary, 2. collapse (both flashes follow the stars)
        self.play(*drift(1.2), run_time=1.2, rate_func=linear)
        self._collapse_pair(T, s1, s2, drift, r1=0.36, r2=0.31, f1r=1.5, f2r=1.3)
        # 3. ZKL cycles drawn as a track: a faint snapshot of the inner ellipse every quarter cycle
        N_SNAP, T_ZKL = 10, 6.0
        snaps = VGroup(); self.add(snaps)
        for k in range(N_SNAP):
            self.play(zkl.animate.set_value(0.25 * (k + 1)), *drift(T_ZKL / N_SNAP), run_time=T_ZKL / N_SNAP, rate_func=linear)
            snaps.add(inner.copy().clear_updaters().set_stroke(opacity=0.16, width=1.5))
        # 4. e max: bursts, shrink, eccentric merger
        self._merge(T, s1, s2, drift, W_IN, W_OUT, a_final=0.4, rmax=2.0, halo=((0.85, 0.6), (1.25, 0.35)))

    def construct_v3(self):
        # the tertiary rides the far (apocentre) arc during the clip, so it never crosses the binary in projection
        T = self._triple(node=np.radians(-20), incl_out=np.radians(80), a_out=4.8, e_out=0.2, a0=2.4,
                         e_min=0.12, e_max=0.9, inc_tilt=np.radians(72), m_out0=np.radians(115))
        c, M_in, M_out, zkl, inner = T['c'], T['M_in'], T['M_out'], T['zkl'], T['inner']
        self.add(T['outer'], inner)
        s1 = self.star(0.55, STAR_BLUE, T['pos1']())
        s2 = self.star(0.45, STAR_BLUE, T['pos2']())
        s3 = self.star(0.5, STAR_ORANGE, T['pos3']())
        s1.add_updater(lambda m: m.move_to(T['pos1']()))
        s2.add_updater(lambda m: m.move_to(T['pos2']()))
        s3.add_updater(lambda m: m.move_to(T['pos3']()))
        self.add(s1, s2, s3)
        P_IN = 0.8
        W_IN, W_OUT = 2 * np.pi / P_IN, 2 * np.pi * 0.36 / 12.8

        def drift(dt_):
            return [M_in.animate.increment_value(W_IN * dt_), M_out.animate.increment_value(W_OUT * dt_)]

        # 1. quiet, then the stars already feel the tertiary: the ellipse starts to stretch and tilt
        self.play(*drift(1.0), run_time=1.0, rate_func=linear)
        self.play(zkl.animate.set_value(0.3), *drift(1.0), run_time=1.0, rate_func=linear)
        # 2. collapse mid-cycle
        self._collapse_pair(T, s1, s2, drift)
        # 3. three fast cycles, the inner plane flipping toward the edge-on outer orbit at each e max
        T_ZKL = 6.3
        self.play(zkl.animate.set_value(3.5), *drift(T_ZKL), run_time=T_ZKL, rate_func=linear)
        # 4. merger
        self._merge(T, s1, s2, drift, W_IN, W_OUT)
