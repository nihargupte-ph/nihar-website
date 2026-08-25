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
- `interactions:` top-level list — `type: choice|numeric|distribution|text` (+ config). A slide `ask: [id]`s it
  (phone widget appears when opened) and any slide `show: [{id, rect}]`s the aggregate (html slides:
  `<div data-interaction="id">` and `show: [{id}]` with no rect).
- `expertise:` 2–6 tags for the join screen; aggregates are sliceable by tag / "vs rest".
- `footer: {name, affiliation, bg, fg}` draws a thin bar (name · affiliation · `N / total`) at the bottom of every
  slide; omit it for none, `footer: false` on a slide to skip that slide (title slide). `continues: true` on a
  slide marks it a reveal step of the previous one: counters (footer, top bar) show one logical number for the group. `transition:` defaults to `none`.
  In fullscreen (F11 / Fullscreen API) the top chrome bar is hidden (`deck.css` `display-mode: fullscreen`), so the footer is the only slide indicator.
- ids are persistence keys — never rename a slide/interaction id after a session has run.
- Deck-local JS/CSS/data go in `decks/<slug>/static/` → served at `/static/decks/<slug>/…` (use `{{ deck_static }}` in html slides).
  Videos are git-LFS tracked (`presentations/decks/**/*.mp4|webm`).

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
