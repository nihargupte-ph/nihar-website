"""single-capture — single–single GW capture in a galactic nucleus (STORYBOARD.md).

Variant 1: wide view, SMBH at left with a swirling nucleus; hyperbolic flyby at right, capture, ellipses drawn live, merger.
Variant 2: close-up — only the SMBH's disc edge shows in the corner; larger BHs, wider flyby, and the whole capture is a persistent drawn track (flyby bending into shrinking loops), no ellipse overlay.
Variant 3: wide view with both BHs on the same (dashed) orbit around the SMBH; the trailing one catches up, capture happens on the ring and the bound pair keeps circling the SMBH while its wrapped ellipse shrinks.
Variant 4: variant 1's beats in a dense star cluster instead of a nucleus (no SMBH, no disc — just a slowly drifting dot cloud); the whole flyby → capture → loops is one Kepler-timed track whose clock is warped to linger ~1 s on every close passage, the GW bursts playing during the passages.
"""
import numpy as np
from manim import *
from style import *


class SingleCapture(ChannelScene):
    GROUP = 'dynamical'

    def construct(self):
        if VARIANT == 2:
            return self._v2()
        if VARIANT == 3:
            return self._v3()
        if VARIANT == 4:
            return self._v4()
        # 1. galactic nucleus: SMBH at left, a swarm of fast-moving dots orbiting it (faster closer in)
        smbh_c = np.array([-3.6, 0.4, 0])
        cloud = self.dot_cloud(n=520, sigma=2.4, center=smbh_c, seed=11, radius=0.028, opacity=0.32)
        polar = []
        for d in cloud:
            v = d.get_center() - smbh_c
            polar.append([np.hypot(v[0], v[1]), np.arctan2(v[1], v[0])])
        polar = np.array(polar)
        def swirl(m, dt):
            polar[:, 1] += dt * 0.9 / np.maximum(polar[:, 0], 0.6) ** 1.5
            for d, (r, ph) in zip(m, polar):
                d.move_to(smbh_c + np.array([r * np.cos(ph), r * np.sin(ph), 0]))
        cloud.add_updater(swirl)
        smbh = VGroup(Circle(radius=1.3, color=self.accent, stroke_width=2, stroke_opacity=0.6).move_to(smbh_c),
                      Circle(radius=0.95, color=INK, fill_opacity=1, stroke_width=0).move_to(smbh_c))
        self.add(cloud, smbh)

        # 2. two unbound BHs on a hyperbolic flyby (relative orbit e=1.6), bodies at ±½ of the relative vector
        c = np.array([2.4, -0.2, 0])
        tilt = 0.5
        e_h, rp = 1.6, 0.28
        a_h = rp / (e_h - 1)
        th0 = -np.arccos((a_h * (e_h * e_h - 1) / 6.5 - 1) / e_h)      # start with the pair 6.5 units apart
        th_tab, t_tab = anomaly_table(e_h, th0, 0.0)
        s = ValueTracker(0.0)
        rel = lambda: conic_point(a_h, e_h, np.interp(s.get_value(), t_tab, th_tab), ORIGIN, tilt)
        bh1, bh2 = self.bh(0.3), self.bh(0.3)
        bh1.add_updater(lambda m: m.move_to(c + 0.5 * rel())); bh2.add_updater(lambda m: m.move_to(c - 0.5 * rel()))
        bh1.set_z_index(2); bh2.set_z_index(2)
        trails = [TracedPath(b[1].get_center, stroke_color=self.accent, stroke_width=2, stroke_opacity=0.5, dissipating_time=2.5) for b in (bh1, bh2)]
        self.add(*trails, bh1, bh2)
        self.wait(0.6)
        self.play(s.animate.set_value(1.0), run_time=2.6, rate_func=linear)
        bh1.clear_updaters(); bh2.clear_updaters()

        # 3. GW burst at pericentre: the outgoing path bends back into a bound, e→1 orbit
        a, e, M = ValueTracker(rp / (1 - 0.92)), ValueTracker(0.92), ValueTracker(0.0)
        def rel_b():
            return conic_point(a.get_value(), e.get_value(), true_anomaly(M.get_value(), e.get_value()), ORIGIN, tilt)
        bh1.add_updater(lambda m: m.move_to(c + 0.5 * rel_b())); bh2.add_updater(lambda m: m.move_to(c - 0.5 * rel_b()))
        ell = lambda k: orbit_curve(a.get_value() / 2, e.get_value(), c, tilt + k * np.pi, self.accent, stroke_width=2, opacity=0.55)
        orb = [ell(0), ell(1)]
        for k, o in enumerate(orb):
            o.add_updater(lambda m, k=k: m.become(ell(k)))
        rings, burst = gw_rings(c, self.accent, rmax=1.4)
        self.add(rings)
        self.play(burst, M.animate(rate_func=linear).set_value(0.4 * np.pi), run_time=1.0)
        self.remove(rings)
        self.play(FadeIn(orb[0]), FadeIn(orb[1]), M.animate(rate_func=linear).increment_value(0.2 * np.pi), run_time=0.4)
        # 4. a few loops: a burst at every pericentre, the orbit shrinking fast
        for k, (a_new, e_new, rt) in enumerate([(2.2, 0.88, 2.0), (1.4, 0.82, 1.5), (0.95, 0.75, 1.1)]):
            self.play(M.animate.increment_value(2 * np.pi - (0.6 if k == 0 else 0.4) * np.pi), a.animate.set_value(a_new), e.animate.set_value(e_new),
                      run_time=rt, rate_func=linear)
            if k < 2:
                rings, burst = gw_rings(c, self.accent, rmax=1.0)
                self.add(rings)
                self.play(burst, M.animate(rate_func=linear).increment_value(0.4 * np.pi), run_time=0.45)
                self.remove(rings)
                if k == 0:
                    self.remove(*trails)
        # 5. merger; last thin ellipse stays faint for the card face
        for m in (bh1, bh2, *orb):
            m.clear_updaters()
        self.remove(*trails)
        for o in orb:
            o.set_stroke(opacity=0.45)
        remnant = self.bh(0.38, c)
        rings = VGroup(*[Circle(radius=0.05, color=self.accent, stroke_width=3, stroke_opacity=0.9).move_to(c) for _ in range(3)])
        self.play(Transform(bh1, remnant), Transform(bh2, remnant), run_time=0.25)
        self.remove(bh2)
        self.play(LaggedStart(*[r.animate(rate_func=linear).scale(1.5 / 0.05 * (0.55 + 0.15 * i)).set_stroke(opacity=0.5) for i, r in enumerate(rings)], lag_ratio=0.25), run_time=0.9)
        self.wait(0.2)

    # ---- variant 2: close-up beside the SMBH, the capture drawn as a persistent track ---------------------------
    def _v2(self):
        # the nucleus is implied: the SMBH's disc edge fills the lower-left corner, dots stream around it
        smbh_c = np.array([-7.0, -4.4, 0])
        rng = np.random.default_rng(12)
        polar = np.stack([rng.uniform(3.7, 13.0, 520), rng.uniform(-0.15, 1.7, 520)], axis=1)
        cloud = VGroup(*[Dot(smbh_c + np.array([r * np.cos(ph), r * np.sin(ph), 0]), radius=0.03, color=INK, fill_opacity=0.3) for r, ph in polar])
        def swirl(m, dt):
            polar[:, 1] += dt * 2.6 / polar[:, 0] ** 1.5
            for d, (r, ph) in zip(m, polar):
                d.move_to(smbh_c + np.array([r * np.cos(ph), r * np.sin(ph), 0]))
        cloud.add_updater(swirl)
        smbh = VGroup(Circle(radius=3.4, color=self.accent, stroke_width=2.5, stroke_opacity=0.6).move_to(smbh_c),
                      Circle(radius=3.0, color=INK, fill_opacity=1, stroke_width=0).move_to(smbh_c))
        self.add(cloud, smbh)

        # two unbound BHs, a wide hyperbolic flyby; their tracks are kept for the whole clip (no ellipse overlay)
        c = np.array([1.2, 0.3, 0])
        tilt = -0.75
        e_h, rp = 1.5, 0.32
        a_h = rp / (e_h - 1)
        th0 = -np.arccos((a_h * (e_h * e_h - 1) / 8.0 - 1) / e_h)
        th_tab, t_tab = anomaly_table(e_h, th0, 0.0)
        s = ValueTracker(0.0)
        rel = lambda: conic_point(a_h, e_h, np.interp(s.get_value(), t_tab, th_tab), ORIGIN, tilt)
        bh1, bh2 = self.bh(0.36), self.bh(0.36)
        bh1.add_updater(lambda m: m.move_to(c + 0.5 * rel())); bh2.add_updater(lambda m: m.move_to(c - 0.5 * rel()))
        bh1.set_z_index(2); bh2.set_z_index(2); bh1.update(0); bh2.update(0)
        tracks = [TracedPath(b[1].get_center, stroke_color=self.accent, stroke_width=1.8, stroke_opacity=0.45) for b in (bh1, bh2)]
        self.add(*tracks, bh1, bh2)
        self.wait(0.4)
        self.play(s.animate.set_value(1.0), run_time=2.4, rate_func=linear)
        bh1.clear_updaters(); bh2.clear_updaters()

        # GW burst at pericentre bends the outgoing paths back into a bound, e→1 orbit
        a, e, M = ValueTracker(rp / (1 - 0.92)), ValueTracker(0.92), ValueTracker(0.0)
        def rel_b():
            return conic_point(a.get_value(), e.get_value(), true_anomaly(M.get_value(), e.get_value()), ORIGIN, tilt)
        bh1.add_updater(lambda m: m.move_to(c + 0.5 * rel_b())); bh2.add_updater(lambda m: m.move_to(c - 0.5 * rel_b()))
        rings, burst = gw_rings(c, self.accent, rmax=1.7)
        self.add(rings)
        self.play(burst, M.animate(rate_func=linear).set_value(0.6 * np.pi), run_time=1.1)
        self.remove(rings)
        # a few loops, a burst at every pericentre, the drawn loops shrinking fast
        for k, (a_new, e_new, rt) in enumerate([(2.4, 0.88, 2.0), (1.5, 0.82, 1.5), (1.0, 0.75, 1.1)]):
            self.play(M.animate.increment_value(2 * np.pi - (0.6 if k == 0 else 0.4) * np.pi), a.animate.set_value(a_new), e.animate.set_value(e_new),
                      run_time=rt, rate_func=linear)
            if k < 2:
                rings, burst = gw_rings(c, self.accent, rmax=1.1)
                self.add(rings)
                self.play(burst, M.animate(rate_func=linear).increment_value(0.4 * np.pi), run_time=0.45)
                self.remove(rings)
        # merger; the whole drawn track (flyby + shrinking loops) stays as the card face
        for m in (bh1, bh2, *tracks):
            m.clear_updaters()
        for t in tracks:
            t.set_stroke(opacity=0.35)
        remnant = self.bh(0.42, c)
        rings = VGroup(*[Circle(radius=0.05, color=self.accent, stroke_width=3, stroke_opacity=0.9).move_to(c) for _ in range(3)])
        self.play(Transform(bh1, remnant), Transform(bh2, remnant), run_time=0.25)
        self.remove(bh2)
        self.play(LaggedStart(*[r.animate(rate_func=linear).scale(1.5 / 0.05 * (0.55 + 0.15 * i)).set_stroke(opacity=0.5) for i, r in enumerate(rings)], lag_ratio=0.25), run_time=0.9)
        self.wait(0.2)

    # ---- variant 3: wide view, both BHs on the same orbit around the SMBH; capture happens on the ring ----------
    def _v3(self):
        S_c, R = np.array([-1.6, -0.8, 0]), 3.3
        cloud = self.dot_cloud(n=560, sigma=2.5, center=S_c, seed=11, radius=0.028, opacity=0.32)
        polar = []
        for d in cloud:
            v = d.get_center() - S_c
            polar.append([np.hypot(v[0], v[1]), np.arctan2(v[1], v[0])])
        polar = np.array(polar)
        def swirl(m, dt):
            polar[:, 1] += dt * 0.9 / np.maximum(polar[:, 0], 0.6) ** 1.5
            for d, (r, ph) in zip(m, polar):
                d.move_to(S_c + np.array([r * np.cos(ph), r * np.sin(ph), 0]))
        cloud.add_updater(swirl)
        smbh = VGroup(Circle(radius=1.15, color=self.accent, stroke_width=2, stroke_opacity=0.6).move_to(S_c),
                      Circle(radius=0.85, color=INK, fill_opacity=1, stroke_width=0).move_to(S_c))
        ring = DashedVMobject(Circle(radius=R, color=INK, stroke_width=1.2, stroke_opacity=0.3).move_to(S_c), num_dashes=60)
        self.add(cloud, smbh, ring)

        # the pair's relative motion (hyperbola, then bound ellipse) is wrapped onto the ring: x → along it, y → radial
        th = ValueTracker(-0.55)                                   # angle of the pair's centre around the SMBH
        def wrap(p, sign):
            ang = th.get_value() + sign * p[0] / R
            r = R + sign * p[1]
            return S_c + r * np.array([np.cos(ang), np.sin(ang), 0])
        tilt = -0.6
        e_h, rp = 1.6, 0.26
        a_h = rp / (e_h - 1)
        th0 = -np.arccos((a_h * (e_h * e_h - 1) / 4.5 - 1) / e_h)
        th_tab, t_tab = anomaly_table(e_h, th0, 0.0)
        s = ValueTracker(0.0)
        rel = lambda: conic_point(a_h, e_h, np.interp(s.get_value(), t_tab, th_tab), ORIGIN, tilt)
        bh1, bh2 = self.bh(0.3), self.bh(0.3)
        bh1.add_updater(lambda m: m.move_to(wrap(0.5 * rel(), 1))); bh2.add_updater(lambda m: m.move_to(wrap(0.5 * rel(), -1)))
        bh1.set_z_index(2); bh2.set_z_index(2); bh1.update(0); bh2.update(0)
        trails = [TracedPath(b[1].get_center, stroke_color=self.accent, stroke_width=2, stroke_opacity=0.5, dissipating_time=2.5) for b in (bh1, bh2)]
        self.add(*trails, bh1, bh2)
        # 1. the trailing BH catches up with the leading one as both circle the SMBH
        self.wait(0.4)
        self.play(s.animate.set_value(1.0), th.animate.set_value(-0.05), run_time=2.6, rate_func=linear)
        bh1.clear_updaters(); bh2.clear_updaters()

        # 2. GW burst at the close pass binds them; the pair keeps circling the SMBH while its own orbit shrinks
        a, e, M = ValueTracker(rp / (1 - 0.9)), ValueTracker(0.9), ValueTracker(0.0)
        def rel_b():
            return conic_point(a.get_value(), e.get_value(), true_anomaly(M.get_value(), e.get_value()), ORIGIN, tilt)
        bh1.add_updater(lambda m: m.move_to(wrap(0.5 * rel_b(), 1))); bh2.add_updater(lambda m: m.move_to(wrap(0.5 * rel_b(), -1)))
        def ell(sign):
            E = np.linspace(0, 2 * np.pi, 200)
            ev = e.get_value()
            thv = 2 * np.arctan2(np.sqrt(1 + ev) * np.sin(E / 2), np.sqrt(1 - ev) * np.cos(E / 2))
            pts = [wrap(conic_point(a.get_value() / 2, ev, t, ORIGIN, tilt), sign) for t in thv]
            m = VMobject(stroke_color=self.accent, stroke_width=2, stroke_opacity=0.55)
            m.set_points_as_corners(pts + [pts[0]])
            return m
        orb = [ell(1), ell(-1)]
        for sign, o in zip((1, -1), orb):
            o.add_updater(lambda m, sign=sign: m.become(ell(sign)))
        com = lambda: wrap(ORIGIN, 1)
        rings, burst = gw_rings(com(), self.accent, rmax=1.4)
        self.add(rings)
        self.play(burst, M.animate(rate_func=linear).set_value(0.4 * np.pi), th.animate(rate_func=linear).increment_value(0.03), run_time=1.0)
        self.remove(rings)
        self.play(FadeIn(orb[0]), FadeIn(orb[1]), M.animate(rate_func=linear).increment_value(0.2 * np.pi), run_time=0.4)
        for k, (a_new, e_new, rt) in enumerate([(1.7, 0.86, 2.0), (1.15, 0.8, 1.5), (0.8, 0.72, 1.1)]):
            self.play(M.animate.increment_value(2 * np.pi - (0.6 if k == 0 else 0.4) * np.pi), a.animate.set_value(a_new), e.animate.set_value(e_new),
                      th.animate.increment_value(0.12), run_time=rt, rate_func=linear)
            if k < 2:
                rings, burst = gw_rings(com(), self.accent, rmax=1.0)
                self.add(rings)
                self.play(burst, M.animate(rate_func=linear).increment_value(0.4 * np.pi), th.animate(rate_func=linear).increment_value(0.03), run_time=0.45)
                self.remove(rings)
                if k == 0:
                    self.remove(*trails)
        # 3. merger on the ring; the last thin ellipse stays faint
        c_end = com()
        for m in (bh1, bh2, *orb):
            m.clear_updaters()
        self.remove(*trails)
        for o in orb:
            o.set_stroke(opacity=0.45)
        remnant = self.bh(0.38, c_end)
        rings = VGroup(*[Circle(radius=0.05, color=self.accent, stroke_width=3, stroke_opacity=0.9).move_to(c_end) for _ in range(3)])
        self.play(Transform(bh1, remnant), Transform(bh2, remnant), run_time=0.25)
        self.remove(bh2)
        self.play(LaggedStart(*[r.animate(rate_func=linear).scale(1.5 / 0.05 * (0.55 + 0.15 * i)).set_stroke(opacity=0.5) for i, r in enumerate(rings)], lag_ratio=0.25), run_time=0.9)
        self.wait(0.2)

    # ---- variant 4: dense star cluster, one time-warped Kepler track that lingers on every close passage ---------
    def _v4(self):
        # dense star cluster: a centred dot cloud with a slow random drift, nothing else
        cloud = self.dot_cloud(n=350, sigma=2.2, center=ORIGIN, seed=21, radius=0.028, opacity=0.32)
        vel = np.random.default_rng(7).normal(0, 0.05, size=(len(cloud), 2))
        def drift(m, dt):
            for d, (vx, vy) in zip(m, vel):
                d.shift(np.array([vx * dt, vy * dt, 0]))
        cloud.add_updater(drift)
        self.add(cloud)

        c, tilt = ORIGIN, -0.6
        rel, cost, T, peri, u_split = v4_track(tilt)
        u = ValueTracker(0.0)
        bh1, bh2 = self.bh(0.3), self.bh(0.3)
        bh1.add_updater(lambda m: m.move_to(c + 0.5 * rel(u.get_value())[0]))
        bh2.add_updater(lambda m: m.move_to(c - 0.5 * rel(u.get_value())[0]))
        bh1.set_z_index(2); bh2.set_z_index(2); bh1.update(0); bh2.update(0)
        trails = [TracedPath(b[1].get_center, stroke_color=self.accent, stroke_width=2, stroke_opacity=0.5, dissipating_time=2.0) for b in (bh1, bh2)]
        # the pair's ellipses (each body's own, focus at the COM) fade in once the pair is bound
        def ell(k):
            _, a, e, M = rel(u.get_value())
            op = 0.55 * float(np.clip((M - 0.45 * np.pi) / (0.25 * np.pi), 0, 1))
            if op <= 0:
                return VMobject()
            return orbit_curve(a / 2, e, c, tilt + k * np.pi, self.accent, stroke_width=2, opacity=op)
        orb = [ell(0), ell(1)]
        for k, o in enumerate(orb):
            o.add_updater(lambda m, k=k: m.become(ell(k)))
        self.add(*trails, *orb, bh1, bh2)
        self.wait(0.5)

        # one warped clock for flyby -> capture -> loops, split at a calm far-apart moment to drop the trails;
        # a GW burst starts just before each pericentre so the rings expand during the slowed passage
        n = len(cost)
        for (u0, u1) in ((0.0, u_split), (u_split, 1.0)):
            i0, i1 = int(round(u0 * (n - 1))), int(round(u1 * (n - 1)))
            seg = cost[i0:i1 + 1]
            rf, mean = dwell_rate(seg)
            rt = float(mean * (u1 - u0))          # cost is in seconds per unit u, so this segment's real time
            anims = [u.animate(rate_func=rf).set_value(u1)]
            bursts = []
            for up in peri:
                if u0 <= up < u1:
                    t_p = dwell_time(seg, (up - u0) / (u1 - u0)) * rt
                    rings, burst = gw_rings_follow(self, c, rmax=1.4 if up == peri[0] else 1.0, run_time=0.9)
                    bursts.append(rings)
                    anims.append(at_time(burst, max(t_p - 0.3, 0), rt))
            self.play(*anims, run_time=rt)
            self.remove(*trails, *bursts)
        # merger; last thin ellipse stays faint for the card face
        for m in (bh1, bh2, *orb):
            m.clear_updaters()
        for o in orb:
            o.set_stroke(opacity=0.45)
        remnant = self.bh(0.38, c)
        rings = VGroup(*[Circle(radius=0.05, color=self.accent, stroke_width=3, stroke_opacity=0.9).move_to(c) for _ in range(3)])
        self.play(Transform(bh1, remnant), Transform(bh2, remnant), run_time=0.25)
        self.remove(bh2)
        self.play(LaggedStart(*[r.animate(rate_func=linear).scale(1.5 / 0.05 * (0.55 + 0.15 * i)).set_stroke(opacity=0.5) for i, r in enumerate(rings)], lag_ratio=0.25), run_time=0.9)
        self.wait(0.2)


def v4_track(tilt=-0.6, T_hyp=3.0, T_bound=6.5, rp=0.7, e_h=1.6, sep0=6.5, v_cap=1.5, n=6000):
    """Variant 4's relative orbit as one function of a clock u in [0, 1]: u < 1/2 is the hyperbolic flyby
    (Kepler-timed via anomaly_table, ending at pericentre), u >= 1/2 the bound phase with M = 0..6pi and the
    (a, e) shrinking piecewise-linearly in M as in variant 1. Returns (rel(u) -> (point, a, e, M), cost,
    total run_time, clock values of the pericentres, clock value of a calm far-apart split point).
    `cost` is the real-time density over u (seconds per unit u): the Kepler pace, slowed wherever a body would
    move faster than `v_cap` units/s on screen, so that every close passage lingers."""
    a_h = rp / (e_h - 1)
    th0 = -np.arccos((a_h * (e_h * e_h - 1) / sep0 - 1) / e_h)
    th_tab, t_tab = anomaly_table(e_h, th0, 0.0)
    e0 = 0.81
    a0 = rp / (1 - e0)
    Mk = np.array([0, 0.6, 2.0, 2.4, 4.0, 4.4, 6.0]) * np.pi
    ak = [a0, a0, 2.4, 2.4, 1.5, 1.5, 1.0]
    ek = [e0, e0, 0.76, 0.76, 0.70, 0.70, 0.62]
    def rel(uv):
        if uv < 0.5:
            th = np.interp(2 * uv, t_tab, th_tab)
            return conic_point(a_h, e_h, th, ORIGIN, tilt), a_h, e_h, -1.0
        M = (2 * uv - 1) * 6 * np.pi
        a, e = np.interp(M, Mk, ak), np.interp(M, Mk, ek)
        return conic_point(a, e, kepler_nu(M, e), ORIGIN, tilt), a, e, M
    uu = np.linspace(0, 1, n)
    pts = np.array([0.5 * rel(v)[0] for v in uu])                  # one body's track
    base = np.where(uu < 0.5, T_hyp / 0.5, T_bound / 0.5)          # seconds per unit u at the Kepler pace
    cost = speed_dwell(pts, base, v_cap)
    T = float(np.trapezoid(cost, uu))
    peri = [0.5] + [0.5 + m / (12 * np.pi) for m in (2 * np.pi, 4 * np.pi)]
    u_split = 0.5 + 1.2 * np.pi / (12 * np.pi)
    return rel, cost, T, peri, u_split
