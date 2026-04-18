# Catalog page — 3D earth-view mesh + waveform modes

This file documents one specific feature on
`/blog/catalog-of-eccentric-binary-black-holes/`: the **earth-view 3D mesh**
of test particles deformed by the binary's metric, and the **per-event
waveform-mode pipeline** that drives it. The feature is in active iteration
on the visuals.

The bulk of the rendering code lives outside the blog/ directory, in
`static/js/blog/catalog-eccentric-bbh.js`. Read that file alongside this
one when working on the visualization.

---

## Conceptual model — what the mesh represents

The mesh is an **8×8×8 cube of test particles** (`MESH_N3³`) in the
observer's frame, fixed to the screen so every event has the same on-
screen footprint. Vertices are placed at **cell centers**, not corners
— see "one-point perspective and the center-cross flattening" below for
why. The half-side is `1.6 × maxR` where `maxR` is the orbital extent
in geometrized units, so the cube comfortably surrounds the binary.

The cube deforms each frame because **each test particle feels the actual
spacetime metric of the binary at its position**. Two effects combine:

1. **GW tidal field** (wave zone) — at each vertex's source-frame angular
   direction `(θ_p, φ_p)`, we evaluate `h(t, θ, φ) = Σ_lm h_lm(t)
   Y_{−2,lm}(θ, φ)` and apply `δξ^i = ½ h^TT_ij v^j` where the
   separation `v = (x, y, 0)` is the **canvas-plane projection** of
   the vertex position and `h^TT` is the local 3D TT tensor built
   from `(h_+, h_×)` and the stored `(θ̂, φ̂)` at the vertex's `r̂`.
   See the "per-vertex tidal compute" section below for why `v` is
   not the full vertex position `r` — short version: `r = |r| r̂`
   is purely radial in the local tangent triad, `h^TT_ij r^j ≡ 0`
   as a geometric identity, so the separation must drop the
   line-of-sight component to couple to the transverse TT tensor.
2. **Near-zone strong-field gravity** — a regularised radial pull toward
   each BH, generalised to 3D from the existing 2D `_computeMeshZ`. This is
   the "BH actually grabs nearby test particles" effect.

**This is a hard constraint from the user.** The mesh deformation must come
from the *metric's effect* on test particles. Do **not** add fictitious
visualization layers like:

- A "rubber sheet gravity well" depression in some embedding direction.
- A fixed-direction `−L̂` push proportional to the Newtonian potential.
- Any other "looks cool but isn't physics" trick.

If the metric effect is hard to see, the fix is more *visual* (perspective
amount, line density, alpha modulation, color), not adding a fake force.

The volumetric cube (rather than a 2D plane) is also a hard requirement —
the user explicitly asked for a 3D mesh, and the per-vertex SWSH evaluation
relies on having vertices at a range of source-frame angles. A flat plane
in the orbital plane would put every vertex at `θ_src = π/2` and defeat the
whole point.

## What an "earth view" actually means

Each posterior carries a `theta_jn` — the inclination of the orbital
angular momentum from the line of sight. Face-on is `theta_jn = 0`,
edge-on is `theta_jn = π/2`. The earth view uses the **MAP `theta_jn`** for
each event so the binary is rendered the way LIGO actually sees it.

The orbital `L̂` direction in the observer frame is therefore
`(0, sin(θ_jn), cos(θ_jn))` — tilted away from the line of sight. The
source frame is rotated relative to the observer frame by `R_x(−θ_jn)` for
the forward map (source → observer) and `R_x(+θ_jn)` for the inverse
(observer → source).

`theta_jn` is folded to `[0, π/2]` at construction time
(`Math.min(rawTj, π − rawTj)`). Values near π are "face-on from the other
side" — visually identical, mirror-flipped — and folding keeps
`sin(θ_jn) ≥ 0` so depth signs are unambiguous.

`theta_jn` is **not** displayed in the hover posterior heatmaps. It's only
used to drive the geometry.

## Polarization-mode pipeline

### Why modes, not pre-evaluated h+/h×

A naive implementation would precompute `(h+, h×)(t)` at every vertex for
every event and ship them. That's
`4913 verts × 2 × ~800 floats × ~273 (event, bin)` ≈ 1.3 GB. Doesn't ship.

Instead the precompute extracts the **6 unique positive-m waveform modes**
from pyseobnr —
`(2, 2), (2, 1), (3, 3), (3, 2), (4, 4), (4, 3)` —
and the JS resums them on the fly with precomputed Y_lm coefficients per
vertex. Negative-m modes follow from the equatorial-symmetry relation
`h_{l,−m} = (−1)^l h̄_{l,m}` for aligned-spin systems, so we don't ship them
separately. 6 complex modes × ~800 timestamps × 273 (event, bin) ≈ 16 MB
raw, ~5 MB gzipped. Cheap.

### Where modes come from in pyseobnr

pyseobnr exposes them via `wf.generate_td_modes()` — same `GenerateWaveform`
object that produces `generate_td_polarizations()`, just a different
projection of the internal model state. So adding modes is essentially free
on top of the existing call.

`blog/waveforms.py:generate_eccentric_bbh_waveform` was extended to also
call `wf.generate_td_modes()` and return `'modes': {'t': ..., 'hlm': dict}`.
The modes are sliced at the same `f22_display` cut as `hp/hc`. The returned
`hlm_dict` has all 12 modes (positive and negative m) — pyseobnr gives them
both — but downstream we only persist the 6 positive ones.

The unit convention from `generate_td_modes()` is dimensionless physical
strain (already scaled by `−M_total · M_sun_to_m / distance_m`), matching
`generate_td_polarizations()` exactly.

### MAP `psi` rotation

`scripts/generate_o4a_trajectories.py` adds `'psi'` to `ML_COLS` and
applies a `exp(i m ψ_map)` phase rotation to each positive-m mode in the
precompute (same MAP sample as the rest of the ml params). This bakes the
detector-frame polarization angle into the cached modes so the JS doesn't
have to do per-vertex psi handling.

The rotation is equivalent to `Y_{−2,lm}(θ, π/2 − (φ_ref + ψ))` —
absorbing ψ into the modes via `exp(i m ψ)` lets the JS evaluate
`Y_{−2,lm}` with no extra parameter.

The corresponding negative-m mode picks up `exp(−i m ψ)` automatically
through the symmetry relation `h_{l,−m} = (−1)^l h̄_{l,m}`, which is what
the detector-frame rotation requires.

### HDF5 schema

For each `event/bin`, on top of the existing `hp, hc, hp_ringdown,
hc_ringdown` arrays, the precompute writes 24 mode datasets:

```
m22_re, m22_im, m22_re_ringdown, m22_im_ringdown
m21_re, m21_im, m21_re_ringdown, m21_im_ringdown
m33_re, m33_im, m33_re_ringdown, m33_im_ringdown
m32_re, m32_im, m32_re_ringdown, m32_im_ringdown
m44_re, m44_im, m44_re_ringdown, m44_im_ringdown
m43_re, m43_im, m43_re_ringdown, m43_im_ringdown
```

All resampled onto the same uniform time grids as `t` (inspiral) and
`t_ringdown` (post-merger), so the JS uses the same index→time math for
mode lookup as for trajectory playback.

### Backend shipping

`blog/catalog_helpers.py:TRAJECTORY_SIGFIG_COLS` lists the 24 mode column
names (built programmatically from `_MODE_LM`). `views.catalog_posteriors`
loops over `TRAJECTORY_SIGFIG_COLS` and auto-picks them up — no view-side
changes needed when adding/removing mode columns.

Run the precompute via:

```
micromamba run -n django-nihar-website python scripts/generate_o4a_trajectories.py
```

(see `MEMORY.md` — pyseobnr scripts must use this micromamba env). Takes
several minutes; rewrites `static/data/trajectories_ecc.h5` from scratch.

## JS-side rendering pipeline (`static/js/blog/catalog-eccentric-bbh.js`)

### Constants

- `MESH_N3 = 8` (currently) — **vertex count per axis** (not cell count),
  placed at cell centers. `MESH_N3³ = 512` verts and
  `3 × (MESH_N3 − 1) × MESH_N3² = 1344` edges. MUST be even so that no
  vertex lands at coordinate 0 on any axis. The user has been tuning
  this; the cube was originally 16³ but is too dense at that resolution
  for the wireframe to read.
- `MESH_N = 16` (untouched) — the legacy 2D path's grid size.
- `KERR_K_MASS`, `KERR_K_LT` — strong-field deformation strengths,
  shared with the legacy 2D path. The 3D path currently scales these via
  local constants inside `_computeMeshNear3D` while the user iterates.
- `MESH_WAVEZONE_SCALE` / `MESH_NEARZONE_SCALE` — two independent
  boost knobs on the earth-view 3D mesh deformation. Face-on 2D path
  unaffected.
  - `MESH_WAVEZONE_SCALE` multiplies the TT-gauge tidal displacement
    in `_computeMeshTidal3D` (pure linear scale on the 6-mode resum,
    no cap).
  - `MESH_NEARZONE_SCALE` multiplies `KERR_K_MASS` / `KERR_K_LT`
    inside `_computeMeshNear3D` and `_computeMeshNear3DRemnant`.
    Applied *before* the `Math.min(..., 0.6)` crossover cap so the
    cap still fires at a larger effective radius when the boost is
    > 1 (crossover protection preserved).
  Split so the user can tune wave-zone ripple amplitude independently
  from near-zone BH pull without having to retune `GW_AMP_SCALE` or
  the `KERR_K_*` constants individually.

### Spin-weighted spherical harmonics

`swshMinus2Pack(theta, phi, out)` is a hand-written closed-form implementation
of `_{−2}Y_{lm}` for the 12 modes we care about. The formulas were derived
via sympy from the standard Wigner-d definition and **verified against
`lal.SpinWeightedSphericalHarmonic`** at 8 sample `(θ, φ)` points to
sub-1e-10 agreement. The sign convention is `(−1)^{m+s}` prefix on the
`d^l_{−s, m}` form — match this if extending to more modes.

The output is a 24-element flat `Float32Array` (caller-allocated to avoid
per-vertex allocation) ordered as `(Re, Im)` pairs in the
`MODE_ORDER` constant.

### Per-vertex precomputation (constructor)

Once per renderer instance:

1. Build the `MESH_N3³`-vertex cube in observer-frame Cartesian, with
   vertices at cell centers of an `MESH_N3³` subdivision. Position of
   vertex `k` along an axis is `-meshL + (k + 0.5) × step` where
   `step = 2 × meshL / MESH_N3`. This straddles the center so no vertex
   sits at x=0, y=0, or z=0 — avoids the one-point-perspective
   flattening described below.
2. For each vertex, compute its source-frame `(θ_p, φ_p)` via the inverse
   rotation `R_x(+θ_jn)` applied to its observer-frame position.
3. Build the local tangent basis `(θ̂, φ̂)` at the vertex's source-frame
   direction, then rotate it back into observer-frame Cartesian. Stored as
   `mesh3D_thetaHatX/Y/Z` and `mesh3D_phiHatX/Y/Z`.
4. Call `swshMinus2Pack` to get all 12 `Y_{−2,lm}` complex values, then
   fold positive- and negative-m into combined coefficients per `(l, |m|)`
   per vertex:

       A_re = Y_p_re + (−1)^l Y_n_re
       A_im = Y_p_im + (−1)^l Y_n_im
       B_re = Y_p_re − (−1)^l Y_n_re
       B_im = −Y_p_im + (−1)^l Y_n_im

   Stored as `mesh3D_combAre[mi]`, `mesh3D_combAim[mi]`,
   `mesh3D_combBre[mi]`, `mesh3D_combBim[mi]` — six modes, four
   `Float32Array(NV)` each. ~117k floats per renderer.

5. Read the 6 inspiral mode arrays + 6 ringdown mode arrays from
   `traj.m{l}{m}_re/im[_ringdown]`. If any are missing
   (`mesh3D_modesReady === false`), the earth view falls back to the
   legacy face-on path automatically.

6. Build the edge enumeration as a flat `Uint32Array(EDGE_COUNT * 2)` so
   the per-frame draw loop is index-friendly. With `MESH_N3 = 8` that's
   `3 × 7 × 64 = 1344` edges.

### Per-frame strain compute (`_computeMeshTidal3D`)

```js
// Hoist the 6 mode samples once per frame:
for mi in 0..6:
    a[mi] = lerp(mode_re[mi][i0..i1], f)
    b[mi] = lerp(mode_im[mi][i0..i1], f)

// Per vertex:
for idx in 0..NV:
    // 6-mode resum using the combined Y coefficients:
    hRe = sum(a[mi]*A_re[mi][idx] + b[mi]*B_im[mi][idx])
    hIm = sum(a[mi]*A_im[mi][idx] + b[mi]*B_re[mi][idx])
    hp = hRe; hc = -hIm

    // Canvas-plane separation v = (x, y, 0). NOT the full vertex
    // position — see below.
    Tv = x*θ̂_x + y*θ̂_y       // v · θ̂  (the z part of θ̂ drops out since v_z=0)
    Fv = x*φ̂_x + y*φ̂_y       // v · φ̂

    // TT-gauge tidal in the local basis, acting on (Tv, Fv):
    dTheta = ½(hp*Tv + hc*Fv)
    dPhi   = ½(-hp*Fv + hc*Tv)

    // Back to 3D observer-frame Cartesian via the tangent basis.
    // θ̂_z and φ̂_z are generically nonzero when theta_jn > 0, so
    // δz ≠ 0 — the tilted tangent basis carries the out-of-plane
    // component of the 3D deformation.
    delta = ampScale * (dTheta * θ̂ + dPhi * φ̂)
```

The amplitude scale is `MESH_WAVEZONE_SCALE * GW_AMP_SCALE / hpPeak` —
the same base constant the legacy 2D path uses (normalised by the
per-event central-observer peak so visual displacement magnitudes are
stable across events), boosted by the dedicated wave-zone knob.

#### Why the separation is (x, y, 0) and not (x, y, z)

This is load-bearing — reverting it silently zeros the wave-zone
deformation. The geodesic-deviation formula for a comoving observer
is `δξ^i = ½ h^TT_ij ξ_0^j` where `ξ_0` is the separation from the
reference observer. The 3D TT tensor at a point with emission
direction `r̂` is

    h^TT_ij = h_+(θ̂_i θ̂_j − φ̂_i φ̂_j) + h_×(θ̂_i φ̂_j + φ̂_i θ̂_j)

and it satisfies `h^TT_ij r̂^j = 0` by construction — the TT gauge
has no components along the propagation direction. If you take the
reference observer to be at the mesh origin (the natural "comoving
with a particle at the center of the mesh" choice), then the
separation from the reference to the vertex is `ξ_0 = r = |r| r̂` —
**purely radial in the local tangent triad at the vertex's own
direction**. The contraction `h^TT_ij r^j = |r| h^TT_ij r̂^j = 0`
identically for every vertex. No displacement.

This is a geometric identity, not a coding bug. There is no escape
while the reference observer and the source both live at the
origin, because the only direction to any mesh point is the one
direction the TT tensor cannot move.

The fix is to keep the reference observer at the origin but have
its local Lorentz frame aligned with the canvas (`+ẑ_obs` = line of
sight), and take the separation as the canvas-plane projection of
the vertex position, `v = (x, y, 0)`. That vector has nontrivial
components along `θ̂` and `φ̂` at the vertex's direction (it's
`r` minus its line-of-sight piece), so `h^TT_ij v^j ≠ 0`. The
physical reading: "the comoving observer at the mesh origin sees
each vertex as a test particle displaced from it in the canvas
plane, and the local TT tensor at the particle deforms that
canvas-plane separation".

**Do not revert to `r` without understanding this section.** If a
future iteration tries to 'simplify' the loop back to `rTheta =
r · θ̂`, `rPhi = r · φ̂`, every `dxOut`/`dyOut`/`dzOut` will silently
drop to zero and `MESH_WAVEZONE_SCALE` will stop doing anything.
The `baseZ` field is *intentionally not read* in this loop; the
alias has been removed from the local const block to make that
explicit. The z extent of the mesh still participates in the
deformation through `θ̂_z` and `φ̂_z` in the back-rotation, not
through `v_z`.

### Near-zone (`_computeMeshNear3D`)

3D generalisation of the 2D `_computeMeshZ`. Each BH pulls nearby vertices
radially in 3D with a regularised `K_PULL · M / r²` law, capped at a
fraction of the vertex-to-BH distance to prevent crossover. Frame-dragging
direction is `L̂ × (vertex − BH)` where `L̂ = (0, sin(θ_jn), cos(θ_jn))`
in observer frame.

**Constants here are local to the function and are still being tuned.**
The user reverted a "gravity well embedding" version that pushed vertices
in `−L̂` proportional to the Newtonian potential — that's the kind of
fictitious visualization we are NOT doing.

### Projection (`_perspectiveProject`, `_projectSrcToView`)

**One-point perspective.** Camera sits at `(0, 0, mesh3D_camD)` on the
`+z_view` axis looking at the origin, so the vanishing point is the canvas
center. Camera distance is `3.0 × meshL`, currently — smaller is more
aggressive foreshortening, larger is closer to orthographic.

```
denom = camD - zv
f     = camD / denom
sx    = cx + xv * scale * f
sy    = cy - yv * scale * f
```

A guard handles vertices that drift past the camera plane. Both
`_drawWireframe3D` (mesh) and `_projectSrcToView` (orbit BHs / trails) use
this same camera, so the layers stay registered.

The previous orthographic version was a bug — it collapsed the 3D cube
into a 2D grid because every z-slice projected to the same `(sx, sy)`. The
user explicitly called this out and asked for one-point perspective with
the vanishing point at the grid center.

#### One-point perspective and the center-cross flattening

One-point perspective has a second, more subtle failure mode: any vertex
at `x = 0` projects to `sx = cx` regardless of `y` or `z`, and any vertex
at `y = 0` projects to `sy = cy`. So if the mesh has a *vertex column*
at exactly `(x=0, y=0)` — which happens with a corner-based uniform grid
of odd vertex count — that whole column collapses onto the vanishing
point, and the entire `x=0` and `y=0` planes flatten onto the screen's
center cross lines. Visually the mesh gets a big "dead plus sign"
through the middle of the canvas exactly where the BH lives.

The fix is **cell-centered positioning** with an even `MESH_N3`. Vertex
`k` along an axis sits at `-meshL + (k + 0.5) × step`, so the closest-
to-center columns are at `±meshL / MESH_N3` instead of exactly at 0.
The mesh straddles the vanishing point rather than collapsing onto it.
Do not switch back to corner-based positioning, and do not set
`MESH_N3` to an odd value — both reintroduce the flattening.

### Wireframe rendering (`_drawWireframe3D`)

1. Project all `NV` vertices via the perspective formula (one tight loop).
2. Walk all edges, compute per-edge alpha from depth fade × strain
   magnitude, assign to one of 16 buckets.
3. Build a `Path2D` per bucket via `moveTo / lineTo` for each edge.
4. Stroke buckets back-to-front (lowest alpha first) so the foreground
   sits on top of the background.

Bucketing avoids paying per-edge `stroke()` overhead — at MESH_N3 = 16 we
have ~14k edges and ~16 strokes per frame instead of 14k strokes.

Color palette is currently white/teal (cool against the warm BH glow), set
inside step 3 of the function. Line width is 0.4. The user is iterating
on these.

### BH rendering (`_drawOrb`) — face-on only

`_drawOrb` is a **face-on-only** function. It draws the familiar warm
halo + black disk + solid-color rim + rotating white spin stripe, and
it has been restored bit-for-bit to the pre-3D-feature state. No
`zv` parameter, no earth-view branch, no scene-light gradients.

**Earth view does not render BHs at all.** The user's explicit design
call: in 3D mode the BHs are visible only through their *effect* on
the mesh — the near-zone pull in `_computeMeshNear3D` creates two
moving dimples that follow the orbit, and the wave-zone TT strain
creates the rippling wireframe. The viewer infers where the BHs are
from what the spacetime is doing, not from an orb sitting on top.

Because of that:

- `_drawInspiral3D` does **not** call `_drawOrb`. It computes the
  per-vertex tidal and near-zone displacements, draws the wireframe,
  and stops. The local variables for BH projection and depth sorting
  that used to live here have been deleted.
- `_drawRingdown3D` does not call `_drawOrb` either. The remnant is
  visible only as the ringdown ripple in the mesh.
- `draw()` skips `_pushTrail` when `useEarth` is true so we don't even
  pay the ring-buffer write. `setView` calls `resetTrails` on view
  switch, so flipping back to face-on gives the trail a fresh start.

If the user ever asks for BHs back in earth view, do NOT reintroduce
the focal-gradient sphere rendering that previously lived in
`_drawOrb`'s earth-view branch — it was removed on purpose once the
user decided the mesh deformation alone was sufficient. Start from
scratch, and only if the user asks.

### View toggle (`CURRENT_VIEW`, `wireViewSelector`, `setView`)

Two modes: `'earth'` (default) and `'face-on'`. Mirror of the existing
prior selector pattern: `wireViewSelector` wires the `.view-btn` clicks,
broadcasts via `ALL_EVENT_BOXES[k].setView(key)`, which forwards to
`OrbitRenderer.setView`. Switching just flips a flag and resets trails;
no renderer rebuild.

### Draw dispatch (`draw(t)` → `_drawInspiral{2D,3D}` / `_drawRingdown{2D,3D}`)

`draw(t)` computes the playback phase, then dispatches to one of four
methods. The 2D variants are the legacy code lifted verbatim — face-on
view stays bit-for-bit identical to the pre-3D-feature state. The 3D
variants run the strain compute, near-zone compute, wireframe draw, and
BH draw with depth-sorting on top of the wireframe. No trail draw in 3D.

The earth path falls back to face-on automatically when
`mesh3D_modesReady === false` (i.e. trajectory was loaded against an
unregenerated HDF5).

## Critical files

- `blog/waveforms.py` — pyseobnr wrapper. Returns trajectory +
  polarizations + modes. Modes call is `wf.generate_td_modes()`.
- `scripts/generate_o4a_trajectories.py` — precompute that runs pyseobnr
  on each event's MAP sample, applies the MAP psi rotation to the modes,
  resamples, and writes the HDF5. Adds `'psi'` to `ML_COLS`.
- `blog/catalog_helpers.py` — `TRAJECTORY_SIGFIG_COLS` lists the 24 mode
  column names so `catalog_posteriors` auto-ships them.
- `blog/views.py:catalog_posteriors` — JSON endpoint. Loops over
  `TRAJECTORY_SIGFIG_COLS`, no per-mode hard-coding.
- `static/js/blog/catalog-eccentric-bbh.js` — the rendering. Look for
  `OrbitRenderer.constructor`, `swshMinus2Pack`, `_computeMeshTidal3D`,
  `_computeMeshNear3D`, `_perspectiveProject`, `_drawWireframe3D`,
  `_drawOrb`, `_drawInspiral3D`, `_drawRingdown3D`.
- `blog/templates/blog/catalog_eccentric_bbh.html` — page template.
  Contains the `.view-toggle` block in the prior-selector.

## What the user is iterating on

The user is actively tuning the visual style. As of the latest pause, the
state is:

- 3D cube in **one-point perspective** is in place and reading correctly.
- The user explicitly wants the **metric's effect** on the mesh — not a
  "rubber sheet gravity well" embedding, not a fictitious depression.
- The wireframe palette is white/teal at line width 0.4. May change.
- `MESH_N3 = 8` for now; user wanted "less mesh points and something a
  bit thinner" relative to the original 16³.
- BH should look more like a 3D sphere — directional radial gradient
  added but the user may want more (limb darkening? specular?). Iterating.
- Reference image the user provided was a "gravity-well rubber sheet"
  visual style — but **the visual style is the goal, not the embedding
  trick**. The lines should curve due to the actual metric deformation,
  not an artificial dip.

When iterating, prefer changes to projection / colour / line weight /
density / contrast over adding new "physics" layers. If a new physics
layer is genuinely needed, it should be derived from the actual metric,
not an embedding diagram.

## Verification

After regenerating the HDF5:

```
micromamba run -n django-nihar-website python -c "
import h5py
g = h5py.File('static/data/trajectories_ecc.h5', 'r')['GW150914']['qc']
print(sorted(k for k in g.keys() if k.startswith('m')))
"
```

Should list all 24 mode datasets.

Mode-resum sanity check: the per-vertex strain at a vertex with source-frame
angles `(θ_p ≈ θ_jn, φ_p ≈ 0)` should reproduce the central-observer
`traj.hp(t)` to within sig-fig rounding. (i.e. the vertex sitting at the
"observer's direction" should feel exactly the strain that LIGO measured.)

For the JS wireframe to look right:

- The cube should read as a 3D shape (perspective vanishing at the canvas
  center, lines fanning outward to the front face).
- The BHs should sit at their projected positions, with depth ordering so
  one passes in front of the other when they overlap on screen.
- Mesh edges near each BH should curve (or at least show colour/alpha
  modulation) as the GW tidal field passes through.
- The face-on view (toggled) should look bit-for-bit identical to the
  pre-feature state — that's the regression check.
