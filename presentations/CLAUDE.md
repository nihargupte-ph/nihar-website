# presentations — interactive, audience-synced talks

Engine app (built once). Each talk is a folder `presentations/decks/<slug>/`.
Spec: `docs/superpowers/specs/2026-08-25-interactive-presentations-design.md`
(binding). Plan: `docs/superpowers/plans/2026-08-25-interactive-presentations.md`.
Reference deck that exercises everything: `presentations/decks/example/`.

## Authoring a deck (the only editor is `deck.yaml`)

```bash
# scaffold from a Canva PDF export ("PDF Standard"), or a folder of .svg/.pdf/.mp4/.webm exports
micromamba run -n django-nihar-website python manage.py newdeck <slug> --title "…" --from ~/Downloads/talk.pdf [--date YYYY-MM-DD]
micromamba run -n django-nihar-website python manage.py newdeck <slug> --title "…" --from ~/Downloads/canva-export/
micromamba run -n django-nihar-website python manage.py checkdecks   # validate every deck; run after each edit
# re-export from Canva later: replace ALL svg slides, keep html/video entries (moved to the end of slides: to reorder)
micromamba run -n django-nihar-website python manage.py reslides <slug> --from ~/Downloads/talk-v2.pdf [--dry-run] [--force]
# retrofit a deck imported before the raster extraction landed (idempotent; leaves slide ids alone)
micromamba run -n django-nihar-website python manage.py extractrasters [<slug>…] [--dry-run] [--prune]
```

`newdeck` sanitises the SVGs, numbers them `slides/NN-<id>.svg`, derives `theme:` from their colours/fonts,
and writes `deck.yaml` with commented examples. `reslides` re-imports the svg layer: old svg files are deleted,
new pages come in as `page-NN`, authored `hotspots/ask/show/footer` are carried over where the id matches (else
they're only in `deck.yaml.bak`), everything above `slides:` and all inline comments survive. It refuses if the
deck has had a session (ids are persistence keys) unless `--force`. A PDF is split with poppler (`pdftocairo`/`pdfinfo`) into one
slide per page (ids `page-NN`); inside a folder it expands in place, so files sort by name (zero-pad: `01…`) and
videos go alongside. PDF text becomes outlines, so `theme:` falls back to defaults — set it by hand. Then edit `deck.yaml`:

- `slides:` order = talk order. Kinds: `svg:` (16:9 stage), `html:` (a Django template file in the deck folder,
  extends `presentations/slide_base.html`, scrolls, may set `underlay: slides/x.svg`), `video:` (+ `poster:`).
- `hotspots:` on svg slides: `rect: [x, y, w, h]` fractions of a 1920×1080 stage, `title`, markdown `body`, `links`.
  On html slides use markup instead: `<span data-hotspot="Title" data-body="…" data-link="…">`.
- `interactions:` top-level list — `type: choice|numeric|distribution|text|prior` (+ config). A slide `ask: [id]`s it
  (phone widget appears when opened) and any slide `show: [{id, rect}]`s the aggregate (html slides:
  `<div data-interaction="id">` and `show: [{id}]` with no rect).
- `venue:` free text shown under the title on the index/join pages (`GR-Amaldi @ Glasgow, UK`).
- `expertise:` 2–6 tags for the join screen; aggregates are sliceable by tag / "vs rest".
- `footer: {name, affiliation, bg, fg}` draws a thin bar (name · affiliation · `N / total`) at the bottom of every
  slide; omit it for none, `footer: false` on a slide to skip that slide (title slide). `continues: true` on a
  slide marks it a reveal step of the previous one: counters (footer, top bar) show one logical number for the group. `transition:` defaults to `none`.
  In fullscreen (F11 / Fullscreen API) the top chrome bar is hidden (`deck.css` `display-mode: fullscreen`), so the footer is the only slide indicator.
- ids are persistence keys — never rename a slide/interaction id after a session has run.
- Deck-local JS/CSS/data go in `decks/<slug>/static/` → served at `/static/decks/<slug>/…` (use `{{ deck_static }}` in html slides).
  Videos are git-LFS tracked (`presentations/decks/**/*.mp4|webm`).
- **Page weight (the iOS OOM fix).** Canva/poppler exports embed every bitmap as a base64 data URI and
  `render.py` inlines *every* slide into one document: the corfu archive page was 20.4 MB of HTML (14.1 MB of it
  base64) and iOS Safari jettisoned the tab — tapping the comment box (keyboard + relayout) was the last straw.
  Two things now keep it small, and both must stay true of any new deck:
  1. `presentations/rasters.py` writes the bitmaps out to `slides/img/<sha1>.<ext>` (straight bytes, no re-encode,
     deduplicated by content — 96 embeds in corfu were 60 distinct files) and rewrites the `<image>` to the
     **relative** href `img/<sha1>.png`, so the SVG also works when fetched on its own. `render.inline_svg` takes an
     `asset_base` and makes those hrefs absolute (`/static/decks/<slug>/slides/img/…`) at inline time — a relative
     href would otherwise resolve against `/presentations/<slug>/`, not against the SVG. `sanitize.py` allows exactly
     that one href shape (`rasters.RASTER_HREF`) and nothing else relative. Hash names are self-busting under nginx's
     30-day `immutable`. `newdeck`/`reslides` do this on import; `extractrasters` retrofits an existing deck
     (`--prune` drops images no slide references any more; `reslides` prunes on its own).
  2. Only `render.EAGER_SLIDES` (+1) svg slides ship their markup in the page; the rest carry
     `data-svg-src="/presentations/<slug>/slide/<id>/"` (view `archive.slide_markup`, same bytes `rendered_slides`
     would have inlined) and `stage.js` hydrates within ±2 of the current slide and dehydrates beyond ±5, so the
     resident DOM is bounded however far the deck is walked. Hydration is a `fetch` + `innerHTML`, **so a deferred
     slide's `<script>` would not run** — that is why only `kind: svg` slides are deferred; html slides (and the
     `underlay:` svg of an html slide) are always inlined. Corfu: 20.4 MB → 0.32 MB of HTML, 166 k → 13 k DOM nodes
     at load, peak ~12 k walking all 56 slides.
  **Watch the underlays.** Every `underlay:` is inlined eagerly, so each html slide over a Canva page costs ~120 KB
  of markup that deferral does not reclaim. The nine on corfu (the TOC plus the eight expert-BF event slides) take
  the archive page from 0.32 MB to 1.35 MB — still fine, but the cost is linear in how many event slides get an
  html overlay. If that grows much past a dozen, defer underlays too: `slide_markup` would need to serve an html
  slide's underlay and `stage.js` to hydrate `.stage--underlay .stage__inner` (expertbf.js already retries every 4s
  when the underlay svg is not there yet, so it would cope). Test: `test_archive_ships_only_a_window_of_slide_markup`
  counts *deferred svg slides* and holds the page under 3 MB — do not count `class="slide-svg"`, underlays carry it too.
- Corfu deck: `static/timeline/timeline.json` drives the citation-timeline html slide: one lane; `lane: real-data` entries are
  circles, `lane: model` entries (waveform models, `model` = display name, `note` = who used it) are horizontal rules. The column
  sits in the left 38vw and the popup docks right (58vw); container id is `#tl-root` (not `#timeline`, the slide hash);
  `tools/figpicker.py` (run from the deck folder) pulls arXiv sources and lets you click a figure per paper into
  `static/timeline/figs/`; `tools/arxivmeta.py <ids> --lane=…` prints new entries; verdicts in `tools/citations.md`.
- Corfu deck: `static/channels/channels.json` drives the formation-channel html slide (`05-channels.html`): each
  channel has `band`/`peak`/`tail` in log10 e at 10 Hz, `row: eccentric|circular` (above/below the line), an optional
  `family` (members are laid out contiguously, share one bracket and get a dashed box labelled from `families`), a
  `media` entry (`{type: video, src: media/<id>.mp4, still: media/<id>.png, candidate}` once chosen): Manim cartoons of each
  mechanism. `tools/manim/render.sh [<id>…]` (`VARIANT=n`, `QUALITY=l` for previews) renders *candidates* into
  `tools/manim/candidates/<id>-<n>.{mp4,png}` (storyboards in `tools/manim/STORYBOARD.md`, shared look + `VARIANT` in `style.py`,
  one `scene_<id>.py` per channel branching on the variant; last frame = card still; needs `manim` in the micromamba env);
  `tools/videopicker.py --port 8767` is the choose-one page that copies the pick into `static/channels/media/` and updates the json.
  Hover plays the clip on the card. The previous YouTube/gif entries are kept under `previous_media`. A cropped prediction `figure` and `sources`; optional `icon`
  (line-art card face; `tools/channelicons.py` + `tools/iconpicker.py --port 8766`, superseded by the videos). Cards size themselves
  to the row; the container is `#ch-root` (not `#channels` — that is the slide's hash and would scroll). `tools/channelgraph.py --fetch` queries INSPIRE for the intro citations of
  arXiv:2603.29019 (cached in `tools/.cache/channels/`), plain `tools/channelgraph.py` rebuilds `static/channels/graph.json`.
- Corfu deck: `static/events/events.json` drives the per-event case slides (`06..09-ev-<event>.html`, all `<div class="ev" data-event=…>`
  + shared `events.js/css`): per event `for`/`against` rows `{model, text, refs[]}`, `methods` rows (sampler / waveform / noise per
  paper) and a shared `refs` table; citation numbers are assigned per slide in order of first use. Claims were quoted from the
  papers' sources (`tools/.cache/<arxiv>/src`), see the session notes in `tools/citations.md`.
- Corfu deck: `10-bayes.html` (Bayes factors / significance) uses KaTeX from jsdelivr; its body sits inside `{% verbatim %}` because
  LaTeX `{{` collides with Django templating. Questions are `.bf-q[data-q]` buttons + `#bf-answer article[data-q]`; `?q=<id>` opens one.
  The `trials` answer draws `static/bayes/eccbf.json` via `static/bayes/trials.js`: a small square histogram of log₁₀ℬ across the
  catalogue (log ℬ along x, counts up). `tools/digitize_eccbf.py` built that json from the published raster of the log₁₀ℬ-vs-e
  figure: the 59 resolvable green error bars and all 8 highlighted events are read off the pixels, and the events lost to overlap
  are synthesised so the marginal reproduces the original bin counts. Per-event e values are therefore approximate; the histogram
  the slide actually shows is not. The json still carries the per-event `e`/`lo`/`hi` if the scatter is ever wanted back.
  `static/bayes/priors.js` holds two widgets for the `priors` answer: the spike-and-slab mixture on the right (test
  \(\log_{10}\mathcal{B}_\mathcal{U}\) is fixed at `LNB = 1` and displayed, only `w` is dialled) and, on the left, a slider over
  four fiducial \(p(e\,|\,\lambda)\) (uniform, thermal, log-uniform, Beta(2,5)) defined in the `PRIORS` array — add a fiducial
  there and the slider's range follows automatically; each fiducial draws its own posterior, so sliding shows the same data
  giving a different answer. The likelihood lives only in that left panel
  (prior dashed, \(\mathcal{L}\) dotted, posterior solid): `BF_LIK` is one broad Gaussian (`MU`/`SIG`, ~14% of peak by \(e=1\))
  chosen so the posterior is prior-dominated — widen SIG for more domination, narrow it to let the data win.
  \(\mathcal{B}_\mathcal{U}\) on the right is derived from the same likelihood, not hardcoded, so a flat SIG drives it to 0.
  The `neither` answer shows
  `static/bayes/detector-projection.png` — Fig. 5 of Gupte+ 2024 (arXiv:2404.14286), which is **GW200129**, not GW190701;
  swap the file and the figcaption together if a GW190701 version turns up.
- Corfu deck: `11-riskgrid.html` + `static/riskgrid/` replaces the old page-34 event table with a colour grid.
  `riskgrid.json` carries the columns (each with `scale: risk|significance`) and one row per event; green always means good news,
  so the `risk` columns map Low→green and the `significance` columns map High→green (`tone()` in `riskgrid.js` reverses the rank).
  html slides that include a script per slide must select *their own* root (`:not([data-done])` pattern in `events.js`) — a bare
  `querySelector` hits the first html slide on the archive page.
- Corfu deck: `12-prior-poll.html` (right after `bayes`) is the live "draw your eccentricity prior" poll: interaction `ecc-prior` of
  the engine type `prior` (`interactions/prior.py` + `js/interactions/prior.js`), axis = log₁₀ e ∈ [−4, 0] in 60 bins. Phones get a
  freehand canvas + name / institute / expertise checkboxes (the fixed `EXPERTISE` list in `prior.py`, `other` has a free-text box)
  / confidence 1–5; resubmitting replaces. The presenter plot draws every curve grey (hover → who), the unweighted mixture, a second
  filter row by *poll* expertise (e.g. astrophysics only — client-side, the aggregate returns every curve with its tags) under the
  usual join-tag slicer, and once the poll is `closed`/`revealed` two reference priors on the same grid: log-uniform (flat) and
  uniform in e (∝ e ln10, clipped at the top). `widgets.js` calls a type's optional `update()` on re-poll so the plot refreshes in
  place (keeps hover/filter). `static/prior-poll/poll.js` only clones the session QR (`#qr-box`) onto the slide in present mode.
  Payload metadata lives in `Response.payload` — no model change.
- Corfu deck: `14-expert-bf.html` + `static/expertbf/` + `tools/expertbf.py` fill the `__` in "Bayes factor ~ 17, 3, __
  (uniform, log-uni, expert prior)" with the number the **audience's** poll mixture implies. One template serves all eight
  affected slides (`page-06..09` GW200208_22, `page-14` GW200105, `page-16/17` GW190701, `page-23` GW200129): each is now
  `html: 14-expert-bf.html` + `underlay: slides/NN-page-NN.svg`, ids unchanged. Canva text is outlines, so the number is drawn
  as an SVG `<text>` **inside the underlay's own viewBox** (SVG positions text by its baseline, so it lands on the underscores
  at any window size); the `__` word boxes came from `pdftotext -bbox` (page size 1440×810 pt = the viewBox) and live in the
  json as fractions. `tools/expertbf.py` (run from the deck folder) writes `static/expertbf/expertbf.json`; the browser only
  does `B = k · Σ wᵢ Λᵢ` against the poll's `mean`. Aggregates 403 while the poll is hidden/open for non-staff, so a failed
  fetch just leaves the dash — no session / no responses / poll still open all degrade to "—", never NaN.
  **The maths, and what it assumes.** Three of the four pairs are one table (Gupte+ 2024, arXiv:2404.14286 Tab. 5), e₁₀Hz
  uniform on [0, 0.5] or log-uniform on [1e-4, 0.5], eccentric aligned-spin (EAS) vs quasi-circular **precessing** (QCP).
  With Λ(x) = L(x)/Z_QCAS on x = log₁₀e, B_{EAS/QCAS}(π) = ∫πΛ and B_{EAS/QCP}(π) = k∫πΛ with k = Z_QCAS/Z_QCP. The same
  table's *nested* EAS/QCAS column is the trick: it pins Λ(−∞) = 1 exactly, and k = B_QCP/B_QCAS is measured twice (uniform
  and log-uniform rows) and agrees to ≤0.03 dex — the first consistency check. Λ(x) = 1 + A·N(x; μ, σ) with σ taken from the
  published 90% HDI on e₁₀Hz (not a free knob) and (A, μ) fixed exactly by the two quoted Bayes factors.
  *Checks that passed:* (i) rigorous bound B_U/B_LU ≤ ln(e_max/e_min) = 8.52 for any Λ ≥ 0 — the three events sit at 66%,
  92%, 69%; (ii) the implied bump eccentricity e* = 0.33 / 0.46 / 0.34 reproduces the published e₁₀Hz posteriors
  (0.40 [0.25,0.48] / 0.46 [0.42,0.50] / 0.34 [0.28,0.45]) without ever being fitted to them.
  *Assumptions and limits:* below e = 1e-4 nothing anchors Λ and it is **assumed** flat at its e→0 value — without that the
  answer is formally unbounded above, since the audience puts most of its mass where the published analyses carry no
  information; above e = 0.5 the runs never sampled and Λ relaxes back to the plateau, which should really fall, so the
  number **over-estimates** for curves with mass at e > 0.5. The fitted bump is narrower than one 0.125-dex poll bin, so the
  answer is driven by the audience's mass in the single bin at e ≈ 0.33–0.47; halving/tripling σ moves a fiducial expert
  prior's answer by roughly −2%/+15% (GW200208_22, GW200129) and −7%/+70% (GW190701) — read the number as **one significant
  figure**. `grid_error` in the json records the round-trip loss through the 88-bin grid (7%, 36%, 3%; the 36% is GW190701's
  bump landing in the bin that straddles the e = 0.5 prior edge, not an error in the answer).
  **GW200105 is deliberately left as a dash.** Its 17 and 1.3 come from *different* papers at a *different* reference
  frequency (uniform: Morras+/Kacanja+/Planas+; log-uniform: Clarke+ 2026, e ∈ [1e-4, 0.2] at 20 Hz), and their ratio 13.1
  exceeds ln(0.2/1e-4) = 7.60 — no non-negative likelihood reproduces both, so there is nothing to reweight. The tooltip says
  so. Tests: `tests/presentations/test_corfu_expertbf.py` (round trips, the bound, the deck wiring, Python↔JS parity via
  `tests/presentations/js/expertbf.test.mjs`).
- Presenter dev aid: `/presentations/<slug>/present/phone-preview/` (staff) frames the live join page in a phone-shaped iframe so you
  can join and answer polls from the laptop (`phone` view sends `X-Frame-Options: SAMEORIGIN` for that).

## Giving the talk

1. Log in at `/admin/` (staff), open `/presentations/<slug>/present/` — this window is the projector.
   Bottom bar auto-hides; move the mouse: prev/next, per-interaction `hidden → open → closed → revealed`,
   **QR** (join code), **Lock**. Space = next, or play/pause on a video slide.
2. Audience scans the QR → `/p/<CODE>/` → picks an expertise tag (name optional) → synced mirror with free roam.
3. **Lock** at the end: freezes interactions as the archive at `/presentations/<slug>/`, bounces phones there.
   Locked present page offers **Unlock** (fat-finger recovery) and **New session** (re-give the talk).
Comments are open to anyone forever, post-moderated in `/admin/presentations/comment/` (hide/unhide).
On a phone `.comments-panel` covers the whole screen, so it is a column — head (title + ✕, the only way out;
`#comment-toggle` is underneath it), scrolling `#comment-list`, pinned composer — and `comments.js` insets it from
`visualViewport` so iOS's keyboard cannot bury the box. Rate limit: 5 comments/min per *participant* (a lecture hall
NATs to one IP), with a 30/min per-IP ceiling behind it. Emulator harness for phone bugs: Playwright + Chromium
mobile emulation (`pw.devices['iPhone 13']`) against `runserver`; WebKit's headless build does not start on this box.

## Dev workflow

- Everything runs via `micromamba run -n django-nihar-website …`. Tests: `python -m pytest tests/presentations -q`
  (`tests/__init__.py` + `--import-mode=importlib` are required because `tests/presentations` shadows the app name).
- JS math test needs Node ≥ 14: `~/.nvm/versions/node/v22.22.2/bin/node tests/presentations/js/stage.test.mjs`
  (system node is v10). `node --check` each JS file you touch; there is no bundler.
- Local presenter login: `python manage.py createsuperuser` once (dev `db.sqlite3` has no staff user).
- Sync is short polling (`static/presentations/js/sync.js`, 1.5 s); the live-state cache is per gunicorn worker.
- Script load order matters: `core → sync → stage → hotspots → widgets → interactions/* → comments → <page>.js`.

## Known gaps / deferred (from the branch review)

- Deck assets are still cache-pinned. nginx serves `/static/` as `immutable` for 30 days (90 for svg) behind
  Cloudflare; engine assets are content-hashed by `nihar_website.storage.ForgivingManifestStaticFilesStorage`, but
  deck templates concatenate onto the `{{ deck_static }}` *directory* prefix, so `decks/<slug>/**` (deck js/css, the
  json they fetch, media) keeps one URL for ever. Editing a deck asset in place will not reach anyone who has already
  loaded the deck. Slide svgs are safe — `render.py` inlines them into the (uncached) HTML, and the rasters they
  reference are content-hashed (`slides/img/<sha1>.png`), so those bust themselves. Fix would be a version
  segment in the prefix that `DeckStaticFinder` strips; until then, rename the file when its contents matter.
- Phone: a viewer-started video is re-paused by the presenter-sync loop once the presenter has ever paused
  (`phone.js` `onState`); gate on `following` or drop — spec says phones don't follow playback.
- No join rate limit (a NAT'd lecture hall shares one IP); a bored attendee could inflate `n` — delete the
  session in admin if it happens.
- Comment boxes are draw-once (no move/resize); comment numbers can tie on identical timestamps.
- Slide markup is still ~120 KB a slide (pdftocairo turns all text into outlined `<path>`/`<use>`), so a deck of
  outlined text is ~6 MB of markup on disk however few slides are resident. Squeezing that means an svgo-style
  pass on path precision, which risks changing the rendering — not attempted.
- Sanitizer doesn't scan `<style>` element bodies; Plotly CDN tag has no SRI; `pytest-django` sits in prod
  `requirements.txt`; `stage.test.mjs` isn't wired into pytest.
- `CLAUDE.md` (repo root) lines ~62–63 carry a pre-existing garbled docs link unrelated to this app.
