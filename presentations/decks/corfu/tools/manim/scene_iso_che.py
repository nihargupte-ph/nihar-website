"""iso-che — chemically homogeneous evolution (STORYBOARD.md).

Variant 1: face-on tight binary; latitude bands + spin arrows; dashed orange ghost of the radius a normal star would reach.
Variant 2: close-up on the mixing: swirling current arcs inside each star (differential rotation), and the "normal star" is
           a translucent orange disc that swells right through the Roche lobes while the real stars stay compact.
Variant 3: inclined viewpoint: the orbit is seen as a foreshortened ellipse, stars drawn as globes with latitude bands and
           running dots for the spin, the final BH–BH orbit drawn as a tilted ellipse.
Variant 4: split comparison, no ghost: top half a *normal* binary (greyed) at the same separation whose stars swell, fill
           their Roche lobes and merge; bottom half the spun-up CHE binary that stays compact and blue and collapses to
           BHs on the same tight orbit. Thin horizontal divider.
Variant 5: no ghost at all: fixed orbit circle, swirling mixing currents inside the stars, which *shrink slightly* and go
           white-blue (helium burning) before collapsing; ends on the same tight circular BH orbit.
Variant 6: time-lapse: the same tight binary drawn three times left→right (main sequence with spin arrows → contracted
           helium stars → black holes) with faint arrows of time between; identical orbit circle in all three; the BH
           pair on the right animates its inspiral.
"""
import numpy as np
from manim import *
from style import *

HOT_BLUE = '#7fb0e0'
WHITE_BLUE = '#9cc3ea'


class IsoCHE(ChannelScene):
    GROUP = 'field'

    def construct(self):
        if VARIANT == 2:
            return self.construct_v2()
        if VARIANT == 3:
            return self.construct_v3()
        if VARIANT == 4:
            return self.construct_v4()
        if VARIANT == 5:
            return self.construct_v5()
        if VARIANT == 6:
            return self.construct_v6()
        c = ORIGIN
        half = 1.35                                   # half separation: a very tight orbit (~1–2 d)
        r0 = 0.62
        t = ValueTracker(0.0)                         # orbital phase
        spin = ValueTracker(0.0)                      # fast rotation of the tidally locked stars
        rs = ValueTracker(r0)

        def pos(k):
            return c + half * np.array([np.cos(t.get_value() + np.pi * k), np.sin(t.get_value() + np.pi * k), 0])

        def spin_arrow(r, ang, p):
            arc = Arc(radius=r + 0.16, start_angle=ang + 0.2, angle=2.6, color=INK, stroke_width=2.5, stroke_opacity=0.8)
            arc.add_tip(tip_length=0.18, tip_width=0.14)
            return arc.move_arc_center_to(p)

        def make_star(k):
            g = self.star(r0, STAR_BLUE, pos(k))
            bands = VGroup(*[Circle(radius=r0 * f, color=WHITE, stroke_width=1.5, stroke_opacity=0.45).move_to(pos(k)) for f in (0.42, 0.72)])
            arrow = spin_arrow(r0, 0.0, pos(k))
            grp = VGroup(g[0], g[1], bands, arrow)
            grp.k = k
            return grp

        def update_star(m):
            p = pos(m.k); r = rs.get_value()
            m[0].set(width=2 * (r + 0.32)).move_to(p); m[1].set(width=2 * r).move_to(p)
            m[2][0].set(width=2 * r * 0.42).move_to(p); m[2][1].set(width=2 * r * 0.72).move_to(p)
            m[3].become(spin_arrow(r, spin.get_value(), p))

        s1, s2 = make_star(0), make_star(1)
        for s in (s1, s2):
            s.add_updater(update_star)
        # faint Roche lobes rotating with the binary — the stars never fill them
        lobes, _ = roche_lobes(1.0, 1.0, 2 * half, center=c + LEFT * half, opacity=0.3)
        base = [v.points.copy() for v in lobes]
        def rot_lobes(m):
            a = t.get_value(); R = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
            for v, b in zip(m, base):
                v.set_points(b @ R.T)
        lobes.add_updater(rot_lobes)
        self.add(lobes, s1, s2)

        # 1. tight orbit, fast spin
        self.play(t.animate.increment_value(2 * np.pi), spin.animate.increment_value(6 * np.pi), run_time=1.6, rate_func=linear)

        # 2. a normal star would swell (dashed ghost) — these stay compact, mixed, blue-white
        g = ValueTracker(r0)
        ghosts = VGroup(*[VMobject() for _ in range(2)])
        def ghost_upd(m, k):
            circ = Circle(radius=g.get_value(), color=STAR_ORANGE, stroke_width=3.2).move_to(pos(k))
            m.become(DashedVMobject(circ, num_dashes=30, dashed_ratio=0.6)).set_stroke(opacity=0.85)
        ghosts[0].add_updater(lambda m: ghost_upd(m, 0)); ghosts[1].add_updater(lambda m: ghost_upd(m, 1))
        self.add(ghosts)
        col = ValueTracker(0)
        def tint(m):
            m[1].set_color(interpolate_color(ManimColor(STAR_BLUE), ManimColor(WHITE_BLUE), col.get_value()))
            m[0].set_color(interpolate_color(ManimColor(STAR_BLUE), ManimColor(HOT_BLUE), col.get_value()))
        s1.add_updater(tint); s2.add_updater(tint)
        self.play(g.animate.set_value(1.8), rs.animate.set_value(0.55), col.animate.set_value(1),
                  t.animate.increment_value(2.5 * np.pi), spin.animate.increment_value(7.5 * np.pi), run_time=3.0, rate_func=linear)
        self.play(t.animate.increment_value(np.pi), spin.animate.increment_value(3 * np.pi), run_time=0.8, rate_func=linear)
        # the ghosts (and the unused Roche lobes) fade: no expansion, no mass transfer
        fade = ValueTracker(1)
        ghosts[0].add_updater(lambda m: m.set_stroke(opacity=0.85 * fade.get_value()))
        ghosts[1].add_updater(lambda m: m.set_stroke(opacity=0.85 * fade.get_value()))
        lobes.add_updater(lambda m: m.set_stroke(opacity=0.3 * fade.get_value()))
        self.play(fade.animate.set_value(0), t.animate.increment_value(0.5 * np.pi), spin.animate.increment_value(1.5 * np.pi), run_time=0.6, rate_func=linear)
        self.remove(ghosts, lobes)

        # 3. both collapse in place (same orbit, same separation)
        s1.clear_updaters(); s2.clear_updaters()
        p1, p2 = s1[1].get_center(), s2[1].get_center()
        flashes = VGroup(*[Circle(radius=rs.get_value() * 2.4, color=WHITE, fill_opacity=0.9, stroke_width=0).move_to(p) for p in (p1, p2)])
        b1, b2 = self.bh(0.3, p1), self.bh(0.3, p2)
        self.play(FadeIn(flashes, run_time=0.15))
        self.play(FadeOut(flashes), Transform(s1, b1), Transform(s2, b2), run_time=0.45)
        # 4. tight circular BH–BH orbit, inspiralling slowly over Gyr
        a = ValueTracker(half)
        s1.add_updater(lambda m: m.move_to(c + a.get_value() * np.array([np.cos(t.get_value()), np.sin(t.get_value()), 0])))
        s2.add_updater(lambda m: m.move_to(c - a.get_value() * np.array([np.cos(t.get_value()), np.sin(t.get_value()), 0])))
        ring = Circle(radius=half, color=self.accent, stroke_width=1.5, stroke_opacity=0.5).move_to(c)
        ring.add_updater(lambda m: m.set(width=2 * a.get_value()).move_to(c))
        self.add(ring)
        self.play(t.animate.increment_value(4 * np.pi), a.animate.set_value(1.1), run_time=2.6, rate_func=linear)
        self.wait(0.2)

    # ---- variant 2: close-up on the mixing currents, filled ghost stars ----------------------------
    def construct_v2(self):
        c = ORIGIN
        half = 1.6
        r0 = 0.78
        t = ValueTracker(0.0); spin = ValueTracker(0.0); rs = ValueTracker(r0)

        def pos(k):
            return c + half * np.array([np.cos(t.get_value() + np.pi * k), np.sin(t.get_value() + np.pi * k), 0])

        CUR = [(0.32, 1.0, 0.0), (0.55, 0.7, 2.1), (0.55, 0.7, 2.1 + np.pi), (0.8, 0.45, 1.0), (0.8, 0.45, 1.0 + np.pi)]   # (radius frac, spin rate, phase)
        def current(r, ang, p):
            arc = Arc(radius=r, start_angle=ang, angle=1.9, color=WHITE, stroke_width=2.6, stroke_opacity=0.8)
            arc.add_tip(tip_length=0.14, tip_width=0.11)
            return arc.move_arc_center_to(p)

        def make_star(k):
            g = self.star(r0, STAR_BLUE, pos(k))
            cur = VGroup(*[current(r0 * f, ph, pos(k)) for f, _, ph in CUR])
            grp = VGroup(g[0], g[1], cur); grp.k = k
            return grp

        def update_star(m):
            p = pos(m.k); r = rs.get_value(); sp = spin.get_value()
            m[0].set(width=2 * (r + 0.32)).move_to(p); m[1].set(width=2 * r).move_to(p)
            for a, (f, w, ph) in zip(m[2], CUR):
                a.become(current(r * f, ph + w * sp, p))

        s1, s2 = make_star(0), make_star(1)
        for s in (s1, s2):
            s.set_z_index(3); s.add_updater(update_star)
        lobes, _ = roche_lobes(1.0, 1.0, 2 * half, center=c + LEFT * half, opacity=0.35)
        base = [v.points.copy() for v in lobes]
        def rot_lobes(m):
            a = t.get_value(); R = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
            for v, b in zip(m, base):
                v.set_points(b @ R.T)
        lobes.add_updater(rot_lobes); lobes.set_z_index(2)
        self.add(lobes, s1, s2)
        # 1. tight orbit, fast differential rotation
        self.play(t.animate.increment_value(1.5 * np.pi), spin.animate.increment_value(5 * np.pi), run_time=1.4, rate_func=linear)
        # 2. what a normal star would do: translucent orange discs swell through the lobes; the mixed stars stay compact
        g = ValueTracker(r0)
        ghosts = VGroup(*[Circle(radius=r0, color=STAR_ORANGE, fill_opacity=0.28, stroke_color=STAR_ORANGE, stroke_width=2, stroke_opacity=0.7).move_to(pos(k)) for k in (0, 1)])
        ghosts[0].add_updater(lambda m: m.set(width=2 * g.get_value()).move_to(pos(0)))
        ghosts[1].add_updater(lambda m: m.set(width=2 * g.get_value()).move_to(pos(1)))
        ghosts.set_z_index(1)
        self.add(ghosts)
        col = ValueTracker(0)
        def tint(m):
            m[1].set_color(interpolate_color(ManimColor(STAR_BLUE), ManimColor(WHITE_BLUE), col.get_value()))
            m[0].set_color(interpolate_color(ManimColor(STAR_BLUE), ManimColor(HOT_BLUE), col.get_value()))
        s1.add_updater(tint); s2.add_updater(tint)
        self.play(g.animate.set_value(2.3), rs.animate.set_value(0.66), col.animate.set_value(1),
                  t.animate.increment_value(2.5 * np.pi), spin.animate.increment_value(8 * np.pi), run_time=3.2, rate_func=linear)
        self.play(t.animate.increment_value(np.pi), spin.animate.increment_value(3 * np.pi), run_time=0.9, rate_func=linear)
        fade = ValueTracker(1)
        ghosts[0].add_updater(lambda m: m.set_fill(opacity=0.28 * fade.get_value()).set_stroke(opacity=0.7 * fade.get_value()))
        ghosts[1].add_updater(lambda m: m.set_fill(opacity=0.28 * fade.get_value()).set_stroke(opacity=0.7 * fade.get_value()))
        lobes.add_updater(lambda m: m.set_stroke(opacity=0.35 * fade.get_value()))
        self.play(fade.animate.set_value(0), t.animate.increment_value(0.5 * np.pi), spin.animate.increment_value(1.5 * np.pi), run_time=0.6, rate_func=linear)
        self.remove(ghosts, lobes)
        # 3. both collapse in place
        s1.clear_updaters(); s2.clear_updaters()
        p1, p2 = s1[1].get_center(), s2[1].get_center()
        flashes = VGroup(*[Circle(radius=rs.get_value() * 2.4, color=WHITE, fill_opacity=0.9, stroke_width=0).move_to(p) for p in (p1, p2)])
        b1, b2 = self.bh(0.34, p1), self.bh(0.34, p2)
        self.play(FadeIn(flashes, run_time=0.15))
        self.play(FadeOut(flashes), Transform(s1, b1), Transform(s2, b2), run_time=0.45)
        # 4. same tight circular orbit, slow inspiral
        a = ValueTracker(half)
        s1.add_updater(lambda m: m.move_to(c + a.get_value() * np.array([np.cos(t.get_value()), np.sin(t.get_value()), 0])))
        s2.add_updater(lambda m: m.move_to(c - a.get_value() * np.array([np.cos(t.get_value()), np.sin(t.get_value()), 0])))
        ring = Circle(radius=half, color=self.accent, stroke_width=1.5, stroke_opacity=0.5).move_to(c)
        ring.add_updater(lambda m: m.set(width=2 * a.get_value()).move_to(c))
        self.add(ring)
        self.play(t.animate.increment_value(4 * np.pi), a.animate.set_value(1.3), run_time=2.6, rate_func=linear)
        self.wait(0.2)

    # ---- variant 3: inclined viewpoint, globes with running spin dots ----------------------------
    def construct_v3(self):
        c = ORIGIN
        half = 1.7
        r0 = 0.66
        INC = 1.05                                    # inclination of the orbital plane to the sky (rad)
        CI = np.cos(INC)
        t = ValueTracker(0.0); spin = ValueTracker(0.0); rs = ValueTracker(r0)

        def pos(k):
            a = t.get_value() + np.pi * k
            return c + half * np.array([np.cos(a), CI * np.sin(a), 0])

        LATS = (-0.7, 0.0, 0.7)
        def make_star(k):
            g = self.star(r0, STAR_BLUE, pos(k))
            bands = VGroup(*[Ellipse(width=1, height=1, color=WHITE, stroke_width=1.5, stroke_opacity=0.5) for _ in LATS])
            dots = VGroup(*[Dot(radius=0.055, color=WHITE, fill_opacity=0.9) for _ in range(6)])
            grp = VGroup(g[0], g[1], bands, dots); grp.k = k
            return grp

        def band_geom(r, lat):
            return 2 * r * np.cos(lat), 2 * r * np.cos(lat) * 0.38, r * np.sin(lat) * 0.92

        def update_star(m):
            p = pos(m.k); r = rs.get_value(); sp = spin.get_value()
            m[0].set(width=2 * (r + 0.32)).move_to(p); m[1].set(width=2 * r).move_to(p)
            for b, lat in zip(m[2], LATS):
                w, h, dy = band_geom(r, lat)
                b.set(width=w).set(height=h).move_to(p + UP * dy)
            for i, d in enumerate(m[3]):
                lat = LATS[i % 3]
                w, h, dy = band_geom(r, lat)
                ang = sp * (1.0 + 0.15 * (i % 3)) + i * 2.1
                d.move_to(p + UP * dy + np.array([0.5 * w * np.cos(ang), -0.5 * h * np.sin(ang), 0]))
                d.set_fill(opacity=0.9 if np.sin(ang) > 0 else 0.15)          # behind the star when on the far side

        s1, s2 = make_star(0), make_star(1)
        for s in (s1, s2):
            s.set_z_index(3); s.add_updater(update_star)
        # Roche lobes, projected onto the inclined view
        lobes, _ = roche_lobes(1.0, 1.0, 2 * half, center=c + LEFT * half, opacity=0.3)
        base = [v.points.copy() for v in lobes]
        def rot_lobes(m):
            a = t.get_value(); R = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
            for v, b in zip(m, base):
                q = b @ R.T; q = q.copy(); q[:, 1] *= CI
                v.set_points(q)
        lobes.add_updater(rot_lobes)
        # the orbit itself, a foreshortened ellipse
        track = Ellipse(width=2 * half, height=2 * half * CI, color=INK, stroke_width=1.2, stroke_opacity=0.3).move_to(c)
        self.add(track, lobes, s1, s2)
        # 1. tight orbit, fast spin
        self.play(t.animate.increment_value(2 * np.pi), spin.animate.increment_value(6 * np.pi), run_time=1.6, rate_func=linear)
        # 2. dashed ghost of a normal star's radius grows; the mixed stars shrink a little and go blue-white
        g = ValueTracker(r0)
        ghosts = VGroup(*[VMobject() for _ in range(2)])
        def ghost_upd(m, k):
            circ = Circle(radius=g.get_value(), color=STAR_ORANGE, stroke_width=3.2).move_to(pos(k))
            m.become(DashedVMobject(circ, num_dashes=30, dashed_ratio=0.6)).set_stroke(opacity=0.85)
        ghosts[0].add_updater(lambda m: ghost_upd(m, 0)); ghosts[1].add_updater(lambda m: ghost_upd(m, 1))
        self.add(ghosts)
        col = ValueTracker(0)
        def tint(m):
            m[1].set_color(interpolate_color(ManimColor(STAR_BLUE), ManimColor(WHITE_BLUE), col.get_value()))
            m[0].set_color(interpolate_color(ManimColor(STAR_BLUE), ManimColor(HOT_BLUE), col.get_value()))
        s1.add_updater(tint); s2.add_updater(tint)
        self.play(g.animate.set_value(2.0), rs.animate.set_value(0.58), col.animate.set_value(1),
                  t.animate.increment_value(2.5 * np.pi), spin.animate.increment_value(7.5 * np.pi), run_time=3.0, rate_func=linear)
        self.play(t.animate.increment_value(np.pi), spin.animate.increment_value(3 * np.pi), run_time=0.8, rate_func=linear)
        fade = ValueTracker(1)
        ghosts[0].add_updater(lambda m: m.set_stroke(opacity=0.85 * fade.get_value()))
        ghosts[1].add_updater(lambda m: m.set_stroke(opacity=0.85 * fade.get_value()))
        lobes.add_updater(lambda m: m.set_stroke(opacity=0.3 * fade.get_value()))
        self.play(fade.animate.set_value(0), t.animate.increment_value(0.5 * np.pi), spin.animate.increment_value(1.5 * np.pi), run_time=0.6, rate_func=linear)
        self.remove(ghosts, lobes)
        # 3. both collapse in place
        s1.clear_updaters(); s2.clear_updaters()
        p1, p2 = s1[1].get_center(), s2[1].get_center()
        flashes = VGroup(*[Circle(radius=rs.get_value() * 2.4, color=WHITE, fill_opacity=0.9, stroke_width=0).move_to(p) for p in (p1, p2)])
        b1, b2 = self.bh(0.3, p1), self.bh(0.3, p2)
        self.play(FadeIn(flashes, run_time=0.15))
        self.play(FadeOut(flashes), Transform(s1, b1), Transform(s2, b2), run_time=0.45)
        # 4. tilted circular BH–BH orbit, slowly shrinking
        a = ValueTracker(half)
        s1.add_updater(lambda m: m.move_to(c + a.get_value() * np.array([np.cos(t.get_value()), CI * np.sin(t.get_value()), 0])))
        s2.add_updater(lambda m: m.move_to(c - a.get_value() * np.array([np.cos(t.get_value()), CI * np.sin(t.get_value()), 0])))
        self.remove(track)
        ring = Ellipse(width=2 * half, height=2 * half * CI, color=self.accent, stroke_width=1.5, stroke_opacity=0.55).move_to(c)
        ring.add_updater(lambda m: m.set(width=2 * a.get_value()).set(height=2 * a.get_value() * CI).move_to(c))
        self.add(ring)
        self.play(t.animate.increment_value(4 * np.pi), a.animate.set_value(1.35), run_time=2.6, rate_func=linear)
        self.wait(0.2)

    # ---- shared bits for variants 4–6 ------------------------------------------------------------
    @staticmethod
    def _spin_arrow(r, ang, p):
        arc = Arc(radius=r + 0.16, start_angle=ang + 0.2, angle=2.6, color=INK, stroke_width=2.5, stroke_opacity=0.8)
        arc.add_tip(tip_length=0.18, tip_width=0.14)
        return arc.move_arc_center_to(p)

    @staticmethod
    def _rotating_lobes(lobes, t, center):
        """Make the figure-of-eight follow the orbital phase tracker `t` about `center`."""
        base = [v.points.copy() - center for v in lobes]
        def rot(m):
            a = t.get_value(); R = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
            for v, b in zip(m, base):
                v.set_points(b @ R.T + center)
        lobes.add_updater(rot)
        return lobes

    def _collapse_pair(self, s1, s2, r_star, r_bh):
        s1.clear_updaters(); s2.clear_updaters()
        p1, p2 = s1[1].get_center(), s2[1].get_center()
        flashes = VGroup(*[Circle(radius=r_star * 2.4, color=WHITE, fill_opacity=0.9, stroke_width=0).move_to(p) for p in (p1, p2)])
        b1, b2 = self.bh(r_bh, p1), self.bh(r_bh, p2)
        self.play(FadeIn(flashes, run_time=0.15))
        self.play(FadeOut(flashes), Transform(s1, b1), Transform(s2, b2), run_time=0.45)

    # ---- variant 4: split comparison — normal binary (top, greyed) vs CHE binary (bottom) ----------
    def construct_v4(self):
        yT, yB = 2.05, -2.05
        half = 1.1; r0 = 0.5
        GREY = '#b4aea5'
        t = ValueTracker(0.0); spin = ValueTracker(0.0)
        rN = ValueTracker(r0); hN = ValueTracker(half)          # normal stars: radius, half-separation (→ merger)
        rC = ValueTracker(r0); col = ValueTracker(0.0)          # CHE stars: radius, blue→white tint
        fadeT = ValueTracker(1.0); fadeB = ValueTracker(1.0)    # Roche-lobe opacities
        cT, cB = np.array([0, yT, 0]), np.array([0, yB, 0])

        def posT(k):
            a = t.get_value() + np.pi * k
            return cT + hN.get_value() * np.array([np.cos(a), np.sin(a), 0])
        def posB(k):
            a = t.get_value() + np.pi * k
            return cB + half * np.array([np.cos(a), np.sin(a), 0])

        divider = Line(LEFT * 6.6, RIGHT * 6.6, color=INK, stroke_width=1.2, stroke_opacity=0.35)

        # top: a normal massive binary, drawn faintly in grey
        def make_normal(k):
            g = VGroup(Circle(radius=r0 * 1.5, color=GREY, fill_opacity=0.2, stroke_width=0),
                       Circle(radius=r0, color=GREY, fill_opacity=0.75, stroke_width=0))
            g.k = k
            return g
        def upd_normal(m):
            p = posT(m.k); r = rN.get_value()
            m[0].set(width=2 * r * 1.5).move_to(p); m[1].set(width=2 * r).move_to(p)
        n1, n2 = make_normal(0), make_normal(1)
        for n in (n1, n2):
            n.add_updater(upd_normal)
        lobesT, _ = roche_lobes(1.0, 1.0, 2 * half, center=cT + LEFT * half, color=INK, opacity=0.35)
        self._rotating_lobes(lobesT, t, cT)
        lobesT.add_updater(lambda m: m.set_stroke(opacity=0.35 * fadeT.get_value()))

        # bottom: the CHE binary — spun up, mixed, compact and blue
        def make_che(k):
            g = self.star(r0, STAR_BLUE, posB(k))
            bands = VGroup(*[Circle(radius=r0 * f, color=WHITE, stroke_width=1.5, stroke_opacity=0.45).move_to(posB(k)) for f in (0.42, 0.72)])
            grp = VGroup(g[0], g[1], bands, self._spin_arrow(r0, 0.0, posB(k))); grp.k = k
            return grp
        def upd_che(m):
            p = posB(m.k); r = rC.get_value(); cv = col.get_value()
            m[0].set(width=2 * (r + 0.32)).move_to(p).set_color(interpolate_color(ManimColor(STAR_BLUE), ManimColor(HOT_BLUE), cv))
            m[1].set(width=2 * r).move_to(p).set_color(interpolate_color(ManimColor(STAR_BLUE), ManimColor(WHITE_BLUE), cv))
            m[2][0].set(width=2 * r * 0.42).move_to(p); m[2][1].set(width=2 * r * 0.72).move_to(p)
            m[3].become(self._spin_arrow(r, spin.get_value(), p))
        s1, s2 = make_che(0), make_che(1)
        for s in (s1, s2):
            s.add_updater(upd_che)
        lobesB, _ = roche_lobes(1.0, 1.0, 2 * half, center=cB + LEFT * half, color=INK, opacity=0.35)
        self._rotating_lobes(lobesB, t, cB)
        lobesB.add_updater(lambda m: m.set_stroke(opacity=0.35 * fadeB.get_value()))
        self.add(divider, lobesT, lobesB, n1, n2, s1, s2)

        # 1. both binaries on the same tight orbit; only the CHE stars spin fast
        self.play(t.animate.increment_value(2 * np.pi), spin.animate.increment_value(6 * np.pi), run_time=1.6, rate_func=linear)
        # 2. the normal stars swell to their Roche lobes; the CHE stars stay compact (even shrink a little) and whiten
        self.play(rN.animate.set_value(0.86), rC.animate.set_value(0.44), col.animate.set_value(1),
                  t.animate.increment_value(2.5 * np.pi), spin.animate.increment_value(7.5 * np.pi), run_time=3.0, rate_func=linear)
        # 3. the normal binary overflows and merges into one blob; the CHE binary is untouched
        self.play(rN.animate.set_value(1.05), hN.animate.set_value(0.22), fadeT.animate.set_value(0),
                  t.animate.increment_value(1.5 * np.pi), spin.animate.increment_value(4.5 * np.pi), run_time=1.8, rate_func=linear)
        self.remove(lobesT)
        self.play(fadeB.animate.set_value(0), t.animate.increment_value(0.5 * np.pi), spin.animate.increment_value(1.5 * np.pi), run_time=0.5, rate_func=linear)
        self.remove(lobesB)
        # 4. CHE stars collapse in place → BHs on the same tight orbit
        self._collapse_pair(s1, s2, rC.get_value(), 0.27)
        a = ValueTracker(half)
        s1.add_updater(lambda m: m.move_to(cB + a.get_value() * np.array([np.cos(t.get_value()), np.sin(t.get_value()), 0])))
        s2.add_updater(lambda m: m.move_to(cB - a.get_value() * np.array([np.cos(t.get_value()), np.sin(t.get_value()), 0])))
        ring = Circle(radius=half, color=self.accent, stroke_width=1.5, stroke_opacity=0.55).move_to(cB)
        ring.add_updater(lambda m: m.set(width=2 * a.get_value()).move_to(cB))
        self.add(ring)
        self.play(t.animate.increment_value(4 * np.pi), a.animate.set_value(0.95), run_time=2.6, rate_func=linear)
        self.wait(0.2)

    # ---- variant 5: no ghost — fixed orbit circle, mixing currents, stars shrink and whiten -------
    def construct_v5(self):
        c = ORIGIN
        half = 1.5; r0 = 0.78
        MIX = '#2b5f9e'; PALE = '#b9d4ee'
        t = ValueTracker(0.0); spin = ValueTracker(0.0); rs = ValueTracker(r0); col = ValueTracker(0.0)

        def pos(k):
            return c + half * np.array([np.cos(t.get_value() + np.pi * k), np.sin(t.get_value() + np.pi * k), 0])

        CUR = [(0.3, 1.0, 0.0), (0.55, 0.7, 2.1), (0.55, 0.7, 2.1 + np.pi), (0.8, 0.45, 1.0), (0.8, 0.45, 1.0 + np.pi)]
        def current(r, ang, p):
            arc = Arc(radius=r, start_angle=ang, angle=1.9, color=MIX, stroke_width=2.6, stroke_opacity=0.75)
            arc.add_tip(tip_length=0.14, tip_width=0.11)
            return arc.move_arc_center_to(p)
        def make_star(k):
            g = self.star(r0, STAR_BLUE, pos(k))
            cur = VGroup(*[current(r0 * f, ph, pos(k)) for f, _, ph in CUR])
            grp = VGroup(g[0], g[1], cur); grp.k = k
            return grp
        def update_star(m):
            p = pos(m.k); r = rs.get_value(); sp = spin.get_value(); cv = col.get_value()
            m[0].set(width=2 * (r + 0.32)).move_to(p).set_color(interpolate_color(ManimColor(STAR_BLUE), ManimColor(HOT_BLUE), cv))
            m[1].set(width=2 * r).move_to(p).set_color(interpolate_color(ManimColor(STAR_BLUE), ManimColor(PALE), cv))
            for arc, (f, w, ph) in zip(m[2], CUR):
                arc.become(current(r * f, ph + w * sp, p))
        s1, s2 = make_star(0), make_star(1)
        for s in (s1, s2):
            s.set_z_index(2); s.add_updater(update_star)
        # the orbit: one circle, drawn from the start and never changing size while the stars evolve
        a = ValueTracker(half)
        ring = Circle(radius=half, color=INK, stroke_width=1.6, stroke_opacity=0.4).move_to(c)
        ring.add_updater(lambda m: m.set(width=2 * a.get_value()).move_to(c))
        self.add(ring, s1, s2)
        # 1. tight orbit, strong internal circulation
        self.play(t.animate.increment_value(2 * np.pi), spin.animate.increment_value(6 * np.pi), run_time=1.6, rate_func=linear)
        # 2. fully mixed: the stars contract slightly and go white-blue (core helium burning) — the orbit stays put
        self.play(rs.animate.set_value(0.56), col.animate.set_value(1),
                  t.animate.increment_value(3 * np.pi), spin.animate.increment_value(10 * np.pi), run_time=3.6, rate_func=linear)
        self.play(t.animate.increment_value(np.pi), spin.animate.increment_value(3 * np.pi), run_time=1.0, rate_func=linear)
        # 3. both collapse in place
        self._collapse_pair(s1, s2, rs.get_value(), 0.32)
        # 4. same tight circular orbit, slow inspiral
        s1.add_updater(lambda m: m.move_to(c + a.get_value() * np.array([np.cos(t.get_value()), np.sin(t.get_value()), 0])))
        s2.add_updater(lambda m: m.move_to(c - a.get_value() * np.array([np.cos(t.get_value()), np.sin(t.get_value()), 0])))
        ring.set_stroke(color=self.accent, opacity=0.55)
        self.play(t.animate.increment_value(4 * np.pi), a.animate.set_value(1.3), run_time=2.6, rate_func=linear)
        self.wait(0.2)

    # ---- variant 6: time-lapse — the same binary at three epochs, left to right ---------------------
    def construct_v6(self):
        X = (-4.7, 0.0, 4.7); y0 = 0.1
        half = 0.95; r_ms, r_he, r_bh = 0.5, 0.36, 0.28
        PALE = '#a9cbec'
        t = ValueTracker(0.0); spin = ValueTracker(0.0)
        al = [ValueTracker(1.0), ValueTracker(0.0), ValueTracker(0.0)]     # visibility of each epoch
        a3 = ValueTracker(half)                                           # BH orbit radius (right)
        cen = [np.array([x, y0, 0]) for x in X]

        def pos(i, k, h=None):
            a = t.get_value() + np.pi * k
            return cen[i] + (half if h is None else h.get_value()) * np.array([np.cos(a), np.sin(a), 0])

        def make_pair(i, r, color, glow, arrows):
            pair = VGroup()
            for k in (0, 1):
                s = VGroup(Circle(radius=r * 1.9, color=glow, fill_opacity=0.18, stroke_width=0),
                           Circle(radius=r, color=color, fill_opacity=1, stroke_width=0),
                           VGroup(*[Circle(radius=r * f, color=WHITE, stroke_width=1.5, stroke_opacity=0.45) for f in (0.42, 0.72)]),
                           self._spin_arrow(r, 0.0, ORIGIN) if arrows else VMobject())
                s.k = k
                def upd(m, i=i, r=r, arrows=arrows):
                    p = pos(i, m.k); v = al[i].get_value()
                    m[0].move_to(p).set_fill(opacity=0.18 * v); m[1].move_to(p).set_fill(opacity=v)
                    m[2].move_to(p).set_stroke(opacity=0.45 * v)
                    if arrows:
                        m[3].become(self._spin_arrow(r, spin.get_value(), p))
                s.add_updater(upd)
                pair.add(s)
            return pair

        def ring(i, tracker=None):
            rg = Circle(radius=half, color=INK, stroke_width=1.4, stroke_opacity=0.4).move_to(cen[i])
            rg.add_updater(lambda m: m.set(width=2 * (half if tracker is None else tracker.get_value())).move_to(cen[i]).set_stroke(opacity=0.4 * al[i].get_value()))
            return rg

        def time_arrow(i):
            x0 = X[i] + half + 0.9; x1 = X[i + 1] - half - 0.8
            return Arrow(np.array([x0, y0, 0]), np.array([x1, y0, 0]), buff=0, color=INK, stroke_width=3, max_tip_length_to_length_ratio=0.3).set_opacity(0.35)

        ms = make_pair(0, r_ms, STAR_BLUE, STAR_BLUE, True)
        he = make_pair(1, r_he, PALE, HOT_BLUE, False)
        he3 = make_pair(2, r_he, PALE, HOT_BLUE, False)
        r1, r2, r3 = ring(0), ring(1), ring(2, a3)
        self.add(r1, r2, r3, ms, he, he3)
        # 1. epoch 1: tidally locked main-sequence stars, spinning fast
        self.play(t.animate.increment_value(1.5 * np.pi), spin.animate.increment_value(5 * np.pi), run_time=1.4, rate_func=linear)
        # 2. → epoch 2: contracted, white-blue helium stars on the identical orbit
        arr1 = time_arrow(0)
        self.play(GrowArrow(arr1), al[1].animate.set_value(1), t.animate.increment_value(np.pi), spin.animate.increment_value(3 * np.pi), run_time=1.2, rate_func=linear)
        self.play(t.animate.increment_value(1.5 * np.pi), spin.animate.increment_value(4.5 * np.pi), run_time=1.4, rate_func=linear)
        # 3. → epoch 3: the helium stars appear once more, then collapse in place
        arr2 = time_arrow(1)
        self.play(GrowArrow(arr2), al[2].animate.set_value(1), t.animate.increment_value(np.pi), spin.animate.increment_value(3 * np.pi), run_time=1.2, rate_func=linear)
        self.play(t.animate.increment_value(np.pi), spin.animate.increment_value(3 * np.pi), run_time=0.9, rate_func=linear)
        b1, b2 = he3[0], he3[1]
        self._collapse_pair(b1, b2, r_he, r_bh)
        # 4. the BH pair on the right inspirals on its tight circular orbit while the earlier epochs keep turning
        b1.add_updater(lambda m: m.move_to(cen[2] + a3.get_value() * np.array([np.cos(t.get_value()), np.sin(t.get_value()), 0])))
        b2.add_updater(lambda m: m.move_to(cen[2] - a3.get_value() * np.array([np.cos(t.get_value()), np.sin(t.get_value()), 0])))
        r3.set_stroke(color=self.accent)
        r3.clear_updaters()
        r3.add_updater(lambda m: m.set(width=2 * a3.get_value()).move_to(cen[2]).set_stroke(color=self.accent, opacity=0.55))
        self.play(t.animate.increment_value(4 * np.pi), spin.animate.increment_value(12 * np.pi), a3.animate.set_value(0.72), run_time=2.8, rate_func=linear)
        self.wait(0.2)
