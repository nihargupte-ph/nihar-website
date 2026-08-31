# Formation-channel animations (slide 05) — storyboards

One short looping animation per channel, rendered with Manim (`tools/manim/render.sh`).
Each is a *cartoon of the physical mechanism*, not a simulation: the point is that a viewer
who glances at the card understands, in ~8 s, what makes this channel different and why it
ends up eccentric (top row) or circular (bottom row) in the LVK band.

Conventions (see `style.py`): 16:9, background = deck paper `#faf8f4`, ink `#504c44`,
one accent per group (field grey, dynamical red, ZKL purple, AGN teal). Stars are filled
discs with a soft glow; black holes are solid ink discs with a thin ring. Gravitational-wave
emission is shown as a few expanding concentric rings from the pericentre. Every scene
ends on a frame that reads well as the still card face (`--still` exports it). No text
except an optional 1–2 word label at the bottom; keep motion legible at 300 px wide.

## Isolated binaries (bottom row, family box)

**iso-smt — stable mass transfer.** Two massive stars in a ~100 R☉ orbit. The primary
evolves, swells and fills its Roche lobe (teardrop equipotential drawn faintly). Gas leaves
through L1 as a thin stream and settles into an accretion disc around the companion. The
transfer is *stable*: the stream stays thin, the donor shrinks back gradually, the orbit
widens/shrinks smoothly (no plunge). Donor collapses to a BH (brief flash, then ink disc).
Later the secondary swells, and a second, stable mass-transfer phase feeds a disc around
the BH. Second collapse → two BHs on a wide *circular* orbit, which shrink very slowly.
Key contrast with CE: nothing engulfs anything; the orbit changes smoothly.

**iso-ce — common envelope.** Same start. The primary becomes a giant whose envelope grows
until it *swallows the companion*. Inside the translucent envelope the companion and the
giant's core spiral rapidly inwards (dynamical friction; draw the tightening spiral track).
The orbital energy heats the envelope, which puffs away as an expanding shell. What remains
is a very tight core–companion binary. Both collapse (flash → BH). Tight circular BH–BH
orbit; slow inspiral. Key visual: the engulfing envelope and the spiral-in.

**iso-che — chemically homogeneous evolution.** Two massive stars already very close
(~1–2 day orbit, separation ~ a few stellar radii), tidally locked and spinning fast (draw
rotation arrows/latitude bands). Rotational mixing keeps each star uniformly mixed: show
the star staying compact and blue-white while a faint "ghost" outline shows the radius a
normal star would have reached — it never fills its Roche lobe. Both collapse in place to
BHs, still in the same tight circular orbit; GW inspiral over Gyr. Key visual: the stars
*don't* expand.

## Dynamical — clusters (dense dot cloud, red accent)

**cluster-ejected.** A globular cluster core (a few hundred faint dots with a density
gradient). A hard binary in the core. Single BHs fly in one after another; each
three-body encounter kicks the single out faster and leaves the binary *tighter*
(Heggie's law: hard binaries harden). Each interaction also gives the binary a recoil
(binary drifts); after the third or fourth the recoil exceeds the escape speed and the
binary leaves the cluster (trails out of the dot cloud). Alone in the field for Gyr, GW
emission circularises it: the orbit drawn as a mildly eccentric ellipse morphs into a
circle and shrinks. Bottom row: arrives circular.

(cluster-incluster removed 2026-08-30: physically the same encounters as binary–single / single–single captures; files in removed/.)

**cluster-capture — GW capture in 3-/4-body encounters.** A binary–single (optionally
binary–binary) encounter goes *resonant*: three bodies swap partners chaotically in a
tangled temporary triple (draw messy interleaved paths). During one of these exchanges
two BHs pass extremely close; a GW burst (rings) at that pericentre binds them on the
spot. The new pair is on a very eccentric orbit (e ≈ 1: long thin ellipse) that shrinks
in a few pericentre passages; the third body is flung away. Top row: forms inside the
band, eccentric.

**single-capture — single–single GW capture.** Galactic nucleus: SMBH disc at centre,
many fast-moving dots. Two unbound BHs on hyperbolic paths approach; at the close
pericentre a burst of GW rings carries away more energy than their kinetic energy at
infinity, so the outgoing path bends back into a bound, extremely eccentric orbit
(e → 1). Two or three loops, each pericentre with a burst, orbit shrinking rapidly, then
merger. Top row: highest eccentricities of all channels.

## ZKL (purple accent)

**triples — field triples.** An inner binary (two stars → later BHs) plus a distant
tertiary on an inclined outer orbit (draw the outer orbit as a tilted ellipse). Secular
von Zeipel–Kozai–Lidov cycles: the inner ellipse slowly stretches (eccentricity up) while
its plane tilts toward the outer orbit (inclination down), then relaxes — repeat 2–3
cycles with a small e/i indicator. At an eccentricity maximum the pericentre is close
enough that GW rings appear and the inner orbit shrinks and merges *while still
eccentric*. Top row.

**zkl-smbh — ZKL near a supermassive BH.** Same physics, but the tertiary is the SMBH
of a nuclear star cluster: a huge ink disc at the centre, the compact binary on a wide
orbit around it. The binary's inner orbit (drawn magnified in an inset or scaled up)
undergoes ZKL cycles driven by the SMBH, reaching e close to 1; GW bursts at pericentre
and merger mid-cycle. Top row.

## AGN (teal accent)

**agn — AGN disc.** Face-on accretion disc around an SMBH (soft radial gradient, faint
spiral). Stellar-mass BHs embedded in the disc: gas torques make them migrate inward
(arrows along the disc) and pile up at a migration trap (dashed ring). Two meet and pair
off; gas drag keeps hardening the pair (tightening circle). A third BH on a *disc-plane*
encounter (co-planar, so the exchange is nearly 2-D) kicks the pair into an eccentric
orbit; GW rings, eccentric merger inside the disc. Top row.
