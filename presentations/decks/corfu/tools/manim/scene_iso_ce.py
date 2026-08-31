"""iso-ce — common envelope (STORYBOARD.md).

Variant 1: translucent envelope disc engulfs the companion; dissipating spiral trail; shell puffs off.
Variant 2: close-up; the envelope is a swarm of gas particles that swirls with the spiral-in and is flung outward at ejection.
Variant 3: wide framing; the initial orbit circles stay as dashed ghosts, the spiral-in leaves a persistent drawn track,
           and the ejected envelope is an expanding annulus — the last frame contrasts the wide start with the tight end.
"""
import numpy as np
from manim import *
from style import *


class IsoCE(ChannelScene):
    GROUP = 'field'

    def construct(self):
        if VARIANT == 2:
            return self.construct_v2()
        if VARIANT == 3:
            return self.construct_v3()
        a = 4.0                                   # initial separation (scene units)
        c = ORIGIN
        primary = self.star(0.75, STAR_BLUE, c + LEFT * a * 0.4)
        secondary = self.star(0.5, STAR_BLUE, c + RIGHT * a * 0.6)
        self.add(primary, secondary)
        # 1. a quiet orbit
        t = ValueTracker(0)
        def orbit(mob, frac, r):
            mob.move_to(c + r * np.array([np.cos(t.get_value() + np.pi * frac), np.sin(t.get_value() + np.pi * frac), 0]))
        primary.add_updater(lambda m: orbit(m, 1, a * 0.4)); secondary.add_updater(lambda m: orbit(m, 0, a * 0.6))
        self.play(t.animate.set_value(2 * np.pi), run_time=2.0, rate_func=linear)
        # 2. the primary becomes a giant and swallows the companion
        env_r = ValueTracker(0.8)
        env = Circle(radius=0.8, color=STAR_RED, fill_opacity=0.35, stroke_width=0)
        env.add_updater(lambda m: m.set(width=2 * env_r.get_value()).move_to(c + a * 0.4 * np.array([np.cos(t.get_value() + np.pi), np.sin(t.get_value() + np.pi), 0])))
        self.add(env); primary.set_z_index(1); secondary.set_z_index(1)
        primary[1].set_color(STAR_ORANGE)             # NB: never .animate a sub-mobject whose parent has an updater — the animation resets its position
        self.play(env_r.animate.set_value(1.8), t.animate.increment_value(np.pi), run_time=1.6, rate_func=linear)
        self.play(env_r.animate.set_value(a * 0.6 + 0.9), t.animate.increment_value(np.pi / 2), run_time=1.0, rate_func=linear)
        env.clear_updaters(); primary.clear_updaters(); secondary.clear_updaters()
        # 3. spiral-in inside the envelope (dynamical friction)
        core = self.star(0.26, STAR_ORANGE, primary[1].get_center()); self.remove(primary); self.add(core)
        env.move_to(c)
        r_in = ValueTracker(a * 0.6); phi = ValueTracker(t.get_value())
        core.add_updater(lambda m: m.move_to(c - 0.4 * r_in.get_value() * np.array([np.cos(phi.get_value()), np.sin(phi.get_value()), 0])))
        secondary.add_updater(lambda m: m.move_to(c + 0.6 * r_in.get_value() * np.array([np.cos(phi.get_value()), np.sin(phi.get_value()), 0])))
        trail = TracedPath(secondary[1].get_center, stroke_color=INK, stroke_width=1.5, stroke_opacity=0.5, dissipating_time=1.2)
        self.add(trail)
        self.play(r_in.animate.set_value(0.7), phi.animate.increment_value(8 * np.pi), env.animate.set_fill(opacity=0.5), run_time=3.0, rate_func=linear)
        # 4. the envelope is ejected
        shell = Circle(radius=env_r.get_value(), color=STAR_RED, stroke_width=6, stroke_opacity=0.6, fill_opacity=0).move_to(c)
        self.remove(trail)
        self.play(FadeOut(env, run_time=0.4), shell.animate.scale(3.5).set_stroke(opacity=0), phi.animate.increment_value(2 * np.pi), run_time=1.2)
        core.clear_updaters(); secondary.clear_updaters()
        # 5. both collapse to black holes; tight circular inspiral
        core = self.collapse(core, 0.28); secondary = self.collapse(secondary, 0.36)
        core.add_updater(lambda m: m.move_to(c - 0.4 * r_in.get_value() * np.array([np.cos(phi.get_value()), np.sin(phi.get_value()), 0])))
        secondary.add_updater(lambda m: m.move_to(c + 0.6 * r_in.get_value() * np.array([np.cos(phi.get_value()), np.sin(phi.get_value()), 0])))
        ring = Circle(radius=0.6 * r_in.get_value(), color=self.accent, stroke_width=1.5, stroke_opacity=0.5).move_to(c)
        ring.add_updater(lambda m: m.set(width=1.2 * r_in.get_value()).move_to(c))
        self.add(ring)
        self.play(phi.animate.increment_value(6 * np.pi), r_in.animate.set_value(1.1), run_time=2.5, rate_func=linear)
        self.wait(0.2)

    # ---- variant 2: gas-particle envelope, close-up -------------------------------------------
    def construct_v2(self):
        a = 4.6
        c = ORIGIN
        t = ValueTracker(0)
        def opos(k, r):
            return c + r * np.array([np.cos(t.get_value() + np.pi * k), np.sin(t.get_value() + np.pi * k), 0])
        primary = self.star(0.85, STAR_BLUE, opos(1, a * 0.4)); secondary = self.star(0.55, STAR_BLUE, opos(0, a * 0.6))
        primary.add_updater(lambda m: m.move_to(opos(1, a * 0.4))); secondary.add_updater(lambda m: m.move_to(opos(0, a * 0.6)))
        primary.set_z_index(2); secondary.set_z_index(2)
        self.add(primary, secondary)
        # 1. a quiet orbit
        self.play(t.animate.set_value(2 * np.pi), run_time=1.6, rate_func=linear)
        # 2. the primary's envelope (a swarm of gas particles) grows until it engulfs the companion
        rng = np.random.default_rng(3)
        N = 260
        rf = np.sqrt(rng.uniform(0.02, 1.0, N)); ang = rng.uniform(0, 2 * np.pi, N); om = 0.8 / np.maximum(rf, 0.2) ** 1.5
        env_r = ValueTracker(0.9); k_c = ValueTracker(0.0); swirl = ValueTracker(0.0); ej = ValueTracker(0.0); op = ValueTracker(0.0)
        def env_centre():
            return interpolate(opos(1, a * 0.4), c, k_c.get_value())
        gas = VGroup(*[Dot(radius=0.07, color=STAR_RED, fill_opacity=0.0) for _ in range(N)])
        def gas_upd(m):
            ec = env_centre(); R = env_r.get_value(); sw = swirl.get_value(); e = ej.get_value(); o = op.get_value()
            for i, d in enumerate(m):
                r = rf[i] * R + e * (2.5 + 5.0 * rf[i])
                th = ang[i] + sw * om[i]
                d.move_to(ec + r * np.array([np.cos(th), np.sin(th), 0])).set_fill(opacity=o * 0.55 * (1 - e))
        gas.add_updater(gas_upd)
        self.add(gas)
        primary[1].set_color(STAR_ORANGE)
        self.play(op.animate.set_value(1), env_r.animate.set_value(1.9), swirl.animate.set_value(1.0), t.animate.increment_value(np.pi), run_time=1.5, rate_func=linear)
        self.play(env_r.animate.set_value(a * 0.6 + 0.9), k_c.animate.set_value(1), swirl.animate.set_value(2.0), t.animate.increment_value(np.pi / 2), run_time=1.0, rate_func=linear)
        primary.clear_updaters(); secondary.clear_updaters()
        # 3. spiral-in: the swarm is stirred faster as the companion and the core plunge inwards
        core = self.star(0.3, STAR_ORANGE, primary[1].get_center()); self.remove(primary); self.add(core); core.set_z_index(2)
        r_in = ValueTracker(a * 0.6); phi = ValueTracker(t.get_value())
        core.add_updater(lambda m: m.move_to(c - 0.4 * r_in.get_value() * np.array([np.cos(phi.get_value()), np.sin(phi.get_value()), 0])))
        secondary.add_updater(lambda m: m.move_to(c + 0.6 * r_in.get_value() * np.array([np.cos(phi.get_value()), np.sin(phi.get_value()), 0])))
        trail = TracedPath(secondary[1].get_center, stroke_color=INK, stroke_width=1.8, stroke_opacity=0.6, dissipating_time=1.0)
        trail.set_z_index(1)
        self.add(trail)
        self.play(r_in.animate.set_value(0.75), phi.animate.increment_value(8 * np.pi), swirl.animate.set_value(6.5), run_time=3.0, rate_func=linear)
        # 4. the envelope is flung away
        self.remove(trail)
        self.play(ej.animate.set_value(1), phi.animate.increment_value(2 * np.pi), run_time=1.3, rate_func=rush_from)
        self.remove(gas)
        core.clear_updaters(); secondary.clear_updaters()
        # 5. both collapse; tight circular inspiral
        core = self.collapse(core, 0.28); secondary = self.collapse(secondary, 0.36)
        core.add_updater(lambda m: m.move_to(c - 0.4 * r_in.get_value() * np.array([np.cos(phi.get_value()), np.sin(phi.get_value()), 0])))
        secondary.add_updater(lambda m: m.move_to(c + 0.6 * r_in.get_value() * np.array([np.cos(phi.get_value()), np.sin(phi.get_value()), 0])))
        ring = Circle(radius=0.6 * r_in.get_value(), color=self.accent, stroke_width=1.5, stroke_opacity=0.5).move_to(c)
        ring.add_updater(lambda m: m.set(width=1.2 * r_in.get_value()).move_to(c))
        self.add(ring)
        self.play(phi.animate.increment_value(6 * np.pi), r_in.animate.set_value(1.15), run_time=2.4, rate_func=linear)
        self.wait(0.2)

    # ---- variant 3: wide framing, persistent spiral track, initial-orbit ghosts -----------------
    def construct_v3(self):
        a = 5.6
        c = ORIGIN
        t = ValueTracker(0)
        def opos(k, r):
            return c + r * np.array([np.cos(t.get_value() + np.pi * k), np.sin(t.get_value() + np.pi * k), 0])
        primary = self.star(0.62, STAR_BLUE, opos(1, a * 0.4)); secondary = self.star(0.42, STAR_BLUE, opos(0, a * 0.6))
        primary.add_updater(lambda m: m.move_to(opos(1, a * 0.4))); secondary.add_updater(lambda m: m.move_to(opos(0, a * 0.6)))
        primary.set_z_index(2); secondary.set_z_index(2)
        # the initial orbits, drawn and kept as dashed ghosts for the whole clip
        ghosts = VGroup(*[DashedVMobject(Circle(radius=r, color=self.accent, stroke_width=1.5).move_to(c), num_dashes=48, dashed_ratio=0.55).set_stroke(opacity=0.45)
                          for r in (a * 0.4, a * 0.6)])
        self.add(ghosts, primary, secondary)
        # 1. a quiet wide orbit (one turn)
        self.play(t.animate.set_value(2 * np.pi), run_time=1.8, rate_func=linear)
        # 2. quick engulfing: the giant's envelope swallows the companion
        env_r = ValueTracker(0.7)
        env = Circle(radius=0.7, color=STAR_RED, fill_opacity=0.32, stroke_width=0)
        env.add_updater(lambda m: m.set(width=2 * env_r.get_value()).move_to(interpolate(opos(1, a * 0.4), c, np.clip((env_r.get_value() - 0.7) / (a * 0.6 + 0.6 - 0.7), 0, 1))))
        self.add(env)
        primary[1].set_color(STAR_ORANGE)
        self.play(env_r.animate.set_value(a * 0.6 + 0.6), t.animate.increment_value(0.8 * np.pi), run_time=1.3, rate_func=linear)
        env.clear_updaters(); primary.clear_updaters(); secondary.clear_updaters(); env.move_to(c)
        # 3. long spiral-in with a persistent drawn track for both bodies
        core = self.star(0.24, STAR_ORANGE, primary[1].get_center()); self.remove(primary); self.add(core); core.set_z_index(2)
        r_in = ValueTracker(a * 0.6); phi = ValueTracker(t.get_value())
        def cpos():
            return c - 0.4 * r_in.get_value() * np.array([np.cos(phi.get_value()), np.sin(phi.get_value()), 0])
        def spos():
            return c + 0.6 * r_in.get_value() * np.array([np.cos(phi.get_value()), np.sin(phi.get_value()), 0])
        core.add_updater(lambda m: m.move_to(cpos())); secondary.add_updater(lambda m: m.move_to(spos()))
        track_s = TracedPath(spos, stroke_color=INK, stroke_width=1.6, stroke_opacity=0.55)
        track_c = TracedPath(cpos, stroke_color=STAR_ORANGE, stroke_width=1.6, stroke_opacity=0.7)
        track_s.set_z_index(1); track_c.set_z_index(1)
        self.add(track_s, track_c)
        self.play(r_in.animate.set_value(0.8), phi.animate.increment_value(11 * np.pi), env.animate.set_fill(opacity=0.45), run_time=4.2, rate_func=linear)
        track_s.clear_updaters(); track_c.clear_updaters()
        # 4. the envelope leaves as an expanding annulus
        ann = Annulus(inner_radius=env_r.get_value() * 0.55, outer_radius=env_r.get_value(), color=STAR_RED, fill_opacity=0.35, stroke_width=0).move_to(c)
        self.add(ann)
        self.play(FadeOut(env, run_time=0.5), ann.animate.scale(2.6).set_fill(opacity=0), phi.animate.increment_value(2 * np.pi),
                  track_s.animate.set_stroke(opacity=0.3), track_c.animate.set_stroke(opacity=0.4), run_time=1.3)
        self.remove(ann)
        core.clear_updaters(); secondary.clear_updaters()
        # 5. both collapse; tight circular inspiral, drawn inside the ghost of the original orbit
        core = self.collapse(core, 0.26); secondary = self.collapse(secondary, 0.32)
        core.add_updater(lambda m: m.move_to(cpos())); secondary.add_updater(lambda m: m.move_to(spos()))
        ring = Circle(radius=0.6 * r_in.get_value(), color=self.accent, stroke_width=1.5, stroke_opacity=0.6).move_to(c)
        ring.add_updater(lambda m: m.set(width=1.2 * r_in.get_value()).move_to(c))
        self.add(ring)
        self.play(phi.animate.increment_value(6 * np.pi), r_in.animate.set_value(1.2), run_time=2.2, rate_func=linear)
        self.wait(0.2)
