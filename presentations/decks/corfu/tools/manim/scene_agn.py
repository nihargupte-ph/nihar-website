"""agn — stellar-mass BHs in an AGN accretion disc: migration trap, gas hardening, disc-plane encounter (STORYBOARD.md).

Variant 1: face-on disc (radial gradient + spiral), two BHs migrate to the dashed trap ring, pair, harden; a third sweeps past.
Variant 2: the same beats seen from 60° above the disc plane: annuli, spiral, trap ring, arrows and the pair's orbit are all
           projected, so the co-planar flyby and the eccentric final ellipse read as in-plane geometry.
Variant 3: crowded trap — the disc is drawn as differentially rotating gas streamlines and a translucent trap band, five BHs
           spiral in leaving traced tracks and pile up on the band; the pair forms out of the crowd and the intruder is a
           neighbour on the same ring catching up.
"""
import numpy as np
from manim import *
from style import *


class Agn(ChannelScene):
    GROUP = 'agn'

    def construct(self):
        if VARIANT == 2:
            return self.construct_v2()
        if VARIANT == 3:
            return self.construct_v3()
        c = ORIGIN
        R_DISC, R_TRAP = 3.7, 2.35
        OMEGA = 0.95                     # angular speed at the trap (rad/s)
        # ---- the disc: radial gradient, faint two-arm spiral, SMBH, migration trap -----------
        disc = VGroup(*[Annulus(inner_radius=r0, outer_radius=r1, color=self.accent, fill_opacity=0.19 * (1 - i / 9) ** 1.4 + 0.02, stroke_width=0)
                        for i, (r0, r1) in enumerate(zip(np.linspace(0.7, R_DISC, 10)[:-1], np.linspace(0.7, R_DISC, 10)[1:]))])
        spiral = VGroup(*[ParametricFunction(lambda u, k=k: c + 0.75 * np.exp(0.33 * u) * np.array([np.cos(u + k), np.sin(u + k), 0]),
                                             t_range=[0, 4.8], color=INK, stroke_width=1.5, stroke_opacity=0.22) for k in (0, np.pi)])
        spiral.add_updater(lambda m, dt: m.rotate(0.2 * dt, about_point=c))
        smbh = VGroup(Circle(radius=0.8, color=self.accent, stroke_width=3), Circle(radius=0.58, color=INK, fill_opacity=1, stroke_width=0)).move_to(c)
        trap = DashedVMobject(Circle(radius=R_TRAP, color=self.accent, stroke_width=2.5, stroke_opacity=0.7), num_dashes=48)
        arrows = VGroup(*[Arrow(start=c + 3.45 * np.array([np.cos(p), np.sin(p), 0]), end=c + 2.75 * np.array([np.cos(p), np.sin(p), 0]),
                                buff=0, stroke_width=3, max_tip_length_to_length_ratio=0.35, color=self.accent).set_opacity(0.6)
                          for p in np.radians([15, 75, 135, 195, 255, 315])])
        self.add(disc, spiral, trap, arrows, smbh)
        # ---- embedded black holes ---------------------------------------------------------
        t = ValueTracker(0.0)            # scene clock (s)
        mig = ValueTracker(0.0)          # 0 → 1 migration progress of A and B to the trap

        def polar(r, ph):
            return c + r * np.array([np.cos(ph), np.sin(ph), 0])

        def smooth(x):
            x = np.clip(x, 0, 1); return x * x * (3 - 2 * x)

        # pair centre P rides the trap ring; A and B converge onto it from outside
        PHI0 = np.radians(200)
        def P():
            return polar(R_TRAP, PHI0 + OMEGA * t.get_value())
        def free(r0, ph0, w):
            r = R_TRAP + (r0 - R_TRAP) * (1 - smooth(mig.get_value()))
            return polar(r, ph0 + w * t.get_value())
        # at t = T_PAIR both must sit next to P: choose start azimuths accordingly
        T_PAIR = 3.4
        WA, WB = 0.72, 1.25
        PHA0 = PHI0 + OMEGA * T_PAIR - WA * T_PAIR + 0.17
        PHB0 = PHI0 + OMEGA * T_PAIR - WB * T_PAIR - 0.17
        # relative orbit of the pair (used after pairing)
        a_p, e_p, M_p = ValueTracker(0.42), ValueTracker(0.0), ValueTracker(0.0)
        PSI = ValueTracker(0.0)
        def rel():
            nu = kepler_nu(M_p.get_value(), e_p.get_value())
            return rot2(self.ellipse_point(a_p.get_value(), e_p.get_value(), nu), PSI.get_value())
        paired = [False]
        def posA():
            return P() - rel() if paired[0] else free(3.3, PHA0, WA)
        def posB():
            return P() + rel() if paired[0] else free(3.1, PHB0, WB)
        A, B = self.bh(0.27, posA()), self.bh(0.27, posB())
        A.add_updater(lambda m: m.move_to(posA())); B.add_updater(lambda m: m.move_to(posB()))
        # third BH C: co-rotating out at the disc edge, then a hyperbolic disc-plane flyby of P
        E_H, PERI = 1.6, 0.75
        TH_INF = np.arccos(-1 / E_H)
        th_c = ValueTracker(-(TH_INF - 0.55))
        def posC():
            th = th_c.get_value()
            r = PERI * (1 + E_H) / (1 + E_H * np.cos(th))
            v = r * np.array([np.cos(th), np.sin(th), 0])
            ph = PHI0 + OMEGA * t.get_value()      # rotate into P's co-moving frame (x = outward, y = along the flow)
            return P() + rot2(rot2(v, np.radians(-10)), ph)
        C = self.bh(0.27, posC()); C.add_updater(lambda m: m.move_to(posC()))
        self.add(A, B, C)
        # 1. gas torques: A and B migrate inward and pile up at the trap
        self.play(t.animate.set_value(T_PAIR), mig.animate.set_value(1.0), run_time=T_PAIR, rate_func=linear)
        # 2. pairing: hand over to the bound-pair parametrisation exactly where they are
        d = posB() - posA()
        a_p.set_value(0.5 * np.linalg.norm(d)); PSI.set_value(np.arctan2(d[1], d[0])); M_p.set_value(0)
        paired[0] = True
        pair_orbit = always_redraw(lambda: VGroup(*[ParametricFunction(
            lambda th, s=s: P() + s * rot2(self.ellipse_point(a_p.get_value(), e_p.get_value(), th), PSI.get_value()),
            t_range=[0, 2 * np.pi], color=self.accent, stroke_width=2.5, stroke_opacity=0.75) for s in (1, -1)]))
        self.add(pair_orbit)
        # 3. gas hardening: the pair's circle tightens; C drifts in at the disc edge
        T_H = 2.4
        self.play(t.animate.increment_value(T_H), a_p.animate.set_value(0.24), M_p.animate.increment_value(2 * np.pi * 3.2),
                  th_c.animate.set_value(-(TH_INF - 0.72)), FadeOut(arrows), run_time=T_H, rate_func=linear)
        # 4. disc-plane encounter: C sweeps past the pair and flings off; the pair is left eccentric
        T_E = 2.2
        self.play(t.animate.increment_value(T_E), M_p.animate.increment_value(2 * np.pi * 4.5),
                  th_c.animate(rate_func=smooth).set_value(TH_INF - 0.5),
                  e_p.animate(rate_func=lambda x: smooth(2 * x - 0.6)).set_value(0.72), run_time=T_E, rate_func=linear)
        # 5. GW bursts at pericentre, shrink, eccentric merger inside the disc
        T_M = 2.0
        trace = pair_orbit.copy().clear_updaters().set_stroke(opacity=0.35, width=2)
        trace.add_updater(lambda m: m.move_to(P()))
        self.add(trace)
        bursts, rings = [], []
        for t0 in (0.2, 0.85, 1.4):
            r, an = gw_rings_follow(self, n=3, rmax=1.3, run_time=0.7, follow=P, stroke_width=3)
            rings.append(r); bursts.append(at_time(an, t0, T_M))
        self.play(t.animate.increment_value(T_M), a_p.animate.set_value(0.05), M_p.animate.increment_value(2 * np.pi * 6),
                  *bursts, run_time=T_M, rate_func=linear)
        self.remove(*rings, pair_orbit)
        A.clear_updaters(); B.clear_updaters(); self.remove(A, B)
        remnant = self.bh(0.36, P()); remnant.add_updater(lambda m: m.move_to(P()))
        self.add(remnant)
        r3, burst3 = gw_rings_follow(self, n=4, rmax=2.2, run_time=1.2, follow=P, stroke_width=3)
        self.play(t.animate.increment_value(1.2), burst3, run_time=1.2, rate_func=linear)
        self.remove(r3)
        halo = VGroup(*[Circle(radius=r, color=self.accent, stroke_width=2.5, stroke_opacity=o) for r, o in ((0.65, 0.6), (0.95, 0.35))])
        halo.add_updater(lambda m: m.move_to(P()))
        self.play(FadeIn(halo), t.animate.increment_value(0.4), run_time=0.4, rate_func=linear)

    # ---- shared machinery for variants 2 / 3 ------------------------------------------------
    def _bodies(self, c, R_TRAP, OMEGA, sky, T_PAIR=3.4, rA=0.3, extra=()):
        """Trackers + position functions for the pair (A, B), the intruder C and optional extra ring-dwellers.
        `sky` maps a disc-plane point to the screen. Returns a dict."""
        t, mig = ValueTracker(0.0), ValueTracker(0.0)

        def polar(r, ph):
            return c + r * np.array([np.cos(ph), np.sin(ph), 0])

        def smooth(x):
            x = np.clip(x, 0, 1); return x * x * (3 - 2 * x)

        PHI0 = np.radians(200)
        def P():
            return polar(R_TRAP, PHI0 + OMEGA * t.get_value())
        def free(r0, ph0, w, lag=0.0, span=1.0):
            r = R_TRAP + (r0 - R_TRAP) * (1 - smooth((mig.get_value() - lag) / span))
            tt = t.get_value()                          # once on the trap (t ≥ T_PAIR) everything co-rotates at OMEGA
            return polar(r, ph0 + w * min(tt, T_PAIR) + OMEGA * max(tt - T_PAIR, 0))
        WA, WB = 0.72, 1.25
        PHA0 = PHI0 + OMEGA * T_PAIR - WA * T_PAIR + 0.17
        PHB0 = PHI0 + OMEGA * T_PAIR - WB * T_PAIR - 0.17
        a_p, e_p, M_p, PSI = ValueTracker(0.42), ValueTracker(0.0), ValueTracker(0.0), ValueTracker(0.0)
        def rel():
            nu = kepler_nu(M_p.get_value(), e_p.get_value())
            return rot2(self.ellipse_point(a_p.get_value(), e_p.get_value(), nu), PSI.get_value())
        paired = [False]
        def posA():
            return P() - rel() if paired[0] else free(3.3 / 2.35 * R_TRAP, PHA0, WA)
        def posB():
            return P() + rel() if paired[0] else free(3.1 / 2.35 * R_TRAP, PHB0, WB)
        E_H, PERI = 1.6, 0.75
        TH_INF = np.arccos(-1 / E_H)
        th_c = ValueTracker(-(TH_INF - 0.55))
        def posC():
            th = th_c.get_value()
            r = PERI * (1 + E_H) / (1 + E_H * np.cos(th))
            v = r * np.array([np.cos(th), np.sin(th), 0])
            return P() + rot2(rot2(v, np.radians(-10)), PHI0 + OMEGA * t.get_value())
        A, B, C = self.bh(rA, sky(posA())), self.bh(rA, sky(posB())), self.bh(rA, sky(posC()))
        A.add_updater(lambda m: m.move_to(sky(posA()))); B.add_updater(lambda m: m.move_to(sky(posB()))); C.add_updater(lambda m: m.move_to(sky(posC())))
        others, opos = VGroup(), []
        for (r0, dphi, w, lag) in extra:                 # ring-dwellers: migrate in with a lag, then ride the trap ahead of P
            ph0 = PHI0 + dphi + (OMEGA - w) * T_PAIR
            f = (lambda r0=r0, ph0=ph0, w=w, lag=lag: free(r0, ph0, w, lag=lag, span=1 - lag))
            d = self.bh(rA, sky(f())); d.add_updater(lambda m, f=f: m.move_to(sky(f())))
            others.add(d); opos.append(f)
        return dict(t=t, mig=mig, P=P, posA=posA, posB=posB, posC=posC, a_p=a_p, e_p=e_p, M_p=M_p, PSI=PSI, th_c=th_c,
                    TH_INF=TH_INF, paired=paired, A=A, B=B, C=C, others=others, opos=opos, T_PAIR=T_PAIR, smooth=smooth)

    def _pair_and_merge(self, D, sky, arrows=None, T_H=2.4, rmax=1.3, halo=((0.65, 0.6), (0.95, 0.35))):
        """Beats 2–5 (pairing, hardening, flyby, bursts, merger) for a bodies dict D; positions go through `sky`."""
        t, P, a_p, e_p, M_p, PSI, th_c, TH_INF = D['t'], D['P'], D['a_p'], D['e_p'], D['M_p'], D['PSI'], D['th_c'], D['TH_INF']
        d = D['posB']() - D['posA']()
        a_p.set_value(0.5 * np.linalg.norm(d)); PSI.set_value(np.arctan2(d[1], d[0])); M_p.set_value(0)
        D['paired'][0] = True
        pair_orbit = always_redraw(lambda: VGroup(*[ParametricFunction(
            lambda th, s=s: sky(P() + s * rot2(self.ellipse_point(a_p.get_value(), e_p.get_value(), th), PSI.get_value())),
            t_range=[0, 2 * np.pi], color=self.accent, stroke_width=2.5, stroke_opacity=0.75) for s in (1, -1)]))
        self.add(pair_orbit)
        fade = [FadeOut(arrows)] if arrows is not None else []
        self.play(t.animate.increment_value(T_H), a_p.animate.set_value(0.24), M_p.animate.increment_value(2 * np.pi * 3.2),
                  th_c.animate.set_value(-(TH_INF - 0.72)), *fade, run_time=T_H, rate_func=linear)
        T_E = 2.2
        sm = D['smooth']
        self.play(t.animate.increment_value(T_E), M_p.animate.increment_value(2 * np.pi * 4.5),
                  th_c.animate(rate_func=smooth).set_value(TH_INF - 0.5),
                  e_p.animate(rate_func=lambda x: sm(2 * x - 0.6)).set_value(0.72), run_time=T_E, rate_func=linear)
        T_M = 2.0
        trace = pair_orbit.copy().clear_updaters().set_stroke(opacity=0.35, width=2)
        trace.add_updater(lambda m: m.move_to(sky(P())))
        self.add(trace)
        bursts, rings = [], []
        follow = lambda: sky(P())
        for t0 in (0.2, 0.85, 1.4):
            r, an = gw_rings_follow(self, n=3, rmax=rmax, run_time=0.7, follow=follow, stroke_width=3)
            rings.append(r); bursts.append(at_time(an, t0, T_M))
        self.play(t.animate.increment_value(T_M), a_p.animate.set_value(0.05), M_p.animate.increment_value(2 * np.pi * 6),
                  *bursts, run_time=T_M, rate_func=linear)
        self.remove(*rings, pair_orbit)
        A, B = D['A'], D['B']
        A.clear_updaters(); B.clear_updaters(); self.remove(A, B)
        remnant = self.bh(0.38, sky(P())); remnant.add_updater(lambda m: m.move_to(sky(P())))
        self.add(remnant)
        r3, burst3 = gw_rings_follow(self, n=4, rmax=rmax + 0.9, run_time=1.2, follow=follow, stroke_width=3)
        self.play(t.animate.increment_value(1.2), burst3, run_time=1.2, rate_func=linear)
        self.remove(r3)
        h = VGroup(*[Circle(radius=r, color=self.accent, stroke_width=2.5, stroke_opacity=o) for r, o in halo])
        h.add_updater(lambda m: m.move_to(sky(P())))
        self.play(FadeIn(h), t.animate.increment_value(0.4), run_time=0.4, rate_func=linear)

    def construct_v2(self):
        c = DOWN * 0.15
        INCL, NODE = np.radians(60), np.radians(-8)
        R_DISC, R_TRAP, OMEGA = 5.2, 3.3, 0.95

        def sky(p):
            return c + project(p - c, INCL, NODE)

        def flat(m):
            return m.stretch(np.cos(INCL), 1, about_point=c).rotate(NODE, about_point=c)
        disc = VGroup(*[flat(Annulus(inner_radius=r0, outer_radius=r1, color=self.accent, fill_opacity=0.19 * (1 - i / 9) ** 1.4 + 0.02, stroke_width=0).move_to(c))
                        for i, (r0, r1) in enumerate(zip(np.linspace(0.9, R_DISC, 10)[:-1], np.linspace(0.9, R_DISC, 10)[1:]))])
        spin = ValueTracker(0.0)
        spiral = always_redraw(lambda: VGroup(*[ParametricFunction(
            lambda u, k=k: sky(c + 1.0 * np.exp(0.33 * u) * np.array([np.cos(u + k + spin.get_value()), np.sin(u + k + spin.get_value()), 0])),
            t_range=[0, 4.9], color=INK, stroke_width=1.5, stroke_opacity=0.22) for k in (0, np.pi)]))
        spin.add_updater(lambda m, dt: m.increment_value(0.2 * dt))
        smbh = VGroup(Circle(radius=0.75, color=self.accent, stroke_width=3), Circle(radius=0.54, color=INK, fill_opacity=1, stroke_width=0)).move_to(c)
        trap = DashedVMobject(flat(Circle(radius=R_TRAP, color=self.accent, stroke_width=2.5, stroke_opacity=0.7).move_to(c)), num_dashes=56)
        arrows = VGroup(*[Arrow(start=sky(c + 4.85 * np.array([np.cos(p), np.sin(p), 0])), end=sky(c + 3.85 * np.array([np.cos(p), np.sin(p), 0])),
                                buff=0, stroke_width=3, max_tip_length_to_length_ratio=0.35, color=self.accent).set_opacity(0.6)
                          for p in np.radians([15, 75, 135, 195, 255, 315])])
        self.add(disc, spiral, trap, arrows, smbh)
        D = self._bodies(c, R_TRAP, OMEGA, sky, rA=0.3)
        self.add(D['A'], D['B'], D['C'])
        self.play(D['t'].animate.set_value(D['T_PAIR']), D['mig'].animate.set_value(1.0), run_time=D['T_PAIR'], rate_func=linear)
        self._pair_and_merge(D, sky, arrows=arrows, rmax=1.4, halo=((0.7, 0.6), (1.0, 0.35)))

    def construct_v3(self):
        c = ORIGIN
        R_DISC, R_TRAP, OMEGA = 3.8, 2.35, 0.95
        sky = lambda p: p
        # gas: a faint fill plus differentially rotating dashed streamlines (Keplerian: faster inside)
        fill = Annulus(inner_radius=0.7, outer_radius=R_DISC, color=self.accent, fill_opacity=0.07, stroke_width=0).move_to(c)
        lines = VGroup()
        for r in np.linspace(1.0, R_DISC - 0.1, 9):
            ln = DashedVMobject(Circle(radius=r, color=self.accent, stroke_width=1.6, stroke_opacity=0.45).move_to(c),
                                num_dashes=int(10 * r), dashed_ratio=0.6)
            ln.add_updater(lambda m, dt, r=r: m.rotate(OMEGA * (R_TRAP / r) ** 1.5 * dt, about_point=c))
            lines.add(ln)
        trap = Annulus(inner_radius=R_TRAP - 0.22, outer_radius=R_TRAP + 0.22, color=self.accent, fill_opacity=0.22, stroke_width=0).move_to(c)
        smbh = VGroup(Circle(radius=0.8, color=self.accent, stroke_width=3), Circle(radius=0.58, color=INK, fill_opacity=1, stroke_width=0)).move_to(c)
        self.add(fill, lines, trap, smbh)
        # five BHs: A, B (the future pair), plus three ring-dwellers ahead of the pair, all spiralling in with traced tracks
        extra = ((3.6, 1.9, 0.55, 0.15), (3.3, 3.1, 0.8, 0.0), (3.55, 4.3, 0.62, 0.3))
        D = self._bodies(c, R_TRAP, OMEGA, sky, rA=0.27, extra=extra)
        tracks = VGroup(*[TracedPath(f, stroke_color=self.accent, stroke_width=2, stroke_opacity=0.5, dissipating_time=1.6)
                          for f in (D['posA'], D['posB'], *D['opos'])])
        self.add(tracks, D['others'], D['A'], D['B'], D['C'])
        self.play(D['t'].animate.set_value(D['T_PAIR']), D['mig'].animate.set_value(1.0), run_time=D['T_PAIR'], rate_func=linear)
        self.remove(tracks[0], tracks[1])                # the pair's tracks would only scribble from here on
        self._pair_and_merge(D, sky, T_H=2.0)
