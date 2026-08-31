"""zkl-smbh — ZKL cycles of a compact binary orbiting the SMBH of a nuclear star cluster (STORYBOARD.md).

Variant 1: wide view — cluster, SMBH, the binary drawn hugely magnified as it rides its tilted orbit; merger on the orbit.
Variant 2: true-scale wide view (the binary is a small marker on its SMBH orbit) plus a magnifier inset in the top-right corner
           showing the inner ZKL ellipse, bursts and merger; a dashed connector ties the marker to the inset.
Variant 3: no cluster, a giant face-on SMBH; the binary leaves a trail of faint ellipse snapshots along its orbit, so the
           eccentricity growth is drawn as a track around the SMBH; 3 faster cycles.
"""
import numpy as np
from manim import *
from style import *


class ZklSmbh(ChannelScene):
    GROUP = 'zkl'

    def construct(self):
        if VARIANT == 2:
            return self.construct_v2()
        if VARIANT == 3:
            return self.construct_v3()
        c = DOWN * 0.35
        NODE = np.radians(-15)           # line of nodes of the binary's orbit about the SMBH
        INCL_OUT = np.radians(55)
        A_OUT, E_OUT = 4.0, 0.3
        # ---- trackers -------------------------------------------------------------------
        M_in = ValueTracker(0.0)
        M_out = ValueTracker(np.radians(254))
        a_in = ValueTracker(1.5)        # the binary is drawn hugely magnified relative to its SMBH orbit
        zkl = ValueTracker(0.0)
        E_MIN, E_MAX = 0.15, 0.93
        INC_TILT = np.radians(50)

        def e_in():
            return E_MIN + (E_MAX - E_MIN) * 0.5 * (1 - np.cos(2 * np.pi * zkl.get_value()))

        def incl_in():
            return INC_TILT * 0.5 * (1 - np.cos(2 * np.pi * zkl.get_value()))

        def bary():
            nu = kepler_nu(M_out.get_value(), E_OUT)
            return c + project(self.ellipse_point(A_OUT, E_OUT, nu), INCL_OUT, NODE)

        def rel():
            nu = kepler_nu(M_in.get_value(), e_in())
            return project(rot2(self.ellipse_point(a_in.get_value(), e_in(), nu), np.radians(35)), incl_in(), NODE)

        def pos1():
            return bary() - 0.5 * rel()

        def pos2():
            return bary() + 0.5 * rel()

        # ---- nuclear star cluster + SMBH --------------------------------------------------
        cloud = self.dot_cloud(n=420, sigma=2.6, seed=3, opacity=0.28, radius=0.03)
        smbh_ring = Circle(radius=1.35, color=self.accent, stroke_width=3).move_to(c)
        smbh = Circle(radius=1.0, color=INK, fill_opacity=1, stroke_width=0).move_to(c)
        outer = ParametricFunction(lambda th: c + project(self.ellipse_point(A_OUT, E_OUT, th), INCL_OUT, NODE),
                                   t_range=[0, 2 * np.pi], color=INK, stroke_width=2, stroke_opacity=0.4)
        inner = always_redraw(lambda: ParametricFunction(
            lambda th: bary() + 0.5 * project(rot2(self.ellipse_point(a_in.get_value(), e_in(), th), np.radians(35)), incl_in(), NODE),
            t_range=[0, 2 * np.pi], color=self.accent, stroke_width=2.5, stroke_opacity=0.7))
        inner2 = always_redraw(lambda: ParametricFunction(
            lambda th: bary() - 0.5 * project(rot2(self.ellipse_point(a_in.get_value(), e_in(), th), np.radians(35)), incl_in(), NODE),
            t_range=[0, 2 * np.pi], color=self.accent, stroke_width=2.5, stroke_opacity=0.7))
        self.add(cloud, outer, smbh_ring, smbh, inner, inner2)
        # ---- the compact binary -----------------------------------------------------------
        b1, b2 = self.bh(0.33, pos1()), self.bh(0.29, pos2())
        b1.add_updater(lambda m: m.move_to(pos1())); b2.add_updater(lambda m: m.move_to(pos2()))
        self.add(b1, b2)
        P_IN = 0.7
        W_IN, W_OUT = 2 * np.pi / P_IN, 2 * np.pi * 0.75 / 11.5

        def drift(dt_):
            return [M_in.animate.increment_value(W_IN * dt_), M_out.animate.increment_value(W_OUT * dt_)]

        # 1. quiet: the binary circles the SMBH on its wide, inclined orbit
        self.play(*drift(1.3), run_time=1.3, rate_func=linear)
        # 2. ZKL cycles driven by the SMBH: 2.5 cycles, ending at an eccentricity maximum
        T_ZKL = 6.5
        self.play(zkl.animate.set_value(2.5), *drift(T_ZKL), run_time=T_ZKL, rate_func=linear)
        # 3. e → 1: GW bursts at every pericentre passage, orbit shrinks, merger mid-cycle
        T_M = 2.2
        trace = VGroup(inner.copy().clear_updaters(), inner2.copy().clear_updaters()).set_stroke(opacity=0.3, width=2)
        trace.add_updater(lambda m: m.move_to(bary()))
        self.add(trace)
        bursts, rings = [], []
        for t0 in (0.25, 0.9, 1.5):
            r, an = gw_rings_follow(self, n=3, rmax=1.5, run_time=0.75, follow=bary, stroke_width=3)
            rings.append(r); bursts.append(at_time(an, t0, T_M))
        self.play(a_in.animate.set_value(0.2), M_in.animate.increment_value(W_IN * 2.8 * T_M),
                  M_out.animate.increment_value(W_OUT * T_M), *bursts, run_time=T_M, rate_func=linear)
        self.remove(*rings, inner, inner2)
        b1.clear_updaters(); b2.clear_updaters()
        remnant = self.bh(0.38, bary())
        remnant.add_updater(lambda m: m.move_to(bary()))
        r3, burst3 = gw_rings_follow(self, n=4, rmax=2.4, run_time=1.3, follow=bary, stroke_width=3)
        self.remove(b1, b2); self.add(remnant)
        self.play(burst3, M_out.animate.increment_value(W_OUT * 1.3), run_time=1.3, rate_func=linear)
        self.remove(r3)
        halo = VGroup(*[Circle(radius=r, color=self.accent, stroke_width=2.5, stroke_opacity=o) for r, o in ((0.72, 0.6), (1.05, 0.35))])
        halo.add_updater(lambda m: m.move_to(bary()))
        self.play(FadeIn(halo), M_out.animate.increment_value(W_OUT * 0.4), run_time=0.4, rate_func=linear)

    # ---- shared machinery for variants 2 / 3 ------------------------------------------------
    def _system(self, c, node, incl_out, a_out, e_out, a0, e_min, e_max, inc_tilt, m_out0, spin=np.radians(35)):
        M_in, M_out, a_in, zkl = ValueTracker(0.0), ValueTracker(m_out0), ValueTracker(a0), ValueTracker(0.0)

        def e_in():
            return e_min + (e_max - e_min) * 0.5 * (1 - np.cos(2 * np.pi * zkl.get_value()))

        def incl_in():
            return inc_tilt * 0.5 * (1 - np.cos(2 * np.pi * zkl.get_value()))

        def bary():
            nu = kepler_nu(M_out.get_value(), e_out)
            return c + project(self.ellipse_point(a_out, e_out, nu), incl_out, node)

        def rel(th=None):
            nu = kepler_nu(M_in.get_value(), e_in()) if th is None else th
            return project(rot2(self.ellipse_point(a_in.get_value(), e_in(), nu), spin), incl_in(), node)

        outer = ParametricFunction(lambda th: c + project(self.ellipse_point(a_out, e_out, th), incl_out, node),
                                   t_range=[0, 2 * np.pi], color=INK, stroke_width=2, stroke_opacity=0.4)

        def ellipses(origin, width=2.5, opacity=0.7):
            """The two body ellipses about `origin()` (both bodies orbit the barycentre)."""
            return VGroup(*[ParametricFunction(lambda th, s=s: origin() + s * 0.5 * rel(th), t_range=[0, 2 * np.pi],
                                               color=self.accent, stroke_width=width, stroke_opacity=opacity) for s in (1, -1)])
        return dict(M_in=M_in, M_out=M_out, a_in=a_in, zkl=zkl, bary=bary, rel=rel, outer=outer, ellipses=ellipses)

    def construct_v2(self):
        c = DOWN * 0.45 + LEFT * 1.7
        INS, R_INS = np.array([4.3, 1.45, 0]), 2.15         # magnifier inset centre / radius
        S = self._system(c, node=np.radians(-15), incl_out=np.radians(55), a_out=3.3, e_out=0.3, a0=1.5,
                         e_min=0.15, e_max=0.93, inc_tilt=np.radians(50), m_out0=np.radians(250))
        M_in, M_out, a_in, zkl, bary, rel = S['M_in'], S['M_out'], S['a_in'], S['zkl'], S['bary'], S['rel']
        ins_c = lambda: INS
        # ---- wide view: cluster, SMBH, orbit, the binary as a small marker --------------------------------
        cloud = self.dot_cloud(n=420, sigma=2.6, center=c, seed=3, opacity=0.28, radius=0.03)
        smbh_ring = Circle(radius=1.2, color=self.accent, stroke_width=3).move_to(c)
        smbh = Circle(radius=0.88, color=INK, fill_opacity=1, stroke_width=0).move_to(c)

        def mpos(sign):
            u = np.array([np.cos(M_in.get_value()), np.sin(M_in.get_value()), 0])
            return bary() + sign * 0.13 * u
        marker = VGroup(Circle(radius=0.36, color=self.accent, stroke_width=2.5, stroke_opacity=0.9),
                        Dot(radius=0.09, color=INK), Dot(radius=0.08, color=INK))
        marker.add_updater(lambda m: (m[0].move_to(bary()), m[1].move_to(mpos(1)), m[2].move_to(mpos(-1))))
        # ---- inset: paper disc with an accent rim; the magnified binary lives inside ----------------------
        rim = Circle(radius=R_INS, color=self.accent, stroke_width=3, fill_color=PAPER, fill_opacity=1).move_to(INS)
        link = always_redraw(lambda: DashedLine(bary() + 0.36 * normalize(INS - bary()), INS + R_INS * normalize(bary() - INS),
                                                color=self.accent, stroke_width=1.5, stroke_opacity=0.6, dash_length=0.12))
        inner = always_redraw(lambda: S['ellipses'](ins_c))
        b1, b2 = self.bh(0.33, INS - 0.5 * rel()), self.bh(0.29, INS + 0.5 * rel())
        b1.add_updater(lambda m: m.move_to(INS - 0.5 * rel())); b2.add_updater(lambda m: m.move_to(INS + 0.5 * rel()))
        self.add(cloud, S['outer'], smbh_ring, smbh, link, marker, rim, inner, b1, b2)
        P_IN = 0.7
        W_IN, W_OUT = 2 * np.pi / P_IN, 2 * np.pi * 0.75 / 11.5

        def drift(dt_):
            return [M_in.animate.increment_value(W_IN * dt_), M_out.animate.increment_value(W_OUT * dt_)]

        # 1. quiet, 2. ZKL cycles (in the inset)
        self.play(*drift(1.3), run_time=1.3, rate_func=linear)
        T_ZKL = 6.5
        self.play(zkl.animate.set_value(2.5), *drift(T_ZKL), run_time=T_ZKL, rate_func=linear)
        # 3. e → 1: bursts at pericentre in the inset, orbit shrinks, merger; the marker flashes too
        T_M = 2.2
        trace = inner.copy().clear_updaters().set_stroke(opacity=0.3, width=2)
        self.add(trace)
        bursts, rings = [], []
        for t0 in (0.25, 0.9, 1.5):
            r, an = gw_rings_follow(self, n=3, rmax=1.5, run_time=0.75, follow=ins_c, stroke_width=3)
            rings.append(r); bursts.append(at_time(an, t0, T_M))
        self.play(a_in.animate.set_value(0.2), M_in.animate.increment_value(W_IN * 2.8 * T_M),
                  M_out.animate.increment_value(W_OUT * T_M), *bursts, run_time=T_M, rate_func=linear)
        self.remove(*rings, inner)
        b1.clear_updaters(); b2.clear_updaters(); self.remove(b1, b2)
        remnant = self.bh(0.38, INS)
        marker.clear_updaters(); self.remove(marker)
        m2 = VGroup(Circle(radius=0.36, color=self.accent, stroke_width=2.5, stroke_opacity=0.9), Dot(radius=0.13, color=INK))
        m2.add_updater(lambda m: m.move_to(bary()))
        self.add(remnant, m2)
        r3, burst3 = gw_rings_follow(self, n=4, rmax=1.9, run_time=1.3, follow=ins_c, stroke_width=3)
        r4, burst4 = gw_rings_follow(self, n=3, rmax=1.0, run_time=1.0, follow=bary, stroke_width=2.5)
        self.play(burst3, burst4, M_out.animate.increment_value(W_OUT * 1.3), run_time=1.3, rate_func=linear)
        self.remove(r3, r4)
        halo = VGroup(*[Circle(radius=r, color=self.accent, stroke_width=2.5, stroke_opacity=o).move_to(INS) for r, o in ((0.72, 0.6), (1.05, 0.35))])
        self.play(FadeIn(halo), M_out.animate.increment_value(W_OUT * 0.4), run_time=0.4, rate_func=linear)

    def construct_v3(self):
        c = RIGHT * 0.6 + DOWN * 0.1
        S = self._system(c, node=0.0, incl_out=np.radians(45), a_out=4.2, e_out=0.25, a0=1.2,
                         e_min=0.15, e_max=0.93, inc_tilt=np.radians(50), m_out0=np.radians(300))
        M_in, M_out, a_in, zkl, bary, rel = S['M_in'], S['M_out'], S['a_in'], S['zkl'], S['bary'], S['rel']
        smbh_ring = Circle(radius=2.05, color=self.accent, stroke_width=3.5).move_to(c)
        smbh = Circle(radius=1.6, color=INK, fill_opacity=1, stroke_width=0).move_to(c)
        inner = always_redraw(lambda: S['ellipses'](bary))
        b1, b2 = self.bh(0.3, bary() - 0.5 * rel()), self.bh(0.26, bary() + 0.5 * rel())
        b1.add_updater(lambda m: m.move_to(bary() - 0.5 * rel())); b2.add_updater(lambda m: m.move_to(bary() + 0.5 * rel()))
        snaps = VGroup()
        self.add(S['outer'], snaps, smbh_ring, smbh, inner, b1, b2)
        P_IN = 0.6
        W_IN, W_OUT = 2 * np.pi / P_IN, 2 * np.pi * 0.8 / 11.5

        def drift(dt_):
            return [M_in.animate.increment_value(W_IN * dt_), M_out.animate.increment_value(W_OUT * dt_)]

        # 1. quiet; 2. three ZKL cycles, leaving a snapshot of the inner ellipse every quarter cycle along the orbit
        self.play(*drift(1.0), run_time=1.0, rate_func=linear)
        N_SNAP, T_ZKL = 14, 6.8
        for k in range(N_SNAP):
            self.play(zkl.animate.set_value(3.5 * (k + 1) / N_SNAP), *drift(T_ZKL / N_SNAP), run_time=T_ZKL / N_SNAP, rate_func=linear)
            snaps.add(inner.copy().clear_updaters().set_stroke(opacity=0.22, width=1.5))
        # 3. e → 1: bursts at every pericentre, shrink, merger on the orbit
        T_M = 2.2
        trace = inner.copy().clear_updaters().set_stroke(opacity=0.3, width=2)
        trace.add_updater(lambda m: m.move_to(bary()))
        self.add(trace)
        bursts, rings = [], []
        for t0 in (0.25, 0.9, 1.5):
            r, an = gw_rings_follow(self, n=3, rmax=1.5, run_time=0.75, follow=bary, stroke_width=3)
            rings.append(r); bursts.append(at_time(an, t0, T_M))
        self.play(a_in.animate.set_value(0.2), M_in.animate.increment_value(W_IN * 2.8 * T_M),
                  M_out.animate.increment_value(W_OUT * T_M), *bursts, run_time=T_M, rate_func=linear)
        self.remove(*rings, inner)
        b1.clear_updaters(); b2.clear_updaters(); self.remove(b1, b2)
        remnant = self.bh(0.38, bary()); remnant.add_updater(lambda m: m.move_to(bary()))
        self.add(remnant)
        r3, burst3 = gw_rings_follow(self, n=4, rmax=2.4, run_time=1.3, follow=bary, stroke_width=3)
        self.play(burst3, M_out.animate.increment_value(W_OUT * 1.3), run_time=1.3, rate_func=linear)
        self.remove(r3)
        halo = VGroup(*[Circle(radius=r, color=self.accent, stroke_width=2.5, stroke_opacity=o) for r, o in ((0.72, 0.6), (1.05, 0.35))])
        halo.add_updater(lambda m: m.move_to(bary()))
        self.play(FadeIn(halo), M_out.animate.increment_value(W_OUT * 0.4), run_time=0.4, rate_func=linear)
