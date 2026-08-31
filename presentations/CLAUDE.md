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

## Dev workflow

- Everything runs via `micromamba run -n django-nihar-website …`. Tests: `python -m pytest tests/presentations -q`
  (`tests/__init__.py` + `--import-mode=importlib` are required because `tests/presentations` shadows the app name).
- JS math test needs Node ≥ 14: `~/.nvm/versions/node/v22.22.2/bin/node tests/presentations/js/stage.test.mjs`
  (system node is v10). `node --check` each JS file you touch; there is no bundler.
- Local presenter login: `python manage.py createsuperuser` once (dev `db.sqlite3` has no staff user).
- Sync is short polling (`static/presentations/js/sync.js`, 1.5 s); the live-state cache is per gunicorn worker.
- Script load order matters: `core → sync → stage → hotspots → widgets → interactions/* → comments → <page>.js`.

## Known gaps / deferred (from the branch review)

- Phone: a viewer-started video is re-paused by the presenter-sync loop once the presenter has ever paused
  (`phone.js` `onState`); gate on `following` or drop — spec says phones don't follow playback.
- No join rate limit (a NAT'd lecture hall shares one IP); a bored attendee could inflate `n` — delete the
  session in admin if it happens.
- Comment boxes are draw-once (no move/resize); comment numbers can tie on identical timestamps.
- Sanitizer doesn't scan `<style>` element bodies; Plotly CDN tag has no SRI; `pytest-django` sits in prod
  `requirements.txt`; `stage.test.mjs` isn't wired into pytest.
- `CLAUDE.md` (repo root) lines ~62–63 carry a pre-existing garbled docs link unrelated to this app.
