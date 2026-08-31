# Brief for writing channel scenes

Directory: presentations/decks/corfu/tools/manim/ (all paths below relative to it).
Read first: STORYBOARD.md (what each animation must show), style.py (helpers), scene_iso_ce.py (the finished reference — match its scale, pacing and style).

Rules
- One file per channel: scene_<id with - → _>.py, containing exactly one `class X(ChannelScene)` with `GROUP` set (field / dynamical / zkl / agn). Use the helpers in style.py; add helpers to style.py only if generic (don't break the others' scenes — append, never edit existing functions).
- Duration 8–14 s, 16:9, objects large (stars r≈0.5–0.8, BHs r≈0.3; the frame is 14 units wide and the clip is viewed at ~300 px wide). No text except an optional `self.label(...)`.
- The LAST frame is used as the still card face: end on a frame that summarises the channel (e.g. the final binary with its orbit ellipse drawn, or the merger rings).
- Manim pitfall: never `.animate` a sub-mobject whose parent has an updater (the animation resets its position). Set instantly, or drive with ValueTrackers + updaters.
- Render with `QUALITY=l ./render.sh <id>` (writes ../../static/channels/media/<id>.mp4 + .png). Check your work visually: extract 5 frames with ffmpeg (`-ss T -frames:v 1`), hstack them into a strip png, and Read it. Iterate until the strip clearly shows the storyboard's beats and nothing is off-screen (x within ±7, y within ±4), stray, or invisible. Then do one final `QUALITY=m ./render.sh <id>`.
- Use `micromamba run -n django-nihar-website` for python/manim (render.sh already does).
- Do NOT edit CLAUDE.md, channels.json, channels.js, or any file outside tools/manim/ and static/channels/media/. Do NOT git commit.
- Report: for each scene, one line on what it shows and any deviation from the storyboard.

# Variants (round 2)
Renders now go to tools/manim/candidates/<id>-<VARIANT>.mp4 (`VARIANT=2 QUALITY=l ./render.sh <id>`); the user picks one per
channel in a web picker, so variants must be *visibly different compositions* of the same storyboard, not palette swaps:
e.g. different viewpoint/framing (close-up on the binary vs. wide context), different emphasis (show the orbit
ellipse evolving with a drawn track vs. bodies only), different pacing/ordering of beats, or a different way to depict the
key mechanism (e.g. CE: envelope as a translucent disc vs. as a swarm of gas particles). Branch on `style.VARIANT`
inside `construct()` (keep variant 1 behaviour byte-for-byte unchanged — do not re-render variant 1). Write a one-line
docstring per variant at the top of the scene file saying what differs.
