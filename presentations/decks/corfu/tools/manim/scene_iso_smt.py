"""iso-smt — stable mass transfer (STORYBOARD.md).

Variant 1: inertial view of the orbiting pair; Roche lobes appear per phase; thin stream + solid disc ellipse.
Variant 2: close-up in the co-rotating frame (background star field drifts round): the figure-of-eight Roche lobes stay
           fixed, gas is a swarm of particles trickling through L1 and swirling into a disc; the pair separates smoothly.
Variant 3: wide view with the centre of mass marked and both orbit circles drawn: as mass flows the circles swap sizes
           (mass-ratio reversal) and grow smoothly — the orbit track is the emphasis, not the gas.
"""
import numpy as np
from manim import *
from style import *

CORE_BLUE = '#cfe3f7'


class IsoSMT(ChannelScene):
    GROUP = 'field'

    def construct(self):
        if VARIANT == 2:
            return self.construct_v2()
        if VARIANT == 3:
            return self.construct_v3()
        c = ORIGIN
        sep = ValueTracker(4.0)                    # separation; primary sits at -0.4·sep, secondary at +0.6·sep
        r1 = ValueTracker(0.7); r2 = ValueTracker(0.5)
        t = ValueTracker(np.pi)                    # orbital phase of the primary (π = left)

        def pos1():
            return c + 0.4 * sep.get_value() * np.array([np.cos(t.get_value()), np.sin(t.get_value()), 0])
        def pos2():
            return c - 0.6 * sep.get_value() * np.array([np.cos(t.get_value()), np.sin(t.get_value()), 0])
        def sized(m, r, p):
            m[0].set(width=2 * (r + 0.32)).move_to(p); m[1].set(width=2 * r).move_to(p)

        primary = self.star(0.7, STAR_BLUE, pos1()); secondary = self.star(0.5, STAR_BLUE, pos2())
        primary.add_updater(lambda m: sized(m, r1.get_value(), pos1()))
        secondary.add_updater(lambda m: sized(m, r2.get_value(), pos2()))
        primary[1].set_z_index(2); secondary[1].set_z_index(2)
        self.add(primary, secondary)
        # 1. a quiet wide orbit
        self.play(t.animate.increment_value(2 * np.pi), run_time=1.4, rate_func=linear)

        # ---- helpers for a mass-transfer phase (donor on one side, accretor on the other) ----
        def transfer_phase(donor_pos, acc_pos, m_donor, m_acc, r_donor, r_acc, r_fill, r_after, sep_to, acc_color, acc_is_bh):
            # Roche lobes at unit separation, scaled to the live separation each frame
            base1, l1 = roche_lobe_points(m_donor, m_acc, 1.0, 1); base2, _ = roche_lobe_points(m_donor, m_acc, 1.0, 2)
            sign = 1.0 if acc_pos()[0] > donor_pos()[0] else -1.0
            def lobe_pts(base):
                s = sep.get_value(); d = donor_pos()
                return [d + np.array([sign * p[0] * s, p[1] * s, 0]) for p in base]
            lobes = VGroup(*[VMobject(stroke_color=INK, stroke_width=1.3, stroke_opacity=0.0) for _ in range(2)])
            lobes[0].add_updater(lambda m: m.set_points_smoothly(lobe_pts(base1) + [lobe_pts(base1)[0]]))
            lobes[1].add_updater(lambda m: m.set_points_smoothly(lobe_pts(base2) + [lobe_pts(base2)[0]]))
            L1 = lambda: donor_pos() + np.array([sign * l1[0] * sep.get_value(), 0, 0])
            self.add(lobes)
            lobe_op = ValueTracker(0)
            lobes[0].add_updater(lambda m: m.set_stroke(opacity=0.4 * lobe_op.get_value()))
            lobes[1].add_updater(lambda m: m.set_stroke(opacity=0.4 * lobe_op.get_value()))
            # donor swells to fill its lobe and turns orange
            self.play(lobe_op.animate.set_value(1), run_time=0.3)
            donor = primary if donor_pos is pos1 else secondary
            donor[1].set_color(STAR_ORANGE); donor[0].set_color(STAR_ORANGE)
            self.play(r_donor.animate.set_value(r_fill * sep.get_value()), run_time=1.0, rate_func=smooth)
            # stream from L1 and a disc around the accretor
            disc_w = ValueTracker(0.01)
            disc = Ellipse(width=0.01, height=0.006, color=GAS, fill_opacity=0.55, stroke_width=0)
            disc.add_updater(lambda m: m.set(width=disc_w.get_value()).set(height=0.6 * disc_w.get_value()).move_to(acc_pos()))
            disc.set_z_index(1)
            stream = VMobject(stroke_color=GAS, stroke_width=5, stroke_opacity=0.9)
            def stream_pts():
                a = L1(); b = acc_pos(); v = b - a; n = np.array([-v[1], v[0], 0]) / (np.linalg.norm(v) + 1e-9)
                end = b - 0.42 * disc_w.get_value() * np.array([sign, 0, 0]) - 0.12 * disc_w.get_value() * n
                return [a, a + 0.4 * v - 0.55 * n, a + 0.75 * v - 0.75 * n, end]
            stream.add_updater(lambda m: m.set_points([p for p in stream_pts()]))
            stream.set_points(stream_pts())
            self.add(disc, stream)
            # gas blobs riding the stream
            ph = ValueTracker(0)
            blobs = VGroup(*[Dot(radius=0.07, color=STAR_ORANGE, fill_opacity=0.9) for _ in range(4)])
            for i, b in enumerate(blobs):
                b.add_updater(lambda m, i=i: m.move_to(stream.point_from_proportion((ph.get_value() + i / 4) % 1)))
            self.add(blobs)
            # stable transfer: thin stream, donor shrinks back gently, accretor grows, orbit changes smoothly
            self.play(disc_w.animate.set_value(2.6), ph.animate.increment_value(2.5), r_donor.animate.set_value(r_fill * sep.get_value() * 0.85),
                      r_acc.animate.set_value(r_acc.get_value() * 1.25), sep.animate.set_value(sep_to), run_time=1.9, rate_func=linear)
            # transfer ends: the stripped donor shrinks to a compact helium core
            self.play(FadeOut(stream), FadeOut(blobs), FadeOut(disc), lobe_op.animate.set_value(0), r_donor.animate.set_value(r_after), run_time=0.7)
            self.remove(stream, blobs, disc, lobes)
            donor[1].set_color(CORE_BLUE); donor[0].set_color(STAR_BLUE)

        # 2. primary fills its Roche lobe; stable transfer onto the companion; orbit widens smoothly
        transfer_phase(pos1, pos2, 1.5, 1.0, r1, r2, 0.36, 0.42, 4.6, STAR_BLUE, False)
        # 3. the stripped primary collapses to a black hole
        primary.clear_updaters()
        primary = self.collapse(primary, 0.28); primary.set_z_index(2)
        primary.add_updater(lambda m: m.move_to(pos1()))
        self.play(t.animate.increment_value(np.pi), run_time=0.8, rate_func=linear)      # half an orbit: BH on the right, star on the left
        # 4. the secondary evolves and feeds a disc around the black hole
        transfer_phase(pos2, pos1, 1.2, 0.9, r2, r1, 0.33, 0.35, 4.9, INK, True)
        # 5. second collapse: two black holes on a wide circular orbit, shrinking very slowly
        secondary.clear_updaters()
        secondary = self.collapse(secondary, 0.34)
        secondary.add_updater(lambda m: m.move_to(pos2()))
        ring = Circle(radius=0.6 * sep.get_value(), color=self.accent, stroke_width=1.5, stroke_opacity=0.5).move_to(c)
        ring.add_updater(lambda m: m.set(width=1.2 * sep.get_value()).move_to(c))
        self.add(ring)
        self.play(t.animate.increment_value(2 * np.pi), sep.animate.set_value(4.5), run_time=1.8, rate_func=linear)
        self.wait(0.2)

    # ---- variant 2: co-rotating close-up, particle gas -------------------------------------------
    def construct_v2(self):
        c = ORIGIN
        sep = ValueTracker(5.4)
        r1 = ValueTracker(0.9); r2 = ValueTracker(0.62)
        frame = ValueTracker(0.0)                  # rotation of the inertial background as seen from the co-rotating frame
        def pos1():
            return c + LEFT * 0.45 * sep.get_value()
        def pos2():
            return c + RIGHT * 0.55 * sep.get_value()
        def sized(m, r, p):
            m[0].set(width=2 * (r + 0.32)).move_to(p); m[1].set(width=2 * r).move_to(p)
        # distant stars drifting round: the cue that we ride with the binary
        bg = self.dot_cloud(n=70, sigma=4.5, seed=7, radius=0.035, opacity=0.3)
        bg0 = [d.get_center().copy() for d in bg]
        def bg_upd(m):
            a = frame.get_value(); R = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
            for d, p in zip(m, bg0):
                d.move_to(R @ p)
        bg.add_updater(bg_upd)
        primary = self.star(0.9, STAR_BLUE, pos1()); secondary = self.star(0.62, STAR_BLUE, pos2())
        primary.add_updater(lambda m: sized(m, r1.get_value(), pos1()))
        secondary.add_updater(lambda m: sized(m, r2.get_value(), pos2()))
        primary[1].set_z_index(3); secondary[1].set_z_index(3)
        self.add(bg, primary, secondary)
        self.play(frame.animate.increment_value(-0.6 * np.pi), run_time=0.8, rate_func=linear)

        def transfer_phase(donor_pos, acc_pos, m_donor, m_acc, r_donor, r_acc, r_fill, r_after, sep_to, dt):
            base1, l1 = roche_lobe_points(m_donor, m_acc, 1.0, 1); base2, _ = roche_lobe_points(m_donor, m_acc, 1.0, 2)
            sign = 1.0 if acc_pos()[0] > donor_pos()[0] else -1.0
            def lobe_pts(base):
                s = sep.get_value(); d = donor_pos()
                return [d + np.array([sign * p[0] * s, p[1] * s, 0]) for p in base]
            lobes = VGroup(*[VMobject(stroke_color=INK, stroke_width=1.4, stroke_opacity=0.0) for _ in range(2)])
            lobe_op = ValueTracker(0)
            lobes[0].add_updater(lambda m: m.set_points_smoothly(lobe_pts(base1) + [lobe_pts(base1)[0]]).set_stroke(opacity=0.45 * lobe_op.get_value()))
            lobes[1].add_updater(lambda m: m.set_points_smoothly(lobe_pts(base2) + [lobe_pts(base2)[0]]).set_stroke(opacity=0.45 * lobe_op.get_value()))
            L1 = lambda: donor_pos() + np.array([sign * l1[0] * sep.get_value(), 0, 0])
            self.add(lobes)
            donor = primary if donor_pos is pos1 else secondary
            self.play(lobe_op.animate.set_value(1), frame.animate.increment_value(-0.3 * np.pi), run_time=0.4, rate_func=linear)
            donor[1].set_color(STAR_ORANGE); donor[0].set_color(STAR_ORANGE)
            self.play(r_donor.animate.set_value(r_fill * sep.get_value()), frame.animate.increment_value(-0.7 * np.pi), run_time=1.0, rate_func=linear)
            # gas particles: through L1 along a curved stream, then swirling round the accretor as a disc
            rng = np.random.default_rng(11)
            NS, ND = 22, 80
            ph = ValueTracker(0.0); disc_R = ValueTracker(0.05); gop = ValueTracker(0.0)
            s_off = rng.uniform(0, 1, NS); s_jit = rng.normal(0, 0.06, (NS, 2))
            d_rf = np.sqrt(rng.uniform(0.15, 1.0, ND)); d_ang = rng.uniform(0, 2 * np.pi, ND); d_om = 1.6 / d_rf ** 1.5
            def stream_pt(u):
                a = L1(); b = acc_pos(); v = b - a; n = np.array([-v[1], v[0], 0]) / (np.linalg.norm(v) + 1e-9)
                p0, p1, p2, p3 = a, a + 0.35 * v - 0.55 * n, a + 0.7 * v - 0.75 * n, b - 0.95 * disc_R.get_value() * np.array([sign, 0, 0]) - 0.25 * disc_R.get_value() * n
                return bezier([p0, p1, p2, p3])(u)
            gas = VGroup(*[Dot(radius=0.085, color=STAR_ORANGE, fill_opacity=0.0) for _ in range(NS)],
                         *[Dot(radius=0.08, color=GAS, fill_opacity=0.0) for _ in range(ND)])
            def gas_upd(m):
                o = gop.get_value(); R = disc_R.get_value(); P = ph.get_value(); b = acc_pos()
                for i in range(NS):
                    u = (P * 0.5 + s_off[i]) % 1
                    m[i].move_to(stream_pt(u) + np.array([s_jit[i, 0], s_jit[i, 1], 0])).set_fill(opacity=0.9 * o)
                for j in range(ND):
                    th = d_ang[j] + P * d_om[j] * (1 if sign > 0 else -1)
                    m[NS + j].move_to(b + R * d_rf[j] * np.array([np.cos(th), 0.6 * np.sin(th), 0])).set_fill(opacity=0.85 * o)
            gas.add_updater(gas_upd); gas.set_z_index(2)
            self.add(gas)
            self.play(gop.animate.set_value(1), disc_R.animate.set_value(0.6), ph.animate.increment_value(0.6), frame.animate.increment_value(-0.3 * np.pi), run_time=0.4, rate_func=linear)
            self.play(disc_R.animate.set_value(1.7), ph.animate.increment_value(4.5), r_donor.animate.set_value(r_fill * sep.get_value() * 0.86),
                      r_acc.animate.set_value(r_acc.get_value() * 1.25), sep.animate.set_value(sep_to), frame.animate.increment_value(-1.6 * np.pi), run_time=dt, rate_func=linear)
            self.play(gop.animate.set_value(0), ph.animate.increment_value(0.8), lobe_op.animate.set_value(0), r_donor.animate.set_value(r_after), frame.animate.increment_value(-0.5 * np.pi), run_time=0.7, rate_func=linear)
            self.remove(gas, lobes)
            donor[1].set_color(CORE_BLUE); donor[0].set_color(STAR_BLUE)

        # 2. primary fills its lobe and feeds the companion; the pair drifts apart smoothly
        transfer_phase(pos1, pos2, 1.5, 1.0, r1, r2, 0.36, 0.5, 6.0, 2.0)
        # 3. collapse
        primary.clear_updaters()
        primary = self.collapse(primary, 0.3); primary.set_z_index(3)
        primary.add_updater(lambda m: m.move_to(pos1()))
        self.play(frame.animate.increment_value(-0.5 * np.pi), run_time=0.5, rate_func=linear)
        # 4. the secondary swells in turn and feeds a disc around the black hole
        transfer_phase(pos2, pos1, 1.2, 0.9, r2, r1, 0.33, 0.4, 6.4, 1.8)
        # 5. second collapse; leave the co-rotating frame: two BHs on a wide circular orbit
        secondary.clear_updaters()
        secondary = self.collapse(secondary, 0.36); secondary.set_z_index(3)
        t = ValueTracker(np.pi)
        primary.clear_updaters()
        primary.add_updater(lambda m: m.move_to(c + 0.45 * sep.get_value() * np.array([np.cos(t.get_value()), np.sin(t.get_value()), 0])))
        secondary.add_updater(lambda m: m.move_to(c - 0.55 * sep.get_value() * np.array([np.cos(t.get_value()), np.sin(t.get_value()), 0])))
        ring = Circle(radius=0.55 * sep.get_value(), color=self.accent, stroke_width=1.5, stroke_opacity=0.5).move_to(c)
        ring.add_updater(lambda m: m.set(width=1.1 * sep.get_value()).move_to(c))
        self.add(ring)
        self.play(t.animate.increment_value(2 * np.pi), sep.animate.set_value(6.0), run_time=2.0, rate_func=linear)
        self.wait(0.2)

    # ---- variant 3: wide view, centre of mass + orbit circles that swap with the mass ratio --------
    def construct_v3(self):
        c = ORIGIN
        sep = ValueTracker(3.8)
        m1 = ValueTracker(1.5); m2 = ValueTracker(1.0)
        r1 = ValueTracker(0.66); r2 = ValueTracker(0.48)
        t = ValueTracker(np.pi)
        def u():
            return np.array([np.cos(t.get_value()), np.sin(t.get_value()), 0])
        def f1():
            return m2.get_value() / (m1.get_value() + m2.get_value())
        def pos1():
            return c + f1() * sep.get_value() * u()
        def pos2():
            return c - (1 - f1()) * sep.get_value() * u()
        def sized(m, r, p):
            m[0].set(width=2 * (r + 0.32)).move_to(p); m[1].set(width=2 * r).move_to(p)
        # centre of mass and the two orbit circles (persist for the whole clip)
        cm = VGroup(Line(LEFT * 0.14, RIGHT * 0.14, color=INK, stroke_width=2), Line(DOWN * 0.14, UP * 0.14, color=INK, stroke_width=2)).move_to(c)
        orb1 = Circle(radius=1, color=self.accent, stroke_width=1.6, stroke_opacity=0.55).move_to(c)
        orb2 = Circle(radius=1, color=self.accent, stroke_width=1.6, stroke_opacity=0.55).move_to(c)
        orb1.add_updater(lambda m: m.set(width=2 * f1() * sep.get_value()).move_to(c))
        orb2.add_updater(lambda m: m.set(width=2 * (1 - f1()) * sep.get_value()).move_to(c))
        primary = self.star(0.66, STAR_BLUE, pos1()); secondary = self.star(0.48, STAR_BLUE, pos2())
        primary.add_updater(lambda m: sized(m, r1.get_value(), pos1()))
        secondary.add_updater(lambda m: sized(m, r2.get_value(), pos2()))
        primary[1].set_z_index(2); secondary[1].set_z_index(2)
        self.add(orb1, orb2, cm, primary, secondary)
        # 1. a quiet orbit about the centre of mass: the heavier star on the smaller circle
        self.play(t.animate.increment_value(2 * np.pi), run_time=1.6, rate_func=linear)

        def transfer_phase(donor_pos, acc_pos, m_d, m_a, r_donor, r_acc, r_fill, r_after, d_to, a_to, sep_to, dt, turns):
            donor = primary if donor_pos is pos1 else secondary
            base1, l1 = roche_lobe_points(m_d.get_value(), m_a.get_value(), 1.0, 1); base2, _ = roche_lobe_points(m_d.get_value(), m_a.get_value(), 1.0, 2)
            def lobe_pts(base):
                s = sep.get_value(); d = donor_pos(); v = acc_pos() - d; e = v / (np.linalg.norm(v) + 1e-9); n = np.array([-e[1], e[0], 0])
                return [d + p[0] * s * e + p[1] * s * n for p in base]
            lobe_op = ValueTracker(0)
            lobes = VGroup(*[VMobject(stroke_color=INK, stroke_width=1.2) for _ in range(2)])
            lobes[0].add_updater(lambda m: m.set_points_smoothly(lobe_pts(base1) + [lobe_pts(base1)[0]]).set_stroke(opacity=0.35 * lobe_op.get_value()))
            lobes[1].add_updater(lambda m: m.set_points_smoothly(lobe_pts(base2) + [lobe_pts(base2)[0]]).set_stroke(opacity=0.35 * lobe_op.get_value()))
            def L1():
                d = donor_pos(); v = acc_pos() - d; e = v / (np.linalg.norm(v) + 1e-9)
                return d + l1[0] * sep.get_value() * e
            self.add(lobes)
            self.play(lobe_op.animate.set_value(1), t.animate.increment_value(0.2 * np.pi), run_time=0.3, rate_func=linear)
            donor[1].set_color(STAR_ORANGE); donor[0].set_color(STAR_ORANGE)
            self.play(r_donor.animate.set_value(r_fill * sep.get_value()), t.animate.increment_value(0.5 * np.pi), run_time=0.8, rate_func=linear)
            disc_w = ValueTracker(0.01)
            disc = Circle(radius=0.01, color=GAS, fill_opacity=0.5, stroke_width=0)
            disc.add_updater(lambda m: m.set(width=disc_w.get_value()).move_to(acc_pos()))
            disc.set_z_index(1)
            stream = VMobject(stroke_color=GAS, stroke_width=4.5, stroke_opacity=0.9)
            def stream_pts():
                a = L1(); b = acc_pos(); v = b - a; n = np.array([-v[1], v[0], 0]) / (np.linalg.norm(v) + 1e-9)
                end = b - 0.45 * disc_w.get_value() * v / (np.linalg.norm(v) + 1e-9) - 0.15 * disc_w.get_value() * n
                return [a, a + 0.4 * v - 0.5 * n, a + 0.75 * v - 0.7 * n, end]
            stream.add_updater(lambda m: m.set_points(stream_pts()))
            self.add(disc, stream)
            # stable transfer: mass flows donor → accretor, the orbit circles swap size as the mass ratio reverses
            self.play(disc_w.animate.set_value(1.9), m_d.animate.set_value(d_to), m_a.animate.set_value(a_to), sep.animate.set_value(sep_to),
                      r_donor.animate.set_value(r_fill * sep.get_value() * 0.85), r_acc.animate.set_value(r_acc.get_value() * 1.3),
                      t.animate.increment_value(turns * 2 * np.pi), run_time=dt, rate_func=linear)
            self.play(FadeOut(stream), FadeOut(disc), lobe_op.animate.set_value(0), r_donor.animate.set_value(r_after), t.animate.increment_value(0.3 * np.pi), run_time=0.6, rate_func=linear)
            self.remove(stream, disc, lobes)
            donor[1].set_color(CORE_BLUE); donor[0].set_color(STAR_BLUE)

        # 2. primary → companion: q reverses, the primary's circle grows past the companion's, orbit widens
        transfer_phase(pos1, pos2, m1, m2, r1, r2, 0.36, 0.38, 0.55, 1.95, 4.6, 2.4, 1.0)
        # 3. first collapse
        primary.clear_updaters()
        primary = self.collapse(primary, 0.26); primary.set_z_index(2)
        primary.add_updater(lambda m: m.move_to(pos1()))
        self.play(t.animate.increment_value(0.6 * np.pi), run_time=0.5, rate_func=linear)
        # 4. companion → black hole: the black hole grows, circles swap back
        transfer_phase(pos2, pos1, m2, m1, r2, r1, 0.33, 0.34, 1.0, 1.4, 5.0, 2.0, 0.8)
        # 5. second collapse: two black holes on a wide circular orbit about the centre of mass
        secondary.clear_updaters()
        secondary = self.collapse(secondary, 0.3)
        secondary.add_updater(lambda m: m.move_to(pos2()))
        self.play(t.animate.increment_value(2 * np.pi), sep.animate.set_value(4.7), run_time=1.8, rate_func=linear)
        self.wait(0.2)
