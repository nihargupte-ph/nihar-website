# Corfu Citation Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a scrollable three-lane citation timeline html slide to the Corfu deck (real-data lane populated), with hover/tap figure popups, a comments anchor for missing citations, and a throwaway figure picker that writes chosen figures into the timeline data.

**Architecture:** A JSON data file (`timeline.json`) drives a deck-local html slide (`timeline.js/css`) that lays entries out by arXiv v1 date. Citations are gathered once from the related-work sections of three papers, verdicts recorded in `tools/citations.md`, and metadata (title/authors/v1 date) pulled from the arXiv API by `tools/arxivmeta.py`. `tools/figpicker.py` extracts figures from arXiv source tarballs and serves a local click-to-choose page that edits `timeline.json`.

**Tech Stack:** Django html slide (deck engine), vanilla JS/CSS, Python stdlib (`urllib`, `http.server`, `tarfile`, `xml.etree`), poppler (`pdftocairo`, `pdfimages`), pytest.

**Spec:** `docs/superpowers/specs/2026-08-25-corfu-citation-timeline-design.md`

## Global Constraints

- Everything runs via `micromamba run -n django-nihar-website …` (tests: `python -m pytest tests/presentations -q`).
- No external CDNs on the slide; theme via `--bg`, `--fg`, `--accent`, `--accent-2`, `--accent-3`, `--font-display`, `--font-body`.
- Dates are arXiv v1 dates (API `published` field), ISO `YYYY-MM-DD`.
- Lane ids exactly: `real-data`, `simulated`, `likelihood`. Only `real-data` gets entries now.
- Real-data inclusion rule: eccentricity inference/searches on real LVK strain data; exclude injection-only and forecast studies.
- Deck-local static files live in `presentations/decks/corfu/static/` and are served at `{{ deck_static }}` (`/static/decks/corfu/`).
- Slide ids are persistence keys; the new slide id is `timeline` and must never be renamed.
- `node --check` every JS file touched (`~/.nvm/versions/node/v22.22.2/bin/node`).
- `tools/.cache/` is gitignored; chosen PNGs under `static/timeline/figs/` are committed.

## File structure

```
presentations/decks/corfu/
├── deck.yaml                          # + slide {id: timeline, html: 04-timeline.html}
├── 04-timeline.html                   # html slide: markup shell + script/css tags
├── static/timeline/
│   ├── timeline.json                  # lanes + entries (data)
│   ├── timeline.css                   # lanes, dots, labels, popup
│   ├── timeline.js                    # fetch JSON, layout by date, popup behaviour
│   └── figs/<entry-id>.png            # chosen figures (written by the picker)
└── tools/
    ├── citations.md                   # every candidate citation with verdict + reason
    ├── arxivmeta.py                   # arXiv API → entry dicts (title, authors, v1 date)
    ├── figpicker.py                   # throwaway picker server
    └── .cache/                        # downloaded sources (gitignored)
tests/presentations/
├── test_corfu_timeline.py             # timeline.json validity + deck loads
└── test_corfu_tools.py                # arxivmeta parser + figpicker pick/extract
```

---

### Task 1: arXiv metadata helper

**Files:**
- Create: `presentations/decks/corfu/tools/arxivmeta.py`
- Test: `tests/presentations/test_corfu_tools.py`

**Interfaces:**
- Produces: `parse_atom(xml_text: str) -> list[dict]` with keys `arxiv` (bare id, no version), `title`, `authors` (list of full names), `first_author` (surname of author 0), `v1_date` (`YYYY-MM-DD`); `fetch(ids: list[str]) -> list[dict]` (HTTP, not tested); `entry_id(first_author: str, v1_date: str) -> str` giving `romero-shaw-2020`; `make_entry(meta: dict, lane: str) -> dict` giving a full timeline entry with `figure: None, caption: ''`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/presentations/test_corfu_tools.py
import importlib.util
import json
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / 'presentations' / 'decks' / 'corfu' / 'tools'


def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ATOM = '''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2009.04771v2</id>
    <published>2020-09-10T15:58:51Z</published>
    <title>GW190521: orbital eccentricity and signatures of dynamical
  formation in a binary black hole merger signal</title>
    <author><name>Isobel M. Romero-Shaw</name></author>
    <author><name>Paul D. Lasky</name></author>
  </entry>
</feed>'''


def test_parse_atom_extracts_entry_fields():
    m = load('arxivmeta')
    [e] = m.parse_atom(ATOM)
    assert e['arxiv'] == '2009.04771'
    assert e['v1_date'] == '2020-09-10'
    assert e['title'] == 'GW190521: orbital eccentricity and signatures of dynamical formation in a binary black hole merger signal'
    assert e['authors'] == ['Isobel M. Romero-Shaw', 'Paul D. Lasky']
    assert e['first_author'] == 'Romero-Shaw'


def test_entry_id_and_make_entry():
    m = load('arxivmeta')
    assert m.entry_id('Romero-Shaw', '2020-09-10') == 'romero-shaw-2020'
    assert m.entry_id('Calderón Bustillo', '2021-01-01') == 'calderon-bustillo-2021'
    e = m.make_entry(m.parse_atom(ATOM)[0], 'real-data')
    assert e['id'] == 'romero-shaw-2020' and e['lane'] == 'real-data'
    assert e['figure'] is None and e['caption'] == ''
    assert e['authors'] == 'Romero-Shaw, Lasky'
```

- [ ] **Step 2: Run to verify it fails**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations/test_corfu_tools.py -q`
Expected: FAIL (`FileNotFoundError` loading `arxivmeta.py`).

- [ ] **Step 3: Implement**

```python
# presentations/decks/corfu/tools/arxivmeta.py
"""arXiv API → timeline entry dicts. Usage: python arxivmeta.py 2009.04771 2108.01284 …"""
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

NS = {'a': 'http://www.w3.org/2005/Atom'}
API = 'http://export.arxiv.org/api/query?id_list={}&max_results=200'
UA = 'nihar-website-timeline/1.0 (mailto:gupten8@gmail.com)'


def _surname(full):
    return full.strip().split()[-1]


def parse_atom(xml_text):
    out = []
    for e in ET.fromstring(xml_text).findall('a:entry', NS):
        aid = e.findtext('a:id', '', NS).rsplit('/', 1)[-1]
        aid = re.sub(r'v\d+$', '', aid)
        title = ' '.join(e.findtext('a:title', '', NS).split())
        authors = [' '.join(a.findtext('a:name', '', NS).split()) for a in e.findall('a:author', NS)]
        if not aid or not authors:
            continue
        out.append({'arxiv': aid, 'title': title, 'authors': authors,
                    'first_author': _surname(authors[0]),
                    'v1_date': e.findtext('a:published', '', NS)[:10]})
    return out


def fetch(ids):
    metas = []
    for i in range(0, len(ids), 50):
        url = API.format(','.join(ids[i:i + 50]))
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            metas.extend(parse_atom(r.read().decode('utf-8')))
        time.sleep(3)
    return metas


def entry_id(first_author, v1_date):
    s = unicodedata.normalize('NFKD', first_author).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
    return f'{s}-{v1_date[:4]}'


def make_entry(meta, lane):
    return {'id': entry_id(meta['first_author'], meta['v1_date']), 'lane': lane,
            'first_author': meta['first_author'],
            'authors': ', '.join(_surname(a) for a in meta['authors']),
            'title': meta['title'], 'arxiv': meta['arxiv'], 'v1_date': meta['v1_date'],
            'figure': None, 'caption': ''}


if __name__ == '__main__':
    lane = 'real-data'
    ids = [a for a in sys.argv[1:] if not a.startswith('--lane=')]
    for a in sys.argv[1:]:
        if a.startswith('--lane='):
            lane = a.split('=', 1)[1]
    print(json.dumps([make_entry(m, lane) for m in fetch(ids)], indent=1, ensure_ascii=False))
```

- [ ] **Step 4: Run to verify it passes**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations/test_corfu_tools.py -q`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add presentations/decks/corfu/tools/arxivmeta.py tests/presentations/test_corfu_tools.py
git commit -m "feat(corfu): arXiv metadata helper for the citation timeline"
```

---

### Task 2: Gather the real-data citations → `timeline.json` + `citations.md`

**Files:**
- Create: `presentations/decks/corfu/tools/citations.md`
- Create: `presentations/decks/corfu/static/timeline/timeline.json`
- Test: `tests/presentations/test_corfu_timeline.py`

**Interfaces:**
- Consumes: `tools/arxivmeta.py` CLI (`python tools/arxivmeta.py <ids…> --lane=real-data`).
- Produces: `timeline.json` in the spec's shape; consumed by Task 3 (page) and Task 4 (picker).

- [ ] **Step 1: Write the failing test**

```python
# tests/presentations/test_corfu_timeline.py
import json
import re
from pathlib import Path

DECK = Path(__file__).resolve().parents[2] / 'presentations' / 'decks' / 'corfu'
TL = DECK / 'static' / 'timeline'
LANES = {'real-data', 'simulated', 'likelihood'}


def load():
    return json.loads((TL / 'timeline.json').read_text())


def test_lanes():
    assert [l['id'] for l in load()['lanes']] == ['real-data', 'simulated', 'likelihood']
    assert all(l['title'] for l in load()['lanes'])


def test_entries_are_well_formed():
    entries = load()['entries']
    assert entries, 'no entries'
    ids, arxivs = set(), set()
    for e in entries:
        assert set(e) >= {'id', 'lane', 'first_author', 'authors', 'title', 'arxiv', 'v1_date', 'figure', 'caption'}, e['id']
        assert e['lane'] in LANES, e['id']
        assert re.fullmatch(r'\d{4}-\d{2}-\d{2}', e['v1_date']), e['id']
        assert re.fullmatch(r'\d{4}\.\d{4,5}|[a-z\-]+/\d{7}', e['arxiv']), e['id']
        assert e['id'] not in ids and e['arxiv'] not in arxivs, e['id']
        ids.add(e['id']); arxivs.add(e['arxiv'])
        if e['figure'] is not None:
            assert (TL / e['figure']).is_file(), e['id']


def test_real_data_lane_has_citations():
    assert sum(e['lane'] == 'real-data' for e in load()['entries']) >= 5
```

- [ ] **Step 2: Run to verify it fails**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations/test_corfu_timeline.py -q`
Expected: FAIL (`FileNotFoundError: timeline.json`).

- [ ] **Step 3: Read the three source papers' related-work sections**

For each of `2603.29019`, `2605.12818`, `2512.19513`: fetch `https://arxiv.org/html/<id>` (fall back to `https://arxiv.org/pdf/<id>` + `pdftotext` in the scratchpad) and read the introduction/related-work section. List every cited work that is about eccentricity measurement on real events; resolve each to an arXiv id (from the bibliography's `arXiv:` fields, or an `export.arxiv.org` title search). Keep the candidate list in the scratchpad.

- [ ] **Step 4: Decide inclusion per candidate**

For each candidate fetch its abstract (`tools/arxivmeta.py` output has the title; `https://arxiv.org/abs/<id>` for the abstract) and, when the abstract is ambiguous, the paper's data section. Verdict `include` only when it analyses real LVK strain data for eccentricity (single-event PE, catalogue reanalysis, population constraints from real events, real-data searches with eccentric templates). `exclude` for injection-only, forecast, waveform-model-only or method-only papers. Write `tools/citations.md`:

```markdown
# Citation verdicts — real-data lane

Sources: arXiv:2603.29019, arXiv:2605.12818, arXiv:2512.19513 (related-work sections).
Rule: include iff the paper runs eccentricity inference/searches on real LVK strain data.

| arXiv | First author | v1 | Verdict | Reason |
|---|---|---|---|---|
| 2009.04771 | Romero-Shaw | 2020-09-10 | include | eccentric PE on GW190521 strain |
| … | … | … | exclude | injection study only |
```

Every candidate gets a row, including exclusions.

- [ ] **Step 5: Generate `timeline.json`**

```bash
cd presentations/decks/corfu
micromamba run -n django-nihar-website python tools/arxivmeta.py <included ids…> --lane=real-data > /tmp/claude-1001/…/scratchpad/entries.json
```

Then write `static/timeline/timeline.json` as

```json
{"lanes": [{"id": "real-data",  "title": "Real-data analyses"},
           {"id": "simulated",  "title": "Data analysis (simulated)"},
           {"id": "likelihood", "title": "Likelihood modelling"}],
 "entries": [ …the generated entries, sorted by v1_date… ]}
```

Fix any duplicate `id` by appending `-b`. Check every `v1_date` against `citations.md`.

- [ ] **Step 6: Run to verify it passes**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations/test_corfu_timeline.py -q`
Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add presentations/decks/corfu/tools/citations.md presentations/decks/corfu/static/timeline/timeline.json tests/presentations/test_corfu_timeline.py
git commit -m "content(corfu): real-data citation list with arXiv v1 dates"
```

---

### Task 3: Timeline html slide

**Files:**
- Create: `presentations/decks/corfu/04-timeline.html`
- Create: `presentations/decks/corfu/static/timeline/timeline.css`
- Create: `presentations/decks/corfu/static/timeline/timeline.js`
- Modify: `presentations/decks/corfu/deck.yaml` (append slide)
- Test: `tests/presentations/test_corfu_timeline.py` (add deck-load test)

**Interfaces:**
- Consumes: `timeline.json` (Task 2).
- Produces: slide id `timeline`; DOM: `#timeline[data-src]`, `.tl-lane[data-lane]`, `.tl-entry[data-id]`, `#tl-popup`; section `data-anchor="missing-citation"`.

- [ ] **Step 1: Write the failing test**

Append to `tests/presentations/test_corfu_timeline.py`:

```python
from presentations import interactions
from presentations.schema import load_deck


def test_deck_has_timeline_slide():
    deck = load_deck(DECK, interaction_validator=interactions.validate)
    assert deck.warnings == []
    [s] = [s for s in deck.slides if s.id == 'timeline']
    assert s.kind == 'html' and s.path == '04-timeline.html'
    html = (DECK / '04-timeline.html').read_text()
    assert 'data-anchor="missing-citation"' in html
    assert 'timeline/timeline.json' in html
```

- [ ] **Step 2: Run to verify it fails**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations/test_corfu_timeline.py::test_deck_has_timeline_slide -q`
Expected: FAIL (no slide `timeline`).

- [ ] **Step 3: Add the slide to `deck.yaml`**

Append under `slides:` (after `page-03`):

```yaml
- id: timeline
  html: 04-timeline.html
```

- [ ] **Step 4: Write the html slide**

```django
{% extends "presentations/slide_base.html" %}
{% block slide %}
<link rel="stylesheet" href="{{ deck_static }}timeline/timeline.css">
<h1>Eccentricity in the literature</h1>
<p class="tl-intro">Hover a circle (tap on a phone) to see a figure from the paper. Dates are first arXiv appearance.</p>
<div id="timeline" data-src="{{ deck_static }}timeline/timeline.json" aria-busy="true"></div>
<div id="tl-popup" class="tl-popup" hidden role="dialog" aria-modal="false"></div>
<section data-anchor="missing-citation" class="tl-missing">
  <h3>Missing a citation?</h3>
  <p>Use the 💬 mark to leave a comment with the arXiv id and which lane it belongs in. Comments stay open after the talk.</p>
</section>
<script src="{{ deck_static }}timeline/timeline.js" defer></script>
{% endblock %}
```

- [ ] **Step 5: Write the CSS**

```css
/* presentations/decks/corfu/static/timeline/timeline.css */
#timeline{position:relative;display:grid;grid-template-columns:5rem repeat(3,1fr);column-gap:1rem;margin-top:1.5rem}
.tl-head{position:sticky;top:0;z-index:3;background:var(--bg);padding:.4rem 0 .6rem;font-family:var(--font-display);font-weight:600;font-size:1.05rem;border-bottom:1px solid rgba(255,255,255,.15)}
.tl-head--axis{color:transparent}
.tl-axis,.tl-lane{position:relative}
.tl-axis{grid-column:1}
.tl-year{position:absolute;left:0;right:.6rem;text-align:right;font-size:.85rem;opacity:.6;transform:translateY(-50%)}
.tl-year::after{content:"";position:absolute;left:100%;top:50%;width:100vw;border-top:1px dashed rgba(255,255,255,.08);pointer-events:none}
.tl-lane::before{content:"";position:absolute;left:12px;top:0;bottom:0;border-left:2px solid var(--lane,var(--accent));opacity:.45}
.tl-lane[data-lane="real-data"]{--lane:var(--accent)}
.tl-lane[data-lane="simulated"]{--lane:var(--accent-2,#e9c46a)}
.tl-lane[data-lane="likelihood"]{--lane:var(--accent-3,#e76f51)}
.tl-entry{position:absolute;left:0;display:flex;align-items:center;gap:.6rem;background:none;border:0;color:var(--fg);font:inherit;padding:0;cursor:pointer;transform:translateY(-50%);white-space:nowrap}
.tl-dot{width:26px;height:26px;border-radius:50%;border:3px solid var(--lane,var(--accent));background:var(--bg);box-sizing:border-box;flex:none;transition:transform .15s,background .15s}
.tl-entry:hover .tl-dot,.tl-entry:focus-visible .tl-dot,.tl-entry.active .tl-dot{background:var(--lane,var(--accent));transform:scale(1.15)}
.tl-entry:focus-visible{outline:2px solid var(--lane,var(--accent));outline-offset:4px;border-radius:6px}
.tl-label{font-size:.95rem}
.tl-label small{opacity:.6;margin-left:.3rem}
.tl-empty{position:absolute;top:1rem;left:2.4rem;font-size:.85rem;opacity:.45;font-style:italic}
.tl-popup{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);width:min(72vw,1100px);max-height:82vh;overflow:auto;z-index:40;background:#111d;backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,.18);border-radius:14px;padding:1.2rem 1.4rem;box-shadow:0 20px 60px #000a}
.tl-popup__title{font-family:var(--font-display);font-weight:700;font-size:1.15rem;margin:0 0 .2rem}
.tl-popup__meta{opacity:.75;font-size:.9rem;margin:0 0 .8rem}
.tl-popup__meta a{margin-left:.5rem}
.tl-popup__fig{display:block;max-width:100%;max-height:60vh;margin:0 auto;background:#fff;border-radius:6px}
.tl-popup__nofig{padding:2rem;text-align:center;opacity:.6;border:1px dashed rgba(255,255,255,.25);border-radius:8px}
.tl-popup__cap{font-size:.85rem;opacity:.8;margin:.6rem 0 0;text-align:center}
.tl-missing{margin-top:3rem;padding-top:1.5rem;border-top:1px solid rgba(255,255,255,.15)}
@media (max-width:700px){#timeline{grid-template-columns:3.2rem repeat(3,1fr);column-gap:.4rem}.tl-label{font-size:.8rem}.tl-popup{width:94vw;padding:.8rem}}
```

- [ ] **Step 6: Write the JS**

```js
// presentations/decks/corfu/static/timeline/timeline.js
(async function () {
  const root = document.getElementById('timeline'); const popup = document.getElementById('tl-popup');
  if (!root || !popup) return;
  const base = root.dataset.src.replace(/timeline\.json$/, '');
  const data = await (await fetch(root.dataset.src)).json();
  const touch = matchMedia('(hover: none)').matches;
  const PX_PER_DAY = 0.9, MIN_GAP = 40, TOP = 24, BOTTOM = 40;
  const day = (iso) => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10)) / 864e5;
  const entries = data.entries.slice().sort((a, b) => a.v1_date.localeCompare(b.v1_date));
  const years = entries.map((e) => +e.v1_date.slice(0, 4));
  const y0 = Math.min(...years), y1 = Math.max(...years) + 1;
  const d0 = day(`${y0}-01-01`);
  const yFor = (iso) => TOP + (day(iso) - d0) * PX_PER_DAY;
  const height = yFor(`${y1}-01-01`) + BOTTOM;
  const el = (tag, attrs = {}, ...kids) => { const n = document.createElement(tag); for (const [k, v] of Object.entries(attrs)) { if (k === 'text') n.textContent = v; else if (k === 'html') n.innerHTML = v; else n.setAttribute(k, v); } n.append(...kids); return n; };

  root.innerHTML = '';
  root.append(el('div', { class: 'tl-head tl-head--axis', text: 'year' }));
  data.lanes.forEach((l) => root.append(el('div', { class: 'tl-head', text: l.title })));
  const axis = el('div', { class: 'tl-axis', style: `height:${height}px` });
  for (let y = y0; y <= y1; y++) axis.append(el('div', { class: 'tl-year', text: String(y), style: `top:${yFor(`${y}-01-01`)}px` }));
  root.append(axis);
  const byId = {};
  data.lanes.forEach((l) => {
    const lane = el('div', { class: 'tl-lane', 'data-lane': l.id, style: `height:${height}px` });
    let last = -Infinity;
    const mine = entries.filter((e) => e.lane === l.id);
    if (!mine.length) lane.append(el('div', { class: 'tl-empty', text: 'coming soon' }));
    mine.forEach((e) => {
      const top = Math.max(yFor(e.v1_date), last + MIN_GAP); last = top;
      const b = el('button', { class: 'tl-entry', type: 'button', 'data-id': e.id, style: `top:${top}px`, 'aria-haspopup': 'dialog' },
        el('span', { class: 'tl-dot' }), el('span', { class: 'tl-label', html: `${escapeHtml(e.first_author)}<small>${e.v1_date.slice(0, 4)}</small>` }));
      byId[e.id] = e; lane.append(b);
    });
    root.append(lane);
  });
  root.removeAttribute('aria-busy');

  let active = null, hideTimer = null;
  function escapeHtml(s) { return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
  function show(btn) {
    const e = byId[btn.dataset.id]; if (!e) return; clearTimeout(hideTimer);
    if (active && active !== btn) active.classList.remove('active');
    active = btn; btn.classList.add('active');
    popup.innerHTML = '';
    popup.append(el('h2', { class: 'tl-popup__title', text: e.title }),
      el('p', { class: 'tl-popup__meta', html: `${escapeHtml(e.authors)} · ${e.v1_date}<a href="https://arxiv.org/abs/${escapeHtml(e.arxiv)}" target="_blank" rel="noopener">arXiv:${escapeHtml(e.arxiv)}</a>` }));
    if (e.figure) popup.append(el('img', { class: 'tl-popup__fig', src: base + e.figure, alt: e.caption || e.title }));
    else popup.append(el('div', { class: 'tl-popup__nofig', text: 'No figure chosen yet' }));
    if (e.caption) popup.append(el('p', { class: 'tl-popup__cap', text: e.caption }));
    popup.hidden = false;
  }
  function hide() { clearTimeout(hideTimer); popup.hidden = true; if (active) active.classList.remove('active'); active = null; }
  const hideSoon = () => { clearTimeout(hideTimer); hideTimer = setTimeout(hide, 180); };
  root.addEventListener('pointerenter', (ev) => { const b = ev.target.closest('.tl-entry'); if (b && !touch) show(b); }, true);
  root.addEventListener('pointerleave', (ev) => { if (ev.target.closest && ev.target.closest('.tl-entry') && !touch) hideSoon(); }, true);
  root.addEventListener('focusin', (ev) => { const b = ev.target.closest('.tl-entry'); if (b) show(b); });
  root.addEventListener('click', (ev) => { const b = ev.target.closest('.tl-entry'); if (!b) return; ev.stopPropagation(); if (active === b && !popup.hidden) hide(); else show(b); });
  popup.addEventListener('pointerenter', () => clearTimeout(hideTimer));
  popup.addEventListener('pointerleave', () => { if (!touch) hideSoon(); });
  popup.addEventListener('click', (ev) => ev.stopPropagation());
  document.addEventListener('click', () => { if (!popup.hidden) hide(); });
  document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape' && !popup.hidden) { hide(); ev.stopPropagation(); } });
})();
```

- [ ] **Step 7: Syntax-check the JS and run the tests**

Run: `~/.nvm/versions/node/v22.22.2/bin/node --check presentations/decks/corfu/static/timeline/timeline.js && micromamba run -n django-nihar-website python -m pytest tests/presentations -q`
Expected: no node output; all tests pass (including `test_checkdecks_passes_on_repo`).

- [ ] **Step 8: Browser check**

Start `micromamba run -n django-nihar-website python manage.py runserver`, open `http://localhost:8000/presentations/corfu/` (archive) and navigate to the timeline slide. Verify: three lane headers, year ticks, hollow circles with names in the left lane, hover opens the popup with "No figure chosen yet", Esc/mouse-out closes it, 💬 mark appears on "Missing a citation?". Fix anything broken before committing.

- [ ] **Step 9: Commit**

```bash
git add presentations/decks/corfu/deck.yaml presentations/decks/corfu/04-timeline.html presentations/decks/corfu/static/timeline/timeline.css presentations/decks/corfu/static/timeline/timeline.js tests/presentations/test_corfu_timeline.py
git commit -m "feat(corfu): citation timeline html slide with figure popups"
```

---

### Task 4: Figure picker (throwaway)

**Files:**
- Create: `presentations/decks/corfu/tools/figpicker.py`
- Modify: `.gitignore` (add `presentations/decks/*/tools/.cache/`)
- Test: `tests/presentations/test_corfu_tools.py` (add picker tests)

**Interfaces:**
- Consumes: `timeline.json` (Task 2 shape).
- Produces: `extract_figures(src_dir: Path, out_dir: Path) -> list[Path]` (PNGs), `pick(timeline_path: Path, entry_id: str, png: Path | None, caption: str) -> dict` (updated entry; `png=None` clears), `fetch_source(arxiv: str, cache: Path) -> Path` (HTTP), `render_index(timeline: dict, figs: dict[str, list[Path]], cache: Path) -> str`, `serve(deck_dir: Path, port: int, refresh_all: bool)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/presentations/test_corfu_tools.py`:

```python
PNG = bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63f8cfc0f01f0005000101f9b6a1230000000049454e44ae426082')


def _timeline(tmp_path):
    tl = tmp_path / 'static' / 'timeline'
    tl.mkdir(parents=True)
    (tl / 'timeline.json').write_text(json.dumps({'lanes': [{'id': 'real-data', 'title': 'x'}], 'entries': [
        {'id': 'a-2020', 'lane': 'real-data', 'first_author': 'A', 'authors': 'A', 'title': 't', 'arxiv': '2001.00001',
         'v1_date': '2020-01-01', 'figure': None, 'caption': ''}]}))
    return tl / 'timeline.json'


def test_pick_copies_png_and_updates_json(tmp_path):
    fp = load('figpicker')
    tl = _timeline(tmp_path)
    src = tmp_path / 'fig1.png'; src.write_bytes(PNG)
    e = fp.pick(tl, 'a-2020', src, 'Fig. 1 — thing')
    assert e['figure'] == 'figs/a-2020.png' and e['caption'] == 'Fig. 1 — thing'
    assert (tl.parent / 'figs' / 'a-2020.png').read_bytes() == PNG
    assert json.loads(tl.read_text())['entries'][0]['figure'] == 'figs/a-2020.png'
    e = fp.pick(tl, 'a-2020', None, '')
    assert e['figure'] is None and not (tl.parent / 'figs' / 'a-2020.png').exists()


def test_pick_unknown_entry_raises(tmp_path):
    fp = load('figpicker')
    with pytest.raises(KeyError):
        fp.pick(_timeline(tmp_path), 'nope', None, '')


def test_extract_figures_collects_rasters_and_skips_junk(tmp_path):
    fp = load('figpicker')
    src = tmp_path / 'src'; (src / 'figs').mkdir(parents=True)
    (src / 'figs' / 'plot.png').write_bytes(PNG)
    (src / 'main.tex').write_text('x')
    out = tmp_path / 'out'
    figs = fp.extract_figures(src, out)
    assert [f.name for f in figs] == ['figs__plot.png']
    assert figs[0].read_bytes() == PNG


def test_render_index_lists_papers_and_figures(tmp_path):
    fp = load('figpicker')
    tl = json.loads(_timeline(tmp_path).read_text())
    html = fp.render_index(tl, {'a-2020': [tmp_path / 'x.png']}, tmp_path)
    assert 'a-2020' in html and 'x.png' in html and 'No figure' in html
```

- [ ] **Step 2: Run to verify they fail**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations/test_corfu_tools.py -q`
Expected: 4 new tests FAIL (`FileNotFoundError: figpicker.py`).

- [ ] **Step 3: Implement the picker**

```python
# presentations/decks/corfu/tools/figpicker.py
"""Throwaway figure picker for the citation timeline.

    micromamba run -n django-nihar-website python tools/figpicker.py [--port 8765] [--all]

Downloads each paper's arXiv source into tools/.cache/<arxiv>/, renders every
figure to PNG, and serves a page where clicking a thumbnail writes it into
static/timeline/figs/<id>.png and timeline.json. Ctrl-C to stop.
"""
import gzip
import html
import io
import json
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DECK = Path(__file__).resolve().parents[1]
TL_DIR = DECK / 'static' / 'timeline'
TL_JSON = TL_DIR / 'timeline.json'
CACHE = DECK / 'tools' / '.cache'
UA = 'nihar-website-timeline/1.0 (mailto:gupten8@gmail.com)'
RASTER = {'.png', '.jpg', '.jpeg'}
VECTOR = {'.pdf', '.eps', '.ps'}


def _get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read(), r.headers.get('Content-Type', '')


def fetch_source(arxiv, cache):
    """Download + unpack the e-print into cache/<arxiv>/src (or the PDF into cache/<arxiv>/paper.pdf)."""
    d = cache / arxiv.replace('/', '_'); src = d / 'src'
    if (d / '.done').exists():
        return d
    src.mkdir(parents=True, exist_ok=True)
    blob, ctype = _get(f'https://arxiv.org/e-print/{arxiv}')
    if blob[:4] == b'%PDF':
        (d / 'paper.pdf').write_bytes(blob)
    else:
        try:
            with tarfile.open(fileobj=io.BytesIO(blob), mode='r:*') as t:
                t.extractall(src, filter='data')
        except tarfile.ReadError:
            try:
                (src / 'main.tex').write_bytes(gzip.decompress(blob))
            except OSError:
                (src / 'blob').write_bytes(blob)
    if not any(p.suffix.lower() in RASTER | VECTOR for p in src.rglob('*')) and not (d / 'paper.pdf').exists():
        time.sleep(3)
        (d / 'paper.pdf').write_bytes(_get(f'https://arxiv.org/pdf/{arxiv}')[0])
    (d / '.done').write_text('ok')
    return d


def _to_png(path, out):
    if path.suffix.lower() in RASTER:
        shutil.copyfile(path, out); return out.exists()
    r = subprocess.run(['pdftocairo', '-png', '-singlefile', '-r', '110', str(path), str(out.with_suffix(''))],
                       capture_output=True, text=True)
    return r.returncode == 0 and out.exists()


def extract_figures(src_dir, out_dir):
    """Every figure-like file under src_dir → PNG in out_dir (flat, path-mangled names)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    figs = []
    for p in sorted(src_dir.rglob('*')):
        if not p.is_file() or p.suffix.lower() not in RASTER | VECTOR:
            continue
        rel = p.relative_to(src_dir)
        if rel.parts[0] == 'paper.pdf':
            continue
        out = out_dir / ('__'.join(rel.parts)[: -len(p.suffix)] + '.png')
        if out.exists() or _to_png(p, out):
            figs.append(out)
    pdf = src_dir.parent / 'paper.pdf'
    if not figs and pdf.exists():
        subprocess.run(['pdfimages', '-png', str(pdf), str(out_dir / 'img')], capture_output=True)
        figs = sorted(out_dir.glob('img-*.png'))
    return figs


def _load():
    return json.loads(TL_JSON.read_text())


def pick(timeline_path, entry_id, png, caption):
    data = json.loads(timeline_path.read_text())
    entry = next((e for e in data['entries'] if e['id'] == entry_id), None)
    if entry is None:
        raise KeyError(entry_id)
    figs = timeline_path.parent / 'figs'; dest = figs / f'{entry_id}.png'
    if png is None:
        if dest.exists():
            dest.unlink()
        entry['figure'], entry['caption'] = None, ''
    else:
        figs.mkdir(exist_ok=True); shutil.copyfile(png, dest)
        entry['figure'], entry['caption'] = f'figs/{entry_id}.png', caption.strip()
    timeline_path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n')
    return entry


def render_index(timeline, figs, cache):
    h = html.escape
    rows = []
    for e in sorted(timeline['entries'], key=lambda e: e['v1_date']):
        thumbs = ''.join(
            f'<figure data-id="{h(e["id"])}" data-file="{h(str(f))}" title="{h(f.name)}">'
            f'<img loading="lazy" src="/cache/{h(str(f.relative_to(cache)))}"><figcaption>{h(f.name)}</figcaption></figure>'
            for f in figs.get(e['id'], []))
        chosen = f'<img class="chosen" src="/figs/{h(e["figure"].split("/")[-1])}?{time.time():.0f}">' if e.get('figure') else '<em>nothing chosen</em>'
        rows.append(f'''<section id="{h(e["id"])}"><header><b>{h(e["first_author"])} {e["v1_date"][:4]}</b> · {h(e["title"])}
          <a href="https://arxiv.org/abs/{h(e["arxiv"])}" target="_blank">arXiv:{h(e["arxiv"])}</a>
          <span class="state">{chosen}</span>
          <label>caption <input class="cap" value="{h(e.get("caption") or "")}" placeholder="Fig. 2 — posterior on e"></label>
          <button class="nofig" data-id="{h(e["id"])}">No figure</button></header>
          <div class="grid">{thumbs or "<em>no figures extracted</em>"}</div></section>''')
    return f'''<!doctype html><meta charset="utf-8"><title>figpicker</title>
<style>body{{font:14px system-ui;margin:1rem 2rem;background:#151515;color:#eee}}section{{margin-bottom:2rem;border-top:1px solid #444;padding-top:.6rem}}
header{{display:flex;gap:.8rem;align-items:center;flex-wrap:wrap;position:sticky;top:0;background:#151515;padding:.4rem 0;z-index:2}}
.grid{{display:flex;flex-wrap:wrap;gap:.6rem}}figure{{margin:0;width:220px;cursor:pointer;border:2px solid transparent;padding:2px}}figure:hover{{border-color:#37b49f}}
figure.picked{{border-color:#e9c46a}}img{{max-width:100%;background:#fff}}.chosen{{height:70px;width:auto}}figcaption{{font-size:11px;opacity:.6;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
a{{color:#37b49f}}.cap{{width:22rem}}</style>
<h1>Pick a figure per paper</h1><p>Click a thumbnail to choose it (caption box is saved with it). Ctrl-C the server when done.</p>
{''.join(rows)}
<script>
async function post(id, file, caption){{const r=await fetch('/pick',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{id,file,caption}})}});if(!r.ok)alert(await r.text());else location.reload();}}
document.querySelectorAll('figure').forEach(f=>f.onclick=()=>post(f.dataset.id,f.dataset.file,f.closest('section').querySelector('.cap').value||f.title));
document.querySelectorAll('.nofig').forEach(b=>b.onclick=()=>post(b.dataset.id,null,''));
</script>'''


def serve(deck_dir, port, refresh_all):
    global DECK, TL_DIR, TL_JSON, CACHE
    DECK = deck_dir; TL_DIR = DECK / 'static' / 'timeline'; TL_JSON = TL_DIR / 'timeline.json'; CACHE = DECK / 'tools' / '.cache'
    CACHE.mkdir(parents=True, exist_ok=True)
    tl = _load(); figs = {}
    todo = [e for e in tl['entries'] if refresh_all or not e.get('figure')]
    for i, e in enumerate(todo, 1):
        print(f'[{i}/{len(todo)}] {e["arxiv"]} {e["first_author"]} …', flush=True)
        try:
            d = fetch_source(e['arxiv'], CACHE)
            figs[e['id']] = extract_figures(d / 'src', d / 'png')
        except Exception as ex:  # noqa: BLE001 — keep going, report on the page
            print(f'   failed: {ex}')
        time.sleep(3)

    class H(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype='text/html; charset=utf-8'):
            self.send_response(code); self.send_header('Content-Type', ctype); self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            p = urllib.parse.unquote(self.path.split('?')[0])
            if p == '/':
                return self._send(200, render_index(_load(), figs, CACHE).encode())
            for prefix, base in (('/cache/', CACHE), ('/figs/', TL_DIR / 'figs')):
                if p.startswith(prefix):
                    f = (base / p[len(prefix):]).resolve()
                    if f.is_file() and base.resolve() in f.parents:
                        return self._send(200, f.read_bytes(), 'image/png')
            self._send(404, b'not found', 'text/plain')

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            try:
                pick(TL_JSON, body['id'], Path(body['file']) if body.get('file') else None, body.get('caption', ''))
            except (KeyError, OSError) as ex:
                return self._send(400, str(ex).encode(), 'text/plain')
            self._send(200, b'ok', 'text/plain')

        def log_message(self, *a):
            pass

    print(f'→ http://localhost:{port}/  (Ctrl-C to stop)')
    ThreadingHTTPServer(('127.0.0.1', port), H).serve_forever()


if __name__ == '__main__':
    port = 8765
    if '--port' in sys.argv:
        port = int(sys.argv[sys.argv.index('--port') + 1])
    serve(DECK, port, '--all' in sys.argv)
```

- [ ] **Step 4: gitignore the cache**

Append to `.gitignore`:

```
# arXiv source cache of the corfu figure picker
presentations/decks/*/tools/.cache/
```

- [ ] **Step 5: Run the tests**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations/test_corfu_tools.py -q`
Expected: 6 passed.

- [ ] **Step 6: Smoke-run the picker on two papers**

Run from the deck folder: `micromamba run -n django-nihar-website python tools/figpicker.py` — confirm sources download, thumbnails render at `http://localhost:8765/`, clicking one produces `static/timeline/figs/<id>.png` and the `figure` field in `timeline.json`; reload the deck's timeline slide and hover that entry to see the figure. Then `pick(..., None, '')` via the "No figure" button to leave the choice to the user (or keep it if it's obviously the right one and say so). Stop the server.

- [ ] **Step 7: Commit**

```bash
git add presentations/decks/corfu/tools/figpicker.py .gitignore tests/presentations/test_corfu_tools.py
git commit -m "tools(corfu): throwaway arXiv figure picker for the timeline"
```

---

### Task 5: Docs + handoff

**Files:**
- Modify: `presentations/CLAUDE.md` (one bullet under "Authoring a deck")

- [ ] **Step 1: Document the deck-local tooling**

Add to `presentations/CLAUDE.md` after the `Deck-local JS/CSS/data…` bullet:

```markdown
- Corfu deck: `static/timeline/timeline.json` drives the citation-timeline html slide (lanes `real-data|simulated|likelihood`);
  `tools/figpicker.py` (run from the deck folder) pulls arXiv sources and lets you click a figure per paper into
  `static/timeline/figs/`; `tools/arxivmeta.py <ids> --lane=…` prints new entries; verdicts in `tools/citations.md`.
```

- [ ] **Step 2: Full test run and commit**

Run: `micromamba run -n django-nihar-website python -m pytest tests/presentations -q`
Expected: all pass.

```bash
git add presentations/CLAUDE.md
git commit -m "docs(presentations): corfu timeline tooling"
```

- [ ] **Step 3: Hand off** — tell the user how to run the picker and that lanes `simulated`/`likelihood` are ready for entries.
