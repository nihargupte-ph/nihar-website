# Corfu deck — citation timeline page (design)

Date: 2026-08-25. Deck: `presentations/decks/corfu/`. Status: approved in chat.

## Goal

An html slide in the Corfu deck ("Detecting Eccentricity: what are our Current
Prospects?") showing three vertical timelines of the literature: **real-data
analyses**, **data analysis (simulated)** and **likelihood modelling**. Each
citation is a hollow circle with the first author's name; hovering (tapping on a
phone) opens a large popup with a figure from that paper. The audience can flag
a missing citation. Only the real-data lane is populated in this iteration; the
other two lanes exist in the data model and render empty.

## Non-goals

- A new engine slide kind or interaction type. The page is a plain `html:`
  slide; audience input reuses comments on a `data-anchor` section.
- Syncing popups to phones (hotspots aren't synced either).
- Journal publication dates: dates are arXiv v1 dates only.

## Data — `static/timeline/timeline.json`

```json
{"lanes": [{"id": "real-data",  "title": "Real-data analyses"},
           {"id": "simulated",  "title": "Data analysis (simulated)"},
           {"id": "likelihood", "title": "Likelihood modelling"}],
 "entries": [{"id": "romero-shaw-2020", "lane": "real-data",
              "first_author": "Romero-Shaw", "authors": "Romero-Shaw, Lasky, Thrane, Calderón Bustillo",
              "title": "…", "arxiv": "2009.04771", "v1_date": "2020-09-10",
              "figure": "figs/romero-shaw-2020.png", "caption": "Fig. 2 — …"}]}
```

- `id`: `<first-author-slug>-<year>` (+ `-b` on collision). Stable; the figure
  file is named after it.
- `v1_date`: the arXiv API `published` field (= first version). ISO date.
- `figure`: path relative to `static/timeline/`, or `null` until picked.
- `caption`: free text shown under the figure (which figure it is, one line).

Lane membership for this iteration: a paper is `real-data` when it runs
eccentricity inference/searches on real LVK strain data (single events,
catalogue reanalyses, population constraints from real events). Injection-only
and forecast studies are excluded. Sources: the related-work sections of
arXiv:2603.29019, arXiv:2605.12818 and arXiv:2512.19513, with each candidate's
abstract/body read to decide. The verdicts are recorded in
`tools/citations.md` (every candidate: include/exclude + one-line reason).

## Page — `NN-timeline.html`, `static/timeline/timeline.{js,css}`

- `html:` slide extending `presentations/slide_base.html`, listed in `deck.yaml`.
- Layout: page scrolls top→bottom, oldest first. A year axis on the left with
  a tick per year; three lane columns with headers. Entries are positioned by
  date on a linear scale (px per day) with a minimum vertical gap so labels in
  the same lane never overlap (same-day entries stack).
- Entry: hollow circle (stroke = lane accent from the deck theme, no fill) on
  the lane line; label "First author · YYYY" beside it. Keyboard-focusable.
- Popup: on `mouseenter`/focus (desktop) or tap (touch) a fixed overlay
  (~70 % viewport, centred) shows the figure (`<img>`; a text placeholder
  when `figure` is null), title, authors, arXiv link (`https://arxiv.org/abs/<id>`,
  opens new tab), caption. Closes on `mouseleave` of circle+popup, tap outside,
  Esc. One popup at a time.
- Audience input: a final `<section data-anchor="missing-citation">` with the
  heading "Missing a citation?" and a line asking for the arXiv id. The
  engine's comments module attaches the 💬 mark; comments are open during and
  after the talk and moderated in admin. Nothing to build.
- Empty lanes render their header only.
- Theme: uses the deck's `--bg/--fg/--accent-*` variables like other html
  slides; no external CDN.

## Picker (throwaway) — `tools/figpicker.py`

Python stdlib + poppler (`pdftocairo`, `pdfimages`; `newdeck` already needs
poppler). Run from the deck folder:
`micromamba run -n django-nihar-website python tools/figpicker.py [--port 8765]`.

1. For each entry without a chosen figure (or all with `--all`): download
   `https://arxiv.org/e-print/<arxiv>` into `tools/.cache/<arxiv>/` (gitignored),
   detect tar/gzip/plain-tex, extract every `.pdf/.eps/.png/.jpg/.jpeg` figure
   file, render pdf/eps to PNG at ~120 dpi via `pdftocairo -png -singlefile`.
   If no source (withdrawn or PDF-only) fetch `https://arxiv.org/pdf/<arxiv>`
   and pull raster images with `pdfimages -png`.
   Polite: sequential downloads, 3 s sleep between papers, a UA string.
2. Serve `http://localhost:<port>/`: one row per paper (first author, year,
   title, arXiv link, current choice) with a thumbnail grid of its figures.
   Clicking a thumbnail POSTs `/pick {id, file}`; the server copies the PNG to
   `static/timeline/figs/<id>.png`, sets `figure`/`caption` (caption defaults
   to the source filename, editable inline) in `timeline.json`, and re-renders
   the row as selected. A "no figure" button sets `figure: null`.
3. Stop with Ctrl-C. The picker is kept in the repo so lanes 2–3 can be picked
   later; the cache is not.

## Verification

- `manage.py checkdecks` passes with the new slide.
- `tests/presentations/test_corfu_timeline.py`: `timeline.json` parses; every
  entry has a known lane, ISO `v1_date`, unique id; every non-null `figure`
  file exists; entries are the same set the page will render (no duplicates by
  arXiv id).
- `node --check` on `timeline.js`; manual browser check of hover/tap popup,
  Esc, scroll, and the 💬 mark on the final section.
