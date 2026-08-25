# Interactive Presentations — Design

**Date:** 2026-08-25
**Status:** approved in brainstorm, awaiting spec review
**Scope:** a new Django app `presentations` (the engine), a per-deck folder
convention under `presentations/decks/`, a `newdeck` scaffolder, one example
deck, and a "Presentations" entry in the Science navbar.

## 1. Goal

A new talk format. During the talk, the audience scans a QR code and follows
along on their phones in sync with the projector; at chosen moments they
answer a question and the room's aggregate appears on screen. After the talk
the same URL becomes a permanent reference page: the slides, the room's frozen
results, hover-to-explain hotspots with links to papers, and a comment layer
anyone can add to.

The engine is built once. Each talk is a folder of SVGs, HTML pages, videos
and one `deck.yaml`. The second talk should cost `manage.py newdeck` plus
writing.

## 2. Non-goals (v1)

- Late voting / online cohort. After lock, interactions are read-only.
- A browser editor of any kind. `deck.yaml` is the editor.
- Audience accounts. A random cookie token is the only identity.
- WebSockets / SSE. Sync is short polling behind a swappable module.
- Speaker notes, a separate projector view, multiple sessions per deck in the UI
  (the model allows it; no UI for it).
- Exposing an html slide's widget state as an interaction ("submit what you
  found"). Hook left in the toolkit API; not built.

## 3. Prior art borrowed

- reveal.js multiplex / Slidev `--remote`: master-drives-clients sync.
- Sync (synclive.io): QR join, no accounts, "follow live or roam".
- Mentimeter / Slido: poll → aggregate on the big screen; join-code UX.
- Prior-elicitation "roulette" method: the draw-a-distribution interaction.
- This site's mindmap viewer: rect-with-description data shape (not its UX).

What none of them do, and this does: the live session's audience input
becomes part of the permanent page.

## 4. Repository layout

```
presentations/                          # engine (Django app)
  __init__.py apps.py admin.py urls.py
  models.py                             # Session, Participant, Response, Comment
  registry.py                           # loads + validates decks/*/deck.yaml
  schema.py                             # deck.yaml validation (dataclasses)
  theme.py                              # derive palette from SVGs
  sanitize.py                           # SVG sanitizer
  interactions/
    __init__.py                         # registry: get(type_name)
    base.py                             # Interaction ABC
    choice.py numeric.py distribution.py text.py
  views/
    __init__.py archive.py present.py phone.py api.py
  templates/presentations/
    index.html                          # /presentations/ list
    archive.html present.html phone.html join.html
    slide_base.html                     # base for html slides
    _stage.html _hotspot_card.html _comments.html _interaction.html
  static/presentations/
    css/deck.css
    js/sync.js stage.js hotspots.js comments.js interactions/{choice,numeric,distribution,text}.js
    js/present.js phone.js archive.js
  management/commands/newdeck.py
  migrations/
  decks/
    _template/                          # copied by newdeck
    example/                            # ships with v1; exercises everything
      deck.yaml
      slides/*.svg  slides/*.mp4
      *.html
      static/                           # served at /static/decks/example/
tests/presentations/
docs/superpowers/specs/2026-08-25-interactive-presentations-design.md
```

Deck folders are discovered, not registered: any `presentations/decks/<slug>/deck.yaml`
is a deck with URL `/presentations/<slug>/`. `_`-prefixed folders are ignored.

`STATICFILES_DIRS` gains a finder entry so `presentations/decks/<slug>/static/`
is collected to `static/decks/<slug>/`. Templates: `presentations/decks/<slug>/`
is added to the app's template loader so `html:` entries resolve by filename.

## 5. `deck.yaml`

```yaml
title: Eccentric Binary Black Holes
date: 2026-09-12
subtitle: LVK Collaboration Meeting          # optional
transition: fade                              # fade | slide | none
expertise:                                    # join-screen tags, required, 2–6 entries
  - theory
  - data analysis
  - instrumentation
  - not a physicist
theme:                                        # newdeck pre-fills from the SVGs; edit freely
  bg: "#1f2429"
  fg: "#f4f1ea"
  accents: ["#37b49f", "#e9c46a", "#e76f51"]
  font_display: "Montserrat"
  font_body: "Inter"

interactions:                                 # declared once, deck-wide
  - id: q-orbits
    type: choice
    prompt: Which of these orbits is eccentric?
    options: [A, B, C, D]
    answer: B                                 # optional; shown on "reveal"
  - id: q-prior
    type: distribution
    prompt: Your prior on e at formation
    axis: {min: 0, max: 1, bins: 20, label: "e"}
  - id: q-rate
    type: numeric
    prompt: Merger rate (Gpc⁻³ yr⁻¹)
    log: true
    truth: 23.9                               # optional
  - id: q-word
    type: text
    prompt: One word for eccentric orbits
    max_len: 30

slides:
  - id: title                                 # stable id; comments key on it
    svg: slides/01-title.svg

  - id: orbits
    svg: slides/02-orbits.svg
    hotspots:
      - rect: [0.41, 0.22, 0.27, 0.33]        # x, y, w, h — fractions of the stage
        title: Ringdown
        body: |
          Markdown. The turnover at high frequency is where the
          quasi-normal modes take over. See §4 of the paper.
        links:
          - {label: "arXiv:2401.01234", url: "https://arxiv.org/abs/2401.01234"}
    ask: [q-orbits]                           # phone widget for these appears when opened

  - id: orbits-results
    svg: slides/03-orbits-results.svg
    show:                                     # draw aggregates here (any slide, any number)
      - {id: q-orbits, rect: [0.10, 0.25, 0.80, 0.65]}

  - id: prior
    svg: slides/04-prior.svg
    ask: [q-prior]
    show:                                     # asking and showing on the same slide is fine too
      - {id: q-prior, rect: [0.10, 0.30, 0.80, 0.60]}

  - id: posterior
    html: 05-posterior.html                   # free-form page; scrolls
    ask: [q-rate]
    # html slides show aggregates with <div data-interaction="q-rate"> — no rect

  - id: words
    svg: slides/06-words.svg
    ask: [q-word]
    show:
      - {id: q-word, rect: [0.05, 0.25, 0.90, 0.65]}

  - id: outro
    video: slides/07-outro.mp4
    poster: slides/07-outro.jpg               # optional; newdeck generates with ffmpeg if available
```

Validation (at startup and by `manage.py checkdecks`): every slide `id` and
interaction `id` unique within a deck; every file exists; every `type` is
registered and its `config_schema` accepts the entry; every `ask`/`show`
reference resolves; `show` entries on svg/video slides must give `rect`,
on html slides must not; every interaction is asked on at least one slide
(warning, not error). Validation errors raise at startup in DEBUG and 500
with a clear message on the deck's pages in production, never crash other
decks.

Slide `id`s (comments) and interaction `id`s (responses) are the
persistence keys. `newdeck` assigns slide ids from filenames; renaming an id
after a session orphans its data (documented in `_template/deck.yaml`).

## 6. Slide kinds

All kinds render inside the **deck chrome**: a 40 px top bar (deck title,
`7 / 24`, LIVE pill or LOCKED badge, QR toggle on present) that auto-hides on
present after 2 s without pointer movement.

**`svg`** — a Canva export, inlined into a fixed 16:9 **stage**
(1920×1080 logical units, `transform: scale()` to fit the viewport). Text
stays real DOM text. An overlay `<svg>` in stage coordinates draws hotspot
rects, the interaction aggregate rect, and comment rects.

**`html`** — a Django template extending `presentations/slide_base.html`. It
is a normal page: any height, scrolls, its own JS/CSS from the deck's
`static/`. `slide_base.html` provides the theme as CSS custom properties
(`--bg --fg --accent-1..n --font-display --font-body`), a base stylesheet
that makes headings/body/Plotly defaults match the SVGs, and the toolkit
JS. May declare `underlay: slides/foo.svg` to draw a Canva export as a fixed
stage background beneath the page content.

**`video`** — `<video>` fills the stage; `poster` shown until play. On
present, Space toggles play/pause and the state is written into live state.
Phones show the poster with tap-to-play (mobile autoplay restrictions +
lecture-hall bandwidth); they do not auto-follow playback position.

Navigation: ←/→, Space (next, or play/pause on video), swipe on phone.
Transitions per deck: CSS fade / slide / none.

## 7. The overlay layer: one primitive, three uses

A **rect** in stage fractions `[x, y, w, h]`:

| use          | authored by | behaviour |
|--------------|-------------|-----------|
| hotspot      | deck.yaml   | hover → outline + popover card anchored to the cursor (flips near edges). Click pins it open (scrollable body, clickable links); click-away/Esc closes. Phone: tap opens, tap-away closes; faint corner marker so people know it's there. |
| show         | deck.yaml   | where an interaction's aggregate renders on present/archive. Nothing drawn while that interaction is `hidden`; `closed` draws only the response counter. |
| comment      | audience    | tap "+" → a default box appears under the finger → drag to move, corner handles to resize → type. Rendered as numbered outlines; hover/tap shows the thread. |

On **html** slides there is no stage, so: hotspots are markup
(`<span data-hotspot="Ringdown" data-body="…" data-link="…">`), aggregates
mount into `<div data-interaction="q-rate">` (the slide must `ask` or `show` it), and comments anchor to
`<section data-anchor="fig-2">` elements (or the slide as a whole). The
toolkit auto-marks `data-anchor` elements with a small "💬 n" affordance.

## 8. Interactions

### Lifecycle

`hidden → open → closed → revealed`, driven only by the presenter. State is
per interaction and session-wide, independent of which slide anyone is on:
while an interaction is `open`, the widget is shown on every phone (below
whatever slide they're viewing, with the prompt), so asking on slide 4 and
showing on slide 9 works, as does opening a question while lingering on an
unrelated slide. Phones may respond only while `open` (server enforces; 409
otherwise). `closed` shows "n responses — waiting" wherever it is `show`n;
`revealed` shows the aggregate (and `answer`/`truth` if configured). Several
interactions may be open at once; the phone stacks them.

The presenter bar lists the interactions the current slide `ask`s or `show`s
with their state buttons, plus an "all interactions" dropdown so any can be
driven from any slide. On lock, every interaction that was ever `open`
becomes `revealed` permanently; ones never opened stay `hidden` and are
omitted from the archive.

### Plugin contract

Server, `presentations/interactions/base.py`:

```python
class Interaction(ABC):
    name: str
    config_schema: dict        # JSON Schema for the deck.yaml entry (minus type/id/rect)
    payload_schema: dict       # JSON Schema for Response.payload
    def clean_payload(self, payload, config) -> dict: ...   # normalise; raise ValidationError
    def aggregate(self, payloads: list[dict], config) -> dict: ...   # pure
```

`aggregate` is pure so expertise slicing is free: the API filters payloads
by tag and calls the same function. Registered by importing the module in
`interactions/__init__.py`.

Client, `static/presentations/js/interactions/<name>.js`:

```js
Presentations.registerInteraction("choice", {
  input(el, config, submit)      {/* phone widget; call submit(payload) once */},
  aggregate(el, config, agg, ctx){/* present + archive; ctx.revealed, ctx.tag */},
});
```

### Types shipped

| type | config | payload | aggregate |
|------|--------|---------|-----------|
| `choice` | `prompt, options[], answer?` | `{choice}` | `{n, counts{}}` → horizontal bars; answer highlighted on reveal |
| `numeric` | `prompt, log?, min?, max?, truth?, unit?` | `{value, err?}` | `{n, values[], median, q16, q84}` → strip plot with error bars, truth marked on reveal |
| `distribution` | `prompt, axis{min,max,bins,label}` | `{weights[bins]}` (normalised to sum 1) | `{n, mean[bins], curves[[…]]}` → every curve at α≈0.15 + bold mean; phone input is finger-drag over the bins |
| `text` | `prompt, max_len (≤80)` | `{text}` | `{n, counts{word:count}}` (lower-cased, trimmed, stopwords dropped) → word cloud, per-word cap. Server rejects entries matching a small profanity list; rest is post-moderated in admin |

### Expertise slicing

Every aggregate view has a tag toggle (all / each tag / "tag vs rest").
Slices with n < 3 render as "n too small" rather than a chart.

## 9. Sync (short polling)

Presenter is the **only writer** of live state. Phones and the archive-with-a-live-session
read it.

`GET /p/<code>/state/` → 
```json
{"v": 412, "slide": "orbits", "locked": false,
 "interaction": {"id": "q-orbits", "state": "open"},
 "video": {"playing": true, "t": 12.4, "at": 1724580000.1}}
```
Polled every 1500 ms by phones, 1000 ms by present (for participant count).
Served from an in-process 1 s cache keyed on session; `Cache-Control: no-store`.
`v` is a monotonic version; clients ignore responses with `v` ≤ last seen.

All transport goes through `sync.js` exposing `Presentations.sync.onState(cb)`
and `Presentations.sync.post(path, body)`. Swapping to SSE/WebSockets later
touches this one file plus one server function.

Phone follows the presenter's slide unless the user has navigated away, in
which case a "⟳ jump to live" pill appears; tapping it re-enters follow mode.

## 10. Surfaces and URLs

| URL | who | what |
|-----|-----|------|
| `/presentations/` | public | list of decks (title, date, locked/live/upcoming) |
| `/presentations/<slug>/` | public | **archive**: chrome + slides, prev/next, hotspots, frozen aggregates with slicer, comments. Also the deck's page *before* a talk. If a session is live, a banner offers "join live". |
| `/presentations/<slug>/present/` | staff login | **present**: full-stage, auto-hiding control bar (slide nav, interaction state buttons for the current slide, participant count, QR toggle, **Lock**). This one window is mirrored to the projector. |
| `/p/<code>/` | public | **phone**: join screen (expertise required, name optional) → synced mirror. `code` is a 6-char session join code baked into the QR. |
| `/p/<code>/state/`, `/p/<code>/aggregate/<iid>/?tag=`, `/p/<code>/respond/<iid>/`, `/presentations/<slug>/comment/` | JSON | see §11 |
| `/presentations/<slug>/present/goto/`, `/present/interaction/<iid>/<state>/`, `/present/video/`, `/present/lock/`, `/present/unlock/` | staff POST | presenter actions |

Starting a session: opening `/present/` with no open session creates one
(join code, QR). Reopening `/present/` resumes the open session.
**Lock** sets `Session.is_locked`, `ended_at`, and flips interaction states as
in §8. Unlock is available from the same bar for fat-finger recovery.

## 11. Data model (engine; the only DB tables)

```
Session      deck_slug, join_code (unique, 6 chars), started_at, ended_at?, is_locked,
             current_slide_id, interaction_states JSON {iid: state}, video_state JSON, version int
Participant  session FK, token (32 hex, unique), display_name?, expertise_tag, joined_at, ip_hash
Response     participant FK, session FK, interaction_id, payload JSON, created_at
             UNIQUE(participant, interaction_id)  — upsert on repeat submit
Comment      deck_slug, slide_id, anchor JSON ({rect:[…]} | {anchor:"fig-2"} | null),
             author_name?, participant FK?, body (≤1000), created_at, is_hidden, ip_hash
```

Deck content is never in the DB. `deck_slug` + yaml `id`s are the join to
content. Admin registers all four with list filters and a "hide" action on
Comment.

## 12. Identity, moderation, abuse

- Join sets a `pres_<code>` cookie with the participant token (1 year). One
  response per token per interaction; re-submitting updates.
- Comments: open to anyone, appear immediately, post-moderated (hide/delete in
  admin). Defences: honeypot field, 5 comments / minute per IP-hash+token,
  body ≤ 1000 chars, markdown rendered with a strict allowlist (no HTML,
  links rel=nofollow). Signed with `display_name` if the commenter joined;
  otherwise an optional name field on the form.
- IPs stored only as salted SHA-256.
- Present/lock endpoints require `is_staff`; CSRF on all POSTs.
- SVG uploads go through `sanitize.py` on `newdeck` (strip `<script>`,
  `on*=`, `<foreignObject>`, external `href`s; keep embedded `data:` images).
  Sanitized files are what's committed.

## 13. Theme derivation

`theme.py` scans a deck's SVGs: fill/stroke colour frequency by painted
area → `bg` (largest), `fg` (highest-contrast frequent colour vs bg),
`accents` (next three by area, deduped by ΔE). `font-family` attributes are
collected if present (Canva often outlines text; then defaults
`Montserrat`/`Inter` are written with a `# TODO pick fonts` comment).
Output is *written into* `deck.yaml` by `newdeck`; at runtime only the yaml
is read. Fonts load from Google Fonts with system fallbacks.

## 14. `manage.py newdeck`

```
manage.py newdeck <slug> --title "…" [--from DIR] [--date YYYY-MM-DD]
```
Creates `decks/<slug>/` from `_template/`; if `--from` is given, copies every
`*.svg` (sorted) into `slides/`, sanitizes them, assigns ids from filenames
(`02-orbits.svg` → `orbits`), derives the theme, and writes `deck.yaml` with
one `svg:` entry per file plus commented-out examples of hotspot,
interaction, html and video entries. `*.mp4/*.webm` are copied as video
slides with a poster extracted via ffmpeg when available.

`manage.py checkdecks` validates all decks and prints problems (also run by
tests).

## 15. Navbar

`templates/navbar.html`, under Science, after Posters:
```html
<li><a href="/presentations/">Presentations</a></li>
```
Decks are listed on `/presentations/` rather than nested in the navbar, since
the list grows.

## 16. Ops

- No uploads exist in this design, so nginx needs no changes;
  `/static/decks/…` is served by the existing `/static/` block. Video files
  are tracked with git LFS (`*.mp4 *.webm` in `.gitattributes`); `update.sh`
  already runs `git lfs pull`.
- `db.sqlite3` becomes worth backing up: `deploy/update.sh` gains a
  pre-migrate `cp db.sqlite3 backups/db-$(date +%F).sqlite3` (keep 14).
- `requirements.txt` / `environment.yml`: `PyYAML`, `jsonschema`,
  `markdown`, `bleach`. `qrcode[pil]` for the QR (Pillow already present).
- `presentations` added to `INSTALLED_APPS`; `presentations/urls.py` included
  at `''` (it owns `/presentations/` and `/p/`).

## 17. Testing

`tests/presentations/`, pytest-django (add `pytest-django` + `DJANGO_SETTINGS_MODULE`
to `pytest.ini`):

- `test_schema.py` — deck.yaml validation: good deck loads; each failure mode
  (dup id, missing file, unknown type, unresolved ask/show, html show-with-rect, svg show-without-rect) raises with the path.
- `test_interactions.py` — `aggregate()` for each type on hand-built
  payloads, including the empty and n<3 cases; `clean_payload` rejections.
- `test_state_machine.py` — respond when `hidden/closed` → 409; open → 200 and
  upsert; lock flips states; unlock restores; anon POST to present endpoints
  → 403.
- `test_comments.py` — honeypot drops, rate limit trips on the 6th, markdown
  allowlist strips HTML, hidden comments absent from archive.
- `test_flow.py` — end to end: present opens session → phone joins with tag
  → presenter goes to `orbits`, opens `q-orbits` → phone responds → aggregate
  by tag → lock → archive renders frozen aggregate and the comment.
- `test_example_deck.py` — `checkdecks` passes on `decks/example`.
- JS: no test runner in repo today; `stage.js` coordinate math gets a small
  node-run test file (`tests/presentations/js/stage.test.mjs`) since
  rect ↔ pixel conversion is where bugs hide.

## 18. Example deck

`decks/example/` is a real, short deck (≈8 slides) used by tests and as the
living reference: one svg with two hotspots, one of each interaction type,
at least one interaction asked on one slide and shown on a later one, one
html slide with an underlay and a Plotly widget reading a small JSON from
its `static/`, one video slide. SVGs are simple hand-made placeholders, not
Canva exports.

## 19. Build order (for the plan)

1. App skeleton, models, migrations, admin, registry + schema, example deck
   yaml, `checkdecks`, navbar link, `/presentations/` list.
2. Archive view: stage renderer, svg/html/video kinds, hotspots, theme CSS.
3. Interactions: server plugins + aggregation + JSON endpoints; client
   widgets; archive shows frozen aggregates.
4. Session + present view + sync + phone (join, mirror, respond); lock.
5. Comments (region on stage, anchor on html).
6. `newdeck`, theme derivation, sanitizer, ops changes, example deck filled
   out end to end.
